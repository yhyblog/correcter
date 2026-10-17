"""Native X-VLA sampling and Florence-2 features for inference timing.

This adapter loads no PI05 assets and no trained D/G0 weights. The caller owns
CUDA streams, timing, and any subsequent feature projection or random heads.
Each method owns its processor state; the frozen native model is shared.
"""
from __future__ import annotations

import json
from pathlib import Path
import time


class XNative:
    def __init__(self, cfg):
        import numpy as np
        import torch
        from lerobot.policies.factory import get_policy_class, make_pre_post_processors

        self.cfg, self.np, self.torch = cfg, np, torch
        self.device = torch.device(cfg.get('device', 'cuda:0'))
        torch.set_num_threads(int(cfg.get('cpu_threads', 2)))
        torch.backends.cuda.matmul.allow_tf32 = True
        checkpoint = Path(cfg['checkpoint'])
        started = time.perf_counter()
        self.policy = get_policy_class('xvla').from_pretrained(
            checkpoint, local_files_only=True, strict=True)
        self.policy.config.n_action_steps = 10
        self.policy.config.num_denoising_steps = 10
        self.policy.to(self.device).eval().requires_grad_(False)
        self.model = self.policy.model
        self.raw_horizon, self.nfe = 30, 10
        if (self.policy.config.chunk_size != self.raw_horizon or
                self.policy.config.n_obs_steps != 1 or
                self.policy.config.action_mode != 'auto' or
                self.model.action_space.real_dim != 4 or
                self.policy.config.num_image_views != 1):
            raise ValueError('X-VLA native single-view/raw30/real4 layout differs from timing protocol')
        if tuple(self.model.vlm.image_feature_source) != ('spatial_avg_pool', 'temporal_avg_pool'):
            raise ValueError('Expected native Florence global token followed by spatial tokens')

        # Processor steps retain _current_transition. Never share them between
        # concurrent planning and feedback calls, even though weights are shared.
        self.plan_preprocessor, self.postprocessor = make_pre_post_processors(
            self.policy.config, pretrained_path=checkpoint)
        self.visual_preprocessor, _ = make_pre_post_processors(
            self.policy.config, pretrained_path=checkpoint)
        self.language_preprocessor, _ = make_pre_post_processors(
            self.policy.config, pretrained_path=checkpoint)
        self.metadata = dict(
            kind='xvla', checkpoint=str(checkpoint), device=str(self.device),
            policy_parameters=sum(p.numel() for p in self.policy.parameters()),
            vision_parameters=sum(p.numel() for p in self.model.vlm.vision_tower.parameters()),
            raw_horizon=self.raw_horizon, n_action_steps=10, NFE=self.nfe,
            image_resize=list(self.policy.config.resize_imgs_with_padding),
            native_visual_entry='policy.model.vlm._encode_image',
            native_visual_output=[50, 1024], returned_visual_shape=[5, 49, 1024],
            native_language_dimension=1024,
            language_pooling='masked mean of native Florence/BART input embeddings',
            visual_history_batch_size=1, visual_history_frames=5,
            external_pi05_loaded=False, trained_native_DG0_loaded=False,
            processor_instances=3, shared_frozen_policy=True,
            sampling='native ten-step recurrence with explicit per-call torch.Generator',
            postprocess='entire [1,30,4] once; original processor transfers result to CPU once',
            initialize_host_seconds=time.perf_counter() - started)
        if cfg.get('output'):
            path = Path(cfg['output']) / 'X_NATIVE_METADATA.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix('.json.tmp')
            temporary.write_text(json.dumps(self.metadata, ensure_ascii=False, indent=2) + '\n')
            temporary.replace(path)

    def _sample(self, observation, instruction):
        torch, np = self.torch, self.np
        return {
            'observation.image': torch.from_numpy(np.ascontiguousarray(
                observation['pixels'])).permute(2, 0, 1).float() / 255,
            'observation.state': torch.as_tensor(observation['agent_pos'], dtype=torch.float32),
            'task': instruction,
        }

    def plan(self, ctx, seed):
        """One complete native raw30 query, with no D/G0 or action correction."""
        torch, model = self.torch, self.model
        generator = torch.Generator(device=self.device).manual_seed(int(seed))
        with torch.no_grad(), torch.autocast('cuda', dtype=torch.bfloat16):
            batch = self.plan_preprocessor(self._sample(ctx['currentobs'], ctx['instruction']))
            inputs = self.policy._build_model_inputs(batch)
            target_dtype = model._get_target_dtype()
            images = inputs['image_input'].to(dtype=target_dtype)
            proprio = inputs['proprio'].to(dtype=target_dtype)
            encoded = model.forward_vlm(inputs['input_ids'], images, inputs['image_mask'])
            batch_size = inputs['input_ids'].shape[0]
            x1 = torch.randn(batch_size, model.chunk_size, model.dim_action,
                             device=proprio.device, dtype=target_dtype, generator=generator)
            action = torch.zeros_like(x1)
            # Matches modeling_xvla.XVLAModel.generate_actions exactly; only RNG
            # ownership and the redundant eval()/policy queue writes differ.
            for index in range(self.nfe, 0, -1):
                t = torch.full((batch_size,), index / self.nfe,
                               device=proprio.device, dtype=target_dtype)
                x_t = x1 * t.view(-1, 1, 1) + action * (1 - t).view(-1, 1, 1)
                proprio_m, x_t_m = model.action_space.preprocess(proprio, x_t)
                action = model.transformer(domain_id=inputs['domain_id'],
                    action_with_noise=x_t_m, proprio=proprio_m, t=t, **encoded)
            native = model.action_space.postprocess(action)
            raw_cpu = self.postprocessor(native)
        # The checkpoint's postprocessor already performs the only GPU->CPU copy.
        return raw_cpu.detach().float().numpy()[0]

    def encode_five(self, ctx):
        """Online native preprocessing and five batch-one visual encoder calls."""
        torch = self.torch
        outputs = []
        with torch.no_grad(), torch.autocast('cuda', dtype=torch.bfloat16):
            for frame, prop in zip(ctx['frames'], ctx['props'], strict=True):
                observation = dict(pixels=frame, agent_pos=prop)
                batch = self.visual_preprocessor(self._sample(observation, ctx['instruction']))
                images, _ = self.policy._prepare_images(batch)
                tokens = self.model.vlm._encode_image(images[:, 0])
                # At the native 224x224 resolution: global + 7x7 spatial tokens.
                outputs.append(tokens[0, 1:].float())
        return torch.stack(outputs, dim=0)

    def language(self, ctx):
        """Native language embedding mean, normally cached once per context."""
        torch = self.torch
        with torch.no_grad():
            batch = self.language_preprocessor(self._sample(ctx['currentobs'], ctx['instruction']))
            ids = batch['observation.language.tokens']
            mask = batch['observation.language.attention_mask']
            embeddings = self.model.vlm.get_input_embeddings()(ids).float()
            weights = mask.to(embeddings.dtype).unsqueeze(-1)
            return ((embeddings * weights).sum(dim=1) / weights.sum(dim=1).clamp_min(1))[0]
