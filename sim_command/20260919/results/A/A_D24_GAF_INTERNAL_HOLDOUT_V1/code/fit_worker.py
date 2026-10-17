"""Frozen GAF numerical fit, with A authority and concise actual counters."""
import argparse,time,traceback,signal
from pathlib import Path
import paths
from paths import ROOT
from qio import read,new_json,atomic_json,utc,process_identity
from admission import authority,before_cutoff


def main():
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,required=True);p.add_argument('--slot',type=int,required=True);p.add_argument('--root',required=True);a=p.parse_args()
    out=Path(a.root);config=read(ROOT/f'config/member_{a.seed}.json');authority()
    start=time.monotonic();counts={k:0 for k in config['limits']};returned={k:0 for k in config['limits']}
    status='running';error=None;best=None;best_step=None;dev_history=[];stop=False
    def signal_stop(*_):
        nonlocal stop
        stop=True
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,signal_stop)
    def save():
        atomic_json(out/'status.json',dict(utc=utc(),status=status,seed=a.seed,slot=a.slot,process=process_identity(),
            counts=counts,returned=returned,elapsed_wall_seconds=time.monotonic()-start,error=error,
            selected_development_MSE=best,selected_step=best_step,development_history=dev_history))
    def enter(key):
        if stop or not before_cutoff() or time.monotonic()-start>config['timeout_seconds']:raise TimeoutError('fit stop/deadline')
        if counts[key]>=config['limits'][key]:raise RuntimeError('frozen cap reached: '+key)
        counts[key]+=1
    new_json(out/'STARTED.json',dict(utc=utc(),process=process_identity(),seed=a.seed,slot=a.slot));save()
    try:
        import numpy as np
        import torch
        from guided_action_flow.critics.action_chunk_critic import ActionChunkCritic,ActionChunkCriticConfig
        torch.set_num_threads(2);device=torch.device(f'cuda:{a.slot}');torch.cuda.set_device(device)
        # The fit's real device binding; not a separate hardware experiment.
        props=torch.cuda.get_device_properties(device);u=props.uuid
        cuuuid=getattr(torch._C,'_CUuuid',None)
        if type(u) is not str and (cuuuid is None or type(u) is not cuuuid):raise TypeError('unknown native Torch UUID ABI')
        canonical=u if type(u) is str else str(u)
        target=read(ROOT/'config/BASE.json')['device_list'][a.slot]['gpu_uuid'].removeprefix('GPU-')
        if canonical!=target:raise ValueError('fit UUID mismatch')
        new_json(out/'DEVICE.json',dict(utc=utc(),slot=a.slot,uuid=canonical,name=props.name,uuid_type=type(u).__qualname__,UUID_queries=1))
        enter('array_loads');train=torch.load(config['inputs']['train_view']['path'],map_location='cpu',weights_only=True);returned['array_loads']+=1
        enter('array_loads');dev=torch.load(config['inputs']['development_view']['path'],map_location='cpu',weights_only=True);returned['array_loads']+=1
        decision=read(ROOT/'config/HOLDOUT.json')
        if train['split']!='train' or dev['split']!='development' or set(train['parent_ids'])&set(dev['parent_ids']):raise ValueError('parent split invalid')
        if set(train['parent_ids'])!=set(decision['training_parents']) or set(dev['parent_ids'])!=set(decision['holdout_parents']):raise ValueError('fixed whole-parent membership missing')
        if train.get('synthetic_only') is not False or dev.get('synthetic_only') is not False or train['feature_identities']!=dev['feature_identities']:raise ValueError('genuine feature binding invalid')
        for v,cap in [(train,config['maximum_training_rows']),(dev,config['maximum_development_rows'])]:
            n=len(v['targets'])
            if not 0<n<=cap:raise ValueError('finite input row count')
            for k,shape in [('obs_features',(n,4)),('action_chunks',(n,10,4)),('task_features',(n,2048)),('targets',(n,))]:
                if v[k].shape!=shape or not torch.isfinite(v[k]).all():raise ValueError('invalid actual tensor '+k)
        enter('model_initializations');torch.manual_seed(config['seed'])
        critic=ActionChunkCritic(ActionChunkCriticConfig(obs_feature_dim=4,action_dim=4,action_horizon=10,task_feature_dim=2048,hidden_dim=768,depth=4))
        critic.module.to(device);returned['model_initializations']+=1
        optimizer=torch.optim.AdamW(critic.parameters(),lr=config['learning_rate'],weight_decay=config['weight_decay'])
        rng=np.random.default_rng(config['seed'])
        new_json(out/'MODEL_READY.json',dict(utc=utc(),model_parameters=sum(x.numel() for x in critic.parameters()),config=critic.config.__dict__,train_rows=len(train['targets']),development_rows=len(dev['targets']),device=str(device)))
        for step in range(config['updates']):
            if step%100==0:authority();save()
            indices=rng.choice(len(train['targets']),config['batch_size'],replace=True)
            enter('training_forward_calls')
            pred=critic(obs_features=train['obs_features'][indices].to(device),action_chunk=train['action_chunks'][indices].to(device),task_features=train['task_features'][indices].to(device))
            returned['training_forward_calls']+=1
            loss=torch.nn.functional.mse_loss(pred,train['targets'][indices].to(device))
            if not bool(torch.isfinite(loss)):raise RuntimeError('nonfinite GAF loss')
            optimizer.zero_grad(set_to_none=True);enter('backward_calls');loss.backward();returned['backward_calls']+=1
            if counts['optimizer_updates']>=config['limits']['optimizer_updates']:raise RuntimeError('completed-update cap reached')
            enter('optimizer_attempts');optimizer.step();returned['optimizer_attempts']+=1
            counts['optimizer_updates']+=1;returned['optimizer_updates']+=1
            if (step+1)%config['evaluation_interval']==0 or step+1==config['updates']:
                critic.module.eval();total=0.;n=0
                with torch.no_grad():
                    for i in range(0,len(dev['targets']),config['batch_size']):
                        enter('model_gpu_inference_calls');sl=slice(i,i+config['batch_size'])
                        pred=critic(obs_features=dev['obs_features'][sl].to(device),action_chunk=dev['action_chunks'][sl].to(device),task_features=dev['task_features'][sl].to(device))
                        returned['model_gpu_inference_calls']+=1
                        total+=float(((pred-dev['targets'][sl].to(device))**2).sum());n+=len(pred)
                if not n:raise ValueError('empty development view')
                mse=total/n
                if not np.isfinite(mse):raise ValueError('nonfinite development MSE')
                dev_history.append(dict(step=step+1,MSE=mse,rows=n))
                if best is None or mse<best:
                    best=mse;best_step=step+1
                    temp=out/'selected.tmp.pt'
                    torch.save(dict(critic_config=critic.config.__dict__,model_state_dict={k:v.cpu() for k,v in critic.state_dict().items()},selection='development MSE',step=best_step,seed=config['seed'],development_MSE=best),temp)
                    temp.replace(out/'selected.pt')
                critic.module.train();save()
        torch.save(dict(critic_config=critic.config.__dict__,model_state_dict={k:v.cpu() for k,v in critic.state_dict().items()}),out/'final.pt')
        status='complete'
    except BaseException as e:
        status='failed';error=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc())
    finally:
        save();new_json(out/'RESULT.json',read(out/'status.json'))
    return 0 if status=='complete' else 3

if __name__=='__main__':raise SystemExit(main())
