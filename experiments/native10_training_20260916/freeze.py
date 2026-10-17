"""Freeze P0 after CPU evidence; main collection/training remain unreleased."""
from __future__ import annotations
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
from .storage import ROOT,PACKAGE,dump,sha256
from .prepare import hashes
from .protocol import protocol_digest,validate_protocol,require_stage_budget


def freeze_p0():
    if (ROOT/'p0/freeze.json').exists():
        from .runner import verify_frozen
        verify_frozen()
        return ROOT/'p0/freeze.json'
    cpu=json.loads((ROOT/'preparation/cpu_checks.json').read_text())
    assert cpu['status']=='passed'
    for path,expected in cpu['code_hashes'].items():assert sha256(path)==expected,path
    assert not (ROOT/'sources').exists() and not (ROOT/'rollouts').exists()
    ready_path=PACKAGE/'coordination/NATIVE10_ANALYSIS_READY.json'
    ready=json.loads(ready_path.read_text())
    assert ready['version']>=2
    copies=ROOT/'p0/coordination';copies.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(ready_path,copies/ready_path.name)
    document_keys=['task_document','protocol_review','training_addendum','command_budget_amendment','raw_command_review']
    for key in document_keys:
        source=PACKAGE/ready[key]
        assert sha256(source)==ready[key+'_sha256'],key
        shutil.copyfile(source,copies/source.name)
    cfg=json.loads((ROOT/'preparation/protocol_draft.json').read_text())
    cfg['episode_manifest']=[case for case in cfg['episode_manifest'] if case['split']=='p0']
    assert len(cfg['episode_manifest'])==20
    cfg['status']='frozen'
    cfg['require_saved_bank']=True
    cfg['analysis_ready']={'path':str(copies/ready_path.name),'sha256':sha256(copies/ready_path.name)}
    cfg['analysis_documents']={str(path):sha256(path) for path in copies.glob('*.md')}
    cfg['main_registered_manifest_sha256']=sha256(ROOT/'preparation/episode_manifest.json')
    cfg['p0_design']={
        'queue_probes':{'tasks':5,'episodes':'first preregistered p0 episode per task','implementations':2,'steps':30,'attempts':10},
        'physical_probes':{'states':'first five p0 source cuts; unavailable cuts retained and reported',
                           'gripper_commands':[1.5,1.,-1.5,-1.],'xyz':[0.,0.,0.],'steps':3,'attempts':20},
        'legacy':{'cases':['shelf-place-v3__2026104012','stick-pull-v3__2026104028','disassemble-v3__2026104005'],
                  'implementations':['act','corrector'],'arms':['replan','post_matched'],'repeats':[0,1],
                  'candidate_restore_attempts':6,'branch_attempts':24,'interpretation':'implementation diagnostic only'},
        'native10':{'sources':20,'candidate_restores':20,'arms':5,'repeats':4,'branches':400},
        'planned_attempts':500,'hard_stage_limit':600,'reserve_not_automatic':100,
        'commands_tolerance':1e-6,'physics_tolerance':1e-10,'reward_tolerance':1e-8,
        'historical_diagnostic_commands':'original bounded native50 protocol',
        'native10_command_protocol':'raw anchor plus feasible matched delta',
        'no_outcome_gating':True,'concurrency':{'workers':8,'workers_per_gpu':1}}
    document=copies/Path(ready['task_document']).name
    cfg['analysis_approval']={'status':'approved','approved_by':'analysis',
        'document_path':str(document),'document_sha256':sha256(document),
        'protocol_sha256':protocol_digest(cfg),
        'basis':'Analysis READY v2 conditionally releases P0; executor binds verified implementation and fixed design'}
    validate_protocol(cfg,require_runnable=True)
    require_stage_budget(cfg,'p0')
    dump(ROOT/'p0/config.json',cfg)
    ledger=ROOT/'budget/attempts.jsonl';ledger.parent.mkdir(parents=True,exist_ok=True)
    with ledger.open('x'):pass
    files=hashes()
    files.update({str(path):sha256(path) for path in Path(__file__).parent.glob('*.sh')})
    files.update({str(path):sha256(path) for path in Path(__file__).parent.glob('*.json')})
    files.update({str(path):sha256(path) for path in copies.iterdir()})
    files[str(ROOT/'p0/config.json')]=sha256(ROOT/'p0/config.json')
    files[str(ROOT/'preparation/cpu_checks.json')]=sha256(ROOT/'preparation/cpu_checks.json')
    files[str(ROOT/'preparation/episode_manifest.json')]=sha256(ROOT/'preparation/episode_manifest.json')
    files[str(PACKAGE.parent/'ACT-RECAP/scripts/run_recap_gpu_wave.py')]=sha256(PACKAGE.parent/'ACT-RECAP/scripts/run_recap_gpu_wave.py')
    for path in (PACKAGE/'assets/critic').rglob('*'):
        if path.is_file():files[str(path)]=sha256(path)
    provenance=json.loads((PACKAGE/'outputs/metaworld_small_20260916/provenance/previous.json').read_text())
    dependencies=dict(provenance['dependencies'])
    base=PACKAGE.parent/'ACT-RECAP/outputs/act_recap_future_aware_20260914'
    base_config=json.loads((base/'config.json').read_text())
    auxiliary=[base/'projection.npy',base/'config.json',base/'config_identity.json']
    for member in (241,242):
        auxiliary += [base/f'models/spatial_pair_{member}/normalization.json',base/f'models/spatial_pair_{member}/complete.json']
    legacy=Path(base_config['legacy_source'])
    feature_config=json.loads((legacy/'config.json').read_text())
    auxiliary.append(legacy/'config.json')
    for member in feature_config['detector_members']:
        dependencies[str(legacy/member['path'])]=member['sha256']
    for path in auxiliary:dependencies[str(path)]=sha256(path)
    large={}
    for name,expected in dependencies.items():
        actual=sha256(name)
        if actual!=expected:raise ValueError('Frozen model/normalization changed: '+name)
        stat=Path(name).stat()
        if stat.st_size>512*1024*1024:
            large[name]=dict(sha256=actual,bytes=stat.st_size,mtime_ns=stat.st_mtime_ns,
                             inode=stat.st_ino,device=stat.st_dev,verified_streaming_before_launch=True)
        else:files[name]=actual
    dump(ROOT/'p0/freeze.json',dict(utc=datetime.now(timezone.utc).isoformat(),files=files,
        external_model_dependencies=dependencies,large_files_verified_once_then_stat=large,
        analysis_original_ready_sha256=sha256(ready_path),
        cpu_review_passed=True,raw_mask_mapping_checks_passed=True,
        no_new_simulation_or_training_before_freeze=True,
        main_collection_released=False,training_released=False))
    print(ROOT/'p0/freeze.json')
    return ROOT/'p0/freeze.json'


if __name__=='__main__':freeze_p0()
