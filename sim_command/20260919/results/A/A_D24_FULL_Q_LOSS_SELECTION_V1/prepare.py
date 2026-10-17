from pathlib import Path
import hashlib,json
from collections import Counter
R=Path(__file__).resolve().parent;B=R.parents[2];W=B.parents[2];OLD=B/'results/A/A_D24_MULTI_PRIMARY_VALIDATION_V1'
def load(p):return json.loads(Path(p).read_text())
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 tr=W/'Corrector/outputs/native10_training_20260916/input_bundles/final_train600_input_v1/train'
 train=load(tr/'rows.json');dev=load(B/'results/A/A_D24_CORE_REMAINDER_V1/config/E6_SOURCES.json')['development'];test=load(B/'work/B/B_D24_E1_EVAL_V1_r1/TEST_SOURCES.json')['rows']
 main=[s for s in load(B/'results/A/A_D24_MAIN_ONCE_V1/config/TEST_SOURCES_V1.json')['rows'] if 0<=s['ordinal']<10]
 sets={'DEV':dev,'ABLATION':test,'MAIN':main,'ONCE':main};ident=lambda rows:{(s['task'],s['env_seed']) for s in rows}
 assert len(train)==600 and all(s['split']=='train' for s in train)
 assert len(dev)==100 and set(s['env_seed'] for s in dev)==set(range(2026111600,2026111700))
 assert len(test)==50 and len(main)==500 and all(s['split']=='development' for s in dev)
 assert not ident(train)&ident(dev) and not ident(train)&ident(test) and not ident(dev)&ident(test) and not ident(dev)&ident(main)
 for rows in sets.values():assert len(rows)==len(ident(rows))==len({s['source_id'] for s in rows})
 save(R/'SOURCE_INDEX.json',{'source_sets':sets,'train_rows':str(tr/'rows.json')})
 save(R/'SPLIT_CHECK.json',{'train':600,'development':100,'ablation_test':50,'main_test':500,'train_dev_test_identity_overlap':0,'five_dev_task_counts':dict(Counter(s['task'] for s in dev)),'development_field_only':True,'reserve_used':False})
 losses=['L00','L10','L01','L11'];fits=[9101,9102,9103];members=[1041,1042,1043,1044]
 tc={'train_arrays':str(tr/'arrays.npz'),'train_rows':str(tr/'rows.json'),'preprocessing_only_assets':str(W/'Corrector/assets/critic'),'trainable_parameters':7058,'modules':['state','action','head','residual','advantage'],'losses':losses,'fit_seeds':fits,'members':members,'batch_size':32,'updates_per_fit':4000,'total_updates':192000,'learning_rate':3e-4,'weight_decay':.01,'clip_norm':1.,'training_processes':12,'CPU_threads_per_process':2,'device':'cpu','paired_seed_domain':'corrector_fullQ_paired_v1','paired_key_excludes_loss':True,'preprocessing_fields':['norm_mean','norm_std','residual_scale']+[f'{n}_{s}' for n in ['visual','language'] for s in ['center','basis','scale']],'old_network_parameters_loaded_into_new_model':False,'fixed_last_update':True}
 save(R/'config/TRAIN.json',tc)
 cfg=load(OLD/'config/CONFIG.json');cfg.update(task_id=R.name,run_stage='full_Q_train_dev_select_test',methods=['Post','Velocity'],planned_prior_attempts=14896,overall_A_attempt_cap=27000,planned_episodes=9600,max_episodes=10100,modes=['G0-multi','G0-once'],stages=['DEV','ABLATION','MAIN','ONCE'],evaluation_workers=24,workers_per_GPU=3,training_coverage='new complete Q on historical five-task train600; D/G0 frozen five-task models',cpu={'worker_threads':4,'critic_threads':2},cells=[])
 for k in ['e6_threshold','source_table_sha256','selected_model','critic_assets']:cfg.pop(k,None)
 for stage,number in [('DEV',100),('ABLATION',50)]:
  for loss in losses:
   for fit in fits:
    for method in ['Post','Velocity']:
     cfg['cells'].append(dict(cell_id=f'{stage}_{loss}_s{fit}_{method}_H10',stage=stage,mode='G0-multi',method=method,H=10,priority=0 if stage=='DEV' else 1,planned_episodes=number,renderer='NVIDIA_EGL',loss=loss,fit_seed=fit,ensemble_key=f'{loss}_s{fit}'))
 for stage,hs,mode in [('MAIN',[10,30,50,20,40],'G0-multi'),('ONCE',[10],'G0-once')]:
  for hi,H in enumerate(hs):
   for mi,method in enumerate(['Post','Velocity']):
    cfg['cells'].append(dict(cell_id=f'{stage}_SELECTED_{method}_H{H}',stage=stage,mode=mode,method=method,H=H,priority=(2+2*hi+mi) if stage=='MAIN' else 12+mi,planned_episodes=500,renderer='NVIDIA_EGL',loss='SELECTED',fit_seed=9101,ensemble_key='SELECTED'))
 assert len(cfg['cells'])==60 and sum(c['planned_episodes'] for c in cfg['cells'])==9600
 save(R/'config/CONFIG.json',cfg);cfgsha=sha(R/'config/CONFIG.json');index=[]
 for cell in cfg['cells']:
  rows=sets[cell['stage']]
  for ti,task in enumerate(sorted({s['task'] for s in rows})):
   sr=sorted([s for s in rows if s['task']==task],key=lambda s:s['ordinal'])
   for j in range(0,len(sr),5):
    jid=f"{cell['cell_id']}_{task}_c{j//5:02d}";job=dict(cell,job_id=jid,task=task,task_order=ti,chunk=j//5,sources=sr[j:j+5],retry=0,configuration_sha256=cfgsha);path=R/'jobs'/(jid+'.json');save(path,job);index.append({'job_id':jid,'path':str(path),'sha256':sha(path)})
 assert len(index)==1920
 save(R/'JOB_INDEX.json',{'jobs':index,'first_evaluations':9600,'job_chunk_maximum':5,'episode_admission_guard':True,'no_completed_unit_replay':True})
 snapshot=load(R/'RESOURCE_SNAPSHOT_INITIAL.json');peak={}
 for line in (OLD/'chain/UTILIZATION.jsonl').open():
  d=json.loads(line)
  for g in d.get('GPUs',[]):
   try:peak[g['uuid']]=max(peak.get(g['uuid'],0),float(g['used_MiB']))
   except (KeyError,ValueError):pass
 base=load(R/'config/BASE.json');size=(Path(base['checkpoint'])/'model.safetensors').stat().st_size
 save(R/'RESOURCE_PLAN.json',{'requested_workers':24,'selected_workers':24,'workers_per_GPU':3,'worker_mapping':[{'worker':i,'logical_CUDA_index':i%8,'gpu_uuid':base['device_list'][i%8]['gpu_uuid']} for i in range(24)],'saved_single_worker_sampled_VRAM_peak_MiB':peak,'not_measured_true_peak':True,'VRAM_engineering_allowance_per_worker_GiB':24,'VRAM_allowance_three_workers_plus_margin_GiB':76,'RAM_engineering_allowance_per_worker_GiB':64,'RAM_allowance_total_plus_manager_GiB':1552,'RAM_allowance_is_not_measured_peak':True,'cgroup_hard_limit':None,'cgroup_unknown_reason':'/sys/fs/cgroup is masked by read-only ext4; actual controller and ancestors unavailable','CPU_affinity_count':len(snapshot['cpu_affinity']),'worker_threads':4,'training_CPU_processes':12,'train_threads_each':2,'loading':'8 distinct GPUs per tranche; next after MODEL_READY; planned episodes proceed during later loads','checkpoint_logical_read_bytes_for_24_loads':24*size,'OS_cache_reuse_guaranteed':False,'storage_required_free_GiB':40,'filesystem_quota':None,'quota_unknown_reason':'statvfs is shared capacity, not project quota','no_separate_preflight':True})
 save(R/'METHOD_FROZEN.json',{'losses':losses,'training':tc,'selection':'equal five tasks x three fits x two branches mean success on complete dev100','tie_auxiliary_counts':{'L00':0,'L10':1,'L01':1,'L11':2},'tie_order':losses,'deployment_fit_seed':9101,'test_can_change_selection':False,'whole_wave_all_holders_off':True,'Random_multi_authorized':False})
 print(json.dumps({'cells':60,'jobs':1920,'first_evaluations':9600,'fits':48,'updates':192000,'workers':24}))
if __name__=='__main__':main()
