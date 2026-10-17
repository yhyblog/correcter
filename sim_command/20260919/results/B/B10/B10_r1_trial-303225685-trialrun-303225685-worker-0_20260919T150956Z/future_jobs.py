"""Prepared finite jobs. P00 never authorizes execution; explicit later release required."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import time

HERE=Path(__file__).resolve().parent
BASE=HERE.parents[2]

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()

def check_inputs(config):
    missing=[]
    for name,spec in config['inputs'].items():
        if spec is None or not spec.get('path') or not spec.get('sha256'):
            missing.append(name+': identity not frozen');continue
        if not Path(spec['path']).is_file():missing.append(name+': missing file');continue
        if sha(spec['path'])!=spec['sha256']:missing.append(name+': SHA mismatch')
    return missing

def authorize(config_path,release_path):
    config=json.loads(Path(config_path).read_text());control=json.loads((BASE/'CONTROL.json').read_text())
    if control['stop_requested'] or not control['formal_gpu_runs_enabled']:
        raise PermissionError('CONTROL has not released formal model/optimizer execution; P00 permits CPU preparation only')
    path=Path(release_path).resolve()
    if not path.is_relative_to((BASE/'releases').resolve()):raise PermissionError('Release must be analysis-owned campaign file')
    release=json.loads(path.read_text());board=json.loads((BASE/'TASK_BOARD.json').read_text())
    task=next((x for x in board['tasks'] if x['id']==release.get('task_id')),None)
    if not task or task['owner']!='B' or task['id'] not in control['allowed_task_ids']:raise PermissionError('Task not assigned/released to B')
    if task['release']!=str(path.relative_to(BASE)) or task['revision']!=release['task_revision']:raise PermissionError('Task/release identity mismatch')
    if release.get('campaign_id')!=control['campaign_id'] or release.get('hostname')!=socket.gethostname():raise PermissionError('Campaign/host mismatch')
    if release.get('kind')!='formal_compute' or release.get('participating_hosts')!=[socket.gethostname()]:raise PermissionError('This job wrapper supports an explicitly independent single-host wave only')
    job=release['jobs'][config['job_id']]
    if job['config_sha256']!=sha(config_path) or job['code_manifest_sha256']!=sha(HERE/'CODE_SNAPSHOT.json'):raise PermissionError('Code/config not frozen in release')
    code=json.loads((HERE/'CODE_SNAPSHOT.json').read_text())
    for entry in code['files']:
        if sha(HERE/entry['path'])!=entry['sha256']:raise PermissionError('Code snapshot changed: '+entry['path'])
    if job['limits']!=config['limits']:raise PermissionError('Per-job resource caps differ')
    if any(type(x) is not int or x<0 for x in config['limits'].values()):raise PermissionError('Caps must be explicit nonnegative integers')
    if config.get('updates',0)>config['limits']['optimizer_attempts']:raise PermissionError('Updates exceed cap')
    missing=check_inputs(config)
    if missing:raise PermissionError('Unready inputs: '+'; '.join(missing))
    release['_verified_path']=str(path);release['_verified_sha256']=sha(path)
    return config,release

def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module

def execute(config,release,output):
    import numpy as np
    import torch
    output=Path(output).resolve()
    if not output.is_relative_to((BASE/'results/B').resolve()):raise PermissionError('Output must belong to B')
    claim_dir=BASE/'results/B/compute_claims';claim_dir.mkdir(exist_ok=True)
    # A previously started job is never retried automatically with a new output path.
    claim=claim_dir/(release['release_id']+'__'+config['job_id']+'.json')
    with claim.open('x') as handle:json.dump({'hostname':socket.gethostname(),'pid':os.getpid(),'started_unix':time.time(),'output':str(output)},handle)
    output.mkdir(parents=True,exist_ok=False)
    counts={key:0 for key in config['limits']}
    start=time.monotonic();status='failed';error=None
    def save():
        value={'job_id':config['job_id'],'release_id':release['release_id'],'hostname':socket.gethostname(),'status':status,'counts':counts,'elapsed_wall_seconds':time.monotonic()-start,'error':error}
        temp=output/'status.tmp';temp.write_text(json.dumps(value,indent=2)+'\n');os.replace(temp,output/'status.json')
    def boundary():
        c=json.loads((BASE/'CONTROL.json').read_text())
        if c['stop_requested'] or not c['formal_gpu_runs_enabled'] or release['task_id'] not in c['allowed_task_ids']:raise RuntimeError('CONTROL stopped task at batch boundary')
        if sha(release['_verified_path'])!=release['_verified_sha256']:raise RuntimeError('Release changed at batch boundary')
        if time.monotonic()-start>config['timeout_seconds']:raise TimeoutError('Finite job timeout')
    def charge(key,amount=1):
        boundary()
        if key not in counts or counts[key]+amount>config['limits'][key]:raise RuntimeError('Resource cap reached before operation: '+key)
        counts[key]+=amount;save()
    def update(optimizer):
        if counts['optimizer_updates']>=config['limits']['optimizer_updates']:raise RuntimeError('Completed-update cap reached')
        charge('optimizer_attempts');optimizer.step()
        counts['optimizer_updates']+=1;save()
    save();torch.set_num_threads(2)
    try:
        if config['kind']=='lvm_gpu_probe':
            module=load_module('b10_frozen_lvm',HERE/'local_source_snapshot/siglip_dynamics_mlp.py')
            charge('model_initializations')
            predictor=module.SiglipDynamicsPredictor(Path(config['inputs']['model']['path']).parent,device='cuda:0')
            # Two synthetic technical forwards only; no VLA features or simulator are generated.
            for index in range(2):
                charge('model_gpu_inference_calls')
                prediction=predictor.predict_delta_z(np.zeros((256,2048),np.float32),np.zeros(4,np.float32))
                if prediction.shape!=(256,2048) or not np.isfinite(prediction).all():raise RuntimeError('LVM finite/shape check failed')
            torch.cuda.synchronize()
        elif config['kind']=='e1_fit':
            from b10_adapters import e1_loss
            module=load_module('b10_frozen_critic',HERE/'local_source_snapshot/corrector/critic.py')
            with np.load(config['inputs']['train_arrays']['path'],allow_pickle=False) as data:arrays={k:torch.from_numpy(data[k].copy()) for k in module.STATE_KEYS+['actions','outcomes','candidate_weights','gain_weights','pair_weights']}
            rows=json.loads(Path(config['inputs']['train_rows']['path']).read_text())
            if len(rows)!=600 or any(r['split']!='train' for r in rows):raise RuntimeError('Expected frozen 600 training parents')
            seed=config['train_seed']*100+config['member'];rng=np.random.default_rng(seed)
            bootstrap=[]
            for task in sorted({r['task'] for r in rows}):
                indices=[i for i,r in enumerate(rows) if r['task']==task];bootstrap.extend(rng.choice(indices,len(indices),replace=True).tolist())
            state=torch.load(config['inputs']['initial_model']['path'],map_location='cpu',weights_only=True)
            charge('model_initializations');model=module.from_state(state)
            if sum(p.numel() for p in model.parameters())!=7058:raise RuntimeError('E1 capacity drift')
            model.requires_grad_(False);model.residual.requires_grad_(True);model.advantage.requires_grad_(True)
            with torch.no_grad():features=torch.cat([model.features({k:arrays[k][i:i+1] for k in module.STATE_KEYS}) for i in range(len(rows))])
            optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=config['learning_rate'],weight_decay=.01)
            for step in range(config['updates']):
                charge('training_forward_calls');indices=rng.choice(bootstrap,16,replace=True);logits=model(features[indices],arrays['actions'][indices])
                loss=e1_loss(logits,arrays['outcomes'][indices],candidate_weights=arrays['candidate_weights'][indices],gain_weights=arrays['gain_weights'][indices],pair_weights=arrays['pair_weights'][indices],gain_enabled=config['gain_enabled'],pair_enabled=config['pair_enabled'])['loss']
                if not bool(torch.isfinite(loss)):raise RuntimeError('Nonfinite loss')
                optimizer.zero_grad(set_to_none=True);loss.backward();torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],1.)
                update(optimizer)
                if (step+1)%100==0:save()
            torch.save(model.state_dict(),output/'final.pt')
            (output/'training_lineage.json').write_text(json.dumps({'train_seed':config['train_seed'],'member':config['member'],'bootstrap':bootstrap,'loss':config['loss_id'],'updates':counts['optimizer_updates'],'initial_model':config['inputs']['initial_model'],'selection':'fixed final update; no test selection'},indent=2)+'\n')
        elif config['kind']=='gaf_fit':
            sys.path.insert(0,str(HERE/'upstream/guided-action-flow/src'))
            from guided_action_flow.critics.action_chunk_critic import ActionChunkCritic,ActionChunkCriticConfig
            train=torch.load(config['inputs']['train_view']['path'],map_location='cpu',weights_only=True)
            dev=torch.load(config['inputs']['development_view']['path'],map_location='cpu',weights_only=True)
            if train['split']!='train' or dev['split']!='development' or set(train['parent_ids'])&set(dev['parent_ids']):raise RuntimeError('Parent split invalid')
            if train.get('synthetic_only') is not False or dev.get('synthetic_only') is not False:raise RuntimeError('Synthetic or unknown-origin view cannot train')
            if train['feature_identities']!=dev['feature_identities']:raise RuntimeError('Feature/normalizer identity mismatch')
            if not 0<len(train['targets'])<=config['maximum_training_rows'] or not 0<len(dev['targets'])<=config['maximum_development_rows']:raise RuntimeError('View row count outside finite proposal; request revised release, never silently truncate')
            for view in [train,dev]:
                n=len(view['targets'])
                if view['obs_features'].shape!=(n,4) or view['action_chunks'].shape!=(n,10,4) or view['task_features'].shape!=(n,2048):raise RuntimeError('Frozen GAF feature shape mismatch')
                if any(not bool(torch.isfinite(view[k]).all()) for k in ['obs_features','action_chunks','task_features','targets']):raise RuntimeError('Nonfinite GAF view')
            charge('model_initializations');torch.manual_seed(config['seed']);critic=ActionChunkCritic(ActionChunkCriticConfig(obs_feature_dim=4,action_dim=4,action_horizon=10,task_feature_dim=2048,hidden_dim=768,depth=4));critic.module.cuda()
            optimizer=torch.optim.AdamW(critic.parameters(),lr=config['learning_rate'],weight_decay=config['weight_decay'])
            rng=np.random.default_rng(config['seed']);best=None
            for step in range(config['updates']):
                boundary();indices=rng.choice(len(train['targets']),config['batch_size'],replace=True)
                charge('training_forward_calls');pred=critic(obs_features=train['obs_features'][indices].cuda(),action_chunk=train['action_chunks'][indices].cuda(),task_features=train['task_features'][indices].cuda())
                loss=torch.nn.functional.mse_loss(pred,train['targets'][indices].cuda())
                if not bool(torch.isfinite(loss)):raise RuntimeError('Nonfinite GAF loss')
                optimizer.zero_grad(set_to_none=True);loss.backward();update(optimizer)
                if (step+1)%config['evaluation_interval']==0 or step+1==config['updates']:
                    critic.module.eval();total=0.;n=0
                    with torch.no_grad():
                        for i in range(0,len(dev['targets']),config['batch_size']):
                            charge('model_gpu_inference_calls');sl=slice(i,i+config['batch_size'])
                            p=critic(obs_features=dev['obs_features'][sl].cuda(),action_chunk=dev['action_chunks'][sl].cuda(),task_features=dev['task_features'][sl].cuda());total+=float(((p-dev['targets'][sl].cuda())**2).sum());n+=len(p)
                    if n==0:raise RuntimeError('Empty development view')
                    if best is None or total/n<best:
                        best=total/n;torch.save({'critic_config':critic.config.__dict__,'model_state_dict':{k:v.cpu() for k,v in critic.state_dict().items()},'selection':'development MSE','step':step+1,'seed':config['seed']},output/'selected.pt')
                    critic.module.train()
            torch.save({'critic_config':critic.config.__dict__,'model_state_dict':{k:v.cpu() for k,v in critic.state_dict().items()}},output/'final.pt')
        else:raise ValueError('Unsupported prepared job')
        status='complete'
    except Exception as exc:error=repr(exc);raise
    finally:save()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);parser.add_argument('--release');parser.add_argument('--output');parser.add_argument('--execute',action='store_true');parser.add_argument('--verify-release-only',action='store_true');args=parser.parse_args()
    if not args.execute and not args.verify_release_only:
        config=json.loads(Path(args.config).read_text());print(json.dumps({'job_id':config['job_id'],'execution_authorized':False,'unready_inputs':check_inputs(config),'limits_proposal':config['limits']}));return
    config,release=authorize(args.config,args.release)
    if args.verify_release_only:print('release verified');return
    if not args.output:raise ValueError('A unique output directory is required')
    execute(config,release,args.output)

if __name__=='__main__':main()
