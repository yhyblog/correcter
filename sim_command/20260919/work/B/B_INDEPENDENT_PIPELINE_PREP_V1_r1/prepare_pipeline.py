"""CPU-only stage preparation. Never imports model/framework/simulator code."""
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path('/mnt/bn/arnold-recommend/yaohaoyang')
C=ROOT/'Corrector/sim_command/20260919'
P=Path(__file__).resolve().parent
OLD=C/'work/B/B10_r1_trial-303225685-trialrun-303225685-worker-0_20260919T150956Z'
W=ROOT/'embodied-ai-workspace'
PY=str(ROOT/'.miniforge3/envs/lerobot/bin/python')
GIB=1024**3
AUTH='d73448042b71ecb06940e8d891caf0ef8bef005018f155ee2743903981992928'


def load(p):return json.loads(Path(p).read_text())
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def ref(p):
    p=Path(p).resolve();return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def dump(name,value):
    p=P/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+'\n')


def inputs():
    configs=[load(p) for p in sorted((P/'configs').glob('e1_*.json'))]
    distinct={v['path']:v for cfg in configs for v in cfg['inputs'].values()}
    verified=[]
    for path,v in distinct.items():
        got=ref(path)
        assert got['sha256']==v['sha256'] and got['bytes']==v['bytes'],path
        verified.append(got)
    cfg=configs[0];rows=load(cfg['inputs']['train_rows']['path'])
    manifest=load(cfg['inputs']['train_manifest']['path'])
    bundle=Path(cfg['inputs']['train_rows']['path']).parent.parent
    dev=load(bundle/'development/rows.json')
    ids={r['episode_id'] for r in rows};dev_ids={r['episode_id'] for r in dev}
    assert len(rows)==len(ids)==600 and not ids&dev_ids
    assert all(r['split']=='train' and r['source_horizon']==10 for r in rows)
    assert sorted(Counter(r['task'] for r in rows).values())==[120]*5
    shapes={}
    with zipfile.ZipFile(cfg['inputs']['train_arrays']['path']) as z:
        for name in z.namelist():
            with z.open(name) as f:
                assert f.read(6)==b'\x93NUMPY'
                version=tuple(f.read(2));n=int.from_bytes(f.read(2 if version==(1,0) else 4),'little')
                header=ast.literal_eval(f.read(n).decode('latin1'))
                shapes[name[:-4]]=dict(shape=list(header['shape']),dtype=header['descr'])
    assert shapes['actions']['shape']==[600,13,10,4]
    assert shapes['outcomes']['shape']==[600,13,4]
    assets=[]
    prior=load(C/'receipts/B/B00_ASSETS.json')
    for a in prior['asset_status']:
        p=Path(a['path']);row=dict(a,currently_exists=p.exists(),resolved=str(p.resolve()))
        row['prior_inventory_status']=row.pop('status');row['verification_now']='stat plus small metadata only; no model load or large weight hash'
        meta=p/'config.json'
        if not meta.exists() and (p/'pretrained_model/config.json').exists():meta=p/'pretrained_model/config.json'
        if meta.is_file():row['config']=ref(meta)
        assets.append(row)
    d=[]
    for member in (241,242):
        base=ROOT/f'ACT-RECAP/outputs/act_recap_future_aware_20260914/models/spatial_pair_{member}'
        files=[]
        for p in sorted(base.iterdir()):
            if p.is_file():
                row=dict(path=str(p),bytes=p.stat().st_size)
                if p.suffix=='.json' and p.stat().st_size<2*1024*1024:row['sha256']=sha(p)
                else:row['verification']='stat only; do not read retained model payload'
                files.append(row)
        d.append(dict(member=member,path=str(base),exists=base.exists(),files=files))
    value=dict(status='E1_inputs_ready',checked_at_utc=datetime.now(timezone.utc).isoformat(),
        train_parents=600,unique_train_parents=600,task_counts=dict(Counter(r['task'] for r in rows)),
        training_env_seeds=[r['env_seed'] for r in rows],train_parent_ids=sorted(ids),
        development_cut_rows=len(dev),development_planned=manifest['summary']['development_planned'],
        train_development_disjoint=True,development_rows_ref=ref(bundle/'development/rows.json'),
        development_rows_not_E6_prediction_traces=True,files_verified=verified,npz_headers=shapes,
        historical_provenance=manifest['source_identities'],feature_contract=manifest['feature_contract'],
        D_members=d,asset_metadata=assets,Q_registration=ref(ROOT/'Corrector/assets/critic/training_registration.json'),
        G0_binding=dict(kind='frozen original G0 used for E6 comparator',D_members=[241,242],
            binding_status='D artifacts located; exact G0 calibration/runtime identity must be sealed with E6 traces',
            do_not_substitute_new_MT50_G0=True),
        CPU_only=True,model_loads=0,optimizer_updates=0,feature_extraction=0,large_weight_rehashes=0)
    dump('INPUT_AUDIT.json',value)
    return value


def resources(gpus,ram,tmp,shared,vram=0,threads=2):
    return dict(gpus=gpus,ram_bytes=int(ram*GIB),tmp_bytes=int(tmp*GIB),
                shared_bytes=int(shared*GIB),vram_bytes_per_gpu=int(vram*GIB),cpu_threads=threads,
                basis='engineering admission reservation, not measured peak')


def main():
    current=load(C/'persistent_queue/CONTROL.json')
    assert current['authorization']['sha256']==AUTH and not current['global_stop']
    overrides={r['path']:r['sha256'] for r in current.get('operational_overrides',[])}
    for name,digest in overrides.items():assert sha(C/name)==digest
    audit=inputs()
    for p in sorted((P/'code').rglob('*.py')):ast.parse(p.read_text(),filename=str(p))
    sources=list((P/'code').rglob('*.py'))+[P/'prepare_pipeline.py']
    # The actual GAF imports come from this frozen source tree, so bind every
    # Python dependency, not just its top-level critic file.
    sources+=list((OLD/'upstream/guided-action-flow/src').rglob('*.py'))
    sources+=[OLD/'upstream_lock.json',OLD/'configs/METHODS.json']
    dump('CODE_SNAPSHOT.json',dict(files=[ref(p) for p in sorted(set(sources))],model_code_imported=False))
    code_hash=sha(P/'CODE_SNAPSHOT.json')
    proposals=[]
    for prefix,sid,task in [('e1_','B13_E1_FIT_TRAIN600_V1','B13'),('gaf_','B12_GAF_FIT_FINALPOOL_V1','B12')]:
        jobs={};totals={}
        for path in sorted((P/'configs').glob(prefix+'*.json')):
            cfg=load(path);jid=cfg['job_id'];out=C/'results/B/stage_runs'/sid/jid
            resource=resources(0,3,.25,.025) if prefix=='e1_' else resources(1,16,4,2,vram=4,threads=4)
            for k,v in cfg['limits'].items():totals[k]=totals.get(k,0)+v
            jobs[jid]=dict(config=ref(path),config_sha256=sha(path),limits=cfg['limits'],input_bindings={},
                argv=[PY,str(P/'code/stage_gate.py'),'--config',str(path),'--stage',
                      str(C/'persistent_queue/stages'/f'{sid}.json'),'--output',str(out),'--execute'],
                cwd=str(P/'code'),output=str(out),resources=resource,
                environment={'CUDA_VISIBLE_DEVICES':''} if prefix=='e1_' else {'CUDA_VISIBLE_DEVICES':'QUEUE_ASSIGNED_B_LOCAL_GPU'},
                timeout_seconds=cfg['timeout_seconds'],termination_grace_seconds=20,
                success=['exit0','status.complete','all operation counts within job caps','final checkpoint exists','immutable publication manifest'],
                failure='consume claim; preserve partial artifacts; no automatic retry; pause affected B stage after 3 same-signature failures')
        proposal=dict(schema='B_once_frozen_stage_proposal_v1',stage_id=sid,task_id=task,owner='B',
            hostname='trial-303225685-trialrun-303225685-worker-0',kind='frozen_training_stage',authorized=False,
            basis_authorization_sha256=AUTH,code_manifest_sha256=code_hash,automatic_retry=False,
            operational_overrides_sha256=overrides,
            jobs=jobs,aggregate_operation_limits=totals,
            max_concurrent_jobs=8 if prefix=='e1_' else 3,holder_reservation='one inherited node reservation across runnable formal tasks/publication; original guard holders released; optional supervised idle-card fill only under current SHA-bound override, never on active formal GPU; confirm own holder descendants exit before model loading; no nested lifecycle',
            readiness='ready_for_once_stage_freeze' if prefix=='e1_' else 'blocked_input',
            missing_inputs=[] if prefix=='e1_' else ['A final same common train pool identity','nonempty disjoint development view','immutable tensor views'],
            missing_engineering=[] if prefix=='e1_' else ['final-pool tensor-view materializer binding/implementation; fit worker itself exists'],
            dependencies=[] if prefix=='e1_' else ['A11 immutable final pool','B11 view schema'],
            local_GPU_admission_verified=False,same_final_common_pool_sha_as_A=None,
            stage_timeout_sum_seconds=sum(j['timeout_seconds']+20 for j in jobs.values()),
            selection='fixed final update; no test selection' if prefix=='e1_' else 'development MSE only',
            independent_seeds=[9101,9102,9103] if prefix=='e1_' else [],
            ensemble_members=[1041,1042,1043,1044] if prefix=='e1_' else [9201,9202,9203],
            ensemble_note='4 losses x 3 full fitting seeds x 4 ensemble members = 48 CPU jobs; unchanged frozen numerical recipe' if prefix=='e1_' else '3 critics make 1 ensemble, not 3 complete method seeds',
            registration='Analysis freezes authorized=true stage under persistent_queue/stages and registers its path/SHA in CONTROL.stage_authorizations once; daemon runs jobs without per-job chat. This proposed schema is not installed in public queue yet.',
            actual_scientific_operations_this_preparation=0)
        dump('proposals/'+sid+'.json',proposal);proposals.append(proposal)

    b11=C/'results/B/B11_COMMON_POOL_VIEWS_CPU_V1'
    stages=[]
    def add(sid,status,deps,blockers,argv=None,**other):
        stages.append(dict(id=sid,owner='B',status=status,dependencies=deps,blocked_input=blockers,
            argv=argv,cwd=str(P/'code'),output=str(C/'results/B/stage_runs'/sid),
            automatic_retry=False,A_runtime_waits_for_this=False,**other))
    add('B13_E1_FIT_TRAIN600_V1','ready_for_once_stage_freeze',[],[],
        proposal_ref=ref(P/'proposals/B13_E1_FIT_TRAIN600_V1.json'),commands_in='proposal.jobs[*].argv',
        complete_fit_seeds=[9101,9102,9103],total_optimizer_updates=192000,
        GPU_jobs=0,concurrency_limit=8,resource_note='Frozen E1 CPU recipe retained; 8 CPU workers do not establish 8-card GPU utilization.')
    add('B13_E6_D5_THRESHOLD','blocked_input',[],['real development D predictions/arrivals/actions/reset trace','frozen original G0 intervention decisions and exact D/G0 identities'],
        argv=['/usr/bin/python',str(P/'code/calibrate_e6.py'),'--manifest',str(C/'results/B/stage_inputs/E6_DEV_TRACE.json'),'--output',str(C/'results/B/stage_runs/B13_E6_D5_THRESHOLD/threshold.json')],
        entry_status='implemented metadata-only command; missing input path is explicitly future input',
        resources=resources(0,2,0,.01),model_calls=0,threshold_selection='closest G0 episode count; ties fewer then higher threshold; all dev including no alarm; no test outcomes',
        required_monitor=dict(D_members=[241,242],arrival_horizon=5,features=4096,action_dim=4,downstream='R',H=10,C=10,max_interventions=1))
    add('B21_E1_E6_H10_EVAL','blocked_engineering_and_input',['B13_E1_FIT_TRAIN600_V1','B13_E6_D5_THRESHOLD'],['P20_B_MECHANISM frozen episode/seed/source and exact G0/D/Q identity'],
        implementation_missing=['new-protocol closed-loop driver connecting frozen D5->R and E1 four loss ensembles','E5 operation accounting and stage-aware queue wrapper'],
        episode_cap=None,released_episodes=0,concurrency_limit=8,
        formula=dict(actions='<=300E',E6_extra_resampling='<=E',VLA_calls_E6='<=31E',E6_D_member_forwards='<=120E',E1_fit_calls='0 during evaluation'),
        source_policy='historical five tasks; shared within-method planned evaluation sources; E is set once by P20, no auto-created seeds',
        available_modules=[ref(P/'code/b10_adapters.py')],resources=resources(1,64,16,4,vram=24,threads=4))
    add('B12_GAF_FIT_FINALPOOL_V1','blocked_input_and_engineering',['A11 immutable final pool','B11'],['final same A pool SHA','train/development tensor materialization'],
        proposal_ref=ref(P/'proposals/B12_GAF_FIT_FINALPOOL_V1.json'),commands_in='proposal.jobs[*].argv',concurrency_limit=3,
        total_optimizer_updates=30000,training_views=dict(state=4,action_shape=[10,4],language=2048,gamma=.99,first_success='action-after state, exponent success_state-start-1'),
        B11_interface_only_ref=ref(b11/'REAL_VIEW_SUMMARY.json'),view_materializer_status='B11 provides immutable indices; tensor writer for final runtime needs binding/implementation; not passed off as existing shell command')
    add('B12_LVM_TOKENS_AND_FIT','blocked_engineering_and_input',['A11 immutable final pool','B11'],['normal demonstration t/t+10 frame eligibility','256x2048 endpoint tokens','finite encoder/train/selection budget'],
        implementation_missing=['released feature extraction and normal-demo trainer connected to queue'],
        resources=resources(1,64,32,16,vram=24,threads=4),concurrency_limit=8,
        bytes_per_frame=256*2048*4,frame_dtype='float32',storage_formula='2097152 * unique needed frames plus manifests/temp; extraction once shared by methods',
        historical_checkpoint=str(W/'models/vla-corrector-h1-k10'),retrain_authorized=False,
        recipe=dict(h_window=1,k_step=10,target='z[t+10]-z[t]',loss='cosine over flattened tokens',split='parent split; never original random frame-pair split'))
    add('B20_EXTERNAL_H10_EVAL','blocked_engineering_and_input',['B12_GAF_FIT_FINALPOOL_V1','B12_LVM_TOKENS_AND_FIT','P20_A immutable evaluation identity'],['P20_B_EXTERNAL immutable source/seed/split/budget'],
        implementation_missing=['GAF denoiser hook + original LVM repeated/cooldown trigger in real new-protocol runtime with E5'],
        concurrency_limit=8,released_episodes=0,episode_cap=None,resources=resources(1,64,16,4,vram=24,threads=4),
        per_E_GAF_caps=dict(actions=300,VLA_calls=30,flow_calls=300,critic_member_forwards=900,action_backwards=300),
        fairness=['same final common pool as A','same checkpoint/normalizer/H10/total horizon/env assets/planned init identities','baseline selection frozen before A test outcomes','host-specific E5; no raw cross-host latency ranking'],
        LVM_trigger='original native safety every step/cooldown10 and repeated interventions; not G0-once')
    add('B30_SMOL50K_CORRECTOR','blocked_engineering_and_input',[],['Smol-specific D/G0/Q views and finite P20_B_SMOL recipe'],
        implementation_missing=['real Smol sampler Post/Velocity hooks','Smol-specific Corrector training/evaluation stage entry'],
        checkpoint=str(W/'artifacts/vla-baselines/runs/metaworld/smolvla/mt50-smolvla-s42-mb-20260912-v1/checkpoints/050000/pretrained_model'),
        no_resume_to_100k=True,sequence=['bind retained50k checkpoint and its own normalizer','freeze feature/D/G0/Q adaptation stage','freeze independent N/R/Post/Velocity evaluation with E5'],
        generated_H=50,executed_K=10,physical_action_dim=4,concurrency_limit=8,episode_cap=None,released_episodes=0,
        resources=resources(1,64,16,4,vram=24,threads=4),legacy_baseline_results_are_current_results=False)
    xout=C/'results/B/stage_runs/B30_XVLA_MT50_SFT/seed42'
    add('B30_XVLA_MT50_SFT','blocked_engineering_and_stage_freeze',[],[],
        implementation_missing=['stage-gated DDP wrapper with inherited reservation, durable scientific claim, entered/completed per-rank counters and cancellation','B-local runtime identities/admission, no standalone GPU probe'],
        backend_argv=[str(W/'environments/mw-xvla-lr044/bin/python'),'-m','accelerate.commands.launch','--num_processes=8','--mixed_precision=bf16',str(P/'code/xvla_train.py'),'xvla','--world-size','8','--run-id','B30-xvla-s42-v1','--output',str(xout),'--execute'],
        backend_code=ref(P/'code/xvla_train.py'),backend_is_queue_entry=False,
        existing_recipe_ref=ref(W/'projects/vla-baselines/configs/experiments.json'),
        seed=42,total_complete_training_seeds=1,updates_proposal=30000,global_batch=64,DDP_rank_count=8,
        per_rank_forward_and_backward_limit_proposal=30000,aggregate_rank_optimizer_attempt_limit_proposal=240000,
        scientific_status='local candidate MT50 adaptation; not claimed exact upstream paper recipe',
        generated_H=30,executed_K=10,NFE=10,physical_action_dim=4,internal_action_dimension=20,
        wall_timeout_proposal_seconds=172800,wall_timeout_basis='engineering ceiling only; no throughput measured',
        resources=resources(8,512,128,80,vram=70,threads=32),
        storage_basis='80 GiB admission proposal must be recalculated against resolved optimizer/shards/checkpoint policy before freeze; not measured',
        budget_status='scientific forward/optimizer cap proposed, dataloader/eval/checkpoint/code identities still require bounded wrapper; not ready for execution')
    add('B30_XVLA_CORRECTOR_EVAL','blocked_engineering_and_input',['B30_XVLA_MT50_SFT'],['trained X checkpoint','X-specific D/G0/Q views and frozen evaluation sources'],
        implementation_missing=['X sampler Post/Velocity hooks','new-protocol E5/runtime wrapper'],
        generated_H=30,executed_K=10,physical_action_dim=4,internal_action_dimension=20,
        resources=resources(1,64,16,4,vram=32,threads=4),concurrency_limit=8,episode_cap=None,released_episodes=0)
    add('B30_PI05_LIBERO_CORRECTOR','blocked_engineering_and_input',[],['choose/freeze local29999 checkpoint + own normalization or official weights + official normalization','LIBERO-specific Corrector views and finite training/eval source recipes'],
        implementation_missing=['JAX/OpenPI R/Post/Velocity integration and 7D action derivative/normalization semantics','D/G0/Q adaptation for state8 and two images','persistent model server+client lifecycle with shared single node reservation and per-job ports/cache/E5'],
        sequence=['freeze one checkpoint history and matching normalizer','freeze feature/D/G0/Q adaptation','freeze suites/source/seed and E5 evaluation independently of MW work'],
        local_checkpoint=str(W/'artifacts/vla-baselines/runs/libero/pi05/pi05_libero/libero-pi05-s42-ma-20260912-v1/29999'),
        official_checkpoint=str(W/'models/reference/pi05-libero-official'),optimizer_resume_available=False,
        interfaces=dict(state_dim=8,action_dim=7,images=2,generated_H=10,executed_K=5,NFE=10,settle_wait_steps=10,
            legacy_suite_action_caps=dict(libero_spatial=220,libero_object=280,libero_goal=300,libero_10=520)),
        existing_baseline_entries=[ref(W/'projects/vla-baselines/launchers/serve_pi05.py'),ref(W/'projects/vla-baselines/launchers/eval_libero.py')],
        old_baseline_evaluations_are_complete_current_method_results=False,concurrency_limit=8,episode_cap=None,released_episodes=0,
        resources=resources(1,64,16,4,vram=32,threads=4),seed_policy='P20 freezes suite/task/init-state/model RNG jointly; do not transplant MetaWorld seeds or 300/4D caps')
    dump('STAGE_DAG.json',dict(stages=stages,root_authorization_sha256=AUTH,B_collection_sources=0,A_runtime_dependencies_on_B=[],
        dispatch='authorized + dependencies-ready FIFO, skipping only blocked stage; independent methods/seeds/shards up to local resource-admitted8; refill after owned descendants exit',
        reservation='one inherited node reservation for runnable formal queue including CPU model jobs; original guard holders released; new supervised auxiliary fill only on genuinely inactive GPUs under current override; stop/reap auxiliaries before original guard resumes after full drain',
        operational_overrides_sha256=overrides,
        auxiliary_gpu_accounting='holder runtime/utilization/duty and handoff recorded separately; scientific counters0 never imply total machine GPU activity0; disclose occupancy in timing comparisons',
        failure='ordinary B failure cannot change A/global stop; retry0, unknown entered claim blocks replay; known partial publication records unstarted work without refill',
        storage=dict(A_next8_floor_bytes=93952475136,ledger_lock='short atomic accounting transaction; never across job or publication',quota='unknown',
            selection_helper=ref(P/'code/resource_admission.py')),
        telemetry=dict(period_seconds=15,per_GPU=['actual utilization','VRAM','active owned tasks','queue length','rolling mean','idle seconds'],log_bytes_cap=32*1024*1024,
            distinguish=['loading','CPU simulation','model inference','dependency wait'],no_GPU_diagnostic_jobs=True),
        environment=ref(OLD/'DEPENDENCIES.json'),model_work_performed=False))
    print(json.dumps(dict(stage_count=len(stages),E1_jobs=len(proposals[0]['jobs']),GAF_jobs=len(proposals[1]['jobs']),input_audit='PASS',scientific_work=0)))


if __name__=='__main__':main()
