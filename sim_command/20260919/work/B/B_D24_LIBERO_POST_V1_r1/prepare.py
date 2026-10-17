"""Freeze native adaptation sources and eight-worker pipeline before execution."""
import hashlib
from pathlib import Path
import d24_common as d


def main():
    run='D24_E8_LIBERO_POST_r1';pipeline=d.R/run;batch_path=d.W/'LIBERO_POST_BATCH.json'
    if batch_path.exists():raise RuntimeError('Prepared configuration already exists')
    pipeline.mkdir(exist_ok=False);(d.W/'configs').mkdir(exist_ok=False)
    checkpoint=d.ROOT/'embodied-ai-workspace/models/reference/pi05-libero-official'
    norm=checkpoint/'assets/physical-intelligence/libero/norm_stats.json'
    adaptation=dict(feature_version='official-LIBERO-prefix-mean-fixed-RP329-v1',feature_projection_seed=9221701,
        feature_description='native SigLIP token means per camera projected to64; native prompt embedding mean to128; own norm state8; remaining fraction1; zero-mask padded camera',
        intervention_step=20,intervention_rule='once at fixed natural replan after20 executed policy commands; five XYZ/gripper commands, native K5 thereafter; no trigger/replan extra call',
        metric='official LIBERO action quantiles: S=(q99-q01)/2, physical-command direction S^2 grad_Q',
        post_xyz_command_rms=.02,post_xyz_command_cap=.06,post_xyz_metres_rms=.001,post_xyz_metres_cap=.003,
        post_grip_command_rms=.1,post_grip_command_cap=.2,boundary_margin=.02,
        dev_xyz_command_amplitude=.6,
        dev_candidates='a0 and two parent-seeded antithetic xyz directions; second pair also commands opposite gripper signs; rotations and tail unchanged',
        fit_seeds=[9301,9302,9303,9304],fit_steps=4000,fit_batch_size=64,fit_lr=.0003,fit_weight_decay=.001,
        fit_architecture=[399,128,64,1],fit_loss='BCE logits with train-only class weight',
        train_tasks_per_suite=list(range(6)),validation_tasks_per_suite=[6,7],test_guided_selection=False,
        fixed_train_feature_standardization='train parents only; min feature std .05',
        missing_contrast='block fitting/test if fewer than40 valid rows/8 train parents or only one true train outcome class',
        label='Post-operator-transfer-native-LIBERO; no D/G0; not Full',
        inherited_MW_features_or_weights=False,base_model_fitting=False,rotation_correction=False)
    original=d.load(d.C/'work/B/B_D24_SPRINT_V1_r1/GPU_N_BATCH.json')
    originals=[d.load(j['config']) for j in original['jobs'] if 'libero' in j['job_id']]
    jobs=[];configs=[];dev=[];tests=[]
    for suite_index,old in enumerate(originals):
        for shard in range(2):
            index=2*suite_index+shard;jid='pi05official_Post_'+old['suite']+'_s%d_r1'%shard
            output=d.R/'jobs'/jid;output.mkdir(exist_ok=False)
            cfg=dict(old);cfg.update(job_id=jid,run_id=run,method='Post-operator-transfer-native-LIBERO',
                worker_index=index,output=str(output),pipeline_output=str(pipeline),batch_path=str(batch_path),
                port=28240+index,episodes=[s for s in old['episodes'] if s['task_id']%2==shard],
                development=[],adaptation=adaptation,norm_stats=str(norm))
            for task in range(shard,8,2):
                parent='D24_LIBERO_DEV_v1_%s_t%02d'%(old['suite'],task)
                for candidate in range(5):
                    source=dict(source_id=parent+'_c%d'%candidate,parent_id=parent,task_id=task,
                        split='adapt_train' if task<6 else 'adapt_validation',candidate_id=candidate,
                        reset_seed=45100000+suite_index*100000+task*1000,
                        policy_seed=55100000+suite_index*100000+task*1000,
                        candidate_seed=65100000+suite_index*100000+task*1000)
                    cfg['development'].append(source);dev.append(dict(source,suite=old['suite']))
            tests.extend(dict(s,suite=old['suite']) for s in cfg['episodes'])
            path=d.W/'configs'/(jid+'.json');configs.append((path,cfg))
            jobs.append(dict(job_id=jid,config=str(path),argv=['/usr/bin/python',str(d.W/'libero_job.py'),'--config',str(path)],
                gpus=[index],timeout_seconds=43200,output=str(output),kind='pi05_libero_native_Post',env={}))
    assert len(jobs)==8 and len(dev)==160 and len({s['parent_id'] for s in dev})==32
    assert len(tests)==400 and len({s['source_id'] for s in tests})==400
    assert not {s['source_id'] for s in dev}&{s['source_id'] for s in tests}
    assert not {(s['suite'],s['task_id'],s['reset_seed']) for s in dev}&{(s['suite'],s['task_id'],s['reset_seed']) for s in tests}
    workers=[j['output'] for j in jobs]
    for path,cfg in configs:
        cfg['worker_outputs']=workers;d.exclusive(path,cfg)
    baseline={}
    old_summary=d.load(d.PARENT_R/'D24_LIBERO_UNSTARTED_r3/N_INCREMENTAL_SUMMARY.json')
    for ref in old_summary['inputs']:
        if 'pi05official_N_libero_' not in ref['path']:continue
        path=Path(ref['path'])
        for line in path.read_text().splitlines():
            import json
            row=json.loads(line)
            if row['status']=='complete' and type(row.get('success')) is bool:
                if row['source_id'] in baseline:raise ValueError('Duplicate complete N source')
                baseline[row['source_id']]=row
    assert len(baseline)==394
    # No baseline outcomes are passed into the collector or fitter.
    bpath=d.W/'N_VALID_BASELINE.json';d.exclusive(bpath,list(baseline.values()))
    budget=dict(prior_B_attempts=4727,new_dev_attempts=160,new_test_attempts=400,max_new_attempts=560,
        cumulative_B_max=5287,node_attempt_cap=16000,continuation_attempts_including_prior_MW=1560,
        continuation_attempt_cap=6000,prior_small_network_updates=222000,new_small_network_updates=16000,
        cumulative_updates_max=238000,small_network_cap=500000,continuation_small_network_cap=100000,
        base_model_SFT_updates=0,development_parent_cap=40,development_rollout_cap=200,
        current_new_dev_parents=32,current_new_dev_rollouts=160,retries_reserved_not_scheduled=40)
    batch=dict(batch_id=run,run_id=run,kind='gpu',max_workers=8,jobs=jobs,adaptation=adaptation,
        norm_stats=str(norm),baseline_index=str(bpath),budgets=budget,automatic_retry=False,
        physical_rollout_attempts=560,all_holders_off_entire_wave=True)
    d.exclusive(batch_path,batch)
    d.exclusive(d.W/'PREPARED.json',dict(at_utc=d.utc(),batch=str(batch_path),
        batch_sha256=hashlib.sha256(batch_path.read_bytes()).hexdigest(),parent_authorization_sha256=d.AUTH_SHA,
        continuation_sha256=d.CONT_SHA,norm_sha256=hashlib.sha256(norm.read_bytes()).hexdigest(),
        source_split='32 new parent identities; 24 train/8 descriptive validation; fixed400 test reused only for evaluation',
        no_completed_science_replay=True,budgets=budget,
        prior_capacity='8 H10080GB; 1.6TiB available host RAM; prior eight pi05 servers fit; no new GPU preflight',
        mechanism='eight resident native servers -> 160 development attempts -> CPU final-step heads ->400 Post tests',
        native_feature_scope='LIBERO weights/normalizer only, no MW feature or head transfer',
        code_refs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in d.W.glob('*.py')}))
    (d.W/'METHOD.md').write_text('''# LIBERO Post operator transfer, frozen before development

Official pi05 LIBERO checkpoint and its own normalizer stay frozen. Native H10/K5, NFE10, action7/state8,
and the original four-suite random reset protocol are retained. No base SFT, MetaWorld features, D, or G0.

32 new development parents (8 tasks per suite) each execute five full rollouts: a0 and two antithetic
XYZ direction pairs, the second pair also uses opposite gripper commands. Intervention is at the natural
replan after 20 executed commands. Each candidate changes only the next five XYZ/gripper commands.
Environment/policy seeds are shared within each parent; all candidate attempts count. Development
perturbations explore a wider action interval than the small test-time correction. Labels are actual
terminal success; failed execution and episodes ending before the cut supply no training example.

Tasks 0-5 per suite train the heads; tasks 6-7 provide descriptive validation only. Parent-level separation
is fixed before collection. Four CPU MLP members fit for exactly 4000 updates each, with final checkpoints
used together. No validation checkpoint/threshold/radius selection, and no test outcomes enter fitting.
Insufficient real outcome contrast blocks test admission rather than fabricating a success critic.

Features use frozen native LIBERO prefix embeddings: per-view SigLIP token means, masked prompt-token
mean, native state8 and remaining-step fraction. Fixed Gaussian projection compresses embeddings;
feature standardization uses training parents only. Q consumes context and five-command candidate/reference.

At test time, one fixed intervention at command20 follows S^2 grad Q using LIBERO action quantiles.
The OSC XYZ scale is .05 metres per command unit. XYZ correction has .02 command RMS target (1mm)
and .06 component cap (3mm). Gripper uses .10 command RMS/.20 cap, without a physical-unit claim.
Symmetric action-bound margin .02 suppresses corrections at or outside the feasible boundary.
Rotations and chunk rows5-9 stay bit-identical. No extra base query or modified base RNG stream.

The fixed400 test sources match N. Valid394 N rows are reused only for comparison; missing N remains
missing. This is Post operator transfer with own-domain small-head adaptation, not the Full method.
All eight GPUs carry resident independent workers. The entire formal wave, including its CPU-fit barrier,
has no occupancy holders. Completion/failure drains owned descendants and restores the normal guard.
''')
    print(str(batch_path))


if __name__=='__main__':main()
