"""Read-only PI0.5 SFT backend for native Meta-World control collection.

Heavy VLA/Meta-World imports are intentionally lazy so format tests can run in
the small ACT test environment.  This module never imports or loads the legacy
Corrector.
"""

from __future__ import annotations

import math
import os
import random
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import torch

from .contracts import (
    CONTROL_30_HZ,
    CONTROL_HZ,
    DEFAULT_NATIVE_ACTION_SCALE,
    DEFAULT_TOKENIZER_NAME,
    DEFAULT_TOKENIZER_REVISION,
    PHYSICS_HZ,
    BackendStep,
    VERY_HARD_TASKS,
    physics_substeps_for_control_step,
)


def _prepend_vla_source(vla_root: Path) -> None:
    source = vla_root / "src"
    if not source.is_dir():
        raise FileNotFoundError(f"VLA source directory does not exist: {source}")
    source_text = str(source)
    if source_text not in sys.path:
        sys.path.insert(0, source_text)


def _git_head(repository: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


class MetaWorldPi05Backend:
    """Frozen SFT-only PI0.5 policy plus PI0.5 visual/language features."""

    def __init__(
        self,
        *,
        vla_root: str | Path,
        checkpoint: str | Path,
        device: str,
        tokenizer_name: str = DEFAULT_TOKENIZER_NAME,
        tokenizer_revision: str = DEFAULT_TOKENIZER_REVISION,
        episode_length: int = 300,
        control_hz: int = CONTROL_HZ,
        native_action_scale: float = DEFAULT_NATIVE_ACTION_SCALE,
    ):
        self.vla_root = Path(vla_root).expanduser().resolve(strict=True)
        self.checkpoint = Path(checkpoint).expanduser().resolve(strict=True)
        self.device = torch.device(device)
        self.tokenizer_name = tokenizer_name
        self.tokenizer_revision = tokenizer_revision
        self.episode_length = int(episode_length)
        self.control_hz = int(control_hz)
        self.native_action_scale = float(native_action_scale)
        self._validate_inputs()

        # Both loaders are forced offline.  The SFT directory and the exact
        # PaliGemma tokenizer revision must already be present in the workspace.
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        _prepend_vla_source(self.vla_root)

        from lerobot.configs.policies import PreTrainedConfig
        from lerobot.envs.metaworld import MetaworldEnv, TASK_DESCRIPTIONS
        from lerobot.envs.utils import preprocess_observation
        from lerobot.policies.factory import make_pre_post_processors
        from lerobot.policies.pi05.modeling_pi05 import PI05Policy
        from transformers import AutoTokenizer

        self._env_class = MetaworldEnv
        self._task_descriptions = TASK_DESCRIPTIONS
        self._preprocess_observation = preprocess_observation

        config = PreTrainedConfig.from_pretrained(self.checkpoint, local_files_only=True)
        config.device = str(self.device)
        config.n_action_steps = 10
        config.chunk_size = 50
        config.compile_model = False
        config.pretrained_path = self.checkpoint
        self.policy = PI05Policy.from_pretrained(
            self.checkpoint,
            config=config,
            local_files_only=True,
        )
        self.policy.requires_grad_(False)
        self.policy.eval()
        self.policy_config = config

        self.tokenizer = AutoTokenizer.from_pretrained(
            tokenizer_name,
            revision=tokenizer_revision,
            local_files_only=True,
            padding_side="right",
        )
        self.tokenizer.padding_side = "right"
        rename_map = {"observation.image": "observation.images.base_0_rgb"}
        self.preprocessor, self.postprocessor = make_pre_post_processors(
            policy_cfg=config,
            pretrained_path=str(self.checkpoint),
            preprocessor_overrides={
                "device_processor": {"device": str(self.device)},
                "rename_observations_processor": {"rename_map": rename_map},
                # Reuse the explicitly revision-pinned local tokenizer instead
                # of allowing the saved processor to resolve an unpinned name.
                "tokenizer_processor": {"tokenizer": self.tokenizer},
            },
        )

        self._env: Any | None = None
        self._task_name: str | None = None
        self._instruction: str | None = None
        self._vla_head = _git_head(self.vla_root)
        self._policy_select_action_calls = 0
        self._policy_full_inference_calls = 0
        self._visual_encoder_calls = 0
        self._visual_observations_encoded = 0
        self._control_step_index = 0
        self._native_default_action_scale = DEFAULT_NATIVE_ACTION_SCALE

    def _validate_inputs(self) -> None:
        if self.device.type != "cuda" or not torch.cuda.is_available():
            raise RuntimeError("the real PI0.5 backend requires an assigned CUDA device")
        if self.episode_length != 300:
            raise ValueError("the Very Hard collector is locked to a 300-control-step episode limit")
        # ``getattr`` keeps the identity-only unit fixture compatible; normal
        # construction always sets the explicit cadence before validation.
        control_hz = int(getattr(self, "control_hz", CONTROL_HZ))
        if control_hz not in (CONTROL_HZ, CONTROL_30_HZ):
            raise ValueError(
                f"Meta-World collection supports {CONTROL_HZ} or {CONTROL_30_HZ} Hz control, "
                f"got {control_hz}"
            )
        native_action_scale = float(
            getattr(self, "native_action_scale", DEFAULT_NATIVE_ACTION_SCALE)
        )
        if not math.isfinite(native_action_scale) or native_action_scale <= 0.0:
            raise ValueError("native_action_scale must be finite and positive")
        if control_hz != CONTROL_30_HZ and not math.isclose(
            native_action_scale,
            DEFAULT_NATIVE_ACTION_SCALE,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        ):
            raise ValueError("80 Hz PI0.5 rollout must retain native action_scale=0.01")
        if self.checkpoint.name != "pretrained_model" or self.checkpoint.parent.name != "030000":
            raise ValueError(
                "checkpoint must resolve to the frozen SFT 030000/pretrained_model directory; "
                f"got {self.checkpoint}"
            )
        for filename in ("config.json", "model.safetensors", "policy_preprocessor.json", "policy_postprocessor.json"):
            path = self.checkpoint / filename
            if not path.is_file():
                raise FileNotFoundError(f"incomplete SFT checkpoint: {path}")

    def _ensure_env(self, task_name: str) -> None:
        if task_name not in VERY_HARD_TASKS:
            raise ValueError(f"collector is locked to Very Hard tasks, got {task_name!r}")
        if self._env is not None and self._task_name == task_name:
            self._env._env.action_scale = self.native_action_scale
            return
        if self._env is not None:
            self._env.close()
        self._env = self._env_class(
            task=task_name,
            camera_name="corner2",
            obs_type="pixels_agent_pos",
            render_mode="rgb_array",
            observation_width=480,
            observation_height=480,
            max_path_length=self.episode_length,
        )
        physics_timestep = float(self._env._env.model.opt.timestep)
        expected_timestep = 1.0 / PHYSICS_HZ
        if not math.isclose(physics_timestep, expected_timestep, rel_tol=0.0, abs_tol=1.0e-12):
            raise RuntimeError(
                "Meta-World physics timestep drifted: "
                f"expected {expected_timestep}, got {physics_timestep}"
            )
        default_action_scale = float(self._env._env.action_scale)
        if not math.isclose(
            default_action_scale,
            DEFAULT_NATIVE_ACTION_SCALE,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        ):
            raise RuntimeError(
                "Meta-World native action scale drifted: "
                f"expected {DEFAULT_NATIVE_ACTION_SCALE}, got {default_action_scale}"
            )
        self._native_default_action_scale = default_action_scale
        self._env._env.action_scale = self.native_action_scale
        self._env.metadata = {**self._env.metadata, "render_fps": self.control_hz}
        self._task_name = task_name
        self._instruction = str(self._task_descriptions[task_name])

    def reset_episode(self, task_name: str, seed: int) -> Any:
        self._ensure_env(task_name)
        random.seed(seed)
        np.random.seed(seed)
        torch.random.default_generator.manual_seed(seed)
        torch.cuda.manual_seed(seed)
        self.policy.reset()
        self._policy_select_action_calls = 0
        self._policy_full_inference_calls = 0
        self._visual_encoder_calls = 0
        self._visual_observations_encoded = 0
        self._control_step_index = 0
        observation, _info = self._env.reset(seed=seed)
        self._env._env.action_scale = self.native_action_scale
        return observation

    def task_instruction(self, task_name: str) -> str:
        self._ensure_env(task_name)
        assert self._instruction is not None
        return self._instruction

    def state_from_observation(self, observation: Mapping[str, Any]) -> np.ndarray:
        state = np.asarray(observation["agent_pos"], dtype=np.float32)
        if state.shape != (4,):
            raise ValueError(f"Meta-World audit state must have shape (4,), got {state.shape}")
        return state.copy()

    def _policy_batch(self, observation: Mapping[str, Any], instruction: str) -> dict[str, Any]:
        batch = self._preprocess_observation(dict(observation))
        batch["task"] = [instruction]
        return self.preprocessor(batch)

    @torch.inference_mode()
    def select_action(self, observation: Mapping[str, Any], instruction: str) -> np.ndarray:
        batch = self._policy_batch(observation, instruction)
        # PI0.5 only invokes predict_action_chunk when its 10-action queue is
        # empty. Count that boundary explicitly so artifacts can distinguish
        # per-control-frame critic observations from full VLM replanning.
        self._policy_select_action_calls += 1
        if len(self.policy._action_queue) == 0:
            self._policy_full_inference_calls += 1
        action = self.policy.select_action(batch)
        action = self.postprocessor(action)
        action_array = action.detach().to(device="cpu", dtype=torch.float32).numpy()
        if action_array.shape != (1, 4):
            raise ValueError(f"PI0.5 postprocessed action must be [1,4], got {action_array.shape}")
        return action_array[0].copy()

    def step(self, action: np.ndarray) -> BackendStep:
        if self._env is None:
            raise RuntimeError("reset_episode must be called before step")
        # The repository wrapper auto-resets before formatting a terminal image.
        # Calling the wrapped native Meta-World env here lets us render and retain
        # the true post-action terminal observation before any reset occurs.
        native_env = self._env._env
        if not math.isclose(
            float(native_env.action_scale),
            self.native_action_scale,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        ):
            raise RuntimeError("native Meta-World action_scale drifted during rollout")
        physics_substeps = (
            physics_substeps_for_control_step(self._control_step_index)
            if self.control_hz == CONTROL_30_HZ
            else PHYSICS_HZ // CONTROL_HZ
        )
        native_env.frame_skip = physics_substeps
        sim_time_before = float(native_env.data.time)
        raw_obs, reward, done, truncated, info = native_env.step(
            np.asarray(action, dtype=np.float32)
        )
        sim_time_after = float(native_env.data.time)
        expected_delta = physics_substeps / PHYSICS_HZ
        if not math.isclose(
            sim_time_after - sim_time_before,
            expected_delta,
            rel_tol=0.0,
            abs_tol=1.0e-9,
        ):
            raise RuntimeError(
                "native Meta-World simulation time does not match the requested control cadence: "
                f"substeps={physics_substeps}, before={sim_time_before}, after={sim_time_after}"
            )
        self._control_step_index += 1
        observation = self._env._format_raw_obs(raw_obs)
        success = bool(info.get("success", 0))
        terminated = bool(done or success)
        return BackendStep(
            observation=observation,
            reward=float(reward),
            terminated=terminated,
            truncated=bool(truncated),
            success=success,
            audit_info={
                "native_done": bool(done),
                "native_truncated": bool(truncated),
                "native_success": success,
                "physics_hz": PHYSICS_HZ,
                "native_action_scale": self.native_action_scale,
                "physics_substeps": physics_substeps,
                "sim_time_before_seconds": sim_time_before,
                "sim_time_after_seconds": sim_time_after,
            },
        )

    def replay_actions_for_warm_start(
        self,
        actions: np.ndarray,
        *,
        expected_states: np.ndarray,
        expected_rewards: np.ndarray,
        expected_success_trace: np.ndarray,
        atol: float = 1.0e-6,
    ) -> Mapping[str, Any]:
        """Replay an audited prior episode without rendering or visual encoding.

        Meta-World v3 documents that ``reset(seed=...)`` ignores the seed, and its
        Sawyer solver warm-start survives resets.  Reconstructing a later episode
        therefore requires replaying earlier same-rank/same-task actions.  This
        helper advances the native simulator exactly as :meth:`step` does but
        intentionally avoids the expensive RGB render used for returned policy
        observations.  Every available stored state/reward/success value remains
        a hard replay check.
        """

        if self._env is None:
            raise RuntimeError("reset_episode must be called before warm-start replay")
        action_rows = np.asarray(actions, dtype=np.float32)
        state_rows = np.asarray(expected_states, dtype=np.float32)
        reward_rows = np.asarray(expected_rewards, dtype=np.float32)
        success_rows = np.asarray(expected_success_trace, dtype=np.bool_)
        if (
            action_rows.ndim != 2
            or action_rows.shape[1] != 4
            or state_rows.shape != (len(action_rows) + 1, 4)
            or reward_rows.shape != (len(action_rows),)
            or success_rows.shape != (len(action_rows),)
        ):
            raise ValueError("warm-start replay arrays are not aligned")
        if atol <= 0.0:
            raise ValueError("warm-start replay atol must be positive")

        native_env = self._env._env
        initial_state = np.asarray(native_env._get_obs()[:4], dtype=np.float32)
        maximum_state_error = float(np.max(np.abs(initial_state - state_rows[0])))
        maximum_reward_error = 0.0
        if maximum_state_error > atol:
            raise RuntimeError(
                "warm-start replay initial state mismatch: "
                f"max_abs_error={maximum_state_error}"
            )
        observed_success = False
        for index, action in enumerate(action_rows):
            if not math.isclose(
                float(native_env.action_scale),
                self.native_action_scale,
                rel_tol=0.0,
                abs_tol=1.0e-12,
            ):
                raise RuntimeError("native action scale drifted during warm-start replay")
            substeps = (
                physics_substeps_for_control_step(index)
                if self.control_hz == CONTROL_30_HZ
                else PHYSICS_HZ // CONTROL_HZ
            )
            native_env.frame_skip = substeps
            raw_obs, reward, _done, _truncated, info = native_env.step(action)
            actual_state = np.asarray(raw_obs[:4], dtype=np.float32)
            state_error = float(
                np.max(np.abs(actual_state - state_rows[index + 1]))
            )
            reward_error = abs(float(reward) - float(reward_rows[index]))
            maximum_state_error = max(maximum_state_error, state_error)
            maximum_reward_error = max(maximum_reward_error, reward_error)
            actual_success = bool(info.get("success", 0))
            observed_success = bool(observed_success or actual_success)
            if (
                state_error > atol
                or reward_error > atol
                or actual_success != bool(success_rows[index])
            ):
                raise RuntimeError(
                    "warm-start replay diverged at control "
                    f"{index + 1}: state_error={state_error}, "
                    f"reward_error={reward_error}, success={actual_success}"
                )
        self._control_step_index = len(action_rows)
        return {
            "control_steps": len(action_rows),
            "maximum_state_abs_error": maximum_state_error,
            "maximum_reward_abs_error": maximum_reward_error,
            "success": observed_success,
        }

    @torch.inference_mode()
    def encode_visual(self, observation: Mapping[str, Any]) -> np.ndarray:
        return self.encode_visual_batch((observation,), batch_size=1)[0]

    @torch.inference_mode()
    def encode_visual_batch(
        self,
        observations: Sequence[Mapping[str, Any]],
        *,
        batch_size: int,
    ) -> np.ndarray:
        """Encode control observations in bounded batches with the frozen vision tower.

        This path intentionally does not call ``policy.select_action`` or the
        PaliGemma language/reasoning transformer.  It only materializes the
        same frozen image patch embeddings used by the legacy collector.
        """

        if self._instruction is None:
            raise RuntimeError("reset_episode must be called before visual encoding")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if not observations:
            raise ValueError("observations must not be empty")
        self._visual_encoder_calls += math.ceil(len(observations) / batch_size)
        self._visual_observations_encoded += len(observations)

        encoded_rows: list[torch.Tensor] = []
        for start in range(0, len(observations), batch_size):
            image_rows: list[torch.Tensor] = []
            for observation in observations[start : start + batch_size]:
                policy_batch = self._policy_batch(observation, self._instruction)
                images, image_masks = self.policy._preprocess_images(policy_batch)
                real_images = [
                    image
                    for image, mask in zip(images, image_masks, strict=True)
                    if bool(mask[0].item())
                ]
                if len(real_images) != 1:
                    raise RuntimeError(
                        "Meta-World SFT collection expects one real camera, "
                        f"got {len(real_images)}"
                    )
                image_rows.append(real_images[0])
            image_batch = torch.cat(image_rows, dim=0)
            encoded = self.policy.model.paligemma_with_expert.embed_image(image_batch)
            encoded_rows.append(encoded.to(dtype=torch.float32, device="cpu"))
        # Preserve the collector's [time,camera,patch,feature] convention.
        return torch.cat(encoded_rows, dim=0).unsqueeze(1).numpy()

    @torch.inference_mode()
    def encode_instruction(self, instruction: str) -> np.ndarray:
        cleaned = instruction.strip().replace("_", " ").replace("\n", " ")
        tokenized = self.tokenizer(
            [cleaned],
            max_length=int(self.policy_config.tokenizer_max_length),
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        tokens = tokenized["input_ids"].to(self.device)
        mask = tokenized["attention_mask"].to(self.device, dtype=torch.bool)
        embedded = self.policy.model.paligemma_with_expert.embed_language_tokens(tokens)
        embedding_dim = embedded.shape[-1]
        embedded = embedded * math.sqrt(embedding_dim)
        weights = mask.unsqueeze(-1).to(dtype=embedded.dtype)
        pooled = (embedded * weights).sum(dim=1) / weights.sum(dim=1).clamp_min(1)
        return pooled[0].to(dtype=torch.float32, device="cpu").numpy()

    def metadata(self) -> Mapping[str, Any]:
        return {
            "backend": "metaworld_pi05_sft_only",
            "vla_root": str(self.vla_root),
            "vla_git_head": self._vla_head,
            "checkpoint": str(self.checkpoint),
            "checkpoint_step": 30_000,
            "checkpoint_read_only": True,
            "policy_n_action_steps": 10,
            "policy_chunk_size": 50,
            "policy_num_inference_steps": int(self.policy_config.num_inference_steps),
            "control_hz": self.control_hz,
            "physics_hz": PHYSICS_HZ,
            "physics_timestep_seconds": 1.0 / PHYSICS_HZ,
            "native_action_scale": self.native_action_scale,
            "native_default_action_scale": self._native_default_action_scale,
            "action_scale_adapter": not math.isclose(
                self.native_action_scale,
                self._native_default_action_scale,
                rel_tol=0.0,
                abs_tol=1.0e-12,
            ),
            "physics_substep_schedule": (
                "cumulative_floor_400_over_30_sequence_13_13_14"
                if self.control_hz == CONTROL_30_HZ
                else "fixed_5"
            ),
            "corrector_loaded": False,
            "camera": "corner2",
            "render_size": [480, 480],
            "terminal_observation_source": "native_metaworld_step_before_wrapper_autoreset",
            "language_embedding_spec": {
                "template": "{cleaned_instruction}",
                "cleaning": "strip; underscore_to_space; newline_to_space",
                "tokenizer": self.tokenizer_name,
                "tokenizer_revision": self.tokenizer_revision,
                "padding_side": "right",
                "max_length": int(self.policy_config.tokenizer_max_length),
                "state_in_prompt": False,
                "scaling": "sqrt(2048)",
                "pooling": "masked_mean_valid_tokens",
                "layer": "input_embedding_table",
            },
            "visual_embedding_spec": {
                "extractor": "policy.model.paligemma_with_expert.embed_image",
                "preprocess": "PI05Policy._preprocess_images",
                "camera_count": 1,
                "patches_per_camera": 256,
                "visual_dim": 2048,
                "quantization": "symmetric_int8_per_patch_token_fp16_scale",
            },
        }

    def runtime_counters(self) -> dict[str, int]:
        """Per-episode cadence evidence, reset by ``reset_episode``."""

        return {
            "policy_select_action_calls": self._policy_select_action_calls,
            "policy_full_inference_calls": self._policy_full_inference_calls,
            "visual_encoder_batch_calls": self._visual_encoder_calls,
            "visual_observations_encoded": self._visual_observations_encoded,
        }

    def close(self) -> None:
        if self._env is not None:
            self._env.close()
            self._env = None
