"""Native SmolVLA sampling and features, with no external feature model.

The caller owns CUDA streams. Planning and feedback have separate saved
processors while sharing the frozen native model. Five-frame encoding keeps
batch size one, matching the earlier feedback timing protocol.
"""
from __future__ import annotations

import math
from pathlib import Path


class SmolNative:
    def __init__(self, cfg):
        import numpy as np
        import torch
        from lerobot.policies.factory import get_policy_class, make_pre_post_processors

        self.np, self.torch = np, torch
        self.device = cfg.get('device', 'cuda:0')
        self.checkpoint = Path(cfg['checkpoint'])
        self.policy = get_policy_class('smolvla').from_pretrained(
            self.checkpoint, local_files_only=True, strict=True)
        self.policy.config.n_action_steps = 10
        self.policy.config.num_steps = 10
        self.policy.config.device = self.device
        self.policy.to(self.device).eval().requires_grad_(False)
        self.plan_pre, self.plan_post = make_pre_post_processors(
            self.policy.config, pretrained_path=self.checkpoint)
        self.feedback_pre, _ = make_pre_post_processors(
            self.policy.config, pretrained_path=self.checkpoint)
        self.native = self.policy.model.vlm_with_expert
        self.visual_dim = int(self.native.config.text_config.hidden_size)
        self.language_dim = self.visual_dim
        self.raw_horizon = int(self.policy.config.chunk_size)
        image_hw = list(self.policy.config.resize_imgs_with_padding)
        patch_size = int(self.native.config.vision_config.patch_size)
        scale_factor = int(self.native.config.scale_factor)
        self.token_grid = [side // patch_size // scale_factor for side in image_hw]
        self.metadata = dict(
            model='SmolVLA', checkpoint=str(self.checkpoint), device=self.device,
            raw_horizon=self.raw_horizon, natural_H=10, NFE=10,
            image_resize=image_hw, native_patch_size=patch_size,
            vision_tower_dimension=int(self.native.config.vision_config.hidden_size),
            vision_tower_tokens=math.prod(side // patch_size for side in image_hw),
            connector_scale_factor=scale_factor, visual_token_grid=self.token_grid,
            visual_tokens=math.prod(self.token_grid), visual_dimension=self.visual_dim,
            language_dimension=self.language_dim, frames_per_feedback=5,
            visual_batch_size=1,
            feature_stage='native vision_model + connector + native sqrt(hidden_size) prefix scale',
            language_stage='native text embedding + native sqrt(hidden_size) scale; masked token mean',
            parameters=sum(parameter.numel() for parameter in self.policy.parameters()),
            external_encoder=None, PI05_loaded=False, shared_native_model=True,
            separate_plan_and_feedback_processors=True, native_action_queue_used=False,
            noise='explicit local torch.Generator; no global RNG reset',
            sampling_autocast='cuda bfloat16', per_action_CPU_transfer=False)

    def _sample(self, observation, instruction):
        np, torch = self.np, self.torch
        return {
            'observation.image': torch.from_numpy(np.ascontiguousarray(observation['pixels'])).permute(2, 0, 1).float() / 255,
            'observation.state': torch.as_tensor(observation['agent_pos'], dtype=torch.float32),
            'task': instruction,
        }

    def plan(self, ctx, seed):
        """Full native NFE10 sample, raw50, one horizon-wide saved postprocessor."""
        torch = self.torch
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
            batch = self.plan_pre(self._sample(ctx['currentobs'], ctx['instruction']))
            images, image_masks = self.policy.prepare_images(batch)
            state = self.policy.prepare_state(batch)
            generator = torch.Generator(device=self.device)
            generator.manual_seed(int(seed))
            noise = torch.randn((1, self.raw_horizon, self.policy.config.max_action_dim),
                                device=self.device, dtype=torch.float32, generator=generator)
            native = self.policy.model.sample_actions(
                images, image_masks, batch['observation.language.tokens'],
                batch['observation.language.attention_mask'], state, noise=noise)
            raw = self.plan_post(native[:, :, :4].reshape(-1, 4)).reshape(self.raw_horizon, 4)
            result = raw.float().cpu().numpy().copy()
            torch.cuda.current_stream(self.device).synchronize()
        return result

    def encode_five(self, ctx):
        """Return GPU [5,64,960] native prefix visual tokens on caller's stream.

        Includes the actual saved input processor and native image resize for
        each frame. The caller synchronizes its stream after subsequent D/G0.
        """
        torch = self.torch
        rows = []
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
            for frame, prop in zip(ctx['frames'], ctx['props']):
                batch = self.feedback_pre(self._sample(
                    dict(pixels=frame, agent_pos=prop), ctx['instruction']))
                images, _ = self.policy.prepare_images(batch)
                # This checkpoint has one real camera and empty_cameras=0.
                tokens = self.native.embed_image(images[0])
                rows.append(tokens * math.sqrt(self.visual_dim))
            return torch.cat(rows, dim=0)

    def language(self, ctx):
        """Native 960-D task embedding for preparation/cache, without image forward."""
        torch = self.torch
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
            batch = self.feedback_pre(self._sample(ctx['currentobs'], ctx['instruction']))
            tokens = self.native.embed_language_tokens(batch['observation.language.tokens'])
            tokens = tokens * math.sqrt(self.language_dim)
            mask = batch['observation.language.attention_mask'].to(tokens.dtype).unsqueeze(-1)
            return ((tokens * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1))[0]
