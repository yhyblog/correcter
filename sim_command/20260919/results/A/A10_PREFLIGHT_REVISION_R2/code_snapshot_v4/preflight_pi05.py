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
from core.validation import validate, null_paths, ContractError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', required=True)
    parser.add_argument('--release', required=True)
    parser.add_argument('--proposal', required=True)
    parser.add_argument('--launch-directory', required=True)
    args = parser.parse_args()
    control, release, proposal = load_authorization(args.campaign, args.release, args.proposal)
    verify_device(release)
    if os.environ.get('CUDA_VISIBLE_DEVICES') != release['gpu_uuid']:
        raise ContractError('Use the released single-GPU launcher; explicit UUID isolation is required')
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
        print(json.dumps(claimed))
        return
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
        import numpy as np
        import torch
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
        backend = initialization.invoke('MetaWorldPi05Backend.__init__', {'model_initializations': 1}, lambda: call('audit_io', lambda: MetaWorldPi05Backend(
            vla_root=root / 'vendor_vla', checkpoint=proposal['checkpoint'], device='cuda:0',
            tokenizer_name=proposal['tokenizer_name'], tokenizer_revision=proposal['tokenizer_revision'],
            control_hz=30, native_action_scale=.015)))
        initialization.install_real(backend._env_class,
            json.loads(Path(proposal['external_source_manifest_path']).read_text()),
            root / 'vendor_vla/src/lerobot/envs/metaworld.py')
        torch.cuda.reset_peak_memory_stats()
        if backend.policy_config.num_inference_steps != 10:
            raise ContractError('PI0.5 flow count differs from the frozen ten steps')
        versions = [(p, p._version) for p in backend.policy.parameters()]
        with initialization.scope('diagnostic_reset'):
            observation = call('restore', lambda: backend.reset_episode(proposal['source']['task'], proposal['source']['env_seed']),
                               units={'simulator_attempts': 1})
        instruction = backend.task_instruction(proposal['source']['task'])
        if not np.asarray(observation['pixels']).any():
            raise ContractError('Invalid all-black initial frame')
        initial_path = destination / 'observation_step0.npz'
        np.savez_compressed(initial_path, pixels=observation['pixels'], proprioception=observation['agent_pos'])
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
                gate()
                backend.policy.config.n_action_steps = H
                backend.policy_config.n_action_steps = H
                backend.policy.reset()
                if backend.policy._action_queue.maxlen != H or backend.policy._queues['action'].maxlen != H:
                    raise ContractError('Actual queue capacity differs from requested H')
                before = journal.budget.used.copy()
                with torch.random.fork_rng(devices=[0]):
                    torch.manual_seed(proposal['source']['generation_seed'])
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
        with initialization.scope('policy_control'):
            result = call('env_step', lambda: backend.step(probe_plans[0][0]), units={'env_steps': 1})
        initialization.assert_complete()
        next_path = destination / 'observation_step1.npz'
        np.savez_compressed(next_path, pixels=result.observation['pixels'], proprioception=result.observation['agent_pos'])

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
        write('failure.json', {'error_type': type(failure).__name__, 'error': str(failure),
                               'automatic_retry': False, 'measurements_completed': measurements})
    finally:
        if backend is not None:
            try:
                backend.close()
            except BaseException as close_failure:
                write('close_failure.json', {'error': str(close_failure)})
                if error is None: error = close_failure
        if initialization is not None:
            initialization.uninstall()
            initialization_receipt = initialization.summary()
        else:
            initialization_receipt = {'status': 'not_entered', 'entered_budget_usage': dict.fromkeys(proposal['initialization_caps'], 0)}
        write('initialization_receipt.json', initialization_receipt)
        events = [json.loads(line) for line in journal.path.read_text().splitlines()]
        for row in events: validate(row, schema)
        ledger = summarize(events)
        write('resource_receipt.json', {**ledger, 'completed_rollouts': 0, 'optimizer_updates': 0,
            'initialization_accounting': initialization_receipt,
            'initialization_caps': proposal['initialization_caps'],
            'diagnostic_initial_states_returned': initialization_receipt.get('returned_operation_units', {}).get('diagnostic_reset_calls', 0),
            'elapsed_wall_seconds': time.monotonic() - started,
            'elapsed_wall_scope': 'after in-process authorization/hash/device checks through cleanup; full timed-process duration is in launcher receipt',
            'status': 'failed' if error is not None else 'complete', 'max_retries': 0})
    if error is not None:
        raise error
    store.complete([p for p in destination.iterdir() if p.is_file() and p.name != 'CLAIM.json'], ledger['counts'])
    print(json.dumps({'status': 'complete', 'run_directory': str(destination), 'counts': ledger['counts']}))


if __name__ == '__main__':
    main()
