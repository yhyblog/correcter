"""Prepared fit worker; reachable only after stage_gate.authorize and exclusive claim.
Numerical E1 and GAF loops retained from frozen B10; no new training run here.
"""
import json,time,sys,importlib.util,os,socket
from pathlib import Path
import d24_common as stage_gate
HERE=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B_INDEPENDENT_PIPELINE_PREP_V1_r1/code')
sys.path.insert(0,str(HERE))
BASE=stage_gate.C
def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
def execute(config, release, output):
    output = Path(output).resolve()
    counts = {key: 0 for key in config['limits']}
    start = time.monotonic()
    status = 'failed'
    error = None

    def save():
        value = {'job_id': config['job_id'], 'release_id': release['release_id'], 'hostname': socket.gethostname(), 'status': status, 'counts': counts, 'elapsed_wall_seconds': time.monotonic() - start, 'error': error}
        temp = output / 'status.tmp'
        temp.write_text(json.dumps(value, indent=2) + '\n')
        os.replace(temp, output / 'status.json')

    def boundary():
        stage_gate.boundary(release)
        if time.monotonic() - start > config['timeout_seconds']:
            raise TimeoutError('Finite job timeout')

    def charge(key, amount=1):
        boundary()
        if key not in counts or counts[key] + amount > config['limits'][key]:
            raise RuntimeError('Resource cap reached before operation: ' + key)
        counts[key] += amount

    def update(optimizer):
        if counts['optimizer_updates'] >= config['limits']['optimizer_updates']:
            raise RuntimeError('Completed-update cap reached')
        charge('optimizer_attempts')
        optimizer.step()
        counts['optimizer_updates'] += 1
    save()
    try:
        import numpy as np
        import torch
        torch.set_num_threads(2)
        if config['kind'] == 'e1_fit':
            from b10_adapters import e1_loss
            module = load_module('b10_frozen_critic', HERE / 'local_source_snapshot/corrector/critic.py')
            charge('array_loads')
            with np.load(config['inputs']['train_arrays']['path'], allow_pickle=False) as data:
                arrays = {k: torch.from_numpy(data[k].copy()) for k in module.STATE_KEYS + ['actions', 'outcomes', 'candidate_weights', 'gain_weights', 'pair_weights']}
            rows = json.loads(Path(config['inputs']['train_rows']['path']).read_text())
            if len(rows) != 600 or any((r['split'] != 'train' for r in rows)):
                raise RuntimeError('Expected frozen 600 training parents')
            seed = config['train_seed'] * 100 + config['member']
            rng = np.random.default_rng(seed)
            bootstrap = []
            for task in sorted({r['task'] for r in rows}):
                indices = [i for i, r in enumerate(rows) if r['task'] == task]
                bootstrap.extend(rng.choice(indices, len(indices), replace=True).tolist())
            charge('checkpoint_loads')
            state = torch.load(config['inputs']['initial_model']['path'], map_location='cpu', weights_only=True)
            charge('model_initializations')
            model = module.from_state(state)
            if sum((p.numel() for p in model.parameters())) != 7058:
                raise RuntimeError('E1 capacity drift')
            model.requires_grad_(False)
            model.residual.requires_grad_(True)
            model.advantage.requires_grad_(True)
            charge('feature_transform_calls', len(rows))
            with torch.no_grad():
                features = torch.cat([model.features({k: arrays[k][i:i + 1] for k in module.STATE_KEYS}) for i in range(len(rows))])
            optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=config['learning_rate'], weight_decay=0.01)
            for step in range(config['updates']):
                charge('training_forward_calls')
                indices = rng.choice(bootstrap, 16, replace=True)
                logits = model(features[indices], arrays['actions'][indices])
                loss = e1_loss(logits, arrays['outcomes'][indices], candidate_weights=arrays['candidate_weights'][indices], gain_weights=arrays['gain_weights'][indices], pair_weights=arrays['pair_weights'][indices], gain_enabled=config['gain_enabled'], pair_enabled=config['pair_enabled'])['loss']
                if not bool(torch.isfinite(loss)):
                    raise RuntimeError('Nonfinite loss')
                optimizer.zero_grad(set_to_none=True)
                charge('backward_calls')
                loss.backward()
                torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
                update(optimizer)
                if (step + 1) % 100 == 0:
                    save()
            torch.save(model.state_dict(), output / 'final.pt')
            (output / 'training_lineage.json').write_text(json.dumps({'train_seed': config['train_seed'], 'member': config['member'], 'bootstrap': bootstrap, 'loss': config['loss_id'], 'updates': counts['optimizer_updates'], 'initial_model': config['inputs']['initial_model'], 'selection': 'fixed final update; no test selection'}, indent=2) + '\n')
        elif config['kind'] == 'gaf_fit':
            sys.path.insert(0, '/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B10_r1_trial-303225685-trialrun-303225685-worker-0_20260919T150956Z/upstream/guided-action-flow/src')
            from guided_action_flow.critics.action_chunk_critic import ActionChunkCritic, ActionChunkCriticConfig
            charge('array_loads', 2)
            train = torch.load(config['inputs']['train_view']['path'], map_location='cpu', weights_only=True)
            dev = torch.load(config['inputs']['development_view']['path'], map_location='cpu', weights_only=True)
            if train['split'] != 'train' or dev['split'] != 'development' or set(train['parent_ids']) & set(dev['parent_ids']):
                raise RuntimeError('Parent split invalid')
            if train.get('synthetic_only') is not False or dev.get('synthetic_only') is not False:
                raise RuntimeError('Synthetic or unknown-origin view cannot train')
            if train['feature_identities'] != dev['feature_identities']:
                raise RuntimeError('Feature/normalizer identity mismatch')
            if not 0 < len(train['targets']) <= config['maximum_training_rows'] or not 0 < len(dev['targets']) <= config['maximum_development_rows']:
                raise RuntimeError('View row count outside finite proposal; request revised release, never silently truncate')
            for view in [train, dev]:
                n = len(view['targets'])
                if view['obs_features'].shape != (n, 4) or view['action_chunks'].shape != (n, 10, 4) or view['task_features'].shape != (n, 2048):
                    raise RuntimeError('Frozen GAF feature shape mismatch')
                if any((not bool(torch.isfinite(view[k]).all()) for k in ['obs_features', 'action_chunks', 'task_features', 'targets'])):
                    raise RuntimeError('Nonfinite GAF view')
            charge('model_initializations')
            torch.manual_seed(config['seed'])
            critic = ActionChunkCritic(ActionChunkCriticConfig(obs_feature_dim=4, action_dim=4, action_horizon=10, task_feature_dim=2048, hidden_dim=768, depth=4))
            critic.module.cuda()
            optimizer = torch.optim.AdamW(critic.parameters(), lr=config['learning_rate'], weight_decay=config['weight_decay'])
            rng = np.random.default_rng(config['seed'])
            best = None
            for step in range(config['updates']):
                boundary()
                indices = rng.choice(len(train['targets']), config['batch_size'], replace=True)
                charge('training_forward_calls')
                pred = critic(obs_features=train['obs_features'][indices].cuda(), action_chunk=train['action_chunks'][indices].cuda(), task_features=train['task_features'][indices].cuda())
                loss = torch.nn.functional.mse_loss(pred, train['targets'][indices].cuda())
                if not bool(torch.isfinite(loss)):
                    raise RuntimeError('Nonfinite GAF loss')
                optimizer.zero_grad(set_to_none=True)
                charge('backward_calls')
                loss.backward()
                update(optimizer)
                if (step + 1) % config['evaluation_interval'] == 0 or step + 1 == config['updates']:
                    critic.module.eval()
                    total = 0.0
                    n = 0
                    with torch.no_grad():
                        for i in range(0, len(dev['targets']), config['batch_size']):
                            charge('model_gpu_inference_calls')
                            sl = slice(i, i + config['batch_size'])
                            p = critic(obs_features=dev['obs_features'][sl].cuda(), action_chunk=dev['action_chunks'][sl].cuda(), task_features=dev['task_features'][sl].cuda())
                            total += float(((p - dev['targets'][sl].cuda()) ** 2).sum())
                            n += len(p)
                    if n == 0:
                        raise RuntimeError('Empty development view')
                    if best is None or total / n < best:
                        best = total / n
                        torch.save({'critic_config': critic.config.__dict__, 'model_state_dict': {k: v.cpu() for k, v in critic.state_dict().items()}, 'selection': 'development MSE', 'step': step + 1, 'seed': config['seed']}, output / 'selected.pt')
                    critic.module.train()
            torch.save({'critic_config': critic.config.__dict__, 'model_state_dict': {k: v.cpu() for k, v in critic.state_dict().items()}}, output / 'final.pt')
        else:
            raise ValueError('Unsupported prepared job')
        status = 'complete'
    except Exception as exc:
        error = repr(exc)
        raise
    finally:
        save()

if __name__ == "__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--config",required=True);a=p.parse_args()
    config=json.loads(Path(a.config).read_text());stage_gate.authorize()
    output=Path(config["output"]);output.mkdir(parents=True,exist_ok=True)
    execute(config,{"release_id":"D24_SPRINT_V1"},output)
