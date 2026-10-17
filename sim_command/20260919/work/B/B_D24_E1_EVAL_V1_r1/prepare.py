"""Freeze the existing E1 models and common test identities; no numerical work."""
import copy
import hashlib
import json
from pathlib import Path
import d24_common as d


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    d.authorize(admission=True)
    w = Path(__file__).resolve().parent
    a = d.C/'results/A/A_D24_MAIN_ONCE_V1'
    fit = d.load(d.C/'work/B/B_D24_SPRINT_V1_r1/configs/e1_L00_s9101_m1041.json')
    train = d.load(fit['inputs']['train_rows']['path'])
    tasks = sorted({r['task'] for r in train})
    sources = [r for r in d.load(a/'config/TEST_SOURCES_V1.json')['rows']
               if r['task'] in tasks and 0 <= r['ordinal'] < 10]
    assert len(tasks)==5 and len(sources)==50 and len({r['source_id'] for r in sources})==50
    assert all(r['split']=='test' and 0<=r['ordinal']<10 for r in sources)
    assert not {(r['task'],r['env_seed']) for r in train}&{(r['task'],r['env_seed']) for r in sources}
    d.exclusive(w/'TEST_SOURCES.json', dict(status='frozen_before_B_E1_test', rows=sources,
        selection='all five historical train600 tasks, all first10 fixed D24 test ordinals; no outcome selection',
        origin=str(a/'config/TEST_SOURCES_V1.json'), origin_sha256=sha(a/'config/TEST_SOURCES_V1.json')))
    base0 = d.load(a/'config/BASE.json')
    base = {k:base0[k] for k in ('checkpoint','runtime_packages','projection','tokenizer_name','tokenizer_revision')}
    base['source'] = sources[0]
    d.exclusive(w/'BASE.json',base)
    template = d.load(a/'config/CONFIG.json')
    ensembles = d.load(d.R/'E1_ENSEMBLES.json')['ensembles']
    cells=[]
    for seed in (9101,9102,9103):
        for loss in ('L00','L01','L10','L11'):
            ensemble = next(e for e in ensembles if e['loss']==loss and e['complete_training_seed']==seed)
            assets = w/'assets'/('%s_s%d'%(loss,seed))
            hashes={}
            for member in ensemble['members']:
                p=Path(member['checkpoint']); hashes[str(member['member'])]=sha(p)
                link=assets/'models/refit'/('member_'+str(member['member']))/'selected.pt'
                link.parent.mkdir(parents=True,exist_ok=True);link.symlink_to(p)
            d.exclusive(assets/'ranking.json',dict(horizon=10,model_hashes=hashes,
                selection='all four existing E1 members at fixed4000 update; no ranking or test selection'))
            for method in ('Post','Velocity'):
                cell_id='E1_%s_s%d_%s_H10'%(loss,seed,method)
                cfg=copy.deepcopy(template)
                cfg.update(task_id='B_D24_SPRINT_V1',run_stage='E1_loss_ablation',method=method,methods=[method],
                    loss=loss,complete_training_seed=seed,H=10,sources=sources,source_count=50,max_episodes=50,
                    critic_assets=str(assets),selected_model=dict(member_hashes=hashes,ensemble=ensemble),
                    renderer='Mesa llvmpipe',holder_policy='all eight holders off for whole formal wave',
                    cells=[dict(method=method,H=10)],planned_prior_attempts=1401,overall_B_attempt_cap=16000,
                    training_coverage='historical five tasks, train600,192000 total E1 updates already complete',
                    comparison='four losses x three complete fit seeds x two operators on identical50 test sources',
                    cross_host_comparison_caveat='E1 internal comparisons share B Mesa renderer; A NVIDIA-rendered N/R are not exact renderer-matched controls',
                    config_frozen_at_utc=d.utc())
                cfg.pop('overall_A_attempt_cap',None)
                cfg['matching']['shared_radius_dependencies']='none; each method uses own symmetric feasible radius'
                cfg['matching']['zero_group']='zero direction stays zero for that method and group'
                cfg['matching']['algorithm']='project_solo own symmetric feasible group radius; inherited numerical implementation'
                path=w/'configs'/(cell_id+'.json');d.exclusive(path,cfg)
                cells.append(dict(cell_id=cell_id,config=str(path),config_sha256=sha(path)))
    batch=dict(batch_id='D24_E1_EVAL_r1',run_id='D24_E1_EVAL_r1',kind='gpu',max_workers=8,
        hold_idle=False,formal_holder_policy='all holders off until entire wave including failures drains',jobs=[])
    runtime=d.ROOT/'embodied-ai-workspace/projects/vla-baselines/launchers/runtime.sh'
    python=d.ROOT/'embodied-ai-workspace/environments/lerobot/bin/python'
    checkpoint=Path(base['checkpoint'])
    for gpu in range(8):
        jid='e1eval_PV_worker%d_r1'%gpu
        out=d.R/'jobs'/jid
        cfg=dict(job_id=jid,output=str(out),base_config=str(w/'BASE.json'),cells=cells[gpu::8],
            checkpoint_config_sha256=sha(checkpoint/'config.json'),
            checkpoint_weight_bytes=(checkpoint/'model.safetensors').stat().st_size,
            holder_policy=batch['formal_holder_policy'],planned_episodes=150)
        p=w/'configs'/(jid+'.json');d.exclusive(p,cfg)
        xdg=Path('/tmp/corrector_B_D24_xdg')/jid;xdg.mkdir(parents=True,exist_ok=True);xdg.chmod(0o700)
        batch['jobs'].append(dict(job_id=jid,config=str(p),gpus=[gpu],output=str(out),timeout_seconds=43200,
            argv=['bash',str(runtime),'mw-pi05-legacy',str(python),'-B',str(w/'e1_eval.py'),'--config',str(p)],
            env=dict(XDG_RUNTIME_DIR=str(xdg),PYTHONDONTWRITEBYTECODE='1')))
    d.exclusive(w/'E1_EVAL_BATCH.json',batch)
    d.exclusive(w/'PLAN.json',dict(at_utc=d.utc(),authorization_sha256=d.AUTH_SHA,tasks=tasks,
        cell_count=24,sources_per_cell=50,planned_rollouts=1200,new_optimizer_updates=0,
        concurrency=8,resident_policy_per_worker=True,fits_reused=48,no_completed_episode_replay=True,
        sources=str(w/'TEST_SOURCES.json'),test_guided_selection=False,
        prior_physical_episode_claims=1401,maximum_total_after_batch=2601,authorized_total=16000,
        admission='1.7TiB host memory available; previous8-card H10080GB profile;64GiB engineering host reservation per worker; cgroup cap unknown; no weight copies',
        missing_later_stages=['E6 causal D5 development trace and threshold','Smol/X Post','LIBERO Post','external methods'],
        A_waits_for_B=False,holder_policy=batch['formal_holder_policy']))
    print(json.dumps(dict(batch=str(w/'E1_EVAL_BATCH.json'),cells=len(cells),episodes=1200,tasks=tasks)))


if __name__=='__main__':
    main()
