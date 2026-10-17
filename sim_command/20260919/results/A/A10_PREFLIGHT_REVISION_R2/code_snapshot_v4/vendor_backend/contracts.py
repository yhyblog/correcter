"""Fixed collection contracts for the Meta-World AC-TMIL dataset.

The collector deliberately uses ``torchrun`` only as a process launcher.  Rank
information comes from environment variables; this package never initializes a
``torch.distributed`` process group.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

import numpy as np


SCHEMA_VERSION = 1
CONTROL_FRAME_SCHEMA_VERSION = 2
# Schema v3 is a fresh-policy rollout at 30 Hz control rate. MuJoCo keeps its
# native 400 Hz physics timestep; a deterministic 13/13/14 substep cadence
# realizes exactly 30 control updates per simulated second on average.
CONTROL_30HZ_SCHEMA_VERSION = 3
CONTROL_HZ = 80
VISUAL_HZ = 10
VISUAL_STRIDE = CONTROL_HZ // VISUAL_HZ
CONTROL_FRAME_VISUAL_HZ = CONTROL_HZ
CONTROL_FRAME_VISUAL_STRIDE = 1
CONTROL_30_HZ = 30
CONTROL_30_VISUAL_HZ = CONTROL_30_HZ
CONTROL_30_VISUAL_STRIDE = 1
PHYSICS_HZ = 400
ACTION_DIM = 4
DEFAULT_NATIVE_ACTION_SCALE = 0.01
# Train-only diagnostics selected this explicit adapter for reuse of the frozen
# 80 Hz SFT policy under native 30 Hz control.  It is protocol metadata, not a
# trainable ACT-RECAP hyperparameter.
RECAP_30HZ_NATIVE_ACTION_SCALE = 0.015
DEFAULT_MAX_CONTROL_STEPS = 300
DEFAULT_BASE_SEED = 400_000
DEFAULT_TOKENIZER_NAME = "google/paligemma-3b-pt-224"
DEFAULT_TOKENIZER_REVISION = "35e4f46485b4d07967e7e9935bc3786aad50687c"

VERY_HARD_TASKS: tuple[str, ...] = (
    "shelf-place-v3",
    "disassemble-v3",
    "stick-pull-v3",
    "stick-push-v3",
    "pick-place-wall-v3",
)


@dataclass(frozen=True)
class RankContext:
    """Single-node ``torchrun`` rank information."""

    rank: int
    local_rank: int
    world_size: int

    @classmethod
    def from_environ(cls, *, expected_world_size: int = 8) -> "RankContext":
        if expected_world_size <= 0:
            raise ValueError("expected_world_size must be positive")
        rank = int(os.environ.get("RANK", "0"))
        local_rank = int(os.environ.get("LOCAL_RANK", str(rank)))
        world_size = int(os.environ.get("WORLD_SIZE", "1"))
        context = cls(rank=rank, local_rank=local_rank, world_size=world_size)
        context.validate(expected_world_size=expected_world_size)
        return context

    def validate(self, *, expected_world_size: int) -> None:
        if self.world_size != expected_world_size:
            raise RuntimeError(
                f"collector requires WORLD_SIZE={expected_world_size}, got {self.world_size}; "
                "launch it with torchrun or explicitly change --expected-world-size for a fake smoke test"
            )
        if not 0 <= self.rank < self.world_size:
            raise ValueError(f"invalid rank {self.rank} for world_size={self.world_size}")
        if not 0 <= self.local_rank < self.world_size:
            raise ValueError(f"invalid local_rank {self.local_rank} for world_size={self.world_size}")


@dataclass(frozen=True)
class EpisodeAssignment:
    """One task/seed episode assigned to a launcher rank."""

    task_name: str
    task_id: int
    seed: int
    pair_index: int
    episode_uid: str


def make_episode_uid(task_name: str, seed: int) -> str:
    if task_name not in VERY_HARD_TASKS:
        raise ValueError(f"unsupported task {task_name!r}")
    if seed < 0:
        raise ValueError("seed must be non-negative")
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", task_name).strip("-")
    return f"mwvh-v1__{slug}__seed-{seed:07d}"


def paired_seed_assignments(
    *,
    seeds_per_task: int,
    rank: int,
    world_size: int,
    base_seed: int = DEFAULT_BASE_SEED,
    tasks: Sequence[str] = VERY_HARD_TASKS,
) -> list[EpisodeAssignment]:
    """Shard paired seeds while keeping all five tasks for a seed on one rank.

    The returned order groups assignments by task so a real backend can reuse a
    Meta-World environment.  Pairing is defined by ``pair_index``/``seed``, not
    by adjacent file order.
    """

    if seeds_per_task <= 0:
        raise ValueError("seeds_per_task must be positive")
    if world_size <= 0 or not 0 <= rank < world_size:
        raise ValueError(f"invalid rank/world_size: {rank}/{world_size}")
    if base_seed < 0:
        raise ValueError("base_seed must be non-negative")
    if tuple(tasks) != VERY_HARD_TASKS:
        raise ValueError("the primary collector is locked to the five Very Hard tasks in canonical order")

    local_pairs = [i for i in range(seeds_per_task) if i % world_size == rank]
    assignments: list[EpisodeAssignment] = []
    for task_id, task_name in enumerate(tasks):
        for pair_index in local_pairs:
            seed = base_seed + pair_index
            assignments.append(
                EpisodeAssignment(
                    task_name=task_name,
                    task_id=task_id,
                    seed=seed,
                    pair_index=pair_index,
                    episode_uid=make_episode_uid(task_name, seed),
                )
            )
    return assignments


@dataclass(frozen=True)
class CollectionConfig:
    schema_version: int = SCHEMA_VERSION
    max_control_steps: int = DEFAULT_MAX_CONTROL_STEPS
    control_hz: int = CONTROL_HZ
    visual_hz: int = VISUAL_HZ
    visual_stride: int = VISUAL_STRIDE
    action_dim: int = ACTION_DIM
    visual_encode_batch_size: int = 1
    physics_hz: int = PHYSICS_HZ
    native_action_scale: float = DEFAULT_NATIVE_ACTION_SCALE

    @classmethod
    def control_30hz(
        cls,
        *,
        max_control_steps: int = DEFAULT_MAX_CONTROL_STEPS,
        visual_encode_batch_size: int = 16,
        native_action_scale: float = DEFAULT_NATIVE_ACTION_SCALE,
    ) -> "CollectionConfig":
        return cls(
            schema_version=CONTROL_30HZ_SCHEMA_VERSION,
            max_control_steps=max_control_steps,
            control_hz=CONTROL_30_HZ,
            visual_hz=CONTROL_30_VISUAL_HZ,
            visual_stride=CONTROL_30_VISUAL_STRIDE,
            visual_encode_batch_size=visual_encode_batch_size,
            physics_hz=PHYSICS_HZ,
            native_action_scale=native_action_scale,
        )

    def __post_init__(self) -> None:
        if self.max_control_steps <= 0:
            raise ValueError("max_control_steps must be positive")
        if self.visual_encode_batch_size <= 0:
            raise ValueError("visual_encode_batch_size must be positive")
        timing_by_schema = {
            SCHEMA_VERSION: (CONTROL_HZ, VISUAL_HZ, VISUAL_STRIDE),
            CONTROL_FRAME_SCHEMA_VERSION: (
                CONTROL_HZ,
                CONTROL_FRAME_VISUAL_HZ,
                CONTROL_FRAME_VISUAL_STRIDE,
            ),
            CONTROL_30HZ_SCHEMA_VERSION: (
                CONTROL_30_HZ,
                CONTROL_30_VISUAL_HZ,
                CONTROL_30_VISUAL_STRIDE,
            ),
        }
        expected = timing_by_schema.get(self.schema_version)
        if expected is None:
            raise ValueError(f"unsupported collection schema_version={self.schema_version}")
        actual = (self.control_hz, self.visual_hz, self.visual_stride)
        if actual != expected or self.action_dim != ACTION_DIM:
            raise ValueError(
                f"schema v{self.schema_version} collection timing must be {expected} "
                f"with action_dim={ACTION_DIM}, got {actual} action_dim={self.action_dim}"
            )
        if self.physics_hz != PHYSICS_HZ:
            raise ValueError(f"Meta-World physics must remain fixed at {PHYSICS_HZ} Hz")
        if not math.isfinite(self.native_action_scale) or self.native_action_scale <= 0.0:
            raise ValueError("native_action_scale must be finite and positive")
        if (
            self.schema_version != CONTROL_30HZ_SCHEMA_VERSION
            and not math.isclose(
                self.native_action_scale,
                DEFAULT_NATIVE_ACTION_SCALE,
                rel_tol=0.0,
                abs_tol=1.0e-12,
            )
        ):
            raise ValueError("non-30-Hz collection must retain native action_scale=0.01")

    @property
    def records_physics_cadence(self) -> bool:
        return self.schema_version == CONTROL_30HZ_SCHEMA_VERSION


def physics_substeps_for_control_step(
    control_step_index: int,
    *,
    physics_hz: int = PHYSICS_HZ,
    control_hz: int = CONTROL_30_HZ,
) -> int:
    """Return one exact integer substep count for a zero-based control step."""

    if control_step_index < 0:
        raise ValueError("control_step_index must be non-negative")
    if physics_hz <= 0 or control_hz <= 0 or physics_hz < control_hz:
        raise ValueError("physics_hz/control_hz must be positive and physics_hz >= control_hz")
    before = (control_step_index * physics_hz) // control_hz
    after = ((control_step_index + 1) * physics_hz) // control_hz
    return after - before


@dataclass(frozen=True)
class BackendStep:
    """Result of one actual environment control action."""

    observation: Any
    reward: float
    terminated: bool
    truncated: bool
    success: bool
    audit_info: Mapping[str, Any] | None = None

    @property
    def done(self) -> bool:
        return bool(self.terminated or self.truncated)


class CollectionBackend(Protocol):
    """Narrow adapter required by the backend-agnostic episode runner."""

    def reset_episode(self, task_name: str, seed: int) -> Any: ...

    def task_instruction(self, task_name: str) -> str: ...

    def state_from_observation(self, observation: Any) -> np.ndarray: ...

    def select_action(self, observation: Any, instruction: str) -> np.ndarray: ...

    def step(self, action: np.ndarray) -> BackendStep: ...

    def encode_visual(self, observation: Any) -> np.ndarray: ...

    def encode_visual_batch(
        self, observations: Sequence[Any], *, batch_size: int
    ) -> np.ndarray: ...

    def encode_instruction(self, instruction: str) -> np.ndarray: ...

    def metadata(self) -> Mapping[str, Any]: ...

    def close(self) -> None: ...
