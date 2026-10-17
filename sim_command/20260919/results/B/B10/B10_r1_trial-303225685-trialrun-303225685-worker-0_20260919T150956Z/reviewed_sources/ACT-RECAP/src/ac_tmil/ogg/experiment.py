"""Causal source capture and paired real-simulator OGG interventions."""
from __future__ import annotations
import argparse,json,time
from collections import deque
from pathlib import Path
import numpy as np
import torch
from ac_tmil.future_aware.common import verify_config
from ac_tmil.future_aware.features import FrozenFeatures
from ac_tmil.future_aware.runtime import DeferredRenderRuntime
from ac_tmil.future_aware.critic import load_world
from ac_tmil.future_aware.models import BenefitModel
from ac_tmil.future_aware.controller import ActionQueue
from ac_tmil.idea3.local_collection import Trace,seal
from ac_tmil.idea3.contracts import file_sha256
from .common import ROOT,BASE,config,dump,save_arrays,seed_for,digest,cpu_batch
from .core import ActionTransform,Reference,DenoiseHook,GuidanceError,visual_objective


class Engine:
    def __init__(self,root=ROOT,with_c=False):
        self.root=Path(root);self.cfg=config(root);base=verify_config(BASE)
        self.runtime=DeferredRenderRuntime(base['vla_root'],base['checkpoint'])
        self.features=FrozenFeatures(BASE);self.worlds={};self.gates={};self.identities={};self.critics={}
        self.transform=ActionTransform.from_checkpoint(base['checkpoint'])
        self.hook=DenoiseHook(self.runtime.backend.policy.model,self.transform,self.cfg['guidance'])
        self.feature_id=file_sha256(BASE/'projection.npy')
        for w,g in [(241,341),(242,342)]:
            world,norm=load_world(BASE,w);self.worlds[w]=world.eval().requires_grad_(False)
            meta=json.loads((BASE/f'models/spatial_pair_{w}/complete.json').read_text())
            self.identities[w]=meta['checkpoint_sha256']
            path=BASE/f'critics/gate_{g}/selected.pt';model=BenefitModel(norm).cuda()
            model.load_state_dict(torch.load(path,map_location='cuda:0',weights_only=True))
            self.gates[w]=model.eval().requires_grad_(False)
        if with_c:
            from .temporal import TemporalCritic
            for seed in [451,452]:
                folder=self.root/f'critics/pred_{seed}';meta=json.loads((folder/'complete.json').read_text())
                path=Path(meta['selected']['path'])
                if file_sha256(path)!=meta['checkpoint_sha256']:raise ValueError('C checkpoint changed')
                norm=json.loads((BASE/'models/spatial_pair_241/normalization.json').read_text())
                model=TemporalCritic(norm,self.cfg['c']).cuda();model.load_state_dict(torch.load(path,map_location='cuda:0',weights_only=True))
                self.critics[seed]=model.eval().requires_grad_(False)
        self.versions=[(p,p._version) for m in list(self.worlds.values())+list(self.gates.values())+list(self.critics.values()) for p in m.parameters()]

    def close(self):
        self.hook.close();self.runtime.close()

    def verify(self):
        self.runtime.verify_frozen()
        if any(p.requires_grad or p.grad is not None or p._version!=v for p,v in self.versions):raise ValueError('frozen auxiliary model changed')

    def propose(self,seed,loss=None):
        runtime=self.runtime;runtime.clear_policy(50);before=runtime.fingerprint()
        self.hook.begin(loss);torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats()
        allocated_start=torch.cuda.memory_allocated();begin=time.perf_counter();fallback=None;attempts=1;failed_forwards=failed_backwards=0
        try:_,plan,_=runtime.native_action(seed)
        except GuidanceError as error:
            fallback=str(error);logs=list(self.hook.logs)
            failed_forwards=self.hook.objective_calls;failed_backwards=self.hook.failed_backward_calls
            self.hook.begin(None);runtime.clear_policy(50)
            _,plan,_=runtime.native_action(seed);attempts=2
        else:logs=list(self.hook.logs)
        torch.cuda.synchronize();seconds=time.perf_counter()-begin;times=list(self.hook.times)
        objective_calls=failed_forwards+self.hook.objective_calls
        self.hook.begin(None)
        if len(times)!=10 or not np.allclose(times,np.arange(10,0,-1)/10,atol=1e-6):raise ValueError('unexpected flow schedule')
        if runtime.fingerprint()!=before:raise ValueError('proposal changed environment')
        return plan,dict(seconds=seconds,policy_calls=attempts,fallback=fallback,updates=logs,times=times,
            peak_cuda_allocated_mib=torch.cuda.max_memory_allocated()/2**20,
            peak_cuda_reserved_mib=torch.cuda.max_memory_reserved()/2**20,
            incremental_peak_cuda_allocated_mib=(torch.cuda.max_memory_allocated()-allocated_start)/2**20,
            objective_forward_calls=objective_calls,backward_calls=failed_backwards+sum(x['backward_calls'] for x in logs))

    @torch.no_grad()
    def context(self,frames,proprio,past,language,step):
        raw=self.runtime.backend.encode_visual_batch([dict(pixels=f,agent_pos=p) for f,p in zip(frames,proprio)],batch_size=1)
        spatial,_=self.features.convert(raw,language)
        return cpu_batch(spatial,proprio,past,language,step)

    def capture(self,case,mode):
        dest=self.root/'sources'/mode/case['case_id']
        if (dest/'complete.json').exists():return dest
        if dest.exists():
            archive=self.root/'incomplete'/f"source_{case['case_id']}_{time.time_ns()}";archive.parent.mkdir(parents=True,exist_ok=True);dest.rename(archive)
        dest.mkdir(parents=True);runtime=self.runtime;runtime.reset(case,50);trace=Trace(runtime);queue=ActionQueue()
        frames=deque(maxlen=5);props=deque(maxlen=5);references={};events=[];cuts=[]
        language=runtime.backend.encode_instruction(runtime.instruction);cost=dict(policy_seconds=0.,policy_calls=0,monitor_seconds=0.,feature_seconds=0.)
        while not trace.terminal and trace.step<300:
            t=trace.step;frames.append(runtime.frame().copy());props.append(runtime.proprio().copy())
            if not len(queue.remaining()) or queue.age>=case['source_horizon']:
                proposal_seed=seed_for('ogg_source',case['env_seed'],t)
                plan,stats=self.propose(proposal_seed);queue.replace(plan)
                cost['policy_seconds']+=stats['seconds'];cost['policy_calls']+=stats['policy_calls']
                trace.plans.append(plan);trace.generated.append(t)
                trace.seeds.append(proposal_seed);trace.sampling_steps.append(t)
                trace.policy_calls+=stats['policy_calls'];trace.policy_seconds+=stats['seconds']
            if t%5==0:
                tick=time.perf_counter();batch=self.context(frames,list(props),trace.actions[-4:],language,t)
                cost['feature_seconds']+=time.perf_counter()-tick
                commands=queue.next_block();batch['actions']=torch.as_tensor(commands,device='cuda:0')[None]
                tick=time.perf_counter();predictions={};benefits=[];mature={};errors={};reasons={}
                with torch.no_grad():
                    for seed,world in self.worlds.items():
                        future,_=world(batch);benefits.append(float(self.gates[seed](batch,future)))
                        predictions[seed]=future[0].cpu().numpy()
                        ref=references.get(seed);reason='missing_reference' if ref is None else ref.validate(t,queue.plan_id,np.asarray(trace.actions[-5:]),self.feature_id,self.identities[seed])
                        error=None if reason else float(np.mean(((ref.predicted[-1]-batch['history'][0,-1].cpu().numpy())/world.delta_scale.cpu().numpy())**2))
                        errors[seed]=error;reasons[seed]=reason
                        if reason is None:mature[seed]=ref
                cost['monitor_seconds']+=time.perf_counter()-tick
                gate=float(np.mean(benefits));trigger=bool(gate>self.cfg['gate_threshold'] and queue.age>0 and t+5<=300)
                events.append(dict(step=t,plan_id=queue.plan_id,plan_age=queue.age,gate=gate,trigger=trigger,errors=errors,reference_reasons=reasons))
                wanted=t in case['cut_steps'] if mode=='local' else trigger
                if wanted:
                    cut=dest/f'cut{t:03d}';cut.mkdir();cuts.append(t)
                    values={k:v[0].cpu().numpy() for k,v in batch.items()}
                    save_arrays(cut/'context.npz',**values,full_plan=queue.plan)
                    refs={}
                    for seed in self.worlds:
                        ref=mature.get(seed);refs[str(seed)]=dict(valid=ref is not None,reason=reasons[seed],error=errors[seed],eligible=ref is not None and errors[seed]>self.cfg['reference_threshold'])
                        if ref:
                            refs[str(seed)].update(ref.metadata())
                            save_arrays(cut/f'reference_{seed}.npz',predicted_visual_1to5=ref.predicted,reference_start_visual=ref.start_visual)
                    dump(cut/'anchor.json',dict(source_id=case['case_id'],task=case['task'],step=t,plan_id=queue.plan_id,plan_age=queue.age,
                        image_sha256=digest(runtime.frame()),world_fingerprint=runtime.fingerprint(),gate=gate,trigger=trigger,
                        references=refs,common_prefix_cost=dict(cost)))
                    if mode=='single':break
                for seed in self.worlds:
                    references[seed]=Reference(case['case_id'],t,t+5,queue.plan_id,np.clip(commands,-1,1),predictions[seed],
                        batch['history'][0,-1].cpu().numpy(),self.feature_id,self.identities[seed])
            action=queue.consume();trace.execute(runtime,action)
        save_arrays(dest/'trajectory.npz',**trace.arrays())
        dump(dest/'summary.json',dict(status='complete',case=case,mode=mode,cuts=cuts,events=events,cost=cost,
            success=any(trace.successes),steps=trace.step,no_alarm=mode=='single' and not cuts,
            not_reached=sorted(set(case['cut_steps'])-set(cuts))))
        files=[str(p.relative_to(dest)) for p in dest.rglob('*') if p.is_file()]
        seal(dest,files,config_sha256=file_sha256(self.root/'config.json'));self.verify();return dest

    def restore(self,case,source,step):
        with np.load(source/'trajectory.npz') as z:original={k:z[k] for k in z.files}
        runtime=self.runtime;runtime.reset(case,50);trace=Trace(runtime)
        for t in range(step+1):
            np.testing.assert_allclose(runtime.physics_state(),original['physics_states'][t],atol=1e-10,rtol=0)
            if t==step:break
            trace.execute(runtime,original['actions'][t])
            if trace.terminal:raise ValueError('restored prefix terminated before intervention')
        anchor=json.loads((source/f'cut{step:03d}/anchor.json').read_text())
        if digest(runtime.frame())!=anchor['image_sha256'] or runtime.fingerprint()!=anchor['world_fingerprint']:raise ValueError('source replay image/world mismatch')
        return trace,anchor

    def load_context(self,cut):
        with np.load(cut/'context.npz') as z:
            values={k:torch.as_tensor(z[k],device='cuda:0')[None] for k in z.files if k!='full_plan'}
            full=z['full_plan'].copy()
        return values,full

    def candidate(self,case,source,step,method):
        cut=source/f'cut{step:03d}';trace,anchor=self.restore(case,source,step);batch,full=self.load_context(cut)
        seed=seed_for('ogg_candidate',case['env_seed'],step);reason=None;objective=None;world_seed=None
        if method=='old':
            plan=np.concatenate([full[anchor['plan_age']:],np.repeat(full[-1:],anchor['plan_age'],axis=0)])
            stats=dict(seconds=0.,policy_calls=0,updates=[],fallback=None,objective_forward_calls=0,backward_calls=0)
        else:
            if method.startswith('d_only'):
                world_seed=int(method.rsplit('_',1)[1]);ref=anchor['references'][str(world_seed)]
                if not ref['eligible']:reason=ref['reason'] or 'small_reference_residual'
                else:
                    with np.load(cut/f'reference_{world_seed}.npz') as z:target=torch.as_tensor(z['predicted_visual_1to5'][-1],device='cuda:0')[None]
                    objective=visual_objective(self.worlds[world_seed],batch,target)
            elif method.startswith('dc_'):
                critic_seed=int(method.rsplit('_',1)[1]);world_seed=241+int(critic_seed==452)
                def objective(commands):
                    future,prop=self.worlds[world_seed](dict(batch,actions=commands))
                    return torch.nn.functional.softplus(-self.critics[critic_seed](batch,future,prop)).mean()
            plan,stats=self.propose(seed,objective)
        predicted={};predicted_success={}
        with torch.no_grad():
            for w,world in self.worlds.items():
                ref=anchor['references'][str(w)]
                if ref['valid']:
                    with np.load(cut/f'reference_{w}.npz') as z:target=torch.as_tensor(z['predicted_visual_1to5'][-1],device='cuda:0')
                    future,_=world(dict(batch,actions=torch.as_tensor(plan[:5],device='cuda:0')[None]))
                    predicted[str(w)]=float(((future[0,-1]-target)/world.delta_scale).square().mean())
            for critic_seed,critic in self.critics.items():
                w=241+int(critic_seed==452)
                z,p=self.worlds[w](dict(batch,actions=torch.as_tensor(plan[:5],device='cuda:0')[None]))
                predicted_success[str(critic_seed)]=float(critic(batch,z,p).sigmoid())
        return plan,dict(method=method,seed=seed,reference_ineligible_reason=reason,predicted_match=predicted,
                         predicted_success=predicted_success,diagnostic_score_forward_pairs=len(predicted_success),
                         guidance_requested=objective is not None,world_seed=world_seed,**stats)

    def branch(self,case,source,step,method,plan,replicate,dest):
        trace,anchor=self.restore(case,source,step);runtime=self.runtime;start=time.perf_counter();segment=[]
        for command in plan[:5]:
            if trace.terminal:break
            trace.execute(runtime,command);segment.append(runtime.proprio().copy())
        length=trace.step-step;matches={}
        batch,_=self.load_context(source/f'cut{step:03d}')
        with torch.no_grad():
            raw=runtime.backend.encode_visual_batch([dict(pixels=runtime.frame(),agent_pos=runtime.proprio())],batch_size=1)
            spatial,_=self.features.convert(raw,batch['language'][0].cpu().numpy())
        for w,world in self.worlds.items():
            if anchor['references'][str(w)]['valid'] and length==5:
                with np.load(source/f'cut{step:03d}/reference_{w}.npz') as z:target=z['predicted_visual_1to5'][-1]
                matches[str(w)]=float(np.mean(((spatial[0]-target)/world.delta_scale.cpu().numpy())**2))
        runtime.clear_policy(10);suffix=[]
        while not trace.terminal and trace.step<300:
            t=trace.step;seed=seed_for('ogg_suffix',case['env_seed'],step,replicate,t)
            before=trace.policy_calls;trace.native(runtime,seed)
            if trace.policy_calls!=before:suffix.append(dict(step=t,seed=seed))
        dest.mkdir(parents=True,exist_ok=True);save_arrays(dest/'trajectory.npz',**trace.arrays())
        save_arrays(dest/'local_endpoint.npz',visual=spatial[0],proprio=np.asarray(segment))
        row=dict(status='complete',case_id=case['case_id'],task=case['task'],env_seed=case['env_seed'],step=step,
            method=method,replicate=replicate,success=any(trace.successes),terminal_step=trace.step,
            actual_prefix_steps=length,real_endpoint_match=matches,suffix_seeds=suffix,
            suffix_policy_calls=trace.policy_calls,suffix_policy_seconds=trace.policy_seconds,wall_seconds=time.perf_counter()-start,
            commands_sha256=digest(np.clip(plan[:5],-1,1)))
        dump(dest/'summary.json',row);seal(dest,['trajectory.npz','local_endpoint.npz','summary.json'],config_sha256=file_sha256(self.root/'config.json'))
        return row

    def evaluate_source(self,case,mode,phase):
        source=self.capture(case,mode);meta=json.loads((source/'summary.json').read_text())
        destination=self.root/'rollouts'/phase/mode/case['case_id'];destination.mkdir(parents=True,exist_ok=True)
        methods=['old','replan','d_only_241','d_only_242']+(['dc_451','dc_452'] if phase=='dc' else [])
        if meta['no_alarm']:
            dump(destination/'no_alarm.json',dict(status='complete',case=case,success=meta['success'],steps=meta['steps'],methods=methods,
                source=str(source),common_prefix_cost=meta['cost']))
        for step in meta['cuts']:
            target=destination/f'cut{step:03d}';target.mkdir(exist_ok=True)
            rng=np.random.default_rng(seed_for('ogg_arm_order',phase,case['env_seed'],step))
            order=list(rng.permutation(methods));plans={};generation={}
            for method in order:
                path=target/f'plan_{method}.npz';record=target/f'generation_{method}.json'
                if path.exists() and record.exists():
                    with np.load(path) as z:plans[method]=z['plan'].copy()
                    generation[method]=json.loads(record.read_text())
                else:
                    plan,stats=self.candidate(case,source,step,method);plans[method]=plan;generation[method]=stats
                    save_arrays(path,plan=plan);dump(record,stats)
            for method in methods:
                delta=np.abs(np.clip(plans[method],-1,1)-np.clip(plans['replan'],-1,1))
                generation[method]['final_prefix_delta_linf_vs_replan']=float(delta[:5].max())
                generation[method]['final_full_delta_linf_vs_replan']=float(delta.max())
                dump(target/f'generation_{method}.json',generation[method])
            execution=[]
            for rep in range(self.cfg['suffix_replicates']):
                for method in rng.permutation(methods):
                    dest=target/method/f'replicate_{rep}';execution.append(dict(method=str(method),replicate=rep))
                    if (dest/'complete.json').exists():continue
                    self.branch(case,source,step,str(method),plans[method],rep,dest)
            dump(target/'order.json',dict(generation_order=order,execution_order=execution,seed=seed_for('ogg_arm_order',phase,case['env_seed'],step)))
        dump(destination/'complete.json',dict(status='complete',case=case,phase=phase,mode=mode,methods=methods,cuts=meta['cuts'],no_alarm=meta['no_alarm']))
        self.verify()
        print(json.dumps(dict(event='case_complete',phase=phase,mode=mode,case=case['case_id'],cuts=len(meta['cuts']),no_alarm=meta['no_alarm'])),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=ROOT);parser.add_argument('--rank',type=int,default=0)
    parser.add_argument('--phase',choices=['d_only','dc'],required=True);parser.add_argument('--mode',choices=['local','single'],required=True)
    args=parser.parse_args();cfg=config(args.root);torch.set_num_threads(4);torch.cuda.set_device(0)
    split='development' if args.mode=='local' else 'confirmation';cases=[c for c in cfg['cases'] if c['split']==split][args.rank::8]
    if not cases:return
    engine=Engine(args.root,with_c=args.phase=='dc')
    try:
        for case in cases:engine.evaluate_source(case,args.mode,args.phase)
    finally:engine.close()


if __name__=='__main__':main()
