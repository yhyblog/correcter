"""Publish the completed B00 inventory atomically; no shared control mutations."""
import csv
import hashlib
import io
import json
from pathlib import Path
import os
from inventory import ROOT, BASE, WS, WORK, now, atomic, record

def hashed(path):
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}

def main():
    receipt=BASE/'receipts/B'
    assert not (receipt/'B00_RESULT.json').exists(), 'Do not overwrite a published result'
    ack=json.loads((receipt/'B00_ACK.json').read_text())
    control=json.loads((BASE/'CONTROL.json').read_text())
    board=json.loads((BASE/'TASK_BOARD.json').read_text())
    assert not control['stop_requested'] and 'B00' in control['allowed_task_ids']
    assert next(t for t in board['tasks'] if t['id']=='B00')['revision']==ack['task_revision']
    host=json.loads((WORK/'host_inventory.json').read_text())
    envs=json.loads((WORK/'environments.json').read_text())
    physical=json.loads((WORK/'physical_paths.json').read_text())
    verified=json.loads((WORK/'asset_verification.json').read_text())
    extra=json.loads((WORK/'extra_asset_verification.json').read_text())
    gpu_rows=list(csv.reader(io.StringIO(host['queries'][0]['stdout']),skipinitialspace=True))
    gpu=[dict(zip(['index','uuid','name','memory_total_mib','driver_version','utilization_percent','memory_used_mib'],row)) for row in gpu_rows]
    ts=now()
    identity=json.loads((BASE/'nodes/B/identity.json').read_text())
    identity.update(updated_at_utc=ts,gpu={'count':len(gpu),'model':gpu[0]['name'],'devices':gpu},environment_summary={'runtimes':{k:v['details'] for k,v in envs.items()},'cpu_and_storage_evidence':str(WORK/'host_inventory.json'),'gpu_functional_verification':False},local_checkpoint_gaps=extra['legacy_tmp_references'])
    identity['shared_mount_check'].update(mount_type='virtio_pfs_010309',mount_source='BF-bytefuse-arnold-recommend',cross_host_visibility='A ACK readable and controller revision 2 registers matching B identity; marker peer read not independently confirmed')
    identity['occupancy_status_source'].update(observed_at_utc=host['observed_at_utc'],host_snapshot=str(WORK/'host_inventory.json'),shared_log_collision_risk=True)
    atomic(BASE/'nodes/B/identity.json',identity)
    official=WS/'models/reference/pi05-libero-official'
    smol=WS/'artifacts/vla-baselines/runs/metaworld/smolvla/mt50-smolvla-s42-mb-20260912-v1/checkpoints/050000'
    libfinal=WS/'artifacts/vla-baselines/runs/libero/pi05/pi05_libero/libero-pi05-s42-ma-20260912-v1/29999'
    baseline_review={
        'recommended':'GAF-v1 pi05/MetaWorld adaptation',
        'decision_status':'proposal_only_not_frozen',
        'reason':'Existing PyTorch sampler and policy-side state/language pathways reduce engineering changes compared with a JAX/OGBench critic bridge; target still needs true success timing.',
        'gaf':{'local_clone':None,'dedicated_environment':None,'local_critic':None,'commit':None,'commit_note':'Remote main read only; B10 must pin an immutable upstream revision.','target':'discounted first-future-success-to-go; MSE','required_fields':['episode/source/parent/split','policy_state','task_text_or_frozen_text_features','actual_actions_and_executed_prefix','per_step_success_or_first_success_step'],'preserve':['MSE','episode split','frozen VLA','ensemble','clip/gate','physical dimension mask'],'change':['SmolVLA to pi05','LIBERO to MT50','state/language features','4D actions and execution horizon','reverse-time sampling hook'],'sources':['https://github.com/ylhaichen/guided-action-flow','https://arxiv.org/html/2607.02092v1','https://github.com/ylhaichen/guided-action-flow/blob/main/scripts/train_critic.py']},
        'qgf':{'local_clone':None,'dedicated_environment':None,'local_critic':None,'commit':None,'target':'chunk IQL, TD Q/target-Q and expectile V','required_fields':['episode/source/parent/split','observations','actual action chunk and length','per-step or aggregated rewards','next observations','terminated','truncated','discount/mask'],'main_gap':'JAX/OGBench to existing PyTorch pi05 gradient interface and task/state mapping require adaptation.','sources':['https://github.com/zhouzypaul/qgf','https://github.com/zhouzypaul/qgf/blob/main/agents/qgf.py']},
        'local_search_scope':[str(ROOT),str(WS/'projects'),str(WS/'projects/upstream'),str(ROOT/'Corrector/references'),str(WS/'environments')],
        'gaf_v3_visual_transformer_implementation':'unconfirmed','qpilots':'not required this campaign','read_at_utc':ts,
    }
    costs=[
        {'item':'common data views and VLA-Corrector interface','engineering_hours_range':[4,8],'gpu_hours':None,'new_collection':'none for existing demonstrations; missing latent extraction needs a later release'},
        {'item':'GAF-v1 interface/version/hook','engineering_hours_range':[8,16],'gpu_hours':None,'new_collection':'use common allocated pool; true success timing required'},
        {'item':'E6 and E1 interface/config','engineering_hours_range':[4,8],'gpu_hours':None,'proposed_E1_training_runs':12,'new_collection':'E1 existing bank reusable; E6 development trajectory availability must be checked'},
        {'item':'SmolVLA/X-VLA E8 interface','engineering_hours_range':[6,12],'gpu_hours':None,'new_collection':'not needed for inventory; trained X-VLA missing, Smol final selection unresolved'},
        {'item':'LIBERO E8 interface','engineering_hours_range':[12,24],'gpu_hours':None,'new_collection':'SFT available; common Corrector trajectory/feature budget pending'},
    ]
    blockers=[
        {'id':'X_MT50_MISSING','affects':['B10','B30'],'gap':'No completed MT50 X-VLA run in authoritative workspace; only base/initialization.','resolution':'Controller supplies a completed checkpoint or assigns a separately budgeted SFT task.'},
        {'id':'SMOL_PARTIAL','affects':['B10','B30'],'gap':'Latest visible MT50 checkpoint is 50000/100000; historical queue interrupted.','resolution':'Freeze 50k with declared training history or explicitly assign continuation; do not auto-resume.'},
        {'id':'LATENT_CACHE_MISSING','affects':['B10','B12'],'gap':'Original VLA-Corrector latent directory no longer exists.','resolution':'Prepare shared demonstration view, then release new feature extraction or provide compatible cache.'},
        {'id':'CRITIC_DATA_FIELDS','affects':['P00','B10','B12'],'gap':'Train600 arrays lack continuous next observations/rewards/termination/first-success timing.','resolution':'Audit original trajectory references; fields absent there must be recorded in the planned common collection pool.'},
        {'id':'PUBLIC_BASELINE_VERSION','affects':['B10','B12'],'gap':'No local GAF/QGF clone or locked commit/critic.','resolution':'B10 pin GAF-v1 and adapters; no bulk data/dependency installation needed for B00.'},
        {'id':'NEW_RELEASE_PENDING','affects':['B10','B11','B12','B13','B20','B21','B30'],'gap':'At publication only A00/B00 are allowed; no subsequent release.','resolution':'Wait for controller P00/dependencies and node-specific release.'},
    ]
    assets={'campaign_id':ack['campaign_id'],'task_id':'B00','revision':1,'role':'B','hostname':ack['hostname'],'session_id':ack['executor_session_id'],'run_id':ack['run_id'],'observed_at_utc':ts,'physical_paths':physical,'environment_evidence':str(WORK/'environments.json'),'host_evidence':str(WORK/'host_inventory.json'),'verification':verified,'extra_verification':extra,'asset_status':[
        {'id':'pi05_mt50','status':'shared_inference_assets_present_cpu_static_checked','path':str(WS/'models/vla-sft-030000'),'full_payload_sha_rechecked':False},
        {'id':'vla_corrector','status':'cpu_weights_and_full_sha_verified','path':str(WS/'models/vla-corrector-h1-k10'),'latent_cache_exists':False},
        {'id':'smolvla_mt50','status':'partial_training_checkpoint_50000','path':str(smol),'target_steps':100000},
        {'id':'xvla_mt50','status':'initialization_only_no_trained_run_found','path':str(WS/'models/initializations/xvla-mt50-s42')},
        {'id':'pi05_libero_official','status':'inference_assets_present_sizes_small_hashes_verified','path':str(official)},
        {'id':'pi05_libero_sft','status':'final_inference_assets_retained_optimizer_payloads_removed','path':str(libfinal),'optimizer_resume_available':False},
    ],'e8_interfaces':{'smolvla':{'H':50,'K':10,'physical_action_dim':4},'xvla':{'H':30,'K':10,'physical_action_dim':4,'internal_action_dim':20,'domain':0},'pi05_libero':{'H':10,'K':5,'action_dim':7,'state_dim':8,'image_count':2,'suites':['libero_spatial','libero_object','libero_goal','libero_10'],'normalization':'bind to selected official or SFT checkpoint; stats differ'}},'baseline_review':baseline_review,'E6_proposal':{'preferred_candidate':'existing D five-step prediction residual','causality':'Compare prediction made at t-5 to actual observation at t only if the conditioned action prefix was truly executed.','threshold':'Select one rule on development data before test; no test feedback.','downstream':'same R, same legal cut checks, max one intervention per episode','alternative':'existing h1/k10 LVM residual with explicit delay/monitor alignment','implementation_status':'proposal only'},'cost_estimates':{'type':'rough engineering estimates, not measured runtime or authorization','items':costs,'gpu_total_hours':None,'reason':'Source counts, update caps, throughput and released budgets are not frozen.'},'blockers_for_later_tasks':blockers}
    atomic(WORK/'B00_ASSETS.json',assets);atomic(receipt/'B00_ASSETS.json',assets)
    report=(WORK/'B00_REPORT.draft.md').read_text()
    assert len(report.splitlines())<=150
    for path in [WORK/'B00_REPORT.md',receipt/'B00_REPORT.md']:
        tmp=path.with_name('.'+path.name+'.tmp');tmp.write_text(report);os.replace(tmp,path)
    for rel in ['CONTROL.json','TASK_BOARD.json']:
        (WORK/('publication_'+rel)).write_bytes((BASE/rel).read_bytes())
    data_refs=[hashed(Path(x['info_file']['path'])) for x in verified['dataset_schemas']]
    data_refs.append(hashed(ROOT/'Corrector/outputs/native10_training_20260916/input_bundles/final_train600_input_v1/manifest.json'))
    config_paths=[WS/'projects/vla-baselines/configs/experiments.json',WS/'models/vla-corrector-h1-k10/config.json',ROOT/'Corrector/docs/Experiment_plam.md',ROOT/'Corrector/docs/NATIVE10_CORRECTOR_ALGORITHM_ZH.md']
    artifacts=[hashed(receipt/'B00_REPORT.md'),hashed(receipt/'B00_ASSETS.json'),hashed(BASE/'nodes/B/identity.json')]
    for name in ['host_inventory.json','environments.json','physical_paths.json','asset_verification.json','extra_asset_verification.json','publication_CONTROL.json','publication_TASK_BOARD.json','inventory.py','verify_assets.py']:
        artifacts.append(hashed(WORK/name))
    result={'campaign_id':ack['campaign_id'],'task_id':'B00','revision':1,'role':'B','hostname':ack['hostname'],'session_id':ack['executor_session_id'],'run_id':ack['run_id'],'status':'complete','started_at_utc':ack['started_at_utc'],'finished_at_utc':ts,'input_identity':{'protocol':ack['inputs_checked'],'control_revision_at_finish':control['revision'],'code':verified['code'],'git_heads':verified['git_heads'],'config':[hashed(p) for p in config_paths],'data':data_refs,'model':[{'path':verified['corrector_cpu_weight_check']['path'],'sha256':verified['corrector_cpu_weight_check']['sha256']},{'path':str(WS/'models/vla-sft-030000/model.safetensors'),'sha256':None,'reason':'Inventory checked size/safetensors structure; full large-weight digest not recomputed.'},{'path':str(smol/'pretrained_model/model.safetensors'),'sha256':None,'reason':'Size/header and checkpoint step checked; full payload digest not recomputed.'}],'remote_baselines':{'commit':None,'reason':'Read-only upstream main and paper review; immutable code freeze belongs to B10.'}},'artifacts':artifacts,'resource_counts':{'simulator_attempts':0,'completed_rollouts':0,'vla_sampling_calls':0,'optimizer_updates':0,'gpu_seconds':0,'model_gpu_inference_calls':0},'resource_scope_note':'Formal B00 experiment counts only; existing occupancy holders continued as required. CPU checkpoint deserialization was not a model inference.','failures_and_retries':[{'command':'cat vla-corrector/reproduction/README.md','exit_code':1,'recovery':'Located and read reproduction/metaworld_very_hard/HANDOFF.md and README.md; no compute launched.'},{'command':'rg against guessed vla-corrector/src/lerobot/policies/safety* and corrector* paths','exit_code':2,'recovery':'Used rg --files and located actual src/siglip_dynamics/inference and src/lerobot/safety paths.'}],'findings':[
        'B is distinct from A; 8 H100 80GB holders active, shared B marker roundtrip passed.',
        'Five pinned runtime prefixes launch CPU metadata inspection; legacy CPU torch weight read passed; no simulator/model inference ran.',
        '3219 manifest entries passed size checks and 955 small-file hashes matched; large payloads were not fully rehashed.',
        'Shared pi05-MT50 and VLA-Corrector weights exist; Corrector full SHA and 42509568 finite CPU parameters verified, original latent cache missing.',
        'SmolVLA MT50 has step50000 intermediate checkpoint; completed X-VLA MT50 checkpoint was not found in authoritative workspace.',
        'Official and final-SFT pi05-LIBERO inference assets and four-suite assets exist; final SFT optimizer payloads were previously removed.',
        'Train600 has five tasks and candidate/terminal-label features, not a complete critic transition dataset.',
        'Recommend GAF-v1 MSE/success-to-go adaptation; no local clone/locked critic and no auto-deployment; QGF chunk IQL is an alternative.',
        'E6 can prepare one causal D5 residual detector sharing R; LVM k10 requires explicit monitoring-delay alignment.',
        'Historical /tmp checkpoint references are absent on B; two shared processor replacements match old SHAs; later work awaits release.'
    ],'blockers':blockers,'next_task_proposal':{'task_id':'B10','scope':'public data views, one critic interface, E6/E1/E8 CPU preparation and compute quotation','requires':['P00 frozen interface','CONTROL allow','B-specific release'],'dispatch_state_at_finish':'waiting'},'checks':{'cuda_initialized_during_cpu_check':verified['cuda_initialized_after'],'new_training_started':False,'model_inference_started':False,'simulator_started':False,'shared_code_or_environments_modified':False,'report_lines':len(report.splitlines())}}
    atomic(WORK/'B00_ARTIFACT_MANIFEST.json',{'campaign_id':ack['campaign_id'],'task_id':'B00','revision':1,'run_id':ack['run_id'],'artifacts':artifacts})
    atomic(WORK/'complete.json',{'status':'complete','run_id':ack['run_id'],'artifact_manifest':hashed(WORK/'B00_ARTIFACT_MANIFEST.json'),'completed_at_utc':ts})
    heartbeat=json.loads((receipt/'B00_HEARTBEAT.json').read_text());heartbeat.update(status='complete',updated_at_utc=ts,progress='B00 receipts published; waiting for next released B task');atomic(receipt/'B00_HEARTBEAT.json',heartbeat)
    atomic(WORK/'B00_RESULT.json',result)
    atomic(receipt/'B00_RESULT.json',result)
    print(json.dumps({'result':str(receipt/'B00_RESULT.json'),'status':'complete','report_lines':len(report.splitlines()),'artifact_count':len(artifacts),'blockers_are_for_later_tasks':len(blockers)},ensure_ascii=False))

if __name__=='__main__':
    main()
