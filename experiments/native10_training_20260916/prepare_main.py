"""Build pending round1 configuration, or freeze after a new analysis READY.

This command never creates an environment, samples a model, or launches workers.
It preserves every prior P0/main version and refuses an unreleased main freeze.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import shutil
from collections import defaultdict
from .protocol import canonical_hash,protocol_digest,require_stage_budget,validate_manifest
from .storage import ROOT,PACKAGE,dump,sha256
from .scene_identity import SCHEMA,PRECISION

CODE=Path(__file__).resolve().parent
COLLECTION_CODE=('main_collection.py','main_runner.py','run_main_gpu.sh','scene_identity.py',
    'adapter.py','engine.py','commands.py','bank_audit.py','candidates13.py','semantics.py','protocol.py','storage.py')
STAGE_LIMITS={'p0':600,'round1_labels':23200,'round1_development_policy':2100,
    'round2_labels':17400,'round2_development_policy':2100,'calibration':1200,
    'heldout':2200,'technical_reserve':1200}
MAIN_SCOPE='round1_native10_local_labels'
REPLACEMENT_SCOPE='preregistered_initialization_replacements'


def build_round1():
    cfg=json.loads((ROOT/'preparation/protocol_draft.json').read_text())
    registration=ROOT/'preparation/main_registration_v2'
    manifest=json.loads((registration/'combined_manifest.json').read_text())
    validate_manifest(manifest)
    cfg.update(status='pending',episode_manifest=manifest,analysis_approval={'status':'pending'},
        split_replicates={'train':4,'development':4,'calibration':2,'heldout':4},
        heldout_replicates=4,planned_attempts_upper_bound=48800,
        critic_assets=str(PACKAGE/'assets/critic'),scene_identity={'schema':SCHEMA,'precision':PRECISION,
        'scope':'same task across all initialized main splits','duplicate_rule':'first accepted registry claim; before first policy action',
        'historical_complete_scene_available':False},
        main_manifest_reference={str(p):sha256(p) for p in registration.glob('*.json')})
    stages={name:dict(simulator_attempts=n,training_updates=0) for name,n in STAGE_LIMITS.items()}
    stages.update(training_round1=dict(simulator_attempts=0,training_updates=19200),
                  training_final=dict(simulator_attempts=0,training_updates=32000))
    cfg['budget']=dict(hard_total=50000,training_update_total=51200,count_failures=True,count_retries=True,stages=stages)
    cfg['stage_release_scopes']={name:'not_released_'+name for name in stages}
    cfg['stage_release_scopes'].update(p0='p0_anchor_and_native10_diagnostics',
        round1_labels=MAIN_SCOPE,technical_reserve=REPLACEMENT_SCOPE)
    frozen=json.loads((ROOT/'p0/freeze.json').read_text())
    weights=frozen['external_model_dependencies']
    vla=next(iter(frozen['large_files_verified_once_then_stat'].values()))['sha256']
    d={name:digest for name,digest in weights.items() if '/models/spatial_pair_' in name}
    g={name:digest for name,digest in weights.items() if '/critics/gate_' in name}
    if sum(name.endswith('.pt') for name in d)!=2 or len(g)!=2:
        raise ValueError('Expected frozen two-member D/G0 assets and their normalization metadata')
    ranking=json.loads((PACKAGE/'assets/critic/ranking.json').read_text())
    critical={str(CODE/name):sha256(CODE/name) for name in COLLECTION_CODE}
    hashes=dict(vla=vla,d=canonical_hash(d),g0=canonical_hash(g),implementation=canonical_hash(critical),
        **{'critic_'+str(k):v for k,v in ranking['model_hashes'].items()})
    cases=[row for row in manifest if not row.get('replacement_of') and
           ((row['split']=='train' and row['round']==1) or row['split']=='development')]
    if len(cases)!=400:raise ValueError('Round1 must register300 train plus100 development primary slots')
    counter=defaultdict(int);radii={}
    for row in cases:
        group=(row['task'],row['split'],row['round']);index=counter[group];counter[group]+=1
        # Training cut type alternates, so pair adjacent types before radius
        # alternation; channel radii do not become proxies for alarm/scheduled.
        radii[row['episode_id']]=.5 if (index//2 if row['split']=='train' else index)%2==0 else 1.
    cfg['main_collection']=dict(concurrency={'workers_per_gpu':4,'evidence':str(ROOT/'p0/concurrency32/audit.json')},
        replacement_capture_stage='technical_reserve',
        replacement_candidates=json.loads((registration/'replacement_candidates.json').read_text()),
        banks={'round1_labels_v1':dict(stage='round1_labels',kind='labels13',
            episode_ids=[x['episode_id'] for x in cases],generation_round=1,
            cut_selection_policy='analysis_lead_v1',random_seed_domain='main_local_labels_v1',
            channel_radius_by_episode=radii,model_hashes=hashes,critic_member_hashes=ranking['model_hashes'])})
    cfg['model_dependency_groups']=dict(vla=vla,d=d,g0=g,critical_collection_code=critical)
    cfg['analysis_documents']={str(p):sha256(p) for p in sorted((PACKAGE/'coordination').glob('NATIVE10_*.md'))}
    ready=PACKAGE/'coordination/NATIVE10_ANALYSIS_READY.json'
    cfg['analysis_ready']=dict(path=str(ready),sha256=sha256(ready))
    return cfg


def prepare_pending():
    cfg=build_round1()
    path=ROOT/'preparation/main_round1_pending.json'
    dump(path,cfg,exclusive=False)
    print(path)


def freeze_round1(version):
    import re
    if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,60}',version):raise ValueError('Unsafe version')
    from .runner import verify_frozen as verify_p0_frozen
    verify_p0_frozen()
    cfg=build_round1()
    ready=json.loads(Path(cfg['analysis_ready']['path']).read_text())
    if not {MAIN_SCOPE,REPLACEMENT_SCOPE}<=set(ready['released_scope']):
        raise ValueError('Analysis READY has not released round1 collection and initial-scene replacement scope')
    audit_path=ROOT/'p0/concurrency32/audit.json'
    if json.loads(audit_path.read_text())['status']!='passed':raise ValueError('Concurrency audit must pass')
    dest=ROOT/'main_protocols'/version
    dest.mkdir(parents=True,exist_ok=False)
    coordination=dest/'coordination';coordination.mkdir()
    originals=[Path(name) for name in cfg['analysis_documents']]+[Path(cfg['analysis_ready']['path'])]
    for original in originals:
        shutil.copyfile(original,coordination/original.name)
        if sha256(original)!=sha256(coordination/original.name):raise ValueError('Coordination source changed during freeze')
    cfg['analysis_documents']={str(coordination/Path(name).name):digest for name,digest in cfg['analysis_documents'].items()}
    cfg['analysis_ready']=dict(path=str(coordination/'NATIVE10_ANALYSIS_READY.json'),sha256=sha256(coordination/'NATIVE10_ANALYSIS_READY.json'))
    cfg['status']='frozen'
    task=coordination/'NATIVE10_TRAINING_TASK.md'
    cfg['analysis_approval']=dict(status='approved',approved_by='analysis',document_path=str(task),
        document_sha256=sha256(task),protocol_sha256=protocol_digest(cfg))
    require_stage_budget(cfg,'round1_labels');require_stage_budget(cfg,'technical_reserve')
    config_path=dest/'config.json';dump(config_path,cfg)
    p0=json.loads((ROOT/'p0/freeze.json').read_text())
    files=dict(p0['files'])
    files.update({str(CODE/name):sha256(CODE/name) for name in COLLECTION_CODE})
    extra=[config_path,CODE/'prepare_main.py',CODE/'register_main_v2.py',CODE/'training_design_v2.json',
           CODE/'TRAINING_SCHEMA_MAIN_V2.md',audit_path,
           PACKAGE.parent/'gpu_occupancy_lifecycle.sh',PACKAGE.parent/'gpu_occupancy_guard.py',
           PACKAGE.parent/'ACT-RECAP/scripts/run_recap_gpu_wave.py']
    extra+=list(coordination.glob('*'))+list((ROOT/'preparation/main_registration_v2').glob('*.json'))
    files.update({str(p):sha256(p) for p in extra})
    dump(dest/'freeze.json',dict(files=files,large_files_verified_once_then_stat=p0['large_files_verified_once_then_stat'],
        stage='round1_labels',bank_version='round1_labels_v1',config_sha256=sha256(config_path),
        main_collection_only=True,training_released=False))
    from .main_runner import verify_frozen
    verify_frozen(config_path,dest/'freeze.json','round1_labels','round1_labels_v1',32)
    print(config_path)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('pending','freeze'));p.add_argument('--version',default='round1_v1')
    a=p.parse_args();prepare_pending() if a.action=='pending' else freeze_round1(a.version)
