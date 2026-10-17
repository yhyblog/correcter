"""Freeze a distinct original400-source native Velocity batch; no refitting."""
import hashlib
import json
from pathlib import Path
import d24_common as d


def main():
    oldw=d.C/'work/B/B_D24_LIBERO_POST_V1_r1';old=d.load(oldw/'LIBERO_POST_BATCH.json')
    run='D24_E8_LIBERO_VELOCITY_r1';out=d.R/run;path=d.W/'LIBERO_VELOCITY_BATCH.json'
    if path.exists():raise RuntimeError('Already prepared, never overwrite frozen configuration')
    cpu=d.load(d.W/'CPU_MAPPING_CHECK.json')
    if cpu['status']!='passed':raise RuntimeError('Native CPU mapping not ready')
    out.mkdir(exist_ok=False);(d.W/'configs').mkdir(exist_ok=False)
    head_ready=d.R/'D24_E8_LIBERO_POST_r1/MODEL_READY.json';ready=d.load(head_ready)
    if hashlib.sha256(Path(ready['model_path']).read_bytes()).hexdigest()!=ready['model_sha256']:raise RuntimeError('Frozen native head changed')
    protocol=dict(method='Velocity-operator-transfer-native-LIBERO',Full_method=False,D_or_G0_present=False,
        intervention_step=20,commitment=5,H=10,K=5,NFE=10,
        flow_times=[.3,.2,.1],alpha=10.,objective='frozen native mean success probability with fixed reference; maximize candidate gradient only',
        injection='v <- v +10*dQ/dv, clean=x-tau*v; native transform and true command clamp; five-command XYZ/gripper mask only',
        basis='historical standalone_v2 guidance alpha10 and times .3/.2/.1, adapted to official JAX H10/native7 using its own normalizer',
        base_policy_rng='one natural call at each K5; guided cut uses same base sample_rng/noise without advancing source stream',
        projection='guided native physical direction clipped to command bounds then identical frozen LIBERO Post projection; raw rotations and tail preserved',
        post_radii=old['adaptation'],checkpoint_selection='existing fixed final-step native head and official base; no selection from Post/test outcomes',
        classifier_arithmetic='float32 with stable sigmoid JVP to avoid cancellation; CPU compared to original frozen NumPy head on archived development only',
        new_optimizer_updates=0,new_development_attempts=0,new_base_SFT=0,
        source_policy='identical original400-source table and seeds from Post/N; no completed Post or N replay')
    jobs=[];configs=[];post=[]
    for i,previous in enumerate(old['jobs']):
        cfg=d.load(previous['config']);jid=previous['job_id'].replace('_Post_','_Velocity_')
        p=d.W/'configs'/(jid+'.json');output=d.R/'jobs'/jid;output.mkdir(exist_ok=False)
        cfg.update(job_id=jid,run_id=run,method=protocol['method'],output=str(output),pipeline_output=str(out),
            batch_path=str(path),port=28260+i,development=[],frozen_head_ready=str(head_ready),velocity_protocol=protocol)
        configs.append((p,cfg));jobs.append(dict(job_id=jid,config=str(p),output=str(output),kind='pi05_libero_native_Velocity',
            argv=['/usr/bin/python',str(d.W/'libero_job.py'),'--config',str(p)],gpus=[i],timeout_seconds=43200,env={}))
        for line in (Path(previous['output'])/'episodes.jsonl').read_text().splitlines():
            row=json.loads(line)
            if row['status']=='complete' and type(row.get('success')) is bool:post.append(row)
    assert len(post)==400 and len({r['source_id'] for r in post})==400
    assert {s['source_id'] for _,cfg in configs for s in cfg['episodes']}=={r['source_id'] for r in post}
    for p,cfg in configs:
        cfg['worker_outputs']=[j['output'] for j in jobs];d.exclusive(p,cfg)
    post_path=d.W/'POST_VALID_BASELINE.json';d.exclusive(post_path,post)
    budget=dict(prior_B_attempts=5287,new_Velocity_attempts=400,max_new_attempts=400,cumulative_B_max=5687,node_cap=16000,
        continuation_prior_attempts=1560,continuation_after_full_wave=1960,continuation_cap=6000,
        prior_new_LIBERO_dev_parents=32,prior_new_LIBERO_dev_attempts=160,new_dev_parents=0,new_dev_attempts=0,
        prior_B_small_network_updates=238000,new_small_network_updates=0,base_SFT_updates=0)
    batch=dict(batch_id=run,run_id=run,kind='gpu',max_workers=8,jobs=jobs,baseline_index=old['baseline_index'],post_index=str(post_path),
        frozen_head_ready=str(head_ready),velocity_protocol=protocol,budgets=budget,
        physical_rollout_attempts=400,automatic_retry=False,all_holders_off_entire_wave=True)
    d.exclusive(path,batch)
    d.exclusive(d.W/'PREPARED.json',dict(at_utc=d.utc(),batch=str(path),batch_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        parent_authorization_sha256=d.AUTH_SHA,continuation_sha256=d.CONT_SHA,
        priority=dict(path='deadline_20260924/OURS_FIRST_PRIORITY_V1.json',sha256='f45e4048ff1da43328e5ac9576fbc4be9716e8778393e4ead3b731060e220ce8'),
        frozen_head_sha256=ready['model_sha256'],budgets=budget,native_CPU_mapping=str(d.W/'CPU_MAPPING_CHECK.json'),
        model_norm='same official pi05-libero checkpoint, own normalization with exact1e-6 output epsilon; extra delta transform false',
        old_results_immutable=True,code_refs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in d.W.glob('*.py')}))
    (d.W/'METHOD.md').write_text('''# Native LIBERO Velocity operator transfer

Same official pi05 LIBERO model/norm, H10/K5/NFE10, raw action7/state8 and original400 random-reset sources as N/Post.
Same native head from development160: no new collection, base or small-head training. No D/G0; not Full.
The fixed single intervention remains command20. Base reference comes from the original policy.infer call.
Guided sampling reuses its exact sample key and float32 normal(1,10,32) noise, without advancing the natural RNG.

The JAX sampler preserves the native prefix KV cache, suffix attention and ten Euler steps. At the historical
times .3/.2/.1 and alpha10, it differentiates Q with respect to a detached velocity leaf through clean=x-tau*v,
the official quantile output transform (including1e-6), and the true command clamp. Only first5 XYZ/gripper
velocity entries change. No VLA parameter derivative or update, intermediate trust projection or line search.
The stable sigmoid derivative avoids float32 cancellation at confident logits; frozen-head CPU comparisons use
only saved development rows. There is no separate GPU preflight or extra control rollout.

The guided clean command minus the same-noise base defines the native physical direction. The final XYZ/grip
projection is exactly the Post rule:1mm XYZ RMS target/3mm component cap, .10/.20 gripper command bounds,
same boundary margin. Original raw rotations and chunk tail remain unchanged even if internal guidance couples them.
Q quality is limited by5 negative training candidates and no negative validation candidate. All final-step members
stay fixed; Post/test success does not choose the sampler, head, gain, times, or projection radii.

Eight independent50-source jobs use one whole-wave reservation. All holders are off from loading through full
drain, including early-finished GPUs; the guard restores occupancy after terminal publication/cleanup.
The finite supervisor registers the same original B thread's completion trigger before model loading.
''')
    print(str(path))


if __name__=='__main__':main()
