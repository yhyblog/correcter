"""Changed-path synthetic checks only; no optimizer update, GPU or environment."""
from pathlib import Path
import ast,copy,json,sys
import paths
from paths import ROOT
from qio import read,new_json,utc
from selection import choose_development,engine_config
from train_pair import paired_seed

def main():
 checks={}
 for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text(),filename=str(p))
 checks['changed_package_AST']=True
 cfg=read(ROOT/'config/CONFIG.json');assert len(cfg['cells'])==60 and sum(c['planned_episodes'] for c in cfg['cells'])==9600
 jobs=read(ROOT/'JOB_INDEX.json')['jobs'];assert len(jobs)==1920
 checks['frozen_60_cells_9600_sources_1920_jobs']=True
 from admission import validate_job
 for stage in ['DEV','ABLATION','MAIN','ONCE']:
  c=next(c for c in cfg['cells'] if c['stage']==stage);j=next(j for j in jobs if j['job_id'].startswith(c['cell_id']+'_'))
  validate_job(read(j['path']),stage_gate=False)
  if stage!='DEV':
   try:validate_job(read(j['path']))
   except FileNotFoundError:pass
   else:raise AssertionError('test admitted before dev selection')
 checks['four_real_job_paths_and_test_selection_guard']=True
 mapping=read(ROOT/'RESOURCE_PLAN.json')['worker_mapping'];assert len(mapping)==24 and all(sum(x['logical_CUDA_index']==g for x in mapping)==3 for g in range(8))
 source=(ROOT/'code/resident_worker.py').read_text();assert "base['device_list'][a.slot%8]" in source and 'device=egl.bind_policy(torch)' in source
 checks['actual_worker_slot_mod8_UUID_mapping']=True
 dev=read(ROOT/'SOURCE_INDEX.json')['source_sets']['DEV'];rows=[]
 for c in cfg['cells']:
  if c['stage']!='DEV':continue
  for s in dev:rows.append(dict(s,cell_id=c['cell_id'],status='complete',success=(s['ordinal']<10)))
 choice=choose_development(rows,dev);assert choice['chosen_loss']=='L00'
 rows2=copy.deepcopy(rows)
 for r in rows2:
  if '_L01_' in r['cell_id']:r['success']=True
 choice=choose_development(rows2,dev);assert choice['chosen_loss']=='L01' and choice['fixed_fit_seed']==9101
 try:choose_development(rows2[:-1],dev)
 except ValueError:pass
 else:raise AssertionError('missing dev denominator accepted')
 checks['real_selection_balancing_exact_tie_and_missing_rejection']=True
 assert len({paired_seed(9101,1041,'initialization') for _ in ['L00','L10','L01','L11']})==1
 assert paired_seed(9101,1041,'minibatches')!=paired_seed(9102,1041,'minibatches')
 train=(ROOT/'code/train_pair.py').read_text();assert 'model=copy.deepcopy(initial)' in train and 'TenStepCritic(preprocessing)' in train and 'from_state(' not in train and 'range(4000)' in train and '(4000,32)' in train
 checks['paired_fresh_initialization_and_batch32_AST']=True
 import numpy as np,torch
 from corrector.critic import TenStepCritic
 from loss_formula import e1_loss
 torch.set_num_threads(2)
 prep=dict(norm_mean=torch.zeros(4096),norm_std=torch.ones(4096),residual_scale=torch.tensor([.15,.15,.15,.4]),visual_center=torch.zeros(8192),visual_basis=torch.zeros(8192,16),visual_scale=torch.ones(16),language_center=torch.zeros(2048),language_basis=torch.zeros(2048,8),language_scale=torch.ones(8))
 q=TenStepCritic(prep).requires_grad_(True)
 assert sum(p.numel() for p in q.parameters() if p.requires_grad)==7058
 logits=torch.tensor([[.1*j for j in range(13)],[-.1*j for j in range(13)]])
 y=torch.tensor([[[float((i+j+k)%2) for k in range(4)] for j in range(13)] for i in range(2)])
 cw=torch.ones(2,13);gw=cw.clone();gw[:,0]=0;pw=torch.ones(2,5)
 parts={l:e1_loss(logits,y,candidate_weights=cw,gain_weights=gw,pair_weights=pw,gain_enabled=l in ['L10','L11'],pair_enabled=l in ['L01','L11']) for l in ['L00','L10','L01','L11']}
 assert torch.allclose(parts['L11']['loss'],parts['L00']['loss']+parts['L11']['gain_mse']+.5*parts['L11']['pair_mse'])
 checks['real_Q_all7058_trainable_real_four_loss_formula_no_updates']=True
 from controller import run_episode
 from recorder import record
 class Runtime:
  def frame(self):return np.zeros((2,2,3),np.uint8)
  def proprio(self):return np.zeros(4,np.float32)
  def step(self,action,t):return dict(reward=0.,success=False,done=t==39)
 class Engine:
  namespace=cfg['seed_namespace']
  def language(self):return None
  def start_natural_stream(self,seed):pass
  def propose_natural(self):return np.zeros((50,4),np.float32),dict(policy_calls=1,seconds=0.)
  def context(self,*a):return None
  def monitor(self,*a):return {'gate':.5}
  def intervene(self,*a):return np.zeros((50,4),np.float32),dict(policy_calls=1,seconds=0.)
 out=ROOT/'checks';out.mkdir(exist_ok=True)
 for mode in ['G0-multi','G0-once']:
  events=[];src=dev[0];identity=dict(source_id=src['source_id'],task=src['task'],cell_id='synthetic',H=10,mode=mode,branch='Post')
  def emit(kind,event):
   events.append((kind,event));record(out/(mode+'.jsonl'),identity,kind,dict(event,synthetic=True))
  row=run_episode(Runtime(),Engine(),src,'Post',10,emit,mode=mode)
  assert row['first_cut']==5 and row['interventions']==(3 if mode=='G0-multi' else 1)
  assert all(b-a>=10 for a,b in zip(row['intervention_cuts'],row['intervention_cuts'][1:]))
 try:run_episode(Runtime(),Engine(),dev[0],'Post',10,lambda *a:None,mode='Random-multi')
 except ValueError:pass
 else:raise AssertionError('revoked random mode accepted')
 checks['real_controller_recorder_multi_once_lock_firstcut_and_Random_rejection']=True
 new_json(ROOT/'TARGETED_CPU_CHECK.json',dict(utc=utc(),status='PASS',checks=checks,synthetic=True,optimizer_updates=0,real_model_forwards=0,GPU_calls=0,environment_calls=0,claim_calls=0))
 print(json.dumps(checks))
if __name__=='__main__':main()
