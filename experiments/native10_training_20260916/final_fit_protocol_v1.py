"""Immutable cross-protocol final CPU execution contracts; no model imports.

``preview_specification`` is a read-only metadata/SHA preview for a future READY.
``prepare`` needs that explicit release before reading the bundle or writing a
new protocol. Neither function loads feature arrays, checkpoints, PCA or models.
All initialization and optimization remain in the separately frozen pipeline.
"""
from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import tarfile

from . import storage
from .protocol import canonical_hash, pending_protocol, protocol_digest, require_stage_budget, validate_protocol

CODE = Path(__file__).resolve().parent
CONTRACT = storage.PACKAGE/'coordination/NATIVE10_FINAL_INPUT_CONTRACT.md'
CONTRACT_SHA = 'bceeccecbe2f5a41a27f05e8245ee8b9e68c525e8cb3d653a3460f275fab54a0'
BRIEF = storage.PACKAGE/'coordination/NATIVE10_FINAL_PREFLIGHT_IMPLEMENTATION_BRIEF.md'
BRIEF_SHA = 'c27e7cf502114e079e04df103ba3239726a41b2f15505ebdf2450c60a88de261'
NUMERICAL_DECISION = storage.PACKAGE/'coordination/NATIVE10_FINAL_NUMERICAL_DECISION.md'
NUMERICAL_DECISION_SHA = '3e556bad66cff0105c243b841cd24b619efdcc1c681bbf38b41bb0b71888cb1a'
DESIGN = storage.ROOT/'fit_protocols/round1_preflight_v1/training_design.json'
DESIGN_SHA = '3b9bbf7a67fc15123ac761c13358c0bfd8492ea9aea3c25649cefb02c66ef0cf'
SCHEMA = 'native10_final_training_pipeline_v1'
ROLE = 'native10_final_fit_protocol_v1'
STAGES = {'preflight':'final_fit_preflight', 'fit':'training_final'}
SCOPES = {'preflight':'final_fit_preflight', 'fit':'final_critic_training'}
RELEASES = {'preflight':'final_fit_preflight', 'fit':'final_training'}
STEPS = [200,400,800,1600,2400,3200,4000]
IDENTITY_KEYS = ('phase','input_bundle','source_bindings','manifest_sha256',
                 'feature_contract_sha256','design','documents','code_files','stop_after','numeric_runtime')


def read(path):
    return json.loads(Path(path).read_text())


def checked(path, digest):
    path = Path(path).resolve()
    if not isinstance(digest,str) or not re.fullmatch('[a-f0-9]{64}',digest) or not path.is_file() or storage.sha256(path)!=digest:
        raise ValueError('Immutable file SHA mismatch: '+str(path))
    return path


def sealed(directory, digest):
    directory = Path(directory).resolve()
    complete = checked(directory/'complete.json',digest)
    record = read(complete)
    actual = {str(p.relative_to(directory)) for p in directory.rglob('*') if p.is_file() and p!=complete}
    if record.get('status')!='complete' or set(record.get('files',{}))!=actual:
        raise ValueError('Incomplete or changed sealed directory')
    for name,expected in record['files'].items():
        path = (directory/name).resolve()
        if not path.is_relative_to(directory):
            raise ValueError('Sealed file escapes its directory')
        checked(path,expected)
    return record


def code_files():
    """Explicit dependency closure, with no import of torch or the pipeline."""
    names = ('final_fit_protocol_v1.py','final_fit_runner_v1.py','final_training_pipeline_v1.py',
        'final_input_bundle_v1.py','final_prepare_v1.py','round2_dataset_audit_v1.py',
        'training.py','training_pipeline.py','dataset.py','artifact_loader.py','protocol.py',
        'storage.py','semantics.py','candidates13.py','scene_identity.py')
    paths = [CODE/name for name in names]
    paths += [storage.PACKAGE/'src/corrector'/name for name in ('critic.py','guidance.py','actions.py')]
    # Package initializers are executable imports too.
    paths += [CODE/'__init__.py',CODE.parent/'__init__.py',storage.PACKAGE/'src/corrector/__init__.py']
    return {str(p.resolve()):storage.sha256(p) for p in paths if p.is_file() or p.name!='__init__.py'}


def numeric_runtime():
    """Read the full installed Torch version without importing/executing torch.

    Distribution metadata can omit the CUDA build suffix. The literal in the
    SHA-bound version module preserves it; execution compares actual imports.
    """
    module=importlib.util.find_spec('torch')
    if module is None or module.origin is None:raise ValueError('Frozen CPU runtime requires an installed Torch')
    path=Path(module.origin).resolve().parent/'version.py'
    values=[]
    for node in ast.parse(path.read_text()).body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__version__' for t in node.targets):
            values.append(ast.literal_eval(node.value))
        elif isinstance(node,ast.AnnAssign) and isinstance(node.target,ast.Name) and node.target.id=='__version__':
            values.append(ast.literal_eval(node.value))
    if len(values)!=1 or not isinstance(values[0],str):raise ValueError('Cannot statically bind full Torch version')
    numpy_version=importlib.metadata.version('numpy')
    return dict(torch=values[0],numpy=numpy_version,python=sys.version,executable=str(Path(sys.executable).resolve()),
        device='cpu',dtype='float32',threads=2,torch_distribution=importlib.metadata.version('torch'),
        numpy_distribution=numpy_version,torch_version_file=dict(path=str(path),sha256=storage.sha256(path)))


def _design():
    path = checked(DESIGN,DESIGN_SHA)
    value = read(path)
    a = value['approved_parameters']
    if (value.get('schema_version')!=2 or value.get('task_id')!='native10-training-20260916'
            or a['training_stages']['final']['checkpoints']!=STEPS
            or a['training_stages']['final']['max_updates_per_member']!=4000
            or a['training_stages']['final']['planned_train_episodes']!=600
            or a['ensemble']['members']!=4 or a['loss']['weights']!={'bce':1,'gain':1,'pair_difference':.5}
            or a['paths']['A']['learning_rate']!=1e-4 or a['paths']['B']['learning_rate']!=3e-4):
        raise ValueError('Final scientific design changed')
    return value


def _bundle_metadata(binding):
    """Verify bytes and metadata only; array deserialization belongs after gate."""
    if set(binding)!={'path','seal_sha256','input_bundle_sha256'}:
        raise ValueError('Explicit complete independent bundle binding required')
    directory = Path(binding['path']).resolve()
    if str(directory)!=binding['path'] or not directory.is_relative_to((storage.ROOT/'input_bundles').resolve()):
        raise ValueError('Only a canonical new-workflow input bundle is accepted')
    seal = sealed(directory,binding['seal_sha256'])
    manifest = read(directory/'manifest.json')
    if (manifest.get('schema')!='native10_final_input_bundle_v1' or manifest.get('status')!='complete'
            or canonical_hash(manifest)!=binding['input_bundle_sha256']
            or seal.get('input_bundle_sha256')!=binding['input_bundle_sha256']
            or canonical_hash(manifest['registered_manifest'])!=manifest['manifest_sha256']):
        raise ValueError('Independent bundle identity differs from its seal/manifest')
    summary = manifest['summary']
    if (summary.get('train_planned')!=600 or summary.get('development_planned')!=100
            or any(summary.get(k) is not True for k in ('complete_planned_disposition','canonical_features_only','source_uniform','no_future_split_outcomes'))):
        raise ValueError('Incomplete or noncanonical final input coverage')
    sources = manifest['source_identities']
    if set(sources)!={'round1_train','round2_train','development'}:
        raise ValueError('Two true training sources and original development are required')
    protocols, namespaces = {}, set()
    for role,source in sources.items():
        b = source['pipeline_binding']; c = source['collection']
        sealed(b['path'],b['seal_sha256'])
        audit = read(checked(b['input_audit_path'],b['input_audit_sha256']))
        if (audit.get('status')!='passed' or audit.get('protocol_sha256')!=b['input_protocol_sha256']
                or audit.get('dataset_seal_sha256')!=b['seal_sha256']
                or audit.get('manifest_sha256')!=manifest['manifest_sha256']
                or audit.get('purpose')!=('development' if role=='development' else 'train')):
            raise ValueError('Original child dataset audit identity changed')
        from .final_input_bundle_v1 import CHECKS
        if any(audit.get('checks',{}).get(key) is not True for key in CHECKS):
            raise ValueError('Original child input audit is incomplete')
        cfg_path = checked(c['config_path'],c['config_sha256'])
        cfg = read(cfg_path); frozen = read(checked(c['freeze_path'],c['freeze_sha256']))
        if (frozen.get('config_sha256')!=c['config_sha256'] or frozen.get('files',{}).get(str(cfg_path))!=c['config_sha256']
                or protocol_digest(cfg)!=cfg['analysis_approval']['protocol_sha256']
                or cfg['episode_manifest']!=manifest['registered_manifest']
                or cfg['analysis_approval']['protocol_sha256']!=b['input_protocol_sha256']):
            raise ValueError('True collection config/freeze/protocol identity differs')
        namespaces.add(cfg['seed_namespace']); protocols[role]=b['input_protocol_sha256']
        critic = source['generation_critic']
        if len(critic['members'])!=4 or len(set(critic['members']))!=4:
            raise ValueError('Each original generation critic requires four unchanged member IDs')
        for name,digest in critic['files'].items():checked(name,digest)
        if role=='round2_train':
            completion = source['completion_audit']
            sealed(completion['path'],completion['seal_sha256'])
            result = read(checked(Path(completion['path'])/'result.json',completion['result_sha256']))
            if (result.get('status')!='passed' or result.get('dataset_binding')!=b
                    or any(result.get('collection',{}).get(k)!=v for k,v in c.items())
                    or result.get('wave_gate',{}).get('all_300_disposed') is not True
                    or result.get('wave_gate',{}).get('wave_exited') is not True
                    or result.get('coverage',{}).get('planned_slot_count')!=300):
                raise ValueError('Round2 must have its complete independent whole-wave audit')
    if (protocols['round1_train']!=protocols['development'] or protocols['round1_train']==protocols['round2_train']
            or len(namespaces)!=1):
        raise ValueError('True child protocols or common seed namespace changed')
    return manifest,namespaces.pop()


def preview_specification(bundle_binding):
    """Read-only preview for analysis to bind; no READY, model or output writes."""
    binding = read(bundle_binding) if not isinstance(bundle_binding,dict) else deepcopy(bundle_binding)
    design = _design()
    checked(CONTRACT,CONTRACT_SHA); checked(BRIEF,BRIEF_SHA); checked(NUMERICAL_DECISION,NUMERICAL_DECISION_SHA)
    manifest,namespace = _bundle_metadata(binding)
    spec = dict(schema=SCHEMA,phase='final',input_bundle=binding,
        source_bindings=manifest['source_identities'],manifest_sha256=manifest['manifest_sha256'],
        feature_contract_sha256=canonical_hash(manifest['feature_contract']),
        design=dict(path=str(DESIGN.resolve()),sha256=DESIGN_SHA),
        documents=dict(input_contract=dict(path=str(CONTRACT.resolve()),sha256=CONTRACT_SHA),
                       implementation_brief=dict(path=str(BRIEF.resolve()),sha256=BRIEF_SHA),
                       numerical_decision=dict(path=str(NUMERICAL_DECISION.resolve()),sha256=NUMERICAL_DECISION_SHA)),
        code_files=code_files(),stop_after={'A':4000,'B':4000},numeric_runtime=numeric_runtime())
    identity = {key:deepcopy(spec[key]) for key in IDENTITY_KEYS}
    identity['seed_namespace']=namespace
    return dict(specification=spec,design=design,identity=identity,
        specification_sha256=canonical_hash(identity),manifest=manifest['registered_manifest'])


def _release(ready,mode):
    if mode not in STAGES:raise ValueError('Unsupported final execution mode')
    if (ready.get('task_id')!='native10-training-20260916'
            or not (ready.get('status')=='approved' or str(ready.get('status','')).startswith('protocol_approved_'))
            or SCOPES[mode] not in ready.get('released_scope',[])):
        raise ValueError('Analysis READY has not released '+SCOPES[mode])
    release = ready.get(RELEASES[mode],{})
    cap = 0 if mode=='preflight' else 32000
    if (release.get('stage')!=STAGES[mode] or release.get('scope')!=SCOPES[mode]
            or release.get('simulator_attempts_limit')!=0 or release.get('optimizer_updates_limit')!=cap
            or release.get('training_updates')!=cap
            or release.get('workflow_optimizer_updates_hard_limit')!=51200):
        raise ValueError('Final READY stage/scope/resource limits differ')
    return release


def _gate(config,mode):
    validate_protocol(config,require_runnable=True)
    ready = read(config['analysis_ready']['path']); release = _release(ready,mode)
    spec = config.get('final_training_pipeline',{})
    identity = {key:spec.get(key) for key in IDENTITY_KEYS}; identity['seed_namespace']=config['seed_namespace']
    expected = dict(simulator_attempts=0,training_updates=0 if mode=='preflight' else 32000)
    if (config.get('final_fit_preparation',{}).get('mode')!=mode
            or config['budget']['hard_total']!=50000 or config['budget']['training_update_total']!=51200
            or config['budget']['stages'].get(STAGES[mode])!=expected
            or config['stage_release_scopes'].get(STAGES[mode])!=SCOPES[mode]
            or release.get('input_bundle')!=spec.get('input_bundle')
            or release.get('design_sha256')!=DESIGN_SHA
            or release.get('specification_sha256')!=canonical_hash(identity)):
        raise ValueError('Final READY does not bind this complete science/input identity')
    for stage,scope in config['stage_release_scopes'].items():
        if stage!=STAGES[mode] and scope in ready['released_scope']:
            raise ValueError('Unrelated formal stage is released by this final-only config')
    if mode=='preflight' and 'preflight' in spec:
        raise ValueError('Preflight cannot masquerade as a bound future fit')
    if mode=='fit' and release.get('preflight')!=spec.get('preflight'):
        raise ValueError('Final fit READY does not bind its exact passed initial state')
    return STAGES[mode]


def require_preflight(config):
    """True zero-resource scope check; does not reserve a fake optimizer update."""
    return _gate(config,'preflight')


def require_fit(config,*,used=0,total_used=0,requested=1):
    _gate(config,'fit')
    return require_stage_budget(config,'training_final',resource='training_updates',
        used=used,total_used=total_used,requested=requested)


def _preflight(binding,identity):
    if not isinstance(binding,dict) or set(binding)!={'path','seal_sha256','result_sha256'}:
        raise ValueError('Final fit requires a complete independent preflight binding')
    directory=Path(binding['path']).resolve()
    if not directory.is_relative_to((storage.ROOT/'fit_preflight/final').resolve()):
        raise ValueError('Only final preflight initialization is accepted')
    seal=sealed(directory,binding['seal_sha256'])
    result=read(checked(directory/'result.json',binding['result_sha256']))
    if (seal.get('role')!='native10_final_fit_preflight_zero_updates' or seal.get('audit_status')!='passed'
            or seal.get('optimizer_updates')!=0 or seal.get('model_fit_complete') is not False
            or result.get('status')!='passed' or result.get('identity')!=identity
            or result.get('optimizer_updates')!=0 or result.get('simulator_calls')!=0
            or result.get('model_fit_complete') is not False
            or any(result.get(k) is not True for k in ('both_paths_checked_before_any_optimizer_update',
                'all_eight_initial_states_checked','canonical_reload_passed','dense_diagnostics_complete',
                'dense_report_analysis_review_required_before_training'))
            or type(result.get('batch_singleton_bit_exact')) is not bool
            or result.get('numeric_contract')!='canonical_strict_passed_dense_reported'
            or result.get('numeric_runtime')!=identity['numeric_runtime']
            or result.get('numerical_review_required') is not False):
        raise ValueError('Only passed zero-update identical final preflight is accepted')
    if set(result.get('initial_assets',{}))!={'A','B'}:
        raise ValueError('Final preflight needs both original initial ensembles')
    for assets in result['initial_assets'].values():
        if len(assets.get('model_hashes',{}))!=4 or not Path(assets['path']).resolve().is_relative_to(directory):
            raise ValueError('Final preflight needs eight sealed initial members')
        sealed(assets['path'],assets['seal_sha256'])
    saved=read(directory/'config.json')
    _,_,saved_identity=validate_specification(saved,'preflight')
    if saved_identity!=identity:raise ValueError('Saved preflight configuration identity differs')
    return result


def validate_specification(config,mode='preflight'):
    """Mode gate first, then metadata/SHA only; caller next validates raw arrays."""
    _gate(config,mode)
    spec=deepcopy(config['final_training_pipeline'])
    preview=preview_specification(spec['input_bundle'])
    without_preflight={k:v for k,v in spec.items() if k!='preflight'}
    if (without_preflight!=preview['specification'] or config['episode_manifest']!=preview['manifest']
            or config['seed_namespace']!=preview['identity']['seed_namespace']):
        raise ValueError('Frozen final specification differs from actual immutable inputs/code')
    if mode=='fit':_preflight(spec.get('preflight'),preview['identity'])
    return spec,preview['design'],preview['identity']


validate_final_config = validate_specification


def _references(ready_path,ready):
    refs={str(ready_path):storage.sha256(ready_path)}
    for key in ('task_document','protocol_review'):
        path=Path(ready[key])
        if not path.is_absolute():path=ready_path.parent.parent/path
        path=checked(path,ready[key+'_sha256']);refs[str(path)]=ready[key+'_sha256']
    return refs


def _add(files,path,digest):
    path=str(checked(path,digest))
    if path in files and files[path]!=digest:raise ValueError('Frozen dependency identity collision')
    files[path]=digest


def _directory_files(files,path,digest):
    path=Path(path).resolve();record=sealed(path,digest)
    _add(files,path/'complete.json',digest)
    for name,expected in record['files'].items():_add(files,path/name,expected)


def _dependencies(spec,design):
    files={}
    for path,digest in spec['code_files'].items():_add(files,path,digest)
    for item in [spec['design'],*spec['documents'].values()]:_add(files,item['path'],item['sha256'])
    runtime_file=spec['numeric_runtime']['torch_version_file'];_add(files,runtime_file['path'],runtime_file['sha256'])
    b=spec['input_bundle'];_directory_files(files,b['path'],b['seal_sha256'])
    manifest=read(Path(b['path'])/'manifest.json')
    # Canonical extraction and ActionTransform identities remain explicit even
    # though those collectors are not executed by this CPU training pipeline.
    feature=manifest['feature_contract']
    for bindings in (manifest.get('implementation',{}),manifest.get('analysis_sources',{}),
                     feature.get('feature_extractor',{}),feature.get('action_transform',{}).get('files',{})):
        for name,digest in bindings.items():_add(files,name,digest)
    for source in spec['source_bindings'].values():
        b=source['pipeline_binding'];c=source['collection']
        _directory_files(files,b['path'],b['seal_sha256']);_add(files,b['input_audit_path'],b['input_audit_sha256'])
        _add(files,c['config_path'],c['config_sha256']);_add(files,c['freeze_path'],c['freeze_sha256'])
        for name,digest in source['generation_critic']['files'].items():_add(files,name,digest)
        completion=source.get('completion_audit')
        if completion:_directory_files(files,completion['path'],completion['seal_sha256'])
    imports=design['old_weight_import']
    _add(files,storage.PACKAGE/imports['ranking'],imports['ranking_sha256'])
    for path,digest in imports['files'].items():_add(files,storage.PACKAGE/path,digest)
    if 'preflight' in spec:
        b=spec['preflight'];_directory_files(files,b['path'],b['seal_sha256'])
    return files


def prepare(*,bundle_binding,ready_path,version,mode='preflight',preflight_binding=None,cpu_evidence=()):
    """Freeze a NEW final-only execution config; not execution or new permission.

    READY.<final_fit_preflight|final_training> must bind the preview's complete
    input_bundle, design_sha256 and specification_sha256, stage/scope, resource
    limits, training_updates and workflow_optimizer_updates_hard_limit=51200.
    Fit additionally binds preflight={path,seal_sha256,result_sha256}.
    """
    if mode not in STAGES or not isinstance(version,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',version):
        raise ValueError('Use an explicit mode and safe NEW version')
    ready_path=Path(ready_path).resolve()
    if ready_path.name!='NATIVE10_ANALYSIS_READY.json':raise ValueError('Expected workflow READY filename')
    ready=read(ready_path);_release(ready,mode) # fail before any bundle access/write
    references=_references(ready_path,ready)
    preview=preview_specification(bundle_binding);spec=deepcopy(preview['specification'])
    if mode=='fit':
        binding=read(preflight_binding) if not isinstance(preflight_binding,dict) else deepcopy(preflight_binding)
        _preflight(binding,preview['identity']);spec['preflight']=binding
    elif preflight_binding is not None:raise ValueError('Preflight cannot consume a fit binding')
    cfg=pending_protocol();base=read(spec['source_bindings']['round2_train']['collection']['config_path'])
    cfg.update(status='frozen',episode_manifest=preview['manifest'],seed_namespace=preview['identity']['seed_namespace'],
        replicates=4,cpu={'worker_threads':2,'critic_threads':2},budget=deepcopy(base['budget']),
        final_training_pipeline=spec,final_fit_preparation=dict(mode=mode,phase='final',scope=SCOPES[mode]))
    cfg['budget']['stages']['final_fit_preflight']=dict(simulator_attempts=0,training_updates=0)
    cfg['stage_release_scopes']={stage:('p0_anchor_and_native10_diagnostics' if stage=='p0' else 'locked_final_'+stage)
        for stage in cfg['budget']['stages']}
    cfg['stage_release_scopes'][STAGES[mode]]=SCOPES[mode]
    cfg['analysis_ready']=dict(path=str(ready_path),sha256=storage.sha256(ready_path))
    task=Path(ready['task_document'])
    if not task.is_absolute():task=ready_path.parent.parent/task
    cfg['analysis_approval']=dict(status='approved',approved_by='analysis',document_path=str(task.resolve()),
        document_sha256=ready['task_document_sha256'],protocol_sha256=protocol_digest(cfg))
    validate_specification(cfg,mode)
    files=_dependencies(spec,preview['design'])
    # Live READY is mutable by the analysis handoff. Its immutable copy, not
    # the live pathname, is the runtime dependency for this released stage.
    for evidence in cpu_evidence:_directory_files(files,evidence['path'],evidence['seal_sha256'])
    destination=storage.ROOT/'final_fit_protocols'/version
    destination.mkdir(parents=True,exist_ok=False)
    try:
        # Keep READY verbatim with its two canonical relative documents together.
        snapshots=destination/'coordination';snapshots.mkdir()
        for source,digest in references.items():
            target=snapshots/Path(source).name
            if target.exists():raise ValueError('Duplicate analysis snapshot basename')
            shutil.copyfile(checked(source,digest),target);_add(files,target,digest)
        snapshot_ready=snapshots/ready_path.name
        copied=read(snapshot_ready)
        if any(Path(copied[k]).is_absolute() or Path(copied[k]).parts!=('coordination',Path(copied[k]).name)
               for k in ('task_document','protocol_review')):
            raise ValueError('READY analysis references must use coordination/<filename>')
        cfg['analysis_ready']=dict(path=str(snapshot_ready),sha256=storage.sha256(snapshot_ready))
        cfg['analysis_approval']['document_path']=str(snapshots/Path(ready['task_document']).name)
        cfg['analysis_approval']['protocol_sha256']=protocol_digest(cfg)
        validate_specification(cfg,mode)
        config_path=destination/'config.json';storage.dump(config_path,cfg);_add(files,config_path,storage.sha256(config_path))
        archive=destination/'code_snapshot.tar.gz'
        archive_files={**spec['code_files'],str(config_path):storage.sha256(config_path)}
        with tarfile.open(archive,'x:gz') as stream:
            for name,digest in sorted(archive_files.items()):
                checked(name,digest);stream.add(name,arcname=name.lstrip('/'),recursive=False);checked(name,digest)
        freeze_path=destination/'freeze.json'
        storage.dump(freeze_path,dict(role=ROLE,mode=mode,phase='final',files=files,
            config_sha256=storage.sha256(config_path),specification_sha256=preview['specification_sha256'],
            code_snapshot=dict(path=str(archive),sha256=storage.sha256(archive),files=archive_files),
            simulator_calls=0,optimizer_updates=0,pca_fits=0,model_initializations=0,
            child_protocols_preserved=True,cpu_evidence=list(cpu_evidence)))
        verify_frozen(config_path,freeze_path,mode)
        return dict(config=str(config_path),config_sha256=storage.sha256(config_path),
                    freeze=str(freeze_path),freeze_sha256=storage.sha256(freeze_path))
    except BaseException as error:
        storage.dump(destination/'failure.json',dict(status='failed',error=repr(error),simulator_calls=0,optimizer_updates=0))
        raise


def verify_frozen(config_path,freeze_path,mode='preflight'):
    config_path=Path(config_path).resolve();freeze_path=Path(freeze_path).resolve()
    if (not config_path.is_relative_to((storage.ROOT/'final_fit_protocols').resolve())
            or freeze_path!=config_path.with_name('freeze.json')):
        raise ValueError('Expected an independent final protocol config/freeze pair')
    frozen=read(freeze_path)
    if (frozen.get('role')!=ROLE or frozen.get('mode')!=mode or frozen.get('phase')!='final'
            or frozen.get('config_sha256')!=storage.sha256(config_path)
            or frozen.get('files',{}).get(str(config_path))!=storage.sha256(config_path)):
        raise ValueError('Final execution freeze/config identity differs')
    for name,digest in frozen['files'].items():checked(name,digest)
    config=read(config_path);spec,design,identity=validate_specification(config,mode)
    if frozen.get('specification_sha256')!=canonical_hash(identity):raise ValueError('Frozen specification identity changed')
    expected=_dependencies(spec,design)
    if any(frozen['files'].get(name)!=digest for name,digest in expected.items()):
        raise ValueError('Final freeze omits a required execution/input dependency')
    archive=frozen['code_snapshot'];checked(archive['path'],archive['sha256'])
    required={**spec['code_files'],str(config_path):storage.sha256(config_path)}
    if archive.get('files')!=required:raise ValueError('Code archive dependency list differs')
    with tarfile.open(archive['path'],'r:gz') as stream:
        members=stream.getmembers()
        if len(members)!=len(required) or {m.name for m in members}!={p.lstrip('/') for p in required}:
            raise ValueError('Code archive member list differs')
        for item in members:
            if not item.isfile():raise ValueError('Code archive must contain regular files')
            if hashlib.sha256(stream.extractfile(item).read()).hexdigest()!=required['/'+item.name]:
                raise ValueError('Archived implementation bytes changed')
    return config


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=STAGES,required=True)
    parser.add_argument('--bundle-binding',type=Path,required=True)
    parser.add_argument('--ready-path',type=Path,required=True)
    parser.add_argument('--version',required=True)
    parser.add_argument('--preflight-binding',type=Path)
    parser.add_argument('--cpu-evidence',type=Path,action='append',default=[])
    args=vars(parser.parse_args());args['cpu_evidence']=[read(path) for path in args['cpu_evidence']]
    print(json.dumps(prepare(**args),ensure_ascii=False))


if __name__=='__main__':main()
