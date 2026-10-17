"""Metadata-only input assembly, exact future READY contract and new freeze."""
from copy import deepcopy
from pathlib import Path
import argparse
import json
import re
import shutil
import tarfile

from experiments.native10_training_20260916.calibration_prepare_v1 import authorization_references
from . import storage
from .protocol import (TASK_ID,TASKS,PREFLIGHT,FORMAL,REPAIR,CAPS,METHODS,OLD_METHODS,
    PRIMARY_IDS,PRIMARY_IDS_SHA,PRE_IDS,BASE_LEDGER_SHA,SELECTED_SHA,
    canonical_hash,protocol_digest,validate_config,require_stage_budget)

CODE = Path(__file__).resolve().parent
OLD_CONFIG = storage.OLD_ROOT/'heldout_protocols/heldout_v1/config.json'
OLD_CONFIG_SHA = 'd86dc14afddf81a37587ff020cd36cc07e85869bf315502dc1778a97bda8f795'
OLD_FREEZE_SHA = 'a2db97fd0c76650e730b58836b0cd6059d25c76f42e5da4e2ce06611784d11b8'
AUDIT = storage.OLD_ROOT/'heldout_audits/heldout_v1'
AUDIT_SHA = 'd776f54ceb94879bc1945a6e5e02736d04ba9d7e4652e02e06280be3a85a833e'
TASK = storage.PACKAGE/'coordination/STANDALONE_ABLATION_TASK_20260918.md'
READY = storage.PACKAGE/'coordination/STANDALONE_ABLATION_ANALYSIS_READY.json'
SCIENTIFIC = ('source_horizon','prefix_horizon','suffix_horizon','control_budget',
    'generated_horizon','gate_threshold','guidance','matching','command_semantics','cpu','seed_namespace','critic_assets')


def ref(path, *, directory=False):
    path = Path(path).resolve()
    return dict(path=str(path), **{('seal_sha256' if directory else 'sha256'):
        storage.sha256(path/'complete.json' if directory else path)})


def build_inputs(*, preflight_attempts=None):
    """No new labels/model/inference. Assemble the already audited old cohort."""
    old = storage.read(storage.checked(OLD_CONFIG,OLD_CONFIG_SHA))
    oldf = storage.read(storage.checked(OLD_CONFIG.with_name('freeze.json'),OLD_FREEZE_SHA))
    audit_seal = storage.read(storage.checked(AUDIT/'complete.json',AUDIT_SHA))
    record = storage.read(storage.checked(AUDIT/'result.json',audit_seal['files']['result.json']))
    storage.checked(AUDIT/'budget_snapshot.jsonl',BASE_LEDGER_SHA)
    storage.checked(storage.OLD_ROOT/'budget/attempts.jsonl',BASE_LEDGER_SHA)
    task_text = TASK.read_text()
    match = re.search(r'\|\s*技术预检\s*\|\s*(\d+)\s*\|',task_text)
    if not match: raise ValueError('TASK must explicitly name its preflight plan')
    plan = int(match.group(1))
    if preflight_attempts is not None and preflight_attempts != plan:
        raise ValueError('Latest requested preflight size differs from actual TASK; resolve before freeze')
    if plan not in (30,50): raise ValueError('Explicit registered preflight implementation needed')
    lookup = {x['episode_id']:x for x in old['episode_manifest']}
    sources = {}
    for row in record['per_source']:
        identity = row['planned_slot_id']; actual = row['resolved_episode_id']; cut = row['actual_cut']
        source = Path(row['source_path']); collection = Path(row['collection_path'])
        oldbank = storage.OLD_ROOT/'banks/heldout_policy_v1'/actual/f'cut{cut:03d}' if cut is not None else None
        source_seal = storage.read(storage.checked(source/'complete.json',row['source_seal_sha256']))
        collection_seal = storage.read(storage.checked(collection/'complete.json',row['collection_seal_sha256']))
        item = {k:row[k] for k in ('planned_slot_id','resolved_episode_id','task','actual_cut','no_cut',
            'common_outcome','scene_fingerprint','source_path','source_seal_sha256','collection_path','collection_seal_sha256')}
        item.update(case=deepcopy(lookup[actual]),source_protocol_sha256=source_seal['protocol_sha256'],
            old_bank_path=str(oldbank) if oldbank is not None else None,
            old_bank_seal_sha256=storage.sha256(oldbank/'complete.json') if oldbank is not None else None,
            source_files=source_seal['files'],old_collection_files=collection_seal['files'])
        if oldbank is not None: item['old_bank_files']=storage.read(oldbank/'complete.json')['files']
        sources[identity]=item
    if list(sources) != list(PRIMARY_IDS): raise ValueError('Audited source order changed')
    selected=Path(old['critic_assets']);selected_seal=storage.read(storage.checked(selected/'complete.json',SELECTED_SHA))
    cfg={key:deepcopy(old[key]) for key in SCIENTIFIC}
    cfg.update(schema_version=1,task_id=TASK_ID,status='pending',tasks=list(TASKS),
        episode_manifest=[deepcopy(lookup[key]) for key in PRIMARY_IDS],
        task_document=ref(TASK),method_review=ref(storage.PACKAGE/'coordination/STANDALONE_ABLATION_METHOD_REVIEW.md'),
        input_review=ref(storage.PACKAGE/'coordination/STANDALONE_ABLATION_INPUT_REVIEW.md'),
        carry_in=dict(ledger=ref(AUDIT/'budget_snapshot.jsonl'),legacy_ledger_path=str(storage.OLD_ROOT/'budget/attempts.jsonl'),
            simulator_attempts=48183,optimizer_updates=51200,global_simulator_limit=50000,global_optimizer_limit=51200),
        budget=dict(hard_total=1500,training_update_total=0,count_failures=True,count_retries=True,
            stages={s:dict(simulator_attempts=n,training_updates=0) for s,n in CAPS.items()}),
        stage_release_scopes={s:s for s in CAPS},capture_allowed=False,replacement_allowed=False,scene_append_allowed=False,
        training_allowed=False,replicates=4,output_root=str(storage.ROOT),
        selected_model=dict(path=str(selected),seal_sha256=SELECTED_SHA,selection=dict(path='A',step=4000),
            member_hashes=deepcopy(old['main_collection']['banks']['heldout_policy_v1']['critic_member_hashes']),
            selected_training=deepcopy(old['heldout_collection']['selected_training'])),
        inputs=dict(sources=sources,source_bindings_hash=canonical_hash(sources),primary_ids_hash=PRIMARY_IDS_SHA,
            old_config=ref(OLD_CONFIG),old_freeze=ref(OLD_CONFIG.with_name('freeze.json')),
            old_audit=ref(AUDIT,directory=True),old_audit_result=ref(AUDIT/'result.json'),
            old_source_records=ref(AUDIT/'source_records.json'),scene_snapshot=ref(AUDIT/'scene_registry_snapshot.jsonl'),
            source_protocol_sha256=old['analysis_approval']['protocol_sha256']),
        solo_rule=dict(radius='own_symmetric_capacity',shrink=1-1e-6,expand_native=True,
            other_direction_dependencies=False,each_method_regenerates_a0=True,random_fallback=False,q_acceptance_gate=False),
        execution_plans={FORMAL:dict(episode_ids=list(PRIMARY_IDS),methods=list(METHODS),repeats=[0,1,2,3],
            bank_mode='solo',expected_attempts=1274,workers=32),
            PREFLIGHT:dict(episode_ids=list(PRE_IDS),methods=list(METHODS),repeats=[0] if plan==50 else [],
                reference_methods=list(OLD_METHODS) if plan==50 else ['alarm_replan10','post'],
                ref_repeats=[0] if plan==50 else [0,1],bank_mode='paired_reference',expected_attempts=plan,workers=5)},
        statistics=dict(seed=2026091801,draws=10000,task_order=list(TASKS),source_order=list(PRIMARY_IDS),
            quantile_method='linear',unit='whole_source_within_task',primary_methods=list(METHODS),
            confidence_quantiles=[.025,.975],primary_family_quantiles=[.05/6,1-.05/6],posthoc_selection=False),
        analysis_ready=dict(path=str(READY),sha256=None),analysis_approval=dict(status='pending'))
    validate_config(cfg)
    return cfg


def ready_contract(config):
    return dict(task_id=TASK_ID,inputs_hash=canonical_hash(config['inputs']),primary_ids_hash=PRIMARY_IDS_SHA,
        scientific_parameters={k:deepcopy(config[k]) for k in SCIENTIFIC},solo_rule=deepcopy(config['solo_rule']),
        selected_model=deepcopy(config['selected_model']),carry_in=deepcopy(config['carry_in']),
        budget=deepcopy(config['budget']),stage_release_scopes=deepcopy(config['stage_release_scopes']),
        execution_plans=deepcopy(config['execution_plans']),statistics=deepcopy(config['statistics']),
        output_root=str(storage.ROOT),model_training_allowed=False,pca_allowed=False,
        capture_allowed=False,replacements_allowed=False,old_files_read_only=True,
        formal_requires_passed_preflight=True,hold_idle=False,automatic_retry=False,
        old_config=deepcopy(config['inputs']['old_config']),old_freeze=deepcopy(config['inputs']['old_freeze']),
        old_audit=deepcopy(config['inputs']['old_audit']),scene_snapshot=deepcopy(config['inputs']['scene_snapshot']))


def pending(output, *, preflight_attempts=None):
    config=build_inputs(preflight_attempts=preflight_attempts)
    output=storage.destination(Path(output)/'config.json').parent
    if output.exists() and any(output.iterdir()): raise FileExistsError(output)
    storage.dump(output/'config.json',config);storage.dump(output/'ready_contract.json',ready_contract(config))
    storage.seal(output,role='standalone_isolated_pending_inputs',model_calls=0,simulator_calls=0,optimizer_updates=0)
    return ref(output,directory=True)


def cpu_checks(directory):
    storage.sealed(directory)
    result=storage.read(Path(directory)/'result.json')
    before=result.get('code_before',{});after=result.get('code_after',{})
    if (result.get('status')!='passed' or result.get('returncode')!=0 or not before or before!=after
            or any(result.get(k)!=0 for k in ('simulator_calls','model_calls','optimizer_updates'))):
        raise ValueError('Successful zero-resource CPU evidence with before/after code hashes required')
    expected={str(p.resolve()) for p in CODE.rglob('*') if p.is_file() and p.suffix in ('.py','.sh')}
    if not expected <= set(after): raise ValueError('CPU archive omits an actual new code or test dependency')
    for name,digest in after.items():storage.checked(name,digest)
    return after


def future_ready_fields(pending_path,cpu_path):
    storage.sealed(pending_path);config=storage.read(Path(pending_path)/'config.json')
    code=cpu_checks(cpu_path)
    if storage.read(Path(pending_path)/'ready_contract.json')!=ready_contract(config):raise ValueError('Pending contract changed')
    return dict(task_id=TASK_ID,task_document=config['task_document']['path'],
        task_document_sha256=config['task_document']['sha256'],
        standalone_ablation=ready_contract(config),
        standalone_preparation_binding=dict(pending_inputs=ref(pending_path,directory=True),
            ready_contract=ref(Path(pending_path)/'ready_contract.json'),cpu_evidence=ref(cpu_path,directory=True),
            code_sha256=code,input_reviews={name:deepcopy(config[name]) for name in ('method_review','input_review')}))


def _inventory(ready,dest):
    rows=authorization_references(ready,base_dir=storage.PACKAGE)
    for index,row in enumerate(rows):
        original=storage.checked(row['original_path'],row['sha256'])
        target=dest/'authorization_references'/f'{index:04d}_{original.name}'
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(original.read_bytes())
        row['snapshot_path']=str(storage.checked(target,row['sha256']))
    storage.dump(dest/'authorization_inventory.json',dict(status='passed',references=rows))
    return rows


def verify_frozen(config_path,freeze_path,stage):
    config_path,freeze_path=Path(config_path).resolve(),Path(freeze_path).resolve()
    frozen=storage.read(freeze_path);config=storage.read(storage.checked(config_path,frozen['config_sha256']))
    require_stage_budget(config,stage)
    old=storage.read(storage.checked(OLD_CONFIG,OLD_CONFIG_SHA))
    if any(config.get(key)!=old[key] for key in SCIENTIFIC):
        raise ValueError('Only standalone matching may change; original scientific parameters differ')
    if frozen.get('task_id')!=TASK_ID or frozen['files'].get(str(config_path))!=storage.sha256(config_path):
        raise ValueError('Wrong independent freeze identity')
    for path,digest in frozen['files'].items():storage.checked(path,digest)
    for path,spec in frozen.get('large_files_verified_once_then_stat',{}).items():
        stat=Path(path).stat()
        if (stat.st_size!=spec['bytes'] or stat.st_mtime_ns!=spec['mtime_ns']
                or ('inode' in spec and stat.st_ino!=spec['inode'])
                or ('device' in spec and stat.st_dev!=spec['device'])):
            raise ValueError('Frozen large asset changed: '+path)
    ready=storage.read(config['analysis_ready']['path'])
    inventory=storage.read(config['authorization_inventory']['path'])
    expected=authorization_references(ready,base_dir=storage.PACKAGE)
    if [{k:v for k,v in row.items() if k!='snapshot_path'} for row in inventory['references']]!=expected:
        raise ValueError('Authorization references not exhaustively inventoried')
    for row in inventory['references']:
        for key in ('original_path','snapshot_path'):
            if frozen['files'].get(row[key])!=row['sha256']:raise ValueError('Authorization original/snapshot omitted')
    for path in CODE.rglob('*'):
        if path.is_file() and path.suffix in ('.py','.sh') and str(path.resolve()) not in frozen['files']:
            raise ValueError('Current new implementation/test not in frozen code')
    storage.checked(config['carry_in']['legacy_ledger_path'],BASE_LEDGER_SHA)
    if stage==FORMAL:
        completion=storage.ROOT/'preflight_audits'/frozen['version']/'complete.json'
        record=storage.sealed(completion.parent)
        result=storage.read(completion.parent/'result.json')
        if (record.get('role')!='standalone_preflight_audit' or result.get('status')!='passed'
                or result.get('config_sha256')!=frozen['config_sha256']
                or result.get('freeze_sha256')!=storage.sha256(freeze_path)
                or result.get('expected_attempts')!=config['execution_plans'][PREFLIGHT]['expected_attempts']):
            raise ValueError('Same-freeze complete passing preflight is mandatory before formal work')
    return config


def freeze(pending_path,ready_path,cpu_path,*,version):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,60}',version):raise ValueError('Safe protocol version required')
    ready_path=Path(ready_path).resolve();ready_bytes=ready_path.read_bytes();ready_sha=storage.sha256(ready_path)
    ready=json.loads(ready_bytes);fields=future_ready_fields(pending_path,cpu_path)
    if any(ready.get(k)!=v for k,v in fields.items()):raise ValueError('Exact actual input/code/CPU future READY binding differs')
    if PREFLIGHT not in ready.get('released_scope',[]):raise ValueError('Preflight not released')
    config=deepcopy(storage.read(Path(pending_path)/'config.json'))
    oldfreeze=storage.read(storage.checked(OLD_CONFIG.with_name('freeze.json'),OLD_FREEZE_SHA))
    dest=storage.ROOT/'protocols'/version;dest.mkdir(parents=True,exist_ok=False)
    try:
        snapshot=dest/'coordination/STANDALONE_ABLATION_ANALYSIS_READY.json';snapshot.parent.mkdir()
        snapshot.write_bytes(ready_bytes)
        rows=_inventory(ready,dest)
        config.update(status='frozen',analysis_ready=ref(snapshot),release_contract=fields['standalone_ablation'],
            preparation_binding=fields['standalone_preparation_binding'],authorization_inventory=ref(dest/'authorization_inventory.json'),
            protocol_version=version)
        config['analysis_approval']=dict(status='approved',approved_by='analysis',
            document_path=config['task_document']['path'],document_sha256=config['task_document']['sha256'],
            protocol_sha256=protocol_digest(config))
        validate_config(config,require_runnable=True)
        storage.dump(dest/'config.json',config)
        files=dict(oldfreeze['files'])
        # Old artifact audit hashes bind all source/bank/trajectory data without new model execution.
        oldaudit=storage.read(config['inputs']['old_audit_result']['path'])
        for row in oldaudit['artifacts']:
            if row['path'] in files and files[row['path']]!=row['sha256']:
                raise ValueError('Old audit and original freeze disagree: '+row['path'])
            files[row['path']]=row['sha256']
        paths=[p for folder in (CODE,Path(pending_path),Path(cpu_path),dest) for p in folder.rglob('*')
               if p.is_file() and '__pycache__' not in p.parts]
        paths += [Path(row['original_path']) for row in rows]
        for path in paths:
            digest=storage.sha256(path);name=str(path.resolve())
            if name in files and files[name]!=digest:raise ValueError('Old sealed dependency changed: '+name)
            files[name]=digest
        archive=dest/'code_snapshot.tar.gz'
        with tarfile.open(archive,'x:gz') as output:
            for name in sorted(files):
                path=Path(name)
                if path.suffix in ('.py','.sh'):
                    output.add(path,arcname=str(path).lstrip('/'),recursive=False)
        files[str(archive)]=storage.sha256(archive)
        storage.checked(ready_path,ready_sha)
        storage.dump(dest/'freeze.json',dict(task_id=TASK_ID,version=version,files=files,
            config_sha256=storage.sha256(dest/'config.json'),
            large_files_verified_once_then_stat=oldfreeze.get('large_files_verified_once_then_stat',{}),
            preflight_and_formal_separately_gated=True,old_sources_read_only=True))
        verify_frozen(dest/'config.json',dest/'freeze.json',PREFLIGHT)
        return dict(config=str(dest/'config.json'),config_sha256=storage.sha256(dest/'config.json'),
            freeze=str(dest/'freeze.json'),freeze_sha256=storage.sha256(dest/'freeze.json'))
    except BaseException as error:
        storage.dump(dest/'failure.json',dict(error=repr(error),model_calls=0,simulator_calls=0,optimizer_updates=0))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('pending','future-ready','freeze'))
    parser.add_argument('--output',type=Path);parser.add_argument('--pending',type=Path)
    parser.add_argument('--cpu',type=Path);parser.add_argument('--ready',type=Path);parser.add_argument('--version')
    parser.add_argument('--preflight-attempts',type=int);args=parser.parse_args()
    result=pending(args.output,preflight_attempts=args.preflight_attempts) if args.action=='pending' else (
        future_ready_fields(args.pending,args.cpu) if args.action=='future-ready' else
        freeze(args.pending,args.ready,args.cpu,version=args.version))
    print(json.dumps(result,ensure_ascii=False,indent=2))
