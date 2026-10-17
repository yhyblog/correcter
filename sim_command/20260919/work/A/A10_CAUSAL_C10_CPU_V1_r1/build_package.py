from pathlib import Path
import json,hashlib,shutil,ast
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919');R=B.parents[2]
P=B/'results/A/A10_CAUSAL_C10_CPU_V1';O=B/'results/A/A10_PV_HANDOFF_CPU_REPAIR_V1';N=B/'results/A/A10_TORCH_UUID_ABI_CPU_REPAIR_V1'
def put(p,t):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:f.write(t)
def jput(p,x):put(p,json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def ref(p):return dict(path=str(p),realpath=str(p.resolve()),size_bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
for d in ['corrector','vendor_vla']:shutil.copytree(O/'code'/d,P/'code'/d,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
for name in ['__init__.py','handoff.py','identity.py','wave_timing.py','process_family.py','contracts.py']:
 t=(O/'code/core'/name).read_text()
 if name=='contracts.py':
  t=t.replace('A10_PV_OFFLINE_PREFLIGHT_V3','A10_CAUSAL_C10_PREFLIGHT_V1').replace('P10_A_PV_OFFLINE_PREFLIGHT_V3','P10_A_CAUSAL_C10_PREFLIGHT_V1').replace('P10_PV_V3','P10_CAUSAL_C10_V1')
  t=t.replace('No current unique offline PV compute authorization','No current unique causal C10 compute authorization').replace('Frozen V3 handoff','Frozen handoff').replace('finite PV budget','finite causal C10 budget')
  t=t.replace("max_retries=0,timeout_seconds=1800,kill_grace_seconds=30,", "max_retries=0,timeout_seconds=1800,kill_grace_seconds=30,branch_order=['Post','Velocity'],branch_attempts_max=2,")
  t=t.replace("for k in ('run_id','wave_id','shard_id'):","if release.get('authorization_identity') != proposal['authorization_identity']:\n        raise ContractError('Frozen identity differs')\n    for k in ('run_id','wave_id','shard_id'):")
  t=t.replace("x=release.get(k)","x=release.get(k)\n        if x != proposal['authorization_identity'][k]:raise ContractError('Wrong unique '+k)")
 put(P/'code/core'/name,t)
put(P/'code/feature_path.py',(O/'code/feature_path.py').read_text())
put(P/'code/native/__init__.py','')
for name in ['native_egl.py','native_egl_bindings.py','cuda_mapping.py','graphics_contract.py','initialization.py']:
 t=(N/'code/core'/name).read_text()
 t=t.replace('from .validation import ContractError','from core.contracts import ContractError').replace('from .resume import sha','from core.contracts import sha')
 if name=='graphics_contract.py':
  for key in ['mujoco_scene_updates','render_calls','rgb_readback_calls']:t=t.replace(repr(key)+': 2',repr(key)+': 17')
 if name=='native_egl.py':
  t=t.replace("phase not in ('diagnostic', 'post_control')","phase not in self.config['observation_phases']")
  t=t.replace("runtime.phase not in ('diagnostic', 'post_control')","runtime.phase not in runtime.config['observation_phases']")
  # The first replacement also hits runtime.phase; correct the bound receiver.
  t=t.replace("runtime.phase not in self.config['observation_phases']","runtime.phase not in runtime.config['observation_phases']")
  t=t.replace('outside the two observation phases','outside a frozen control-observation phase')
 if name=='initialization.py':
  t=t.replace("'model_initializations': 1,", "'model_initializations': 0,")
  t=t.replace("'policy_do_simulation_calls': 1,", "'policy_do_simulation_calls': 16,")
  t=t.replace("'policy_physics_substeps': 13,", "'policy_physics_substeps': 213,")
  t=t.replace("if n_frames != 13:\n                        raise ContractError('First 30Hz control must request 13 physics substeps')", "index = self.used['policy_do_simulation_calls']\n                    expected = ((index + 1) * 400) // 30 - (index * 400) // 30\n                    if n_frames != expected:\n                        raise ContractError('30Hz control substep schedule drifted')")
 put(P/'code/native'/name,t)
put(P/'code/dg_models.py',(R/'ACT-RECAP/src/ac_tmil/future_aware/models.py').read_text())
c=json.loads((O/'config/CONFIG.json').read_text());nc=json.loads((N/'config/INTEGRATION.json').read_text())
c['schema']='causal_C10_preflight_config_v1'
for k in ['cached_diagnostic_sampling_calls']:c.pop(k,None)
c['source']={k:v for k,v in c['source'].items() if k in ['task','env_seed','generation_seed','suffix_seed','split','instruction']}
c['source'].update(source_id='shelf-place-v3-development-causal-cut5-2026091900',parent_source_id='A10-native-queue-diagnostic-shelf-place-v3-2026091900',purpose='development_engineering_only',selection='fixed source and seeds; no outcome replacement',state_equivalence_claim=False,prefix_mode='two_fresh_independent_seeded_replays',restore_seed=2026091903)
c['control']=dict(H=20,C=10,cut=5,monitor_stride=5,max_interventions_per_branch=1,episode_max_steps=300,max_controls_per_branch=16,physics_hz=400,control_hz=30,native_action_scale=0.015,camera='corner2',width=480,height=480,branch_order=['Post','Velocity'],scheduled_engineering_intervention=True)
c['native']=nc
for key in ['mujoco_scene_updates','render_calls','rgb_readback_calls']:nc['graphics_caps'][key]=17
nc['observation_phases']=['step_'+str(i) for i in range(17)]
c['LD_LIBRARY_PATH']=':'.join([nc['isolation_root']+'/isolation/lib',nc['python_library_directory'],'/usr/lib/x86_64-linux-gnu','/lib/x86_64-linux-gnu'])
c['initialization_source_manifest']=str(B/'results/A/A10_PREFLIGHT_REVISION_R2/preflight_v4/external_source_manifest.json')
fa=R/'ACT-RECAP/outputs/act_recap_future_aware_20260914'
c['DG0']=dict(threshold=0.05,target='mean_fresh_minus_old_execute5_then_fixed10',D_horizon=5,G0_output='raw regression mean of two members; no sigmoid',residual_is_G0_input=False,asset_scope='historical five-task development compatibility only',members=[])
weightshas={241:'789c9fdadc25e145fe2609b0aa93c643fcdc9e3d70ff68eb891d2f470bfbcc7f',242:'0bc60db49baeeea438ab856dfc767bc3f80330f00b6c55be27a37a6614150075',341:'f9c156103fb81dad3c6b3aab3e8f3dd005ae397603915cd21f1d87bab5bf194b',342:'2461da240554d9637d2e2c4bfe30743f83a8dbb85039dc71b3c4ea4e16ea6c78'}
for d,g in [(241,341),(242,342)]:
 c['DG0']['members'].append(dict(D_seed=d,G0_seed=g,D_checkpoint=str(fa/f'models/spatial_pair_{d}/finetune_400.pt'),D_sha256=weightshas[d],normalization=str(fa/f'models/spatial_pair_{d}/normalization.json'),G0_checkpoint=str(fa/f'critics/gate_{g}/selected.pt'),G0_sha256=weightshas[g]))
jput(P/'config/CONFIG.json',c)
sh=(O/'commands/run_proposed_pv_offline.sh').read_text().replace(str(O),str(P)).replace('run_proposed_pv_offline.sh','run_proposed_causal_c10.sh')
put(P/'commands/run_proposed_causal_c10.sh',sh)
# Manifest inheritance reads metadata only, never weight bytes.
inp=json.loads((O/'INPUT_MANIFEST.json').read_text())
files=[dict(x,verification_now='inherited accepted PV V3 identity; no weight hash in this CPU task') for x in inp['files'] if not any(z in x['path'] for z in ['observation_step0.npz','raw_plans.npy'])]
for row in c['DG0']['members']:
 for key in ['D','G0']:
  p=Path(row[key+'_checkpoint']);files.append(dict(path=str(p),realpath=str(p.resolve()),size_bytes=p.stat().st_size,sha256=row[key+'_sha256'],verification_now='inherited frozen_selection/complete checkpoint identity; weight bytes not read'))
 files.append(dict(ref(Path(row['normalization'])),verification_now='small normalization JSON read and SHA frozen'))
jput(P/'INPUT_MANIFEST.json',dict(schema='causal_C10_inputs_v1',files=files,cached_step0_used=False,features='rebuild causally at t0..t5; no saved future/cached Q feature',large_weight_hashes_this_CPU_task=0))
# External dependencies from both accepted lineages. Conflicts fail, no heuristic selection.
ext={}
for source in [O/'EXTERNAL_SOURCE_MANIFEST.json',N/'EXTERNAL_SOURCE_MANIFEST.json']:
 data=json.loads(source.read_text())
 for x in data['files']:
  if x['path'] in ext and ext[x['path']]['sha256']!=x['sha256']:raise ValueError('Conflicting inherited dependency '+x['path'])
  ext[x['path']]=dict(x,verification_now='inherited accepted lineage SHA; not rehashed in this CPU task')
# Old manifest wrappers have non-files metadata only; this source is small.
x=Path(c['initialization_source_manifest']);ext[str(x)]=ref(x)
jput(P/'EXTERNAL_SOURCE_MANIFEST.json',dict(schema='causal_C10_external_v1',files=list(ext.values()),inherited_from=[str(O/'EXTERNAL_SOURCE_MANIFEST.json'),str(N/'EXTERNAL_SOURCE_MANIFEST.json')],full_environment_binary_fingerprint=False))
print('New private snapshot created:',P)
print('Inputs',len(files),'external',len(ext),'CUDA/EGL/Torch/env calls: 0')
