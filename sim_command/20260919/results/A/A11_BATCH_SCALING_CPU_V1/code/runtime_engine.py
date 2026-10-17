"""Released-only five-task collector adapter. Never imported by CPU fixtures."""
import json,random,struct
from pathlib import Path
import numpy as np
import torch
from core.contracts import ContractError,write_new,sha
from numeric_setup import initialize
from feature_path import canonical_decode,spatial_tokens
from pool_protocol import digest,unpack,local_pair,stream_seed,raw_group
from runtime_state import capture
from shared_plans import load_bank as verified_load_bank,make_bank_document,saved_bank_ref
from observation_phase import observation_phase
from task_profiles import validate_config
def wire_ref(row,format):return dict(path=row['path'],sha256=row['sha256'],format=format)
class Engine:
    synthetic=False
    H=10;target=300
    def __init__(self,cfg,out,meter,egl,init,job,store,identity):
        validate_config(cfg);self.task=cfg['source']['task'];self.cut=cfg['source']['cut']
        self.cfg,self.out,self.meter,self.egl,self.init,self.job,self.store=cfg,Path(out),meter,egl,init,job,store
        self.identity=identity;self.source_signature=cfg['source_signature']
        self.env=None;self.steps=0;self.history=[];self.props=[];self.actions=[];self.prefix_records=[]
        self.prefix_plan_shas=[];self.prefix_noise_shas=[];self.plan_refs={};self.plan_noise={};self.decisions={};self.pending=None;self.last_observation=None
        state=initialize(cfg,out,meter,egl.bind_policy(torch))
        for key in ('device','policy','model','pre','post','features','versions','projection'):setattr(self,key,state[key])
        self.language=self.features.encode_instruction(cfg['source']['instruction'])
        self.store.write('language.f32',self.language.astype('<f4').tobytes())
    def reset(self):
        import mujoco
        from gymnasium.envs.mujoco import mujoco_rendering
        from lerobot.envs.metaworld import MetaworldEnv
        self.egl.install_native_hooks(mujoco,mujoco_rendering)
        self.init.install_real(MetaworldEnv,json.loads(Path(self.cfg['initialization_source_manifest']).read_text()),
            str(__import__('inheritance').BASE_CODE/'vendor_vla/src/lerobot/envs/metaworld.py'))
        self.env=MetaworldEnv(task=self.task,camera_name='corner2',obs_type='pixels_agent_pos',
            render_mode='rgb_array',observation_width=480,observation_height=480,max_path_length=300)
        native=self.env._env
        if float(native.model.opt.timestep)!=1/400:raise ContractError('physics timestep')
        seed=self.cfg['source']['env_seed']
        self.meter.call('freeze_global_seed',lambda:(random.seed(seed),np.random.seed(seed),torch.random.default_generator.manual_seed(seed),torch.cuda.manual_seed(seed)),
            {'python_rng_seed_calls':1,'numpy_rng_seed_calls':1,'torch_global_seed_calls':2})
        self.meter.call('native_seed',lambda:native.seed(seed),{'environment_seed_calls':1})
        native.action_scale=.015;self.clear_policy_queue()
        with self.init.scope('diagnostic_reset'),self.egl.observation_scope(observation_phase(0)):
            obs,info=self.meter.call('reset_and_observe',lambda:self.env.reset(seed=seed),
                {'reset_observation_calls':1,'observation_calls':1})
        native.action_scale=.015
        return obs
    def clear_policy_queue(self):
        self.policy.reset()
        if self.policy.config.n_action_steps!=10 or len(self.policy._action_queue) or any(self.policy._queues.values()):
            raise ContractError('hidden H10 policy queue not empty')
    def observe(self,obs,step):
        if obs['pixels'].shape!=(480,480,3) or obs['pixels'].dtype!=np.uint8 or obs['agent_pos'].shape!=(4,):raise ContractError('observation shape')
        rgb=wire_ref(self.store.write(f'observations/step{step:03d}.ppm',b'P6\n480 480\n255\n'+obs['pixels'].tobytes()),'ppm_rgb8')
        with torch.no_grad():
            visual=self.features.encode_visual_batch([obs],batch_size=1)
            decoded=canonical_decode(torch.from_numpy(visual).to(self.device))
            feature=self.meter.call('spatial_features',lambda:spatial_tokens(decoded,self.projection).reshape(1,4096)[0].float().cpu().numpy(),
                {'spatial_projection_calls':1})
        fref=wire_ref(self.meter.call('serialize_feature',lambda:self.store.write(f'features/step{step:03d}.f32',feature.astype('<f4').tobytes()),
            {'feature_state_serializations':1}),'float32_le_4096')
        self.history.append(feature);self.props.append(np.asarray(obs['agent_pos']).copy())
        self.history=self.history[-5:];self.props=self.props[-5:]
        record=dict(step=step,RGB=rgb,features=fref,proprio=obs['agent_pos'].tolist(),
            feature_signature=self.cfg['feature_signature'])
        obref=wire_ref(self.store.json(f'observations/step{step:03d}.json',record),'json_observation_bundle')
        if step<=self.cut:self.prefix_records.append(dict(step=step,pixel_sha=rgb['sha256'],feature_sha=fref['sha256'],proprio=record['proprio']))
        if self.pending is not None:
            transition=self.pending
            from public_records import publish_transition
            publish_transition(self,transition,obref,step)
            if step<=self.cut:self.prefix_records.append(dict(transition={k:transition[k] for k in
                ('step','next_step','raw_actions','normalized_actions','rewards','successes','terminated','truncated')}))
            self.pending=None
        self.last_observation=obref;self.last_proprio=record['proprio']
    def sample(self,obs,namespace,repeat,step):
        self.clear_policy_queue()
        if namespace=='prefix':repeat=None
        key=(namespace,repeat);ordinal=self.decisions.get(key,0);self.decisions[key]=ordinal+1
        seed=stream_seed(self.cfg['source']['master_seed'],self.cfg['source']['parent_source_id'],namespace,repeat,ordinal,cut=self.cut)
        generator=self.meter.call('dedicated_torch_generator',lambda:torch.Generator(device=self.device),{'torch_generator_creations':1})
        self.meter.call('dedicated_generator_seed',lambda:generator.manual_seed(seed),{'torch_generator_seed_calls':1})
        noise=self.meter.call('isolated_noise',lambda:torch.randn((1,50,32),device=self.device,dtype=torch.float32,generator=generator),{'noise_draws':1})
        label=f'{namespace}_{repeat}_{ordinal}'
        noise_ref=wire_ref(self.store.write(f'plans/{label}.noise.f32',noise.detach().cpu().numpy().astype('<f4').tobytes()),'float32_le_1x50x32')
        with torch.no_grad():
            batch=self.features._policy_batch(obs,self.cfg['source']['instruction'])
            images,masks=self.policy._preprocess_images(batch)
            if len(images)!=3 or [bool(x[0]) for x in masks]!=[True,False,False]:raise ContractError('camera signature')
            raw=self.meter.call('native_raw50',lambda:self.model.sample_actions(images,masks,batch['observation.language.tokens'],
                batch['observation.language.attention_mask'],noise=noise,num_steps=10),
                {'vla_sampling_calls':1,'model_gpu_inference_calls':1})
            actions=self.meter.call('native_postprocess',lambda:self.post(raw[:,:,:4].reshape(-1,4)).reshape(50,4),
                {'postprocessor_calls':1})
        payload=actions.float().cpu().numpy().astype('<f4').tobytes();unpack(payload)
        pref=wire_ref(self.store.write(f'plans/{label}.raw50.f32',payload),'float32_le_50x4')
        self.plan_refs[digest(payload)]=pref;self.plan_noise[digest(payload)]=noise_ref
        self.store.json(f'plans/{label}.identity.json',dict(seed=seed,namespace=namespace,repeat_id=repeat,
            decision_index=ordinal,noise_ref=noise_ref,raw50_ref=pref,
            RNG='torch.Generator explicit target device; source global generators unmodified'))
        if namespace=='prefix':
            self.prefix_plan_shas.append(digest(payload));self.prefix_noise_shas.append(noise_ref['sha256'])
        if any(p._version!=v or p.requires_grad for p,v in self.versions):raise ContractError('frozen parameter/buffer changed')
        return payload
    def generate_bank(self,obs):
        plans={f'fresh{k}':self.sample(obs,'fresh',k,self.cut) for k in range(3)};plans['a0']=plans['fresh0']
        seed=stream_seed(self.cfg['source']['master_seed'],self.cfg['source']['parent_source_id'],'local',None,0,cut=self.cut)
        pair=self.meter.call('local_smooth_pair',lambda:local_pair(plans['a0'],seed),
            {'CPU_local_direction_draws':12,'CPU_own_radius_group_calculations':2,'CPU_candidate_raw50_writes':2})
        self.store.json('bank/local_direction.json',dict(**pair['evidence'],
            actual_candidates={k:{n:v for n,v in item.items() if n!='raw'} for k,item in pair['plans'].items()}))
        for key,item in pair['plans'].items():
            plans[key]=item['raw'];self.plan_refs[digest(item['raw'])]=wire_ref(self.store.write('bank/'+key+'.f32',item['raw']),'float32_le_50x4')
            self.plan_noise[digest(item['raw'])]=self.plan_noise[digest(plans['a0'])]
        bank=make_bank_document(self,plans)
        self.bank_manifest_ref=saved_bank_ref(self.store.json('BANK.json',bank))
        return plans
    def step(self,action,step,*,raw_plan,raw_index):
        if step!=self.steps:raise ContractError('absolute control clock mismatch')
        native=self.env._env;n=((step+1)*400)//30-(step*400)//30;native.frame_skip=n
        with self.init.scope('policy_control'):
            raw,reward,terminated,truncated,info=self.meter.call('real_control',lambda:native.step(np.asarray(action,np.float32)),{'env_steps':1})
        with self.egl.observation_scope(observation_phase(step+1)):
            obs=self.meter.call('format_real_next_observation',lambda:self.env._format_raw_obs(raw),
                {'observation_calls':1,'control_observation_calls':1})
        self.steps+=1;self.actions.append(action);self.actions=self.actions[-4:]
        success=bool(info.get('success',False));key=digest(raw_plan)
        if key not in self.plan_refs:
            self.plan_refs[key]=wire_ref(self.store.write('plans/referenced_'+key+'.f32',raw_plan),'float32_le_50x4')
        from public_records import make_transition
        self.pending=make_transition(self,raw_plan,raw_index,action,reward,success,terminated,truncated,step,key)
        return obs,dict(success=success,terminated=bool(terminated),truncated=bool(truncated),
            technical_failure=bool(native._did_see_sim_exception))
    def capture(self,step,raw,age):
        self.last_cut_raw=raw
        state=self.meter.call('full_state_capture',lambda:capture(self,step,raw,age),{'full_state_captures':1})
        self.meter.call('persist_cut_state',lambda:self.store.json('CUT_STATE.json',state),{'state_document_writes':1})
        return state
    def save_reference(self,state):
        self.meter.call('persist_reference_state',lambda:self.store.json('CUT_REFERENCE.json',dict(source_signature=self.source_signature,state=state,
            prefix_records=self.prefix_records,prefix_plan_SHAs=self.prefix_plan_shas,prefix_noise_SHAs=self.prefix_noise_shas)),{'state_document_writes':1})
    def verify_prefix(self,reference):
        if reference['source_signature']!=self.source_signature or reference['prefix_records']!=self.prefix_records or reference['prefix_plan_SHAs']!=self.prefix_plan_shas or reference['prefix_noise_SHAs']!=self.prefix_noise_shas:
            raise ContractError('source/prefix/image/feature/action identity mismatch')
    def save_verification(self,record):
        self.store.json('STATE_VERIFICATION.json',record)
        self.verification=record
    def compare_state(self,reference,observed):
        from full_state import compare
        return self.meter.call('full_state_compare',lambda:compare(reference,observed),
            {'full_state_comparisons':1,'state_field_digest_calls':2*len(observed['fields'])})
    load_bank=verified_load_bank
    def finish(self,result):
        if result['outcome']['outcome_complete']:
            self.meter.call('completed_finite_parent_outcome',lambda:None,{'completed_rollouts':1})
        self.store.json('BRANCH_RESULT.json',result)
        from sidecar_output import emit_sidecar
        emit_sidecar(self,result)
    def close(self):
        if self.env is not None:self.env.close()
