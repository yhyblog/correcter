"""New integration, not yet validated as one native+causal+PV system.

This module may only be imported by the released reserved child after its gate,
SHA verification, exclusive claim, NVML mapping and private EGL preparation.
"""
from pathlib import Path
import hashlib,json,math,os,random
import numpy as np
import torch
from core.contracts import PACKAGE,ContractError,write_new,read,sha
from core.event_recorder import EventRecorder
from causal_contract import Flags,history_indices
from numeric_setup import initialize
from feature_path import canonical_decode,spatial_tokens,cpu_batch
from corrector.guidance import FrozenObjective,FlowHook,post_direction
from corrector.solo import array_sha
from dg_models import WorldModel,BenefitModel

class Engine:
    def __init__(self,cfg,out,meter,egl,init_audit,branch):
        self.cfg,self.out,self.meter,self.egl,self.init_audit,self.branch=cfg,out,meter,egl,init_audit,branch
        self.seeds=cfg['source'];self.threshold=cfg['DG0']['threshold']
        self.env=None;self.steps=0;self.first_success_step=None
        self.recorder=EventRecorder(out/'causal_events.jsonl',branch=branch,
            source_id=cfg['source']['source_id'],parent_source_id=cfg['source']['parent_source_id'],split=cfg['source']['split'])
        self.spatial=[];self.props=[];self.transitions=[];self.predictions={};self.noise_shas={}
        device=egl.bind_policy(torch)
        state=initialize(cfg,out,meter,device)
        for k in ['device','policy','model','pre','post','features','versions','selector','transform','projection','project_solo','audit_solo']:
            setattr(self,k,state[k])
        self.dg=[];self.aux_versions=[]
        for member in cfg['DG0']['members']:
            norm=read(member['normalization'])
            models=[]
            for kind,cls in [('D',WorldModel),('G0',BenefitModel)]:
                path=member[kind+'_checkpoint']
                if sha(path)!=member[kind+'_sha256']:raise ContractError('DG0 checkpoint changed')
                obj=meter.call('construct_'+kind,lambda:cls(norm).to(device),{'model_initializations':1,kind+'_model_initializations':1})
                weights=meter.call('load_'+kind,lambda:torch.load(path,map_location=device,weights_only=True),{kind+'_model_loads':1})
                obj.load_state_dict(weights,strict=True)
                for key in ['mean','std','delta_scale']:
                    if not torch.equal(getattr(obj,key),torch.as_tensor(norm[key],dtype=torch.float32,device=device)):
                        raise ContractError('Frozen normalization differs from checkpoint buffers')
                obj.eval().requires_grad_(False);models.append(obj)
                self.aux_versions.extend((p,p._version) for p in list(obj.parameters())+list(obj.buffers()))
            self.dg.append((member,models[0],models[1]))
        with torch.no_grad():self.language=self.features.encode_instruction(cfg['source']['instruction'])
        write_new(out/'model_identity.json',dict(checkpoint=cfg['checkpoint'],DG0=cfg['DG0'],Q_assets=cfg['Q_assets'],
            Q_scope=cfg['Q_scope'],strict_loader='policy_loader.json',device=device,shared_prefix=False))

    def emit(self,name,**data):
        return self.recorder.emit(name,**data)

    def reset(self):
        import mujoco
        from gymnasium.envs.mujoco import mujoco_rendering
        from lerobot.envs.metaworld import MetaworldEnv
        self.egl.install_native_hooks(mujoco,mujoco_rendering)
        self.init_audit.install_real(MetaworldEnv,read(self.cfg['initialization_source_manifest']),str(PACKAGE/'code/vendor_vla/src/lerobot/envs/metaworld.py'))
        self.env=MetaworldEnv(task='shelf-place-v3',camera_name='corner2',obs_type='pixels_agent_pos',render_mode='rgb_array',
            observation_width=480,observation_height=480,max_path_length=300)
        native=self.env._env
        if not math.isclose(float(native.model.opt.timestep),1/400,rel_tol=0,abs_tol=1e-12):raise ContractError('Physics timestep changed')
        if not math.isclose(float(native.action_scale),0.01,rel_tol=0,abs_tol=1e-12):raise ContractError('Native default action scale changed')
        native.action_scale=0.015;self.env.metadata={**self.env.metadata,'render_fps':30}
        seed=self.seeds['env_seed'];random.seed(seed);np.random.seed(seed)
        torch.random.default_generator.manual_seed(seed);torch.cuda.manual_seed(seed);self.clear_policy_queue()
        # Preserve separate native-reset and full-RGB return counts.
        with self.init_audit.scope('diagnostic_reset'),self.egl.observation_scope('step_0'):
            result=self.meter.call('complete_reset_observation',lambda:self.env.reset(seed=seed),{'reset_observation_calls':1,'observation_calls':1})
        obs,info=result;native.action_scale=0.015
        return obs,Flags(success=bool(info.get('success',info.get('is_success',False))))

    def step(self,command,index,plan_id):
        if index!=self.steps or not 0<=index<16:raise ContractError('Control order or finite cap changed')
        native=self.env._env
        if native.action_scale!=0.015:raise ContractError('Action scale drift')
        action=np.asarray(command,dtype=np.float32)
        if action.shape!=(4,) or not np.isfinite(action).all() or np.max(np.abs(action))>1:raise ContractError('Invalid submitted command')
        n=((index+1)*400)//30-(index*400)//30
        native.frame_skip=n;before=float(native.data.time)
        with self.init_audit.scope('policy_control'):
            value=self.meter.call('native_control_step',lambda:native.step(action),{'env_steps':1})
        raw,reward,terminated,truncated,info=value
        after=float(native.data.time)
        if not math.isclose(after-before,n/400,rel_tol=0,abs_tol=1e-9):raise ContractError('Actual physics time mismatch')
        flags=Flags(bool(info.get('success',False)),bool(terminated),bool(truncated))
        self.steps+=1
        if flags.success and self.first_success_step is None:self.first_success_step=self.steps
        # Native control return is recorded before any later RGB read can fail.
        row=dict(step=index,next_step=index+1,plan_id=plan_id,action=action.tolist(),reward=float(reward),
                 success=flags.success,terminated=flags.terminated,truncated=flags.truncated,
                 first_success_step=self.first_success_step,physics_substeps=n,sim_time_before=before,sim_time_after=after)
        self.transitions.append(row);self.emit('native_transition_returned',**row)
        if native._did_see_sim_exception:raise ContractError('Native simulation exception flag; no further render/control')
        with self.egl.observation_scope('step_'+str(self.steps)):
            obs=self.meter.call('control_observation',lambda:self.env._format_raw_obs(raw),{'observation_calls':1,'control_observation_calls':1})
        return obs,flags

    def save_observation(self,obs,step):
        if obs['pixels'].shape!=(480,480,3) or obs['pixels'].dtype!=np.uint8 or obs['agent_pos'].shape!=(4,):raise ContractError('Observation format changed')
        np.savez_compressed(self.out/f'observation_step{step}.npz',pixels=obs['pixels'],proprioception=obs['agent_pos'])
        self.emit('observation_saved',step=step,pixel_sha256=array_sha(obs['pixels']),proprio_sha256=array_sha(obs['agent_pos']))

    def encode_context(self,obs,step,executed):
        if step!=len(self.spatial) or step>5 or len(executed)!=step:raise ContractError('Causal feature order changed')
        with torch.no_grad():
            vision=self.features.encode_visual_batch([obs],batch_size=1)
            spatial=self.meter.call('canonical_singleton_spatial_projection',lambda:spatial_tokens(
                canonical_decode(torch.as_tensor(vision,device=self.device).float()),self.projection).flatten(1).half().float().cpu().numpy(),{'spatial_projection_calls':1})
            if vision.shape!=(1,1,256,2048) or spatial.shape!=(1,4096):raise ContractError('Feature dimension changed')
            self.spatial.append(spatial[0].copy());self.props.append(obs['agent_pos'].copy())
            # At cut5 frames 1..5 and executed controls 1..4 only; frame0's
            # committed controls 0..4 remain separately in the D reference.
            context=self.meter.call('causal_context',lambda:cpu_batch(self.spatial[-5:],self.props[-5:],executed[-4:],self.language,step,device=self.device),{'context_builds':1})
        expected_mask=[False]*(5-min(step+1,5))+[True]*min(step+1,5)
        if context['history_mask'][0].cpu().tolist()!=expected_mask:raise ContractError('Causal history mask mismatch')
        arrays={k:v[0].detach().cpu().numpy() for k,v in context.items()}
        np.savez_compressed(self.out/f'context_step{step}.npz',**arrays)
        if step in (0,5):np.savez_compressed(self.out/f'encoder_step{step}.npz',visual_patch_tokens=vision,spatial=spatial,language=self.language)
        frames,actions=history_indices(step)
        self.emit('causal_features',step=step,observations=frames,past_action_indices=actions,future_observations_used=False,
            context_shas={k:array_sha(v) for k,v in arrays.items()})
        return context

    def check_prefix_at_cut(self):
        if self.branch=='Post':return True
        prior=self.out.parent/'Post'
        def signature(folder):
            rows=[json.loads(x) for x in (folder/'causal_events.jsonl').read_text().splitlines()]
            obs=[{k:r[k] for k in ['step','pixel_sha256','proprio_sha256']} for r in rows if r['event']=='observation_saved' and r['step']<=5]
            trans=[{k:r[k] for k in ['step','next_step','action','reward','success','terminated','truncated','physics_substeps','sim_time_before','sim_time_after']} for r in rows if r['event']=='native_transition_returned' and r['step']<5]
            contexts=[r['context_shas'] for r in rows if r['event']=='causal_features' and r['step'] in (0,5)]
            if len(obs)!=6 or len(trans)!=5 or len(contexts)!=2:raise ContractError('Incomplete independent prefix evidence')
            return dict(observations=obs,transitions=trans,contexts=contexts,prefix_raw_sha=sha(folder/'prefix_raw50.npy'))
        left=signature(prior);right=signature(self.out);matched=left==right
        write_new(self.out/'PREFIX_COMPARISON.json',dict(observable_prefix_matches=matched,Post=left,Velocity=right,
            hidden_state_equivalence_proven=False,full_state_restore_used=False,next_action='continue own causal cut' if matched else 'stop before intervention; no replay/retry'))
        self.emit('independent_prefix_comparison',observed_matches=matched,hidden_state_equivalence_proven=False)
        return matched

    def forecast(self,context,actions,label):
        batch={**context,'actions':torch.as_tensor(actions,dtype=torch.float32,device=self.device)[None]}
        outputs=[]
        with torch.no_grad():
            for member,world,gate in self.dg:
                future,proprio=self.meter.call('D_predict_five',lambda:world(batch),{'D_forward_calls':1},{'D_seed':member['D_seed'],'target':label})
                if not torch.isfinite(future).all() or not torch.isfinite(proprio).all():raise ContractError('Nonfinite D output')
                outputs.append(future.detach().clone())
                np.savez_compressed(self.out/f'D_{member["D_seed"]}_{label}.npz',visual=future.cpu().numpy(),proprio=proprio.cpu().numpy(),actions=np.asarray(actions,np.float32))
        return outputs

    def residual(self,prior,context):
        values=[]
        # Same canonical source arithmetic: NumPy mean-square on CPU float32.
        for future,(member,world,gate) in zip(prior,self.dg):
            error=float(np.mean(((future[0,-1].cpu().numpy()-context['history'][0,-1].cpu().numpy())/world.delta_scale.cpu().numpy())**2))
            if not math.isfinite(error):raise ContractError('Nonfinite matured D residual')
            values.append(dict(D_seed=member['D_seed'],residual=error,target_step=5,predicted_at=0))
        return values

    def gate_score(self,context,actions,future):
        batch={**context,'actions':torch.as_tensor(actions,dtype=torch.float32,device=self.device)[None]}
        scores=[]
        self.meter.call('legal_cut_monitor',lambda:None,{'monitor_calls':1})
        with torch.no_grad():
            for pred,(member,world,gate) in zip(future,self.dg):
                value=self.meter.call('G0_current_five_step_benefit',lambda:gate(batch,pred),{'G0_forward_calls':1})
                scores.append(float(value))
        score=float(np.mean(scores));write_new(self.out/'G0_outputs.json',dict(member_scores=scores,mean=score,threshold=self.threshold,
            target=self.cfg['DG0']['target'],output_semantics='raw regression',actual_future_used=False,residual_is_input=False))
        return score

    def clear_policy_queue(self):
        self.policy.reset()
        if len(self.policy._action_queue)!=0 or any(len(q) for q in self.policy._queues.values()):raise ContractError('Hidden policy action queues not empty')
        if self.policy.config.n_action_steps!=20:raise ContractError('Native policy H20 changed')

    def sample(self,obs,label,seed,expected_noise=None):
        self.clear_policy_queue()
        with torch.random.fork_rng(devices=[0]):
            torch.random.default_generator.manual_seed(seed);torch.cuda.manual_seed(seed)
            noise=self.model.sample_noise((1,50,32),torch.device(self.device))
        noise_cpu=noise.detach().float().cpu().numpy();noise_sha=array_sha(noise_cpu)
        self.noise_shas[label]=noise_sha
        np.save(self.out/(label+'_noise.npy'),noise_cpu,allow_pickle=False)
        write_new(self.out/(label+'_noise_identity.json'),dict(seed=seed,sha256=noise_sha,expected=expected_noise,paired=expected_noise is not None,
            matches=True if expected_noise is None else noise_sha==expected_noise))
        if expected_noise is not None and noise_sha!=expected_noise:raise ContractError('Paired anchor/guided noise SHA mismatch')
        with torch.no_grad():
            batch=self.features._policy_batch(obs,self.cfg['source']['instruction'])
            images,masks=self.policy._preprocess_images(batch)
            if len(images)!=3 or [bool(x[0]) for x in masks]!=[True,False,False]:raise ContractError('Frozen camera path changed')
            native=self.meter.call('full_raw50_'+label,lambda:self.model.sample_actions(images,masks,batch['observation.language.tokens'],batch['observation.language.attention_mask'],noise=noise,num_steps=10),{'vla_sampling_calls':1,'model_gpu_inference_calls':1})
            internal=native[:,:,:4].detach().clone()
            commands=self.meter.call('postprocess_raw50_'+label,lambda:self.post(internal.reshape(-1,4)).reshape(internal.shape),{'postprocessor_calls':1})
            raw=commands.float().cpu().numpy()[0].copy()
        if raw.shape!=(50,4) or not np.isfinite(raw).all():raise ContractError('Invalid raw50')
        np.save(self.out/(label+'_raw50.npy'),raw,allow_pickle=False)
        if len(self.policy._action_queue)!=0:raise ContractError('Direct full-plan sampling unexpectedly filled hidden queue')
        return raw

    def intervene(self,obs,context,branch,seed):
        raw=self.sample(obs,'cut_anchor',seed);base=np.clip(raw,-1,1).astype(np.float32)
        observed={k:v[0].detach().cpu().numpy().copy() for k,v in context.items()}
        outer=self
        class Objective(FrozenObjective):
            def __call__(self,commands):
                return outer.meter.call('ensemble_objective_two_slots',lambda:super(Objective,self).__call__(commands),{'objective_forward_calls':1},
                    {'branch':branch,'Q_acceptance_gate':False,'gradient_enabled':torch.is_grad_enabled()})
        objective=Objective(observed,base,selector=self.selector)
        original_grad=torch.autograd.grad;gradients=[];hook=None
        def action_grad(*a,**kw):
            if any(p.requires_grad or p.grad is not None for p,_ in self.versions+self.aux_versions):raise ContractError('Frozen model gradient enabled')
            kind='post_action_gradient_calls' if branch=='Post' else 'velocity_action_gradient_calls'
            result=self.meter.call('action_only_gradient',lambda:original_grad(*a,**kw),{'action_gradient_calls':1,'critic_backward_calls':1,kind:1})
            gradients.extend(g.detach().float().cpu().numpy().copy() for g in result)
            return result
        torch.autograd.grad=action_grad
        try:
            anchor=objective.evaluate(base[:10])
            if anchor['mean_gain']!=0:raise ContractError('J(a0;a0) changed')
            if branch=='Post':
                direction,stats=post_direction(objective,self.transform)
                if stats['value']!=0:raise ContractError('Post gradient anchor changed')
            else:
                hook=FlowHook(self.model,self.transform,self.cfg['guidance']);hook.begin(objective)
                guided=self.sample(obs,'guided',seed,expected_noise=self.noise_shas['cut_anchor'])
                if len(hook.times)!=10 or not np.allclose(hook.times,np.arange(10,0,-1)/10,atol=1e-6) or len(hook.logs)!=3 or not np.allclose([x['tau'] for x in hook.logs],[.3,.2,.1],atol=1e-6):raise ContractError('Velocity flow/gradient schedule changed')
                if hook.last_noise_sha!=self.noise_shas['cut_anchor']:raise ContractError('Actual guided initial noise mismatch')
                direction=np.clip(guided,-1,1)[:10].astype(float)-base[:10].astype(float)
                stats=dict(updates=hook.logs,times=hook.times,noise_sha256=hook.last_noise_sha,local_decreases_retained=True)
                hook.close();hook=None
            proposal,matching,arrays=self.project_solo(raw,direction,self.cfg['matching'])
            audit=self.audit_solo(raw,proposal,direction,self.cfg['matching'])
            final=objective.evaluate(np.clip(proposal[:10],-1,1))
            expected=(3,12,1) if branch=='Post' else (8,32,3)
            s=objective.stats()
            if tuple(s[k] for k in ['objective_forward_calls','critic_member_forward_calls','objective_backward_calls'])!=expected:raise ContractError('Objective count mismatch')
            objective.verify();self.selector.verify(check_files=True);self.verify_frozen()
            np.savez_compressed(self.out/(branch+'_arrays.npz'),**arrays,**{f'action_gradient_{i}':x for i,x in enumerate(gradients)})
            np.save(self.out/(branch+'_proposed_raw50.npy'),proposal,allow_pickle=False)
            write_new(self.out/(branch+'_numeric.json'),dict(anchor=anchor,score=final,updates=stats,matching=matching,audit=audit,objective_stats=s,
                own_radius_independent=True,shared_radius=False,Q_acceptance_gate=False,raw_tail_unchanged=True,models_frozen=True,
                deployment_sampling_calls=self.cfg['deployment_sampling_calls'][branch],diagnostic_intervention_sampling_calls=1 if branch=='Post' else 2,
                shared_a0_between_branches=False,saved_numeric_pass_is_not_success_rate=True))
            return proposal
        finally:
            torch.autograd.grad=original_grad
            if hook is not None:hook.close()

    def verify_frozen(self):
        self.selector.verify(check_files=False)
        if any(p.requires_grad or p.grad is not None or p._version!=v for p,v in self.versions+self.aux_versions):raise ContractError('Frozen parameter/buffer drift')

    def finish(self,status,step,queue):
        self.verify_frozen()
        result=dict(status=status,branch=self.branch,controls=step,first_success_step=self.first_success_step,
            remaining_queue=len(queue.rows),current_horizon=queue.horizon,source=self.cfg['source'],
            state_equivalence_claim=False,completed_rollout=False,task_success_sample=False,shared_prefix=False,
            trigger_record='causal_events.jsonl',restoration_coverage=status=='C10_and_H20_checked',
            peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(),peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved())
        write_new(self.out/'BRANCH_RESULT.json',result)
        return result

    def close(self):
        if self.env is not None:self.env.close()
