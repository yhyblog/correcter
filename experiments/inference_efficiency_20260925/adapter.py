"""Private, frozen-L11 inference benchmark bridge (no training or rollout queue).

The native VLA and environment run in their original Python.  The accepted
PI05 feature encoder and the existing D/G0/Q checkpoints live in a separate
process.  Q remains on CPU exactly as in FrozenSelector/FrozenObjective.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
import contextlib
import importlib.util
import json
from multiprocessing.connection import Client, Listener
import os
from pathlib import Path
import random
import sys
import time
import traceback


WORKSPACE = Path(__file__).resolve().parents[3]
CORRECTOR = WORKSPACE / 'Corrector'
RESULTS = CORRECTOR / 'sim_command/20260919/results'
ACCEPTED = RESULTS / 'A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code'
MATCHING = dict(xyz_rms=.05, gripper_rms=.10, xyz_linf=.15, gripper_linf=.4,
                boundary_clearance=.05, tolerance=1e-6, zero_threshold=1e-10)


def _read(path):
    return json.loads(Path(path).read_text())


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False))
    temporary.replace(path)


def _paths(encoder=False):
    paths = [CORRECTOR, CORRECTOR / 'src', WORKSPACE / 'ACT-RECAP/src']
    if encoder:
        paths += [ACCEPTED, ACCEPTED / 'vendor_vla/src']
    for path in paths:
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


def _load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Meter:
    """Accepted numeric_setup's call accounting, with no legacy deadline hooks."""
    def __init__(self):
        self.entered = Counter()
        self.returned = Counter()

    def call(self, name, function, units):
        self.entered[name] += 1
        value = function()
        self.returned.update(units)
        return value


class NativeAdapter:
    """One resident native policy and one real cut context, batch size one.

    prepare_source accepts source_id, task (or alphabetical task_index),
    reset_seed, policy_seed, and optional constructor_seed/instruction.
    generate(None) advances native RNG; generate(int) uses an isolated seeded
    RNG scope, so R and Post can regenerate the same native fresh proposal.
    """
    def __init__(self, cfg):
        _paths()
        import numpy as np
        import torch
        from lerobot.envs.metaworld import MetaworldEnv
        from lerobot.policies.factory import get_policy_class, make_pre_post_processors
        from experiments.standalone_ablation_20260918.candidates import project_solo

        self.cfg, self.np, self.torch = cfg, np, torch
        self.kind = cfg.get('kind', cfg.get('model_kind'))
        if self.kind not in ('smolvla', 'xvla'):
            raise ValueError('Only frozen SmolVLA and X-VLA are benchmarked')
        self.device = 'cuda:0'
        torch.set_num_threads(int(cfg.get('torch_threads', 2)))
        torch.backends.cuda.matmul.allow_tf32 = True
        self.render = _load_file('_benchmark_render_context', RESULTS /
            'C/C_D24_CROSSBASE_H_SWEEP_V1/code/render_context.py')
        self.render.install(native_lifetime=True)
        self.env_class, self.project_solo = MetaworldEnv, project_solo
        self.env = self.connection = None
        self.source = self.obs = self.monitor_request = None
        start = time.perf_counter()
        checkpoint = Path(cfg['checkpoint'])
        self.policy = get_policy_class(self.kind).from_pretrained(
            checkpoint, local_files_only=True, strict=True)
        self.policy.config.n_action_steps = 10
        if self.kind == 'smolvla':
            self.policy.config.num_steps = 10
            if self.policy.config.adapt_to_pi_aloha or self.policy.model._rtc_enabled():
                raise ValueError('Smol coordinate/RTC configuration changed')
        else:
            self.policy.config.num_denoising_steps = 10
            if self.policy.config.action_mode != 'auto' or self.policy.model.action_space.real_dim != 4:
                raise ValueError('X native action coordinates changed')
        self.raw_horizon = 50 if self.kind == 'smolvla' else 30
        if (self.policy.config.chunk_size != self.raw_horizon or
            self.policy.config.n_obs_steps != 1 or
            tuple(self.policy.config.output_features['action'].shape) != (4,)):
            raise ValueError('Frozen native policy dimensions changed')
        self.policy.to(self.device).eval().requires_grad_(False)
        self.preprocessor, self.postprocessor = make_pre_post_processors(
            self.policy.config, pretrained_path=checkpoint)
        self.flow_calls = 0
        self.flow_handle = None
        # Counting only: do not introduce old VelocityBridge's per-step device
        # synchronizations or copy the flow states during a latency measurement.
        if self.kind == 'smolvla':
            original = self.policy.model.denoise_step
            def counted(*args, **kwargs):
                self.flow_calls += 1
                return original(*args, **kwargs)
            self.policy.model.denoise_step = counted
        else:
            def counted(module, args, kwargs, output):
                self.flow_calls += 1
            self.flow_handle = self.policy.model.transformer.register_forward_hook(
                counted, with_kwargs=True)
        self.generators = []
        for module_name, module in self.policy.named_modules():
            for name, value in vars(module).items():
                if isinstance(value, torch.Generator):
                    self.generators.append((module_name + '.' + name, value))
        self.native_slopes = None
        if self.kind == 'smolvla':
            with torch.inference_mode(False), torch.enable_grad():
                leaf = torch.zeros((10, 4), device=self.device, requires_grad=True)
                self.native_slopes = torch.autograd.grad(
                    self.postprocessor(leaf).sum(), leaf)[0].detach().cpu().numpy()
            if not np.isfinite(self.native_slopes).all() or np.any(self.native_slopes == 0):
                raise ValueError('Invalid saved native inverse-action transform')
        self.connection = Client(cfg['socket_path'], family='AF_UNIX',
                                 authkey=bytes.fromhex(cfg['ipc_auth']))
        torch.cuda.synchronize()
        _write(Path(cfg['output']) / 'NATIVE_MODEL_METADATA.json', dict(
            status='ready', pid=os.getpid(), kind=self.kind, device=self.device,
            checkpoint=str(checkpoint), raw_horizon=self.raw_horizon, NFE=10,
            parameters=sum(p.numel() for p in self.policy.parameters()),
            generator_attributes=[name for name, _ in self.generators],
            native_action_slopes=self.native_slopes[0].tolist() if self.native_slopes is not None else None,
            load_seconds=time.perf_counter() - start,
            allocated_bytes=int(torch.cuda.memory_allocated()),
            flow_counter='unmodified outputs; no per-step synchronization'))

    def _rpc(self, kind, **fields):
        start = time.perf_counter()
        self.connection.send(dict(kind=kind, **fields))
        if not self.connection.poll(float(self.cfg.get('rpc_timeout_seconds', 600))):
            raise TimeoutError('Benchmark encoder RPC timed out: ' + kind)
        reply = self.connection.recv()
        if not reply.pop('ok', False):
            raise RuntimeError('Benchmark encoder: ' + reply.get('error', 'unknown') + '\n' + reply.get('traceback', ''))
        reply['rpc_wall_seconds'] = time.perf_counter() - start
        return reply

    def _observation(self, obs):
        np = self.np
        frame, prop = np.asarray(obs['pixels']), np.asarray(obs['agent_pos'], np.float32)
        if (frame.shape != (480, 480, 3) or frame.dtype != np.uint8 or not frame.any()
                or prop.shape != (4,) or not np.isfinite(prop).all()):
            raise ValueError('Invalid real native observation')
        return dict(pixels=frame.copy(), agent_pos=prop.copy())

    def prepare_source(self, source, H=10, cut=5):
        if (H, cut) != (10, 5):
            raise ValueError('This finite benchmark fixes normal H10 and cut5')
        np, torch = self.np, self.torch
        if self.env is not None:
            self.render.close_environment(self.env)
            self.env = None
        self.source, self.monitor_request = dict(source), None
        task = source.get('task')
        if task is None:
            from lerobot.envs.metaworld import TASK_DESCRIPTIONS
            task = sorted(TASK_DESCRIPTIONS)[int(source['task_index'])]
        construction_seed = int(source.get('constructor_seed', source['reset_seed']))
        random.seed(construction_seed)
        np.random.seed(construction_seed)
        self.env = self.env_class(task=task, obs_type='pixels_agent_pos')
        seed = int(source['reset_seed'])
        random.seed(seed)
        np.random.seed(seed)
        self.env._env.seed(seed)
        self.obs, _ = self.env.reset(seed=seed)
        self.obs = self._observation(self.obs)
        self.policy.reset()
        torch.manual_seed(int(source['policy_seed']))
        torch.cuda.manual_seed(int(source['policy_seed']))
        for _, generator in self.generators:
            generator.manual_seed(int(source['policy_seed']))
        self.instruction = self.env.task_description
        if source.get('instruction', self.instruction) != self.instruction:
            raise ValueError('Manifest instruction differs from actual native task')
        physics = dict(timestep=float(self.env._env.model.opt.timestep),
                       frame_skip=int(self.env._env.frame_skip),
                       action_scale=float(self.env._env.action_scale))
        if abs(physics['timestep'] - .0025) > 1e-9 or physics['frame_skip'] != 5 or abs(physics['action_scale'] - .01) > 1e-9:
            raise ValueError('Frozen Mesa80Hz/.01 native physics changed')
        metadata = dict(source_id=source['source_id'], task=task, H=H, cut=cut,
                        physics=physics, instruction=self.instruction,
                        raw_horizon=self.raw_horizon, reset_seed=seed,
                        policy_seed=int(source['policy_seed']))
        frames = deque([self.obs], maxlen=5)
        actions = []
        old = self.generate(None)['raw_plan']
        for index in range(cut):
            action = old[index].copy()
            result = self.env.step(action)
            self.obs = self._observation(result[0])
            if not np.isfinite(float(result[1])) or getattr(self.env._env, '_did_see_sim_exception', False):
                raise RuntimeError('Nonfinite reward or native simulator exception')
            frames.append(self.obs)
            actions.append(np.clip(action, -1, 1).astype(np.float32))
            success = bool(result[4].get('success', result[4].get('is_success', False)))
            if result[2] or result[3] or success:
                return dict(metadata, eligible=False, terminal_before_cut=True,
                            actual_steps=index + 1, success=success)
        self._rpc('begin', source_id=source['source_id'], instruction=self.instruction)
        self.monitor_request = dict(source_id=source['source_id'], step=cut,
            observations=list(frames), props=[obs['agent_pos'] for obs in frames],
            past_actions=actions[-4:], next_five=old[cut:cut + 5].copy())
        return dict(metadata, eligible=True, terminal_before_cut=False, actual_steps=cut,
                    actual_history_frames=len(frames), past_actions=len(actions[-4:]))

    def generate(self, seed):
        np, torch = self.np, self.torch
        if self.obs is None:
            raise RuntimeError('prepare_source is required before native sampling')
        torch.cuda.synchronize()
        start = time.perf_counter()
        sample = {'observation.image': torch.from_numpy(np.ascontiguousarray(self.obs['pixels'])).permute(2, 0, 1).float() / 255,
                  'observation.state': torch.as_tensor(self.obs['agent_pos'], dtype=torch.float32),
                  'task': self.instruction}
        self.flow_calls = 0
        scope = torch.random.fork_rng(devices=[0]) if seed is not None else contextlib.nullcontext()
        generator_states = [(generator, generator.get_state()) for _, generator in self.generators] if seed is not None else []
        try:
            with scope:
                if seed is not None:
                    torch.manual_seed(int(seed))
                    torch.cuda.manual_seed(int(seed))
                    for _, generator in self.generators:
                        generator.manual_seed(int(seed))
                mode = torch.inference_mode() if self.kind == 'smolvla' else torch.no_grad()
                with mode, torch.autocast('cuda', dtype=torch.bfloat16):
                    native = self.policy.predict_action_chunk(self.preprocessor(sample))
                    if tuple(native.shape) != (1, self.raw_horizon, 4):
                        raise ValueError('Native full-plan sampling shape changed')
                    raw = np.stack([self.postprocessor(native[:, i]).reshape(-1).float().cpu().numpy()
                                    for i in range(self.raw_horizon)]).astype(np.float32)
        finally:
            for generator, state in generator_states:
                generator.set_state(state)
        torch.cuda.synchronize()
        seconds = time.perf_counter() - start
        if raw.shape != (self.raw_horizon, 4) or not np.isfinite(raw).all() or self.flow_calls != 10:
            raise ValueError('Invalid full native sample or NFE count')
        return dict(raw_plan=raw, policy_seconds=seconds, flow_calls=self.flow_calls)

    def monitor(self):
        if self.monitor_request is None:
            raise RuntimeError('No eligible cut context')
        # Every call re-encodes all five observations and recomputes both D/G0
        # members; the resulting context is retained solely for the Post query.
        result = self._rpc('monitor', **self.monitor_request)
        result['monitor_seconds'] = result['seconds']
        return result

    def post(self, raw_plan):
        np = self.np
        raw = np.asarray(raw_plan, np.float32)
        if raw.shape != (self.raw_horizon, 4) or not np.isfinite(raw).all():
            raise ValueError('Invalid native raw proposal')
        fields = dict(source_id=self.source['source_id'], step=5)
        anchor = self._rpc('objective', raw_plan=raw, **fields)
        reply = self._rpc('gradient', **fields)
        start = time.perf_counter()
        direction = (np.asarray(reply['gradient']) * self.native_slopes ** 2
                     if self.kind == 'smolvla' else np.asarray(reply['post_direction']))
        padded = raw if self.raw_horizon == 50 else np.concatenate([raw, np.repeat(raw[-1:], 20, axis=0)])
        corrected, matching, _ = self.project_solo(padded, direction, self.cfg.get('matching', MATCHING))
        corrected = corrected[:self.raw_horizon]
        projection_seconds = time.perf_counter() - start
        if corrected[10:].tobytes() != raw[10:].tobytes():
            raise ValueError('Post changed the native uncommitted tail')
        return dict(corrected=corrected, objective_seconds=anchor['objective_seconds'],
            gradient_seconds=reply['gradient_seconds'], projection_seconds=projection_seconds,
            rpc_wall_seconds=anchor['rpc_wall_seconds'] + reply['rpc_wall_seconds'],
            matching=matching, value=reply['value'], Q_device='cpu',
            Post_metric='native Smol S squared' if self.kind == 'smolvla' else 'frozen PI05 S squared')

    def close(self):
        if self.env is not None:
            self.render.close_environment(self.env)
            self.env = None
        if self.connection is not None:
            try:
                self._rpc('close')
            finally:
                self.connection.close()
                self.connection = None
        if self.flow_handle is not None:
            self.flow_handle.remove()


def run_encoder(cfg):
    _paths(encoder=True)
    import numpy as np
    import torch
    from numeric_setup import initialize
    from feature_path import canonical_decode, spatial_tokens, cpu_batch
    from ac_tmil.future_aware.models import WorldModel, BenefitModel
    from corrector.actions import ActionTransform
    from corrector.critic import FrozenSelector
    from corrector.guidance import FrozenObjective

    kind = cfg.get('kind', cfg.get('model_kind'))
    if kind not in ('smolvla', 'xvla'):
        raise ValueError('Unsupported native model')
    output = Path(cfg['output'])
    encoder_output = output / 'encoder'
    encoder_output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(int(cfg.get('torch_threads', 2)))
    torch.backends.cuda.matmul.allow_tf32 = True
    meter = _Meter()
    start = time.perf_counter()
    state = initialize(_read(cfg['base_config']), encoder_output, meter, 'cuda:0')
    features = state['features']
    artifact = Path(cfg['artifact_root'])
    norm = _read(artifact / 'dataset/NORMALIZATION.json')
    seeds = [(1241, 1341), (1242, 1342)] if kind == 'smolvla' else [(2241, 2341), (2242, 2342)]
    worlds, gates = [], []
    for ds, gs in seeds:
        world, gate = WorldModel(norm).cuda(), BenefitModel(norm).cuda()
        world.load_state_dict(torch.load(artifact / f'fits/D_{ds}/final.pt', map_location='cuda', weights_only=True))
        gate.load_state_dict(torch.load(artifact / f'fits/G0_{gs}/final.pt', map_location='cuda', weights_only=True))
        worlds.append(world.eval().requires_grad_(False))
        gates.append(gate.eval().requires_grad_(False))
    selector = FrozenSelector(cfg['q_assets'])
    counts = dict(D=[sum(p.numel() for p in m.parameters()) for m in worlds],
                  G0=[sum(p.numel() for p in m.parameters()) for m in gates],
                  Q=[sum(p.numel() for p in m.parameters()) for m in selector.models])
    if counts != dict(D=[4474116] * 2, G0=[1468033] * 2, Q=[7058] * 4):
        raise ValueError('Benchmark requires the already-trained L11 model sizes: ' + repr(counts))
    post_slopes = None
    if kind == 'xvla':
        transform = ActionTransform.from_checkpoint(state['cfg']['checkpoint'], device='cuda:0')
        post_slopes = ((transform.q99 - transform.q01) / 2).detach().cpu().numpy()
    torch.cuda.synchronize()
    listener = Listener(cfg['socket_path'], family='AF_UNIX', authkey=bytes.fromhex(cfg['ipc_auth']))
    ready = dict(status='ready', kind=kind, pid=os.getpid(), feature_device='cuda:0',
                 D_device='cuda:0', G0_device='cuda:0', Q_device='cpu', parameter_counts=counts,
                 q_assets=cfg['q_assets'], artifact_root=cfg['artifact_root'],
                 encoder_checkpoint=state['cfg']['checkpoint'],
                 load_seconds=time.perf_counter() - start, allocated_bytes=int(torch.cuda.memory_allocated()))
    _write(output / 'ENCODER_READY.json', ready)
    context = objective = source = language = step = None
    language_cache = {}
    counters = Counter()
    fatal = None

    def timed_gpu(function):
        torch.cuda.synchronize()
        begin = time.perf_counter()
        value = function()
        torch.cuda.synchronize()
        return value, time.perf_counter() - begin

    def encode(observations):
        if len(observations) != 5:
            raise ValueError('Exactly five actual cut observations required')
        for obs in observations:
            f, p = np.asarray(obs['pixels']), np.asarray(obs['agent_pos'])
            if f.shape != (480, 480, 3) or f.dtype != np.uint8 or not f.any() or p.shape != (4,) or not np.isfinite(p).all():
                raise ValueError('Invalid real encoder input')
        with torch.no_grad():
            raw = features.encode_visual_batch(observations, batch_size=1)
            raw = torch.as_tensor(raw, device='cuda').float()
            spatial = torch.cat([spatial_tokens(canonical_decode(row[None]), state['projection']).flatten(1) for row in raw], 0)
            result = spatial.half().cpu().numpy()
        if result.shape != (5, 4096) or not np.isfinite(result).all():
            raise ValueError('Invalid real feature history')
        return result

    try:
        with listener.accept() as connection:
            while True:
                req = connection.recv()
                begin = time.perf_counter()
                try:
                    op = req['kind']
                    if op == 'close':
                        selector.verify()
                        if meter.entered.get('denoise_step', 0):
                            raise ValueError('External feature encoder sampled an action')
                        connection.send(dict(ok=True, seconds=time.perf_counter() - begin))
                        break
                    if op == 'begin':
                        source, context, objective, step = req['source_id'], None, None, None
                        features._instruction = req['instruction']
                        if req['instruction'] not in language_cache:
                            language_cache[req['instruction']], language_seconds = timed_gpu(
                                lambda: features.encode_instruction(req['instruction']))
                        else:
                            language_seconds = 0.
                        language = language_cache[req['instruction']]
                        result = dict(language_seconds=language_seconds)
                    else:
                        if req['source_id'] != source or language is None:
                            raise ValueError('Cross-source or missing encoder context')
                        if op == 'monitor':
                            step = int(req['step'])
                            spatial, feature_seconds = timed_gpu(lambda: encode(req['observations']))
                            context, context_seconds = timed_gpu(lambda: cpu_batch(spatial.astype(np.float32),
                                np.asarray(req['props'], np.float32), np.asarray(req['past_actions'], np.float32),
                                language, step, device='cuda:0'))
                            commands = np.asarray(req['next_five'], np.float32)
                            if commands.shape != (5, 4) or not np.isfinite(commands).all():
                                raise ValueError('Invalid old five commands')
                            batch = dict(context, actions=torch.as_tensor(np.clip(commands, -1, 1), device='cuda')[None])
                            values, d_times, g_times = [], [], []
                            with torch.no_grad():
                                for world, gate in zip(worlds, gates):
                                    future_pair, duration = timed_gpu(lambda: world(batch))
                                    d_times.append(duration)
                                    value, duration = timed_gpu(lambda: gate(batch, future_pair[0]))
                                    g_times.append(duration)
                                    values.append(float(value))
                            if not np.isfinite(values).all():
                                raise ValueError('Nonfinite G0 outputs')
                            objective = None
                            counters.update(monitor_calls=1, feature_frames=5, D_calls=2, G0_calls=2)
                            result = dict(gate=float(np.mean(values)), member_gates=values,
                                feature_seconds=feature_seconds, context_seconds=context_seconds,
                                D_seconds=sum(d_times), G0_seconds=sum(g_times),
                                D_member_seconds=d_times, G0_member_seconds=g_times)
                        elif op == 'objective':
                            if context is None or req['step'] != step:
                                raise ValueError('Objective requires current monitor context')
                            raw = np.asarray(req['raw_plan'], np.float32)
                            expected = (50, 4) if kind == 'smolvla' else (30, 4)
                            if raw.shape != expected or not np.isfinite(raw).all():
                                raise ValueError('Invalid native objective anchor')
                            torch.cuda.synchronize()
                            objective_start = time.perf_counter()
                            if kind == 'xvla':
                                raw = np.concatenate([raw, np.repeat(raw[-1:], 20, axis=0)])
                            observed = {key: value[0].detach().cpu().numpy() for key, value in context.items()}
                            objective = FrozenObjective(observed, np.clip(raw, -1, 1).astype(np.float32), selector=selector)
                            torch.cuda.synchronize()
                            result = dict(objective_seconds=time.perf_counter() - objective_start)
                        elif op == 'gradient':
                            if objective is None or req['step'] != step:
                                raise ValueError('Gradient requires the fixed current anchor')
                            torch.cuda.synchronize()
                            gradient_start = time.perf_counter()
                            gradient, stats = objective.gradient()
                            objective.verify(check_hashes=False)
                            gradient = gradient.numpy()
                            torch.cuda.synchronize()
                            result = dict(gradient=gradient, value=float(stats['value']),
                                          gradient_seconds=time.perf_counter() - gradient_start)
                            if kind == 'xvla':
                                result['post_direction'] = gradient * post_slopes[None] ** 2
                            counters.update(action_gradients=1, Q_member_calls=4)
                        else:
                            raise ValueError('Unknown benchmark RPC ' + str(op))
                    connection.send(dict(ok=True, seconds=time.perf_counter() - begin, **result))
                except BaseException as error:
                    connection.send(dict(ok=False, error=repr(error), traceback=traceback.format_exc()))
                    raise
    except BaseException as error:
        fatal = dict(error=repr(error), traceback=traceback.format_exc())
        raise
    finally:
        listener.close()
        _write(output / 'ENCODER_RESULT.json', dict(status='failed' if fatal else 'complete',
            fatal=fatal, counters=dict(counters), ready=ready,
            external_action_sampling_calls=meter.entered.get('denoise_step', 0),
            peak_allocated_bytes=int(torch.cuda.max_memory_allocated())))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--role', required=True, choices=['encoder'])
    parser.add_argument('--config', required=True)
    arguments = parser.parse_args()
    run_encoder(_read(arguments.config))
