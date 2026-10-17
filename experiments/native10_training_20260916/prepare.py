"""CPU-only registration and provenance. Never launches a simulator or training."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from .protocol import TASKS, pending_protocol, validate_protocol
from .storage import ROOT, PACKAGE, dump, sha256

WORKSPACE = PACKAGE.parent
CODE = Path(__file__).resolve().parent


def register():
    existing=ROOT/'preparation/protocol_draft.json'
    if existing.exists():
        cfg=json.loads(existing.read_text())
        manifest=json.loads((ROOT/'preparation/episode_manifest.json').read_text())
        assert manifest==cfg['episode_manifest']
        audit=json.loads((ROOT/'preparation/seed_collision_audit.json').read_text())
        assert audit['passed']
        print(json.dumps(dict(validate_protocol(cfg), registration_status='existing_pending_registration_verified')))
        return
    manifest=[]
    for split,start,count in [('p0',2026110000,20),('train',2026111000,600),
                              ('development',2026111600,100),('calibration',2026111700,50),
                              ('heldout',2026111750,50)]:
        for index in range(count):
            task=TASKS[index%5]
            seed=start+index
            episode=f'{task}__{seed}'
            rule={'kind':'first_alarm'}
            round_id=None
            if split=='train':
                round_id=1+index//300
                within=index%300
                if (within//5)%2:
                    rule={'kind':'scheduled','step':[15,45,95][(within//10)%3],
                          'unreached':'retain_missing_no_replacement',
                          'fallback':'none_pending_analysis_review'}
            manifest.append(dict(episode_id=episode,case_id=episode,task=task,env_seed=seed,
                                 split=split,round=round_id,source_horizon=10,cut_rule=rule))
    cfg=pending_protocol()
    old=json.loads((PACKAGE/'outputs/metaworld_small_20260916/config.json').read_text())
    cfg.update(task_id='native10-training-20260916',episode_manifest=manifest,control_budget=300,
        gate_threshold=.05,minimum_intervention_remaining=10,generated_horizon=50,
        methods=['continue_native10','alarm_replan10','velocity','direct','post'],
        replicates=4,heldout_replicates=8,cpu={'worker_threads':4,'critic_threads':2},
        guidance=old['guidance'],matching=old['matching'],
        command_semantics='raw native a0 + feasible matched delta; no replan-only clamp',
        budget={'hard_total':50000,'training_update_total':51200,
            'count_failures':True,'count_retries':True,'stages':{
                'p0':{'simulator_attempts':600,'training_updates':0},
                'capture_main':{'simulator_attempts':800,'training_updates':0},
                'train_labels_round1':{'simulator_attempts':16800,'training_updates':0},
                'train_labels_round2':{'simulator_attempts':16800,'training_updates':0},
                'development_labels':{'simulator_attempts':5600,'training_updates':0},
                'development_policies':{'simulator_attempts':4000,'training_updates':0},
                'calibration':{'simulator_attempts':1000,'training_updates':0},
                'heldout':{'simulator_attempts':2000,'training_updates':0},
                'technical_reserve':{'simulator_attempts':2400,'training_updates':0},
                'training_round1':{'simulator_attempts':0,'training_updates':19200},
                'training_final':{'simulator_attempts':0,'training_updates':32000}}},
        stage_release_scopes={stage:('p0_anchor_and_native10_diagnostics' if stage=='p0' else 'not_released_'+stage)
            for stage in ['p0','capture_main','train_labels_round1','train_labels_round2','development_labels',
                          'development_policies','calibration','heldout','technical_reserve','training_round1','training_final']})
    ready=PACKAGE/'coordination/NATIVE10_ANALYSIS_READY.json'
    cfg['analysis_ready']={'path':str(ready),'sha256':sha256(ready)}
    cfg['analysis_documents']={str(path):sha256(path) for path in sorted((PACKAGE/'coordination').glob('NATIVE10_*.md'))}
    audit=validate_protocol(cfg)
    target=ROOT/'preparation/protocol_draft.json'
    dump(target,cfg)
    dump(ROOT/'preparation/episode_manifest.json',manifest)
    # Outcome-independent seed collision audit against prior registered cases,
    # source directory names and all historical JSON metadata, excluding new work.
    rg='/home/tiger/.codex/packages/standalone/releases/0.154.0-x86_64-unknown-linux-musl/codex-path/rg'
    pattern=r'(?<![0-9])(?:20261100[0-1][0-9]|2026111[0-7][0-9]{2})(?![0-9])'
    roots=[WORKSPACE/'ACT-RECAP/outputs',PACKAGE/'outputs/metaworld_small_20260916',PACKAGE/'results']
    scan=subprocess.run([rg,'--pcre2','-l','--glob','*.json','--glob','*.jsonl',pattern,*map(str,roots)],
                        capture_output=True,text=True)
    if scan.returncode not in (0,1):
        raise RuntimeError(scan.stderr)
    collision={'command':scan.args,'matches':scan.stdout.splitlines(),'returncode':scan.returncode,
               'seed_range':{'p0':[2026110000,2026110019],'main':[2026111000,2026111799]},
               'passed':not bool(scan.stdout.strip())}
    dump(ROOT/'preparation/seed_collision_audit.json',collision)
    if not collision['passed']:
        raise ValueError('New seeds collided; preserve draft and audit before explicit revision')
    print(json.dumps(dict(audit,registration_status='registered_pending',collision_audit=collision['passed']),ensure_ascii=False))


def hashes():
    paths=list(CODE.glob('*.py'))+list((PACKAGE/'src/corrector').glob('*.py'))
    paths+=list((WORKSPACE/'ACT-RECAP/src/ac_tmil').rglob('*.py'))
    paths+=[WORKSPACE/'embodied-ai-workspace/projects/vla-corrector/src/lerobot/policies/pi05/modeling_pi05.py',
            WORKSPACE/'.miniforge3/envs/lerobot/lib/python3.12/site-packages/metaworld/sawyer_xyz_env.py']
    paths+=list((PACKAGE/'experiments/metaworld_small').glob('*.py'))
    paths+=list((WORKSPACE/'embodied-ai-workspace/projects/vla-corrector/src/lerobot').rglob('*.py'))
    paths+=list(CODE.glob('*.sh'))+list(CODE.glob('*.json'))
    paths+=[WORKSPACE/'embodied-ai-workspace/config/vla-corrector.env',
            WORKSPACE/'embodied-ai-workspace/config/vla-corrector-mesa.env',
            WORKSPACE/'embodied-ai-workspace/projects/vla-corrector/reproduction/metaworld_very_hard/prepare_torch_runtime.sh']
    return {str(path):sha256(path) for path in sorted(set(paths))}


def cpu_check():
    result=subprocess.run([sys.executable,'-m','pytest','-q','-p','no:cacheprovider',str(CODE)],
                          capture_output=True,text=True,cwd=PACKAGE)
    folder=ROOT/'preparation'
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'cpu_checks.log').write_text(result.stdout+result.stderr)
    report={'status':'passed' if result.returncode==0 else 'failed','returncode':result.returncode,
            'code_hashes':hashes(),'log_sha256':sha256(folder/'cpu_checks.log'),
            'no_real_simulator_or_training':True}
    dump(folder/'cpu_checks.json',report,exclusive=False)
    print(result.stdout)
    if result.returncode:raise SystemExit(result.returncode)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['register','cpu-check'])
    args=parser.parse_args()
    {'register':register,'cpu-check':cpu_check}[args.action]()
