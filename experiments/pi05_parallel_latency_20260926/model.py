"""Private PI05 parallel-latency adapter; loading and inference only.

One frozen PI05 is shared by the planning and feedback CUDA streams. Each
thread owns its processor state. Wide Q is random and untrained: this module
measures the proposed architecture, not its task performance.
"""
from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[2]
ACCEPTED = WORKSPACE / 'Corrector/sim_command/20260919/results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code'
MATCHING = dict(xyz_rms=.05, gripper_rms=.10, xyz_linf=.15, gripper_linf=.4,
                boundary_clearance=.05, tolerance=1e-6, zero_threshold=1e-10)


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    temporary.replace(path)


class Meter:
    """The accepted loader's minimal accounting interface."""
    def __init__(self):
        self.entered = Counter()

    def call(self, name, function, units):
        self.entered[name] += 1
        return function()


def make_q(torch, checkpoint_state, width, seed):
    """Five original MLPs at a new width, retaining each member's preprocessing."""
    from corrector.critic import observed_features
    nn = torch.nn

    class WideQ(nn.Module):
        def __init__(self):
            super().__init__()
            keys = ['norm_mean', 'norm_std', 'residual_scale'] + [
                f'{name}_{suffix}' for name in ('visual', 'language')
                for suffix in ('center', 'basis', 'scale')]
            for key in keys:
                self.register_buffer(key, checkpoint_state[key].detach().cpu().float().clone())
            state_dim = self.visual_basis.shape[1] + self.language_basis.shape[1] + 37
            def mlp(a, b, c, last_activation=True):
                return nn.Sequential(nn.Linear(a, b), nn.SiLU(), nn.Linear(b, c),
                                     *([nn.SiLU()] if last_activation else []))
            self.state = mlp(state_dim, 2 * width, width)
            self.action = mlp(40, width, width)
            self.residual = mlp(40, width, width)
            self.head = mlp(2 * width, 2 * width, 1, False)
            self.advantage = mlp(3 * width, 2 * width, 1, False)

        def features(self, arrays):
            visual, language, other = observed_features(arrays, self.norm_mean, self.norm_std)
            parts = []
            for name, values in (('visual', visual), ('language', language)):
                parts.append((((values - getattr(self, name + '_center')) @
                    getattr(self, name + '_basis')) / getattr(self, name + '_scale')).clamp(-8, 8))
            return torch.cat([*parts, other], -1)

        def forward(self, features, actions):
            n, k, _, _ = actions.shape
            base = actions[:, 0].repeat_interleave(k, 0)
            shared = torch.cat([self.state(features).repeat_interleave(k, 0),
                                self.action(base.flatten(1))], -1)
            delta = ((actions.flatten(0, 1) - base) / self.residual_scale).flatten(1)
            actual = self.advantage(torch.cat([shared, self.residual(delta)], -1))
            zero = self.advantage(torch.cat([shared, self.residual(torch.zeros_like(delta))], -1))
            return (self.head(shared) + actual - zero).reshape(n, k)

    # Startup-only CPU RNG scope. Concurrent inference never touches global RNG.
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        model = WideQ()
    return model.eval().requires_grad_(False)


class ParallelModel:
    def __init__(self, cfg):
        self.cfg = cfg
        self.assets = read(cfg.get('assets_path', ROOT / 'assets.json'))
        for path in (WORKSPACE / 'Corrector', WORKSPACE / 'Corrector/src',
                     WORKSPACE / 'ACT-RECAP/src', ACCEPTED, ACCEPTED / 'vendor_vla/src'):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        import numpy as np
        import torch
        from numeric_setup import initialize
        from feature_path import OfflineFeatures, canonical_decode, spatial_tokens, cpu_batch
        from ac_tmil.future_aware.models import WorldModel, BenefitModel
        from corrector.actions import ActionTransform
        from experiments.standalone_ablation_20260918.candidates import project_solo
        from lerobot.processor import PolicyProcessorPipeline
        from lerobot.processor.converters import batch_to_transition, transition_to_batch
        from transformers import AutoTokenizer

        self.np, self.torch = np, torch
        self.canonical_decode, self.spatial_tokens, self.cpu_batch = canonical_decode, spatial_tokens, cpu_batch
        self.project_solo = project_solo
        self.device = cfg.get('device', 'cuda:0')
        torch.set_num_threads(int(cfg.get('cpu_threads', 2)))
        torch.backends.cuda.matmul.allow_tf32 = True
        self.output = Path(cfg.get('output', ROOT))
        self.output.mkdir(parents=True, exist_ok=True)
        load_output = self.output / 'model_load'
        load_output.mkdir(exist_ok=True)
        self.base_config = read(cfg.get('base_config', self.assets['historical_base_config']))
        start = time.perf_counter()
        state = initialize(self.base_config, load_output, Meter(), self.device)
        self.state, self.policy, self.model = state, state['policy'], state['model']
        self.projection = state['projection']
        self.plan_features, self.post = state['features'], state['post']
        # Reload only the small saved processor/tokenizer, never the model.
        # CountedCallable is intentionally not deep-copied: its forwarding
        # __getattr__ does not supply the state needed by deepcopy's new object.
        feedback_tokenizer = AutoTokenizer.from_pretrained(
            self.base_config['tokenizer_name'], revision=self.base_config['tokenizer_revision'],
            local_files_only=True, padding_side='right')
        feedback_pre = PolicyProcessorPipeline.from_pretrained(
            pretrained_model_name_or_path=self.base_config['checkpoint'],
            config_filename='policy_preprocessor.json',
            overrides={'device_processor': {'device': self.device},
                'rename_observations_processor': {'rename_map': {'observation.image': 'observation.images.base_0_rgb'}},
                'tokenizer_processor': {'tokenizer': feedback_tokenizer}},
            to_transition=batch_to_transition, to_output=transition_to_batch)
        self.feedback_features = OfflineFeatures()
        for key in ('device', 'policy', 'policy_config', '_preprocess_observation'):
            setattr(self.feedback_features, key, getattr(self.plan_features, key))
        self.feedback_features.preprocessor = feedback_pre
        self.feedback_features.tokenizer = feedback_tokenizer
        self.feedback_features._instruction = self.base_config['source']['instruction']
        self.feedback_features._visual_encoder_calls = 0
        self.feedback_features._visual_observations_encoded = 0
        self.worlds, self.gates = [], []
        for item in self.assets['DG0']:
            norm = read(item['D_normalization'])
            world = WorldModel(norm).to(self.device)
            gate = BenefitModel(norm).to(self.device)
            world.load_state_dict(torch.load(item['D_checkpoint'], map_location=self.device, weights_only=True))
            gate.load_state_dict(torch.load(item['G0_checkpoint'], map_location=self.device, weights_only=True))
            self.worlds.append(world.eval().requires_grad_(False))
            self.gates.append(gate.eval().requires_grad_(False))
        q_root = Path(cfg.get('q_reference_assets', self.assets['Q']['historical_trained_small_Q_assets']))
        self.q_models = []
        for index, member in enumerate(self.assets['Q']['preprocessing_per_member']):
            q_state = torch.load(member['checkpoint'], map_location='cpu', weights_only=True)
            self.q_models.append(make_q(torch, q_state, int(cfg.get('q_width', 512)),
                                        int(cfg.get('q_seed', 20260926)) + index))
        transform = ActionTransform.from_checkpoint(self.base_config['checkpoint'], device='cpu')
        self.slopes = ((transform.q99 - transform.q01) / 2).numpy()
        self.matching = cfg.get('matching', self.assets.get('matching', MATCHING))
        self.language_cache = {}
        self.plan_stream = torch.cuda.Stream(device=self.device)
        self.feedback_stream = torch.cuda.Stream(device=self.device)
        # Establish loading -> worker dependencies without a device-wide fence.
        initialized = torch.cuda.Event()
        initialized.record(torch.cuda.current_stream(self.device))
        self.plan_stream.wait_event(initialized)
        self.feedback_stream.wait_event(initialized)
        initialized.synchronize()
        self.ready = dict(status='ready', pid=os.getpid(), device=self.device,
            checkpoint=self.base_config['checkpoint'], NFE=10, raw_horizon=50,
            natural_H=10, nominal_execution_Hz=30, nominal_natural_queries_Hz=3,
            D=[sum(p.numel() for p in model.parameters()) for model in self.worlds],
            G0=[sum(p.numel() for p in model.parameters()) for model in self.gates],
            Q=[sum(p.numel() for p in model.parameters()) for model in self.q_models],
            Q_device='cpu', Q_dtype='float32', Q_cpu_threads=torch.get_num_threads(),
            Q_initialization='random untrained MLPs; original per-member preprocessing buffers',
            q_reference_assets=str(q_root), DG0_assets=self.assets['DG0'],
            shared_frozen_PI05=True, separate_preprocessors=True,
            plan_cuda_stream=int(self.plan_stream.cuda_stream),
            feedback_cuda_stream=int(self.feedback_stream.cuda_stream),
            velocity_hook=False, per_query_hashes=False, per_query_device_synchronize=False,
            load_seconds=time.perf_counter() - start)
        write(self.output / 'MODEL_READY.json', self.ready)

    def prepare(self, record):
        """Read an existing real five-frame context before timed work starts."""
        np, torch = self.np, self.torch
        from corrector.critic import STATE_KEYS
        with np.load(record['state_path'], allow_pickle=False) as saved:
            frames = saved['frames'].copy()
            props = saved['props'].astype(np.float32)
            raw = saved['raw'].astype(np.float32)
            observed = {key: saved['observed__' + key][0].copy() for key in STATE_KEYS}
            # Preserve the actual saved model-input action units. The archive's
            # prefix separately contains the raw pre-clamp executed commands.
            past = observed['past_actions'].astype(np.float32)
            current = dict(pixels=saved['pixels'].copy(), agent_pos=saved['agent_pos'].astype(np.float32))
        instruction = record['instruction']
        if instruction not in self.language_cache:
            self.language_cache[instruction] = observed['language'].copy()
        context = dict(source_id=record.get('source_id', record.get('parent_source_id')),
            frames=frames, props=props, past_actions=past, raw_plan=raw,
            raw_age=int(record.get('age', 5)), step=int(record.get('cut', 5)),
            currentobs=current, instruction=instruction,
            language=self.language_cache[instruction].copy(), observed=observed)
        return context

    def plan(self, ctx, seed):
        torch = self.torch
        with torch.cuda.device(self.device), torch.cuda.stream(self.plan_stream), torch.no_grad():
            generator = torch.Generator(device=self.device)
            generator.manual_seed(int(seed))
            noise = torch.randn((1, 50, 32), device=self.device, dtype=torch.float32,
                                generator=generator)
            batch = self.plan_features._policy_batch(ctx['currentobs'], ctx['instruction'])
            images, masks = self.policy._preprocess_images(batch)
            raw = self.model.sample_actions(images, masks,
                batch['observation.language.tokens'], batch['observation.language.attention_mask'],
                noise=noise, num_steps=10)
            actions = self.post(raw[:, :, :4].reshape(-1, 4)).reshape(50, 4)
            result = actions.float().cpu().numpy().copy()
            self.plan_stream.synchronize()
        return result

    def _heads(self, ctx, batch):
        torch, np = self.torch, self.np
        age = ctx['raw_age']
        old = np.clip(ctx['raw_plan'][age:age + 5], -1, 1).astype(np.float32)
        full = dict(batch, actions=torch.as_tensor(old, device=self.device)[None])
        values = []
        for world, gate in zip(self.worlds, self.gates):
            future, _ = world(full)
            values.append(gate(full, future))
        member_gates = torch.stack(values).reshape(-1).float().cpu().numpy()
        observed = {key: value[0].detach().cpu().numpy().copy() for key, value in batch.items()}
        return dict(gate=float(np.mean(member_gates)), member_gates=member_gates.tolist(), observed=observed)

    def monitor(self, ctx):
        torch, np = self.torch, self.np
        with torch.cuda.device(self.device), torch.cuda.stream(self.feedback_stream), torch.no_grad():
            features = self.feedback_features
            features._instruction = ctx['instruction']
            observations = [dict(pixels=frame, agent_pos=prop)
                            for frame, prop in zip(ctx['frames'], ctx['props'])]
            visual = features.encode_visual_batch(observations, batch_size=1)
            visual = torch.as_tensor(visual, device=self.device).float()
            spatial = self.spatial_tokens(self.canonical_decode(visual), self.projection).flatten(1)
            spatial_cpu = spatial.half().float().cpu().numpy()
            batch = self.cpu_batch(spatial_cpu, ctx['props'], ctx['past_actions'],
                                   ctx['language'], ctx['step'], device=self.device)
            result = self._heads(ctx, batch)
            self.feedback_stream.synchronize()
        return result

    def monitor_heads(self, ctx, observed):
        """Cached-visual-feature bound, explicitly omitting the image encoder."""
        torch = self.torch
        with torch.cuda.device(self.device), torch.cuda.stream(self.feedback_stream), torch.no_grad():
            batch = {key: torch.as_tensor(value, device=self.device)[None]
                     for key, value in observed.items()}
            result = self._heads(ctx, batch)
            self.feedback_stream.synchronize()
        return result

    def correct(self, ctx, raw, observed, with_gradient=True):
        """Original four-member action objective with no per-query audit hashes."""
        torch, np = self.torch, self.np
        from corrector.critic import STATE_KEYS
        arrays = {key: torch.as_tensor(observed[key], device='cpu')[None] for key in STATE_KEYS}
        anchor = torch.as_tensor(np.clip(raw[:10], -1, 1), dtype=torch.float32).clone()
        with torch.no_grad():
            features = [model.features(arrays).detach() for model in self.q_models]
        with torch.inference_mode(False), torch.set_grad_enabled(with_gradient):
            leaf = anchor.clone().requires_grad_(with_gradient)
            actions = torch.stack((anchor[None], leaf[None]), dim=1)
            probabilities = torch.stack([model(feature, actions).sigmoid()[0]
                for model, feature in zip(self.q_models, features)])
            objective = (probabilities[:, 1] - probabilities[:, 0]).mean()
            if not with_gradient:
                return np.asarray(raw, np.float32).copy()
            gradient = torch.autograd.grad(objective, leaf)[0].detach().numpy()
        direction = gradient * self.slopes[None] ** 2
        corrected, _, _ = self.project_solo(np.asarray(raw, np.float32), direction, self.matching)
        return corrected
