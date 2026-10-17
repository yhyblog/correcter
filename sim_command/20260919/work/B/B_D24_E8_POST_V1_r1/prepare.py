"""Freeze the authorized paired-source Post jobs without model/simulator entry."""
import ast
import hashlib
import json
from pathlib import Path
import secrets
import d24_common as d


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    d.authorize(admission=True)
    for p in d.W.glob('*.py'):
        ast.parse(p.read_text(),filename=str(p))
    old=d.C/'work/B/B_D24_RECOVERY_V1_r1'
    xbatch=d.load(old/'XVLA_EVAL_BATCH.json')
    xcfgs=[d.load(job['config']) for job in xbatch['jobs']]
    sources=sorted([row for cfg in xcfgs for row in cfg['episodes']],key=lambda row:(row['task_id'],row['episode']))
    assert len(sources)==len({row['source_id'] for row in sources})==500
    original=d.load(d.C/'work/B/B_D24_SPRINT_V1_r1/GPU_N_BATCH.json')
    scfgs=[d.load(job['config']) for job in original['jobs'] if job['job_id'].startswith('smol50k_N')]
    smol_sources=[row for cfg in scfgs for row in cfg['episodes']]
    keys=('source_id','task','task_id','episode','reset_seed','policy_seed','split')
    assert {tuple(row[k] for k in keys) for row in smol_sources}=={tuple(row[k] for k in keys) for row in sources}
    frozen_sources=d.W/'POST_SOURCES.json'
    d.exclusive(frozen_sources,dict(status='frozen_before_Post',at_utc=d.utc(),sources=sources,
        origin_x_batch=str(old/'XVLA_EVAL_BATCH.json'),origin_smol_batch=str(d.C/'work/B/B_D24_SPRINT_V1_r1/GPU_N_BATCH.json'),
        outcome_selection=False,new_development_sources=0))
    baselines={}
    for model,prefix in [('smolvla','smol50k_N'),('xvla','xvla30k_N')]:
        rows={}
        for job in sorted((d.PARENT_R/'jobs').glob(prefix+'*')):
            p=job/'episodes.jsonl'
            if not p.exists():continue
            for line in p.read_text().splitlines():
                row=json.loads(line)
                if row.get('status')!='complete' or type(row.get('success')) is not bool:continue
                sid=row['source_id']
                if sid in rows:raise ValueError('Duplicate completed baseline identity: '+model+'/'+sid)
                rows[sid]=dict(row,origin_rows=str(p))
        assert len(rows)==(496 if model=='smolvla' else 500)
        baselines[model]=list(rows.values())
    baseline_index=d.W/'VALID_N_INDEX.json'
    d.exclusive(baseline_index,baselines)
    engine=d.load(d.W/'ENGINE_CONFIG.json')
    engine.update(task_id='B_D24_EXTENSION_REMAINDER_V1',source_count=500,
        methods=['Post'],renderer='B native MW Mesa via unchanged Smol/X runtime',
        training_coverage='frozen pi05 historical five-task D/G0/Q transferred to Smol/X MT50 commands',
        holder_policy='whole_wave_all_holders_off',e8_native_queue=10,
        post_metric='original pi05 clean-action metric; physical commands provided by external base')
    d.atomic(d.W/'ENGINE_CONFIG.json',engine)
    configs=d.W/'configs';configs.mkdir(exist_ok=True)
    run='D24_E8_MW_POST_r1'
    jobs=[]
    for model,first,gpu_offset,label in [('smolvla',scfgs[0],0,'smol50k'),('xvla',xcfgs[0],4,'xvla30k')]:
        checkpoint=Path(first['checkpoint'])
        meta=d.load(checkpoint/'config.json')
        assert meta['input_features']['observation.state']['shape']==[4]
        assert meta['output_features']['action']['shape']==[4]
        assert meta['chunk_size']==first['H']
        for worker in range(4):
            job_id='%s_Post_shard%d_r1'%(label,worker)
            output=d.R/'jobs'/job_id
            if (d.R/'claims'/(job_id+'.json')).exists():raise ValueError('Consumed Post claim')
            selected=[row for row in sources if row['task_id']%4==worker]
            cfg=dict(job_id=job_id,run_id=run,kind=model,method='Full-Post-transfer',
                checkpoint=str(checkpoint),checkpoint_config_sha256=sha(checkpoint/'config.json'),
                checkpoint_weight_bytes=(checkpoint/'model.safetensors').stat().st_size,
                H=first['H'],K=10,NFE=10,action_dim=4,state_dim=4,max_steps=300,
                output=str(output),episodes=selected,source_table=str(frozen_sources),
                source_table_sha256=sha(frozen_sources),base_environment='mw-'+model+'-lr044',
                base_config=str(d.W/'BASE.json'),engine_config=str(d.W/'ENGINE_CONFIG.json'),
                seed_namespace=engine['seed_namespace'],socket_path='/tmp/corrector_B_E8P_r1/'+job_id+'.sock',
                ipc_auth=secrets.token_hex(16),formal_gpus=[gpu_offset+worker],max_interventions=1,commitment=10,
                transfer_disclosure=engine['training_coverage'],no_base_SFT=True,new_development_attempts=0,
                scientific_retries=0,automatic_retry=False)
            cp=configs/(job_id+'.json');d.exclusive(cp,cfg)
            xdg=Path('/tmp/corrector_B_D24_xdg')/job_id;xdg.mkdir(mode=0o700,parents=True,exist_ok=True)
            jobs.append(dict(job_id=job_id,kind=model,config=str(cp),gpus=cfg['formal_gpus'],
                output=str(output),timeout_seconds=43200,
                argv=['/usr/bin/python',str(d.W/'post_job.py'),'--config',str(cp)],
                env=dict(XDG_RUNTIME_DIR=str(xdg),PYTHONDONTWRITEBYTECODE='1')))
    batch=dict(batch_id=run,run_id=run,kind='gpu',max_workers=8,jobs=jobs,hold_idle=False,
        formal_holder_policy='all holders off until entire wave and all descendants exit',
        handoff_timeout_seconds=300,baseline_index=str(baseline_index),
        budget=dict(prior_B_conservative_physical_attempts=3727,new_Post_attempts=1000,
            B_after_this_wave_upper_bound=4727,parent_B_cap=16000,continuation_cap=6000,
            new_optimizer_updates=0,new_development_attempts=0),
        followed_by='LIBERO Post adaptation when ready; then readyVelocity; event handler follows latest B task')
    path=d.W/'MW_POST_BATCH.json';d.exclusive(path,batch)
    d.exclusive(d.W/'ADMISSION.json',dict(at_utc=d.utc(),status='prepared_not_yet_launched',
        authorization_sha256=d.CONT_SHA,parent_authorization_sha256=d.AUTH_SHA,
        source_count_per_model=500,planned_physical_attempts=1000,useful_GPU_workers=8,
        checks=['native4D state/action; existing frozen weights','same original500sources and seeds for both baselines',
            'no valid N replay','original pi05 feature extractor in separate supported environment',
            'native full chunk generation uses existing select_action implementation pathway',
            'actual RGB validity guard and once-only true G0/C10 Post','no base/test fitting'],
        budget=batch['budget'],libraries_note='Existing base and corrector environments isolated by local authenticated IPC',
        resource_basis='Prior same-node8resident pi05 succeeded; each80GB GPU adds one existing small base; ordinary host snapshot recorded at launch',
        runtime_limits='No claim of bitwise identity to N without actual trajectory observation; matched source/seed/native protocol; diagnostic costs included'))
    print(json.dumps(dict(batch=str(path),jobs=len(jobs),episodes=sum(len(d.load(j['config'])['episodes']) for j in jobs),
        base_N_counts={k:len(v) for k,v in baselines.items()}),indent=2))


if __name__=='__main__':main()
