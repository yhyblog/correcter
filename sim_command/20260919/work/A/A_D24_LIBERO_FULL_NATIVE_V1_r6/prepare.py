"""Freeze exactly the authorized old development parents/test identities on A."""
import copy
import hashlib
import json
from pathlib import Path
import d24_common as d

def main():
    d.authorize(admission=True)
    target=d.W/'BATCH.json'
    if target.exists():raise RuntimeError('Configuration already frozen')
    source=d.C/'work/B/B_D24_LIBERO_POST_V1_r1/LIBERO_POST_BATCH.json'
    original=d.load(source);configs=[d.load(j['config']) for j in original['jobs']]
    parents={}
    for c in configs:
        for s in c['development']:
            if s['candidate_id']==0:parents[s['parent_id']]=dict(s,suite=c['suite'])
    assert len(parents)==32
    selected=[]
    for suite in sorted({s['suite'] for s in parents.values()}):
        for split,n in [('adapt_train',4),('adapt_validation',1)]:
            selected.extend(sorted((s for s in parents.values() if s['suite']==suite and s['split']==split),
                                   key=lambda s:s['parent_id'])[:n])
    assert len(selected)==20 and sum(s['split']=='adapt_train' for s in selected)==16
    jobs=[];development=[];test_sources=[]
    for old in configs:
        slot=old['worker_index'];cfg=copy.deepcopy(old)
        cfg.update(job_id='A_libero_full_worker%d'%slot,run_id=d.TASK,method='Full-native-LIBERO',
            port=29240+slot,output=str(d.R/'workers'/str(slot)),pipeline_output=str(d.R),
            batch_path=str(target),development=[],frozen_head_ready=str(d.R/'MODEL_READY.json'))
        spec=cfg['adaptation']
        spec.update(intervention_step=None,intervention_rule='D2 mature at native age2; meanG0>.05 once; C5 then discard correction tail and restore K5',
            D_horizon=2,G0_old_actions=3,G0_target='fresh3_then_native5_success - old3_then_native5_success',
            threshold=.05,max_interventions=1,commit=5,
            fit_loss='L11 unweighted BCE+gain_MSE+0.5 pair_MSE; five actual B candidates, one actual outcome each',
            Q_gain_coefficient=1.,Q_pair_coefficient=.5,D_seeds=[241,242],G0_seeds=[341,342],
            D_width=256,G0_width=128,D_feature_dim=192,language_dim=128,proprio_dim=8,
            fit_steps=4000,fit_seeds=[9301,9302,9303,9304],
            label='Full-Post/Full-Velocity native-LIBERO D2/G0-execute3/nativeK5/C5; only after genuine supervision',
            normalization='train-only native192 visual and existing8-state quantile coordinates;329 partition192visual+128language+8state+1remaining',
            D_loss='normalized feature trajectory MSE plus normalized native state trajectory MSE',
            G0_loss='MSE on one-pair observed terminal success difference; fixed final update',
            G0_prediction_input='current causal five-observation history + known old3 actions + D2 forecast of first2 old actions; no mature residual in G0',
            no_test_selection=True)
        for parent in selected:
            if parent['suite']==old['suite'] and parent['task_id']%2==slot%2:
                for branch in ['old','fresh']:
                    s={k:v for k,v in parent.items() if k not in ['candidate_id','source_id']}
                    s.update(source_id=parent['parent_id']+'__A_G0_'+branch,branch=branch)
                    cfg['development'].append(s);development.append(s)
        test_sources.extend(dict(s,suite=cfg['suite']) for s in cfg['episodes'])
        path=d.W/'configs'/('worker%d.json'%slot)
        jobs.append(dict(job_id=cfg['job_id'],config=str(path),argv=['/usr/bin/python',str(d.W/'libero_job.py'),'--config',str(path)],
            gpus=[slot],output=cfg['output'],timeout_seconds=8*3600,kind='A_LIBERO_FULL',env={'VLA_RENDERER':'mesa'}))
        d.exclusive(path,cfg)
    assert len(development)==40 and len(test_sources)==400 and len({s['source_id'] for s in test_sources})==400
    all_outputs=[j['output'] for j in jobs]
    for j in jobs:
        cfg=d.load(j['config']);cfg['worker_outputs']=all_outputs;d.atomic(j['config'],cfg)
    loss_source=d.C/'work/B/B_D24_SPRINT_V1_r1/configs/e1_L11_s9101_m1041.json'
    assert d.load(loss_source)['loss_id']=='L11'
    batch=dict(batch_id=d.TASK,run_id=d.TASK+'_launch_r5',kind='gpu',max_workers=8,jobs=jobs,all_holders_off_entire_wave=True,
        development_prior_attempts=160,development_new_attempts=40,development_cumulative_cap=200,
        development_new_parents=0,planned_test_first_entries=800,physical_attempt_cap=1000,
        scheduled_attempts=840,automatic_retry=False,small_network_update_cap=32000,
        Q_loss=dict(source=str(loss_source),implementation=str(d.C/'work/B/B_INDEPENDENT_PIPELINE_PREP_V1_r1/code/b10_adapters.py'),
                    BCE=1.,gain=1.,pair=.5,pairs=[[1,2],[3,4]],repeats=1,alias_weights='inverse true physical-action aliases within parent/cut'),
        source_post_batch=str(source),source_post_jobs=original['jobs'],deadline_hours=8)
    d.exclusive(target,batch)
    d.exclusive(d.R/'SOURCE_PLAN.json',dict(utc=d.utc(),development=development,test=test_sources,
        development_selection='per-suite train ASCII first4 + validation first1 of existing32; old/fresh independent cold branches',
        paired_prefix_policy_seed=True,new_parent_identities=0,development_prior=160,cumulative_cap=200))
    d.exclusive(d.R/'FROZEN_PROTOCOL.json',dict(utc=d.utc(),batch=str(target),batch_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        science=d.load(jobs[0]['config'])['adaptation'],Q_loss=batch['Q_loss'],test_used_for_design=False,
        B_operator_results_preserved=True,scientific_ready=False,remaining475_closed=True))
    print(target)

if __name__=='__main__':main()
