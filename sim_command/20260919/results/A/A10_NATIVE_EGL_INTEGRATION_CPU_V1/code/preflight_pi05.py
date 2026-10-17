"""PROPOSED finite real preflight. No heavy import before the new-release gate.

Two native instances, 51 initialization resets plus one diagnostic reset,
five same-observation native queue probes H10..50, one real action.
This is a diagnostic, not an evaluation episode or Post/Velocity validation.
"""
from pathlib import Path
from copy import deepcopy
import argparse
import hashlib
import json
import os
import platform
import time
from importlib.metadata import version

from core.release import load_authorization, check_current_authorization, verify_device
from core.resume import RunStore, sha
from core.accounting import EventJournal, ResourceBudget, summarize
from core.initialization import InitializationAudit
from core.observation_accounting import ObservationAccounting
from core.native_egl import NativeEGL
from core.wave_timing import held_reservation_fds
from core.validation import validate, null_paths, ContractError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', required=True)
    parser.add_argument('--release', required=True)
    parser.add_argument('--proposal', required=True)
    parser.add_argument('--launch-directory', required=True)
    args = parser.parse_args()
    control, release, proposal = load_authorization(args.campaign, args.release, args.proposal)
    if not held_reservation_fds():
        raise ContractError('Whole-host reservation required before any NVML/driver/model call')
    verify_device(release, proposal)
    claim_path = Path(args.campaign).resolve() / 'results/A/P10_native_release_claims' / (release['release_id'] + '.json')
    claim = json.loads(claim_path.read_text())
    if claim.get('release_sha256') != release['_sha256'] or claim.get('run_id') != release['run_id']:
        raise ContractError('Exclusive release claim missing or mismatched')
    for name, expected in proposal['runtime_packages'].items():
        if version(name) != expected:
            raise ContractError('Runtime package changed: ' + name)
    root = Path(__file__).resolve().parent
    output_root = Path(args.campaign).resolve() / 'results/A/P10_diagnostic_runs'
    identity = dict(campaign_id=control['campaign_id'], task_id=release['task_id'],
        task_revision=release['task_revision'], release_id=release['release_id'],
        code_sha256=release['code_manifest_sha256'], config_sha256=proposal['_sha256'],
        data_sha256=proposal['source_manifest_sha256'], model_sha256=proposal['model_sha256'],
        shard_sha256=proposal['source_manifest_sha256'], hostname=platform.node(), source_id=proposal['source']['source_id'],
        run_id=release['run_id'], shard_id=release['shard_id'], wave_id=release['wave_id'], gpu_uuid=release['gpu_uuid'])
    store = RunStore(output_root, identity)
    launch_directory = Path(args.launch_directory).resolve()
    if launch_directory != Path(args.campaign).resolve() / 'results/A/P10_launcher_runs' / release['run_id']:
        raise ContractError('Launch receipt destination differs from released run identity')
    with (launch_directory / 'diagnostic_link.json').open('x') as stream:
        stream.write(json.dumps({'path': str(store.path), 'identity': identity}) + '\n')
        stream.flush(); os.fsync(stream.fileno())
    claimed = store.claim()
    if claimed['status'] == 'reuse_complete':
        raise ContractError('A consumed diagnostic run cannot be reused')
    destination = store.path
    interface = Path(proposal['interface_directory'])
    examples = {r['record_type']: r for r in map(json.loads, (interface / 'examples.jsonl').read_text().splitlines())}
    schema = json.loads((interface / 'interface.schema.json').read_text())
    template = deepcopy(examples['event'])
    runtime_identity = {
        'campaign_id': control['campaign_id'], 'task_id': release['task_id'], 'run_id': release['run_id'],
        'node_role': 'A', 'hostname': platform.node(), 'wave_id': release['wave_id'],
        'shard_id': release['shard_id'], 'release_id': release['release_id'], 'driver': release['driver'],
        'runtime': release['runtime'], 'gpu_model': release['gpu_model'],
        'code_sha256': release['code_manifest_sha256'], 'config_sha256': proposal['_sha256'],
        'data_manifest_sha256': proposal['source_manifest_sha256'], 'model_sha256': proposal['model_sha256']}
    template.update(synthetic=False, identity=runtime_identity, episode_id=proposal['source']['source_id'])
    template['hardware'] = dict(gpu_index=release['gpu_index'], gpu_uuid=release['gpu_uuid'], worker_id='A-single',
        concurrency=1, precision='checkpoint-config; no autocast override', batch_size=1, warmup=False,
        clock_id=f"{platform.node()}:{os.getpid()}:{time.monotonic_ns()}")
    template['missing_reasons'] = {}
    journal = EventJournal(destination / 'events.jsonl', template, ResourceBudget(proposal['resource_caps']))
    backend = None
    error = None
    measurements = []
    started = time.monotonic()
    initialization = None
    graphics = None
    graphics_receipt = None
    current_stage = "pre_driver_mapping"
    failure_stage = None
    observation_accounting = ObservationAccounting(destination / 'observation_events.jsonl')

    def write(name, value):
        path = destination / name
        with path.open('x') as stream:
            stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n')
        return path

    def gate():
        check_current_authorization(args.campaign, args.release, release, proposal)
        if time.monotonic() - started >= proposal['timeout_seconds']:
            raise ContractError('Finite diagnostic timeout')

    # Heavy imports, CUDA initialization, model load and environment reset occur ONLY below this gate.
    try:
        gate()
        initialization = InitializationAudit(destination / 'initialization_events.jsonl', proposal['initialization_caps'], gate)
        graphics = NativeEGL(json.loads(Path(proposal['integration_config_path']).read_text()), destination, gate)
        graphics.prepare()  # Same-process handle->PCI/kernel UUID; private shim before heavy imports.
        current_stage = "heavy_imports_and_policy_device_binding"
        import numpy as np
        import torch
        policy_device = graphics.bind_policy(torch)
        import mujoco
        import gymnasium.envs.mujoco.mujoco_rendering as native_rendering
        graphics.install_native_hooks(mujoco, native_rendering)
        from vendor_backend.metaworld_pi05 import MetaWorldPi05Backend

        def call(event_type, function, *, units=None, parent=None, gpu=False, sampling_index=None):
            gate()
            event = journal.enter(event_type, methods=[], research_only=True, units=units, parent=parent,
                                  sampling_index=sampling_index)
            begin = end = None
            try:
                if gpu:
                    begin, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
                    begin.record()
                value = function()
                elapsed = None
                if gpu:
                    end.record(); end.synchronize()
                    elapsed = begin.elapsed_time(end) / 1000.
                journal.finish(event, device_elapsed=elapsed)
                return value
            except BaseException as failure:
                journal.finish(event, error=failure)
                raise

        # Persistent checkpoint, not the missing historical /tmp cache.
        current_stage = 'model_initialization'
        backend = initialization.invoke('MetaWorldPi05Backend.__init__', {'model_initializations': 1}, lambda: call('audit_io', lambda: MetaWorldPi05Backend(
            vla_root=root / 'vendor_vla', checkpoint=proposal['checkpoint'], device=policy_device,
            tokenizer_name=proposal['tokenizer_name'], tokenizer_revision=proposal['tokenizer_revision'],
            control_hz=30, native_action_scale=.015)))
        initialization.install_real(backend._env_class,
            json.loads(Path(proposal['initialization_source_manifest_path']).read_text()),
            root / 'vendor_vla/src/lerobot/envs/metaworld.py')
        torch.cuda.reset_peak_memory_stats()
        if backend.policy_config.num_inference_steps != 10:
            raise ContractError('PI0.5 flow count differs from the frozen ten steps')
        versions = [(p, p._version) for p in backend.policy.parameters()]
        current_stage = 'native_initialization_and_diagnostic_observation'
        with initialization.scope('diagnostic_reset'), graphics.observation_scope('diagnostic'):
            observation = call('restore', lambda: backend.reset_episode(proposal['source']['task'], proposal['source']['env_seed']),
                               units={'simulator_attempts': 1})
        observation_accounting.observation_returned('diagnostic')
        instruction = backend.task_instruction(proposal['source']['task'])
        def save_observation(phase, observation, npz_path):
            pixels = np.asarray(observation['pixels'])
            if pixels.shape != (480, 480, 3) or pixels.dtype != np.uint8 or not pixels.any() or pixels.min() == pixels.max():
                raise ContractError('Invalid native RGB shape/dtype/empty/constant buffer: ' + phase)
            np.savez_compressed(npz_path, pixels=pixels, proprioception=observation['agent_pos'])
            observation_accounting.artifact_written(phase, npz_path)
            with (destination / ('RGB_' + phase + '.ppm')).open('xb') as stream:
                stream.write(b'P6\n480 480\n255\n'); stream.write(pixels.tobytes())
            return {'phase': phase, 'camera': 'corner2', 'shape': [480,480,3], 'dtype': 'uint8',
                    'pixels_sha256': hashlib.sha256(pixels.tobytes()).hexdigest(),
                    'orientation': 'Gymnasium readback vertical flip, then frozen corner2 both-axis flip',
                    'visual_acceptance': 'requires inspection of saved frame against native scene; buffer statistics alone insufficient'}
        initial_path = destination / 'observation_step0.npz'
        rgb_metadata = [save_observation('diagnostic', observation, initial_path)]
        initial_state = np.concatenate([backend._env._env.data.qpos.copy(), backend._env._env.data.qvel.copy()])
        model = backend.policy.model
        original_sample, original_denoise, original_noise = model.sample_actions, model.denoise_step, model.sample_noise
        active_sample = None
        last_plan, last_noise = None, None
        sample_index = 0

        def noise_hook(*a, **kw):
            nonlocal last_noise
            tensor = original_noise(*a, **kw)
            last_noise = hashlib.sha256(tensor.detach().float().cpu().numpy().tobytes()).hexdigest()
            return tensor

        def denoise_hook(*a, **kw):
            return call('flow_forward', lambda: original_denoise(*a, **kw), units={'flow_forward_calls': 1},
                        parent=active_sample, gpu=True, sampling_index=sample_index)

        def sample_hook(*a, **kw):
            nonlocal active_sample, last_plan
            gate()
            active_sample = journal.enter('anchor_sample', methods=[], research_only=True,
                units={'vla_sampling_calls': 1}, sampling_index=sample_index)
            begin, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
            try:
                begin.record()
                sampled = original_sample(*a, **kw)
                end.record(); end.synchronize()
                journal.finish(active_sample, device_elapsed=begin.elapsed_time(end) / 1000.)
                raw = sampled[:, :, :4].detach().clone()
                commands = call('action_transform', lambda: backend.postprocessor(raw.reshape(-1, 4)).reshape(raw.shape))
                last_plan = commands.float().cpu().numpy()[0].copy()
                return sampled
            except BaseException as failure:
                if active_sample not in journal.finished:
                    journal.finish(active_sample, error=failure)
                raise
            finally:
                active_sample = None

        model.sample_actions, model.denoise_step, model.sample_noise = sample_hook, denoise_hook, noise_hook
        probe_plans = []
        try:
            for sample_index, H in enumerate(proposal['horizons']):
                current_stage = f'native_sampling_H{H}'
                gate()
                backend.policy.config.n_action_steps = H
                backend.policy_config.n_action_steps = H
                backend.policy.reset()
                if backend.policy._action_queue.maxlen != H or backend.policy._queues['action'].maxlen != H:
                    raise ContractError('Actual queue capacity differs from requested H')
                before = journal.budget.used.copy()
                with torch.random.fork_rng(devices=[graphics.policy_index]):
                    torch.random.default_generator.manual_seed(proposal['source']['generation_seed'])
                    torch.cuda.manual_seed(proposal['source']['generation_seed'])
                    first_action = backend.select_action(observation, instruction)
                if last_plan is None or last_plan.shape != (50, 4) or not np.isfinite(last_plan).all():
                    raise ContractError('Invalid generated raw50x4')
                if journal.budget.used['vla_sampling_calls'] - before['vla_sampling_calls'] != 1 or journal.budget.used['flow_forward_calls'] - before['flow_forward_calls'] != 10:
                    raise ContractError('Observed sampler/flow event counts differ from 1/10')
                np.testing.assert_allclose(first_action, last_plan[0], rtol=0, atol=1e-6)
                if len(backend.policy._action_queue) != H - 1 or last_noise is None:
                    raise ContractError('Queue consumption or actual noise capture failed')
                probe_plans.append(last_plan.copy())
                measurements.append({'H': H, 'queue_after_first_pop': len(backend.policy._action_queue),
                    'generated_length': len(last_plan), 'noise_sha256': last_noise,
                    'plan_sha256': hashlib.sha256(last_plan.tobytes()).hexdigest(), 'actual_flow_calls': 10})
        finally:
            model.sample_actions, model.denoise_step, model.sample_noise = original_sample, original_denoise, original_noise
        if len({m['noise_sha256'] for m in measurements}) != 1:
            raise ContractError('Queue-only probes did not retain the paired initial noise')
        # Same real observation; only queue capacity changed. Keep numeric drift if any as failure evidence.
        for plan in probe_plans[1:]:
            np.testing.assert_allclose(plan, probe_plans[0], rtol=0, atol=1e-6)
        plans_path = destination / 'raw_plans.npy'
        np.save(plans_path, np.stack(probe_plans), allow_pickle=False)
        current_stage = 'policy_step_and_post_control_observation'
        with initialization.scope('policy_control'), graphics.observation_scope('post_control'):
            result = call('env_step', lambda: backend.step(probe_plans[0][0]), units={'env_steps': 1})
        observation_accounting.observation_returned('post_control')
        initialization.assert_complete()
        next_path = destination / 'observation_step1.npz'
        rgb_metadata.append(save_observation('post_control', result.observation, next_path))
        write('RGB_provenance.json', {'frames': rgb_metadata, 'extra_render_for_views': 0})

        current_stage = 'transition_and_queue_validation'
        def ref(path, fmt): return {'path': str(path), 'sha256': sha(path), 'format': fmt}
        source = {'parent_episode_id': proposal['source']['source_id'], 'source_id': proposal['source']['source_id'],
                  'initial_state_id': hashlib.sha256(initial_state.tobytes()).hexdigest(),
                  'branch_id': 'diagnostic-native-H10-one-step', 'suffix_id': 'no-rollout-suffix'}
        transition = deepcopy(examples['transition'])
        transition.update(synthetic=False, identity=runtime_identity, dataset_revision='P10-diagnostic-only',
            split='development', environment={'name': 'metaworld', 'version': '3.0.0',
                'task': proposal['source']['task'], 'instruction': instruction}, source=source,
            collection_policy={'name': 'N', 'version': 'pi05-MT50-SFT030000-diagnostic',
                'checkpoint': {'path': str(Path(proposal['checkpoint']) / 'model.safetensors'),
                               'sha256': proposal['model_sha256'], 'format': 'safetensors'},
                'training_lineage_ref': ref(Path(proposal['lineage_path']), 'json')},
            seed=proposal['source']['env_seed'], step=0, H=10, generated_length=50, executed_prefix_length=1,
            observation_ref=ref(initial_path, 'npz:rgb_uint8+proprio'), proprioception=np.asarray(observation['agent_pos']).tolist(),
            next_observation_ref=ref(next_path, 'npz:rgb_uint8+proprio'), next_step=1,
            raw_actions=probe_plans[0][:1].tolist(), normalized_actions=None,
            normalizer_ref=ref(Path(proposal['checkpoint']) / 'policy_postprocessor.json', 'lerobot-processor-json'),
            generated_chunk_ref=ref(plans_path, 'npy:five_H_probes; first axis0=H10'), executed_actions_ref=None,
            rewards=[result.reward], successes=[result.success], first_success_step=1 if result.success else None,
            terminated=bool(result.audit_info['native_done']), truncated=bool(result.audit_info['native_truncated']),
            cut_reason='success' if result.success else 'diagnostic_stop_after_one_step',
            anchor_id=None, a0_ref=None, candidate_family='native', raw_alias_group=None,
            suffix_seed=proposal['source']['suffix_seed'], terminal_success=True if result.success else None,
            data_origin='new')
        transition['missing_reasons'] = {p: 'not applicable or no full episode outcome; one-step diagnostic only' for p in null_paths(transition)}
        validate(transition, schema)
        write('transition.json', transition)
        if any(p.requires_grad or p.grad is not None or p._version != v for p, v in versions):
            raise ContractError('Frozen base parameters changed')
        write('checks.json', {'status': 'passed', 'queue_probes': measurements,
            'peak_cuda_allocated_bytes': torch.cuda.max_memory_allocated(),
            'peak_cuda_reserved_bytes': torch.cuda.max_memory_reserved(),
            'Post_Velocity_numeric_validation': 'not covered by this native loader/queue diagnostic',
            'completed_rollouts': 0, 'actual_control_steps': 1, 'C10_recovery': 'covered separately by CPU scheduler checks'})
    except BaseException as failure:
        error = failure
        failure_stage = current_stage
        write('failure.json', {'error_type': type(failure).__name__, 'error': str(failure),
                               'automatic_retry': False, 'failure_stage': failure_stage, 'measurements_completed': measurements})
    finally:
        if backend is not None:
            try:
                backend.close()
            except BaseException as close_failure:
                write('close_failure.json', {'error': str(close_failure)})
                if error is None: error, failure_stage = close_failure, 'backend_graphics_cleanup'
        if graphics is not None:
            try:
                graphics_receipt = graphics.finish()
                if error is None and (graphics_receipt['entered_budget_usage'] != proposal['graphics_caps']
                        or graphics_receipt['failed'] or graphics_receipt['incomplete']):
                    raise ContractError('Actual native graphics counts differ from the frozen two-observation path')
            except BaseException as graphics_failure:
                write('graphics_finish_failure.json', {'error': str(graphics_failure)})
                if error is None: error, failure_stage = graphics_failure, 'graphics_finalization_or_count_validation'
        if initialization is not None:
            initialization.uninstall()
            initialization_receipt = initialization.summary()
        else:
            initialization_receipt = {'status': 'not_entered', 'entered_budget_usage': dict.fromkeys(proposal['initialization_caps'], 0)}
        write('initialization_receipt.json', initialization_receipt)
        expected_artifacts = ['observation_step0.npz', 'RGB_diagnostic.ppm', 'raw_plans.npy',
                              'observation_step1.npz', 'RGB_post_control.ppm', 'RGB_provenance.json',
                              'transition.json', 'checks.json']
        write('artifact_status.json', {'failure_stage': failure_stage,
            'artifacts': {name: {'present': (destination / name).is_file(),
                'missing_reason': None if (destination / name).is_file() else
                ('not produced before failure at ' + str(failure_stage) if error is not None else 'unexpected missing artifact')}
                for name in expected_artifacts}})
        events = [json.loads(line) for line in journal.path.read_text().splitlines()]
        for row in events: validate(row, schema)
        ledger = summarize(events)
        write('resource_receipt.json', {**ledger, 'completed_rollouts': 0, 'optimizer_updates': 0,
            'initialization_accounting': initialization_receipt,
            'graphics_accounting': graphics_receipt,
            'failure_stage': failure_stage,
            'initialization_caps': proposal['initialization_caps'],
            **observation_accounting.summary(initialization_receipt),
            'elapsed_wall_seconds': time.monotonic() - started,
            'elapsed_wall_scope': 'after in-process authorization/hash/device checks through cleanup; full timed-process duration is in launcher receipt',
            'status': 'failed' if error is not None else 'complete', 'max_retries': 0})
    if error is not None:
        raise error
    store.complete([p for p in destination.iterdir() if p.is_file() and p.name != 'CLAIM.json'], ledger['counts'])
    print(json.dumps({'status': 'complete', 'run_directory': str(destination), 'counts': ledger['counts']}))


if __name__ == '__main__':
    main()
