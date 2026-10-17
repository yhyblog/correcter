"""Frozen-flow candidates and counted, paired real MetaWorld rollouts."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import numpy as np
import torch
from ac_tmil.ogg.experiment import Engine
from ac_tmil.ogg_research.experiment import ResearchEngine
from ac_tmil.ogg.common import cpu_batch,digest
from ac_tmil.ogg_research.critic_data import STATE_KEYS
from ac_tmil.ogg_research_v3.learning import FrozenSelector
from ac_tmil.ogg_research_v2.evaluation import sealed
from ac_tmil.idea3.local_collection import seal
from .common import ROOT,REPO,OGG,METHODS,read,dump,save_arrays,seed_for,file_sha256,reserve_branch
from .guidance import FrozenObjective,FlowHook
from .candidates import construct

class FlowEngine(Engine):
    spatial=ResearchEngine.spatial
    def __init__(self):
        super().__init__(OGG,with_c=False)
        self.root=ROOT;self.study=read(ROOT/'config.json');self.selector=FrozenSelector()
        self.hook.close()
        self.hook=FlowHook(self.runtime.backend.policy.model,self.transform,dict(self.study['guidance'],mode='velocity'))
        assert self.cfg['gate_threshold']==.05 and self.cfg['control_budget']==300

    @torch.no_grad()
    def context(self,frames,proprio,past,language,step):
        return cpu_batch(self.spatial(list(frames),proprio),proprio,past,language,step)

    def prepare_bank(self,case,source,step,dest):
        packet=dest/'candidates'
        if (packet/'complete.json').exists():sealed(packet,ROOT/'config.json');return
        start=time.perf_counter();self.restore(case,source,step)
        before=self.runtime.fingerprint()
        with np.load(source/f'cut{step:03d}/context.npz') as z:observed={k:z[k].copy() for k in STATE_KEYS}
        seed=seed_for(self.study['candidate_seed_namespace'],case['env_seed'],step)
        base,base_stats=self.propose(seed);base=np.clip(base,-1,1).astype(np.float32)
        noises={'replan':self.hook.last_noise_sha};objective=FrozenObjective(observed,base,selector=self.selector)
        checks={}
        if case['split']=='preflight':
            saved=dict(self.hook.settings);self.hook.settings['alpha']=0
            zero,_=self.propose(seed,objective);noises['zero']=self.hook.last_noise_sha
            np.testing.assert_array_equal(base,np.clip(zero,-1,1));checks['zero_strength_bit_identical']=True
            # At the very last real Euler step there is no subsequent sampler
            # evolution; a linear command objective must move in its known sign.
            for mode in ['velocity','direct']:
                self.hook.settings.update(mode=mode,alpha=10.,times=[.1])
                def linear(commands):return commands[:,:,:3].sum()
                analytic,stats=self.propose(seed,linear);analytic=np.clip(analytic,-1,1)
                assert stats['fallback'] is None and len(stats['updates'])==1
                gain=float((analytic[:10,:3]-base[:10,:3]).sum())
                assert gain>=-1e-5 and float(np.min(analytic[:10,:3]-base[:10,:3]))>=-1e-5
                checks[mode+'_actual_sampler_linear_gain']=gain
                checks[mode+'_actual_sampler_sign_passed']=True
            self.hook.settings.clear();self.hook.settings.update(saved)
        generated={};stats={}
        for mode in ['velocity','direct']:
            self.hook.settings['mode']=mode
            generated[mode],stats[mode]=self.propose(seed,objective)
            generated[mode]=np.clip(generated[mode],-1,1).astype(np.float32)
            noises[mode]=self.hook.last_noise_sha
        assert len(set(noises.values()))==1 and next(iter(noises.values())) is not None
        tick=time.perf_counter();gradient,gradient_stats=objective.gradient()
        scales=((self.transform.q99-self.transform.q01)/2).detach().cpu().numpy()
        post_direction=gradient.numpy()*scales[None]**2
        gradient_stats.update(seconds=time.perf_counter()-tick,transform_slopes=scales.tolist(),metric='S squared command gradient')
        plans,matching=construct(base,generated['velocity'],generated['direct'],post_direction,
            seed_for(self.study['random_seed_namespace'],case['env_seed'],step),self.study['matching'])
        predictions={name:objective.evaluate(plans[name][:10]) for name in METHODS}
        assert predictions['replan']['mean_gain']==0
        base_probs=np.array(predictions['replan']['member_probabilities'])[:,0]
        for name in METHODS:np.testing.assert_array_equal(np.array(predictions[name]['member_probabilities'])[:,0],base_probs)
        objective.verify();self.verify();assert self.runtime.fingerprint()==before
        checks.update(same_noise=True,a0_anchor_exact=True,frozen_models=True,no_environment_steps=True)
        save_arrays(packet/'plans.npz',**plans)
        save_arrays(packet/'directions.npz',post_command_gradient=gradient.numpy(),post_internal_metric_direction=post_direction)
        dump(packet/'generation.json',dict(case_id=case['case_id'],step=step,base_seed=seed,base_generation=base_stats,
            guidance=stats,matching=matching,predictions=predictions,post_gradient=gradient_stats,noise_hashes=noises,
            preflight_checks=checks,objective_stats=objective.stats(),wall_seconds=time.perf_counter()-start,
            context_sha256=file_sha256(source/f'cut{step:03d}/context.npz'),saved_before_any_branch=True))
        seal(packet,['plans.npz','directions.npz','generation.json'],config_sha256=file_sha256(ROOT/'config.json'))

    def branch(self,case,source,step,name,plan,rep,dest,kind=None):
        dest.mkdir(parents=True,exist_ok=True)
        attempt=reserve_branch(kind or case['split'],dest)
        dump(dest/f"attempt_{attempt['number']:04d}.json",attempt)
        begin=time.perf_counter();trace,_=self.restore(case,source,step)
        replay_seconds=time.perf_counter()-begin;runtime=self.runtime
        for command in plan[:10]:
            if trace.terminal or trace.step>=300:break
            trace.execute(runtime,command)
        length=trace.step-step
        assert length>0
        endpoint_image_sha=digest(runtime.frame())
        runtime.clear_policy(10);suffix=[]
        while not trace.terminal and trace.step<300:
            t=trace.step;index=len(suffix)
            seed=seed_for(self.study['suffix_seed_namespace'],case['env_seed'],step,rep,index)
            before=trace.policy_calls;trace.native(runtime,seed)
            if trace.policy_calls!=before:suffix.append(dict(step=t,decision_index=index,seed=seed))
        save_arrays(dest/'trajectory.npz',**trace.arrays())
        row=dict(status='complete',case_id=case['case_id'],task=case['task'],env_seed=case['env_seed'],step=step,
            horizon=10,method=name,replicate=rep,success=bool(any(trace.successes)),terminal_step=trace.step,
            actual_prefix_steps=length,budget_truncated=step+10>300,suffix_seeds=suffix,
            suffix_policy_calls=trace.policy_calls,suffix_policy_seconds=trace.policy_seconds,replay_seconds=replay_seconds,
            environment_seconds=trace.environment_seconds,wall_seconds=time.perf_counter()-begin,
            endpoint_image_sha256=endpoint_image_sha,commands_sha256=digest(plan[:10]),
            continuation='clear_queue_then_fixed10_v1',control_hz=30,physics_hz=400,action_scale=.015,budget_attempt=attempt['number'])
        dump(dest/'summary.json',row);seal(dest,['trajectory.npz','summary.json'],config_sha256=file_sha256(ROOT/'config.json'))

    def collect(self,case):
        target=ROOT/'rollouts'/case['split']/case['case_id']
        if (target/'complete.json').exists():return
        source=ROOT/'sources/single'/case['case_id']
        if not (source/'complete.json').exists():reserve_branch('source_capture',case['case_id'])
        source=self.capture(case,'single');smeta=json.loads((source/'summary.json').read_text())
        repeats=self.study['preflight_replicates'] if case['split']=='preflight' else self.study['replicates']
        for step in smeta['cuts']:
            dest=target/f'cut{step:03d}';self.prepare_bank(case,source,step,dest)
            with np.load(dest/'candidates/plans.npz') as z:plans={k:z[k].copy() for k in METHODS}
            rng=np.random.default_rng(seed_for(self.study['branch_order_seed_namespace'],case['env_seed'],step))
            for rep in range(repeats):
                for name in rng.permutation(METHODS):
                    name=str(name);branch=dest/name/f'replicate_{rep}'
                    if not (branch/'complete.json').exists():self.branch(case,source,step,name,plans[name],rep,branch)
                print(json.dumps(dict(event='replicate_complete',case=case['case_id'],replicate=rep)),flush=True)
        self.verify();self.selector.verify()
        dump(target/'complete.json',dict(status='complete',case=case,cuts=smeta['cuts'],no_alarm=smeta['no_alarm'],
            common_source_success=smeta['success'],replicates=repeats,config_sha256=file_sha256(ROOT/'config.json')))
        print(json.dumps(dict(event='source_complete',case=case['case_id'],cuts=smeta['cuts'])),flush=True)

def worker(rank,execution):
    cfg=read(execution);main=read(ROOT/'config.json');stage=cfg['stage']
    assert cfg['config_sha256']==file_sha256(ROOT/'config.json')
    for name,sha in cfg['code_hashes'].items():assert file_sha256(REPO/name)==sha,name
    if stage=='development':
        frozen=read(ROOT/'formal_freeze.json')
        for name,sha in frozen['code_hashes'].items():assert file_sha256(REPO/name)==sha,name
    cases=[c for c in main['cases'] if c['split']==stage]
    if stage=='preflight' and rank>=len(cases):return
    torch.set_num_threads(4);torch.cuda.set_device(0);engine=FlowEngine()
    try:
        if stage=='development':
            references=sorted((ROOT/'rollouts/preflight').glob('*/cut*/replan/replicate_0'))
            assert references
            reference=references[rank%len(references)];row=json.loads((reference/'summary.json').read_text())
            case=next(c for c in main['cases'] if c['case_id']==row['case_id'])
            with np.load(reference.parents[1]/'candidates/plans.npz') as z:plan=z['replan'].copy()
            target=Path(cfg['checks'])/f'worker_{rank:02d}'
            engine.branch(case,ROOT/'sources/single'/case['case_id'],row['step'],'replan',plan,0,target,kind='concurrency_check')
            new=json.loads((target/'summary.json').read_text())
            for key in ['success','terminal_step','actual_prefix_steps','commands_sha256','endpoint_image_sha256','suffix_seeds']:assert row[key]==new[key],key
            with np.load(reference/'trajectory.npz') as old,np.load(target/'trajectory.npz') as z:
                for key in old.files:np.testing.assert_array_equal(old[key],z[key])
            dump(target/'passed.json',dict(status='passed',rank=rank,full_trajectory_bit_identical=True,reference=str(reference)))
            print(json.dumps(dict(event='concurrency_passed',rank=rank)),flush=True)
            deadline=time.monotonic()+1800
            while not all((Path(cfg['checks'])/f'worker_{i:02d}/passed.json').exists() for i in range(cfg['total_workers'])):
                if time.monotonic()>deadline:raise TimeoutError('Concurrent reproduction barrier')
                time.sleep(.5)
        claims=ROOT/'claims'/stage;claims.mkdir(parents=True,exist_ok=True)
        for case in cases:
            if (ROOT/'rollouts'/stage/case['case_id']/'complete.json').exists():continue
            claim=claims/case['case_id']
            try:claim.mkdir()
            except FileExistsError:continue
            dump(claim/'owner.json',dict(rank=rank,pid=os.getpid(),execution=str(execution),unix=time.time()))
            engine.collect(case)
    finally:engine.close()

def pool(rank,execution):
    cfg=read(execution);logs=Path(cfg['worker_logs']);logs.mkdir(parents=True,exist_ok=True)
    children=[];streams=[]
    def interrupted(sig,_):raise KeyboardInterrupt(f'signal {sig}')
    for sig in [signal.SIGINT,signal.SIGTERM,signal.SIGHUP]:signal.signal(sig,interrupted)
    try:
        for i in range(cfg['workers_per_gpu']):
            wid=rank*cfg['workers_per_gpu']+i;stream=(logs/f'worker_{wid:02d}.log').open('x');streams.append(stream)
            children.append(subprocess.Popen(['bash',str(REPO/'scripts/run_recap_ogg_flow.sh'),'collection','--worker',str(wid),'--execution',str(execution)],cwd=REPO,stdout=stream,stderr=subprocess.STDOUT))
            time.sleep(1)
        while any(p.poll() is None for p in children):
            if any(p.poll() not in (None,0) for p in children):raise RuntimeError('Owned worker failed; inspect worker logs')
            time.sleep(.5)
        assert all(p.returncode==0 for p in children)
    finally:
        for p in children:
            if p.poll() is None:p.terminate()
        for p in children:
            try:p.wait(timeout=20)
            except subprocess.TimeoutExpired:p.kill();p.wait()
        for f in streams:f.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--rank',type=int);p.add_argument('--worker',type=int);p.add_argument('--execution',type=Path,required=True);a=p.parse_args()
    worker(a.worker,a.execution) if a.worker is not None else pool(a.rank,a.execution)
