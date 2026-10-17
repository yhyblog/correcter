"""Synthetic metadata/gates only: no tensor imports, PCA, models or real bundle."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from experiments.native10_training_20260916 import final_fit_protocol_v1 as final
from experiments.native10_training_20260916 import storage
from experiments.native10_training_20260916.protocol import TASKS, canonical_hash, protocol_digest, require_stage_budget


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value))
    return storage.sha256(path)


def finish(path,**metadata):
    storage.seal(path,**metadata)
    return storage.sha256(path/'complete.json')


@pytest.fixture
def synthetic(tmp_path,monkeypatch):
    root=tmp_path/'workflow';root.mkdir();project=tmp_path/'project';project.mkdir()
    monkeypatch.setattr(storage,'ROOT',root);monkeypatch.setattr(storage,'PACKAGE',project)
    for attribute,filename in [('CONTRACT','NATIVE10_FINAL_INPUT_CONTRACT.md'),
            ('BRIEF','NATIVE10_FINAL_PREFLIGHT_IMPLEMENTATION_BRIEF.md'),
            ('NUMERICAL_DECISION','NATIVE10_FINAL_NUMERICAL_DECISION.md')]:
        p=project/'coordination'/filename
        p.parent.mkdir(exist_ok=True);p.write_text('synthetic '+attribute)
        monkeypatch.setattr(final,attribute,p);monkeypatch.setattr(final,attribute+'_SHA',storage.sha256(p))
    # Scientific values are original metadata; synthetic old asset bytes are never deserialized.
    design=json.loads((final.CODE/'training_design_v2.json').read_text())
    p=project/'ranking.json';put(p,{})
    weights=project/'old.pt';weights.write_bytes(b'not a tensor file')
    design['old_weight_import']=dict(ranking='ranking.json',ranking_sha256=storage.sha256(p),files={'old.pt':storage.sha256(weights)},read_only=True)
    dp=root/'original_design.json';put(dp,design);monkeypatch.setattr(final,'DESIGN',dp);monkeypatch.setattr(final,'DESIGN_SHA',storage.sha256(dp))
    code=project/'new_protocol.py';code.write_text('# synthetic implementation dependency')
    monkeypatch.setattr(final,'code_files',lambda:{str(code):storage.sha256(code)})
    manifest=[]
    for split,number,start,count in [('train',1,1000,300),('train',2,1300,300),('development',None,1600,100)]:
        for i in range(count):
            task=TASKS[i%5];manifest.append(dict(episode_id=f'{task}__{start+i}',task=task,env_seed=start+i,split=split,round=number))
    budget=dict(hard_total=50000,training_update_total=51200,count_failures=True,count_retries=True,stages={
        'p0':dict(simulator_attempts=600,training_updates=0),'round2_labels':dict(simulator_attempts=17400,training_updates=0),
        'training_round1':dict(simulator_attempts=0,training_updates=19200),'training_final':dict(simulator_attempts=0,training_updates=32000)})
    collections={}
    for number in (1,2):
        cfg=dict(episode_manifest=manifest,seed_namespace='synthetic-final',budget=budget,number=number)
        cfg['analysis_approval']=dict(protocol_sha256=protocol_digest(cfg))
        folder=root/f'collections/{number}';cp=folder/'config.json';ch=put(cp,cfg)
        fp=folder/'freeze.json';fh=put(fp,dict(config_sha256=ch,files={str(cp):ch}))
        collections[number]=dict(config_path=str(cp),config_sha256=ch,freeze_path=str(fp),freeze_sha256=fh)
    from experiments.native10_training_20260916.final_input_bundle_v1 import CHECKS
    sources={}
    for role,number in [('round1_train',1),('round2_train',2),('development',1)]:
        directory=root/'datasets'/role;put(directory/'metadata.json',{'synthetic':True});dh=finish(directory)
        cfg=json.loads(Path(collections[number]['config_path']).read_text());protocol=cfg['analysis_approval']['protocol_sha256']
        audit=root/'dataset_audits'/role/'input_audit.json'
        ah=put(audit,dict(status='passed',purpose='development' if role=='development' else 'train',
            protocol_sha256=protocol,dataset_seal_sha256=dh,manifest_sha256=canonical_hash(manifest),checks={k:True for k in CHECKS}))
        binding=dict(path=str(directory),seal_sha256=dh,input_audit_path=str(audit),input_audit_sha256=ah,input_protocol_sha256=protocol)
        criticfiles={};members={}
        for member in (['1041','1042','1043','1044'] if number==1 else ['0','1','2','3']):
            weight=root/f'critics/{number}/{member}.pt';weight.parent.mkdir(parents=True,exist_ok=True)
            weight.write_bytes(('synthetic opaque '+member).encode());criticfiles[str(weight)]=storage.sha256(weight);members[member]=storage.sha256(weight)
        source=dict(pipeline_binding=binding,collection=collections[number],bank_version=f'round{number}',
            generation_critic=dict(members=members,files=criticfiles),completion_audit=None)
        if number==2:
            p=root/'round2_completion';rh=put(p/'result.json',dict(status='passed',dataset_binding=binding,collection=collections[number],
                wave_gate=dict(all_300_disposed=True,wave_exited=True),coverage=dict(planned_slot_count=300)))
            source['completion_audit']=dict(path=str(p),seal_sha256=finish(p),result_sha256=rh)
        sources[role]=source
    record=dict(schema='native10_final_input_bundle_v1',status='complete',registered_manifest=manifest,manifest_sha256=canonical_hash(manifest),
        source_identities=sources,feature_contract={'canonical':True},summary=dict(train_planned=600,development_planned=100,
            complete_planned_disposition=True,canonical_features_only=True,source_uniform=True,no_future_split_outcomes=True))
    directory=root/'input_bundles/synthetic';put(directory/'manifest.json',record)
    binding=dict(path=str(directory),input_bundle_sha256=canonical_hash(record))
    binding['seal_sha256']=finish(directory,input_bundle_sha256=binding['input_bundle_sha256'])
    preview=final.preview_specification(binding)
    coordination=project/'coordination';task=coordination/'task.md';review=coordination/'review.md'
    task.write_text('synthetic approved task');review.write_text('synthetic approved review')
    ready_path=coordination/'NATIVE10_ANALYSIS_READY.json'
    def ready(mode='preflight',preflight=None):
        cap=0 if mode=='preflight' else 32000
        release=dict(stage=final.STAGES[mode],scope=final.SCOPES[mode],input_bundle=binding,design_sha256=final.DESIGN_SHA,
            specification_sha256=preview['specification_sha256'],simulator_attempts_limit=0,optimizer_updates_limit=cap,
            training_updates=cap,workflow_optimizer_updates_hard_limit=51200)
        if preflight is not None:release['preflight']=preflight
        value=dict(task_id='native10-training-20260916',status='approved',released_scope=[final.SCOPES[mode]],
            task_document='coordination/task.md',task_document_sha256=storage.sha256(task),protocol_review='coordination/review.md',
            protocol_review_sha256=storage.sha256(review),new_simulator_attempts_hard_limit=50000,p0_attempts_hard_limit=600)
        value[final.RELEASES[mode]]=release;put(ready_path,value);return value
    ready()
    return dict(root=root,binding=binding,preview=preview,ready_path=ready_path,ready=ready,code=code)


def prepare(f,mode='preflight',preflight=None,version=None):
    return final.prepare(bundle_binding=f['binding'],ready_path=f['ready_path'],version=version or mode,
        mode=mode,preflight_binding=preflight)


def initialized(f,*,status='passed',dense_exact=True):
    frozen=prepare(f);config=final.read(frozen['config'])
    directory=f['root']/'fit_preflight/final/synthetic'
    put(directory/'config.json',config)
    assets={}
    for path in ('A','B'):
        dest=directory/path/'initial';members={}
        for member in range(4):
            p=dest/f'member{member}.pt';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(f'initial{path}{member}'.encode());members[str(member)]=storage.sha256(p)
        assets[path]=dict(path=str(dest),seal_sha256=finish(dest),model_hashes=members)
    result=dict(status=status,identity=f['preview']['identity'],optimizer_updates=0,simulator_calls=0,model_fit_complete=False,
        both_paths_checked_before_any_optimizer_update=True,all_eight_initial_states_checked=True,canonical_reload_passed=True,
        batch_singleton_bit_exact=dense_exact,numerical_review_required=status!='passed',initial_assets=assets,
        numeric_contract='canonical_strict_passed_dense_reported',numeric_runtime=f['preview']['identity']['numeric_runtime'],
        dense_diagnostics_complete=True,dense_report_analysis_review_required_before_training=True)
    rh=put(directory/'result.json',result)
    return dict(path=str(directory),seal_sha256=finish(directory,role='native10_final_fit_preflight_zero_updates',
        audit_status=status,optimizer_updates=0,model_fit_complete=False),result_sha256=rh)


def test_preview_is_stable_metadata_only_and_keeps_true_protocols(synthetic):
    f=synthetic;p=final.preview_specification(f['binding'])
    assert p==f['preview']
    protocols={k:v['pipeline_binding']['input_protocol_sha256'] for k,v in p['identity']['source_bindings'].items()}
    assert protocols['round1_train']==protocols['development']!=protocols['round2_train']
    assert len(p['manifest'])==700
    assert not (f['root']/'final_fit_protocols').exists()


def test_zero_resource_preflight_and_other_scopes_locked(synthetic):
    f=synthetic;result=prepare(f);cfg=final.verify_frozen(result['config'],result['freeze'],'preflight')
    assert final.require_preflight(cfg)=='final_fit_preflight'
    for stage,resource in [('final_fit_preflight','training_updates'),('final_fit_preflight','simulator_attempts'),
        ('training_final','training_updates'),('training_round1','training_updates'),('round2_labels','simulator_attempts'),('p0','simulator_attempts')]:
        with pytest.raises(ValueError):require_stage_budget(cfg,stage,resource=resource)
    assert not (f['root']/'budget').exists()


def test_fit_uses_same_identity_initial_state_and_original_budget_gate(synthetic):
    f=synthetic;binding=initialized(f);f['ready']('fit',binding);result=prepare(f,'fit',binding)
    cfg=final.verify_frozen(result['config'],result['freeze'],'fit')
    _,_,identity=final.validate_specification(cfg,'fit')
    assert identity==f['preview']['identity']
    assert cfg['final_training_pipeline']['preflight']==binding
    assert final.require_fit(cfg,used=31999,total_used=51199)['remaining_after']==0
    with pytest.raises(ValueError):final.require_fit(cfg,used=32000,total_used=51200)
    with pytest.raises(ValueError):require_stage_budget(cfg,'round2_labels')
    with pytest.raises(ValueError):final.require_preflight(cfg)


def test_unreleased_prepare_fails_before_bundle_read_or_write(synthetic,monkeypatch):
    f=synthetic;ready=f['ready']();ready['released_scope']=['cpu_protocol_checks'];put(f['ready_path'],ready)
    monkeypatch.setattr(final,'preview_specification',lambda _:pytest.fail('bundle must not be read'))
    with pytest.raises(ValueError,match='has not released'):prepare(f)
    assert not (f['root']/'final_fit_protocols').exists()


@pytest.mark.parametrize('field,value',[('simulator_attempts_limit',1),('optimizer_updates_limit',1),('training_updates',1),
    ('workflow_optimizer_updates_hard_limit',51201),('stage','training_final'),('scope','cpu_protocol_checks')])
def test_preflight_resource_or_scope_change_rejected(synthetic,field,value):
    f=synthetic;ready=f['ready']();ready['final_fit_preflight'][field]=value;put(f['ready_path'],ready)
    with pytest.raises(ValueError):prepare(f)
    assert not (f['root']/'final_fit_protocols').exists()


@pytest.mark.parametrize('field,value',[('specification_sha256','0'*64),('design_sha256','0'*64),('input_bundle',{})])
def test_release_binding_change_rejected(synthetic,field,value):
    f=synthetic;ready=f['ready']();ready['final_fit_preflight'][field]=value;put(f['ready_path'],ready)
    with pytest.raises(ValueError):prepare(f)
    assert not (f['root']/'final_fit_protocols').exists()


def test_pending_numerical_review_cannot_release_fit(synthetic):
    f=synthetic;binding=initialized(f,status='pending_numerical_review');f['ready']('fit',binding)
    with pytest.raises(ValueError,match='Only passed'):prepare(f,'fit',binding)


def test_canonical_strict_passed_with_reported_dense_difference_can_bind_future_fit(synthetic):
    f=synthetic;binding=initialized(f,dense_exact=False);f['ready']('fit',binding)
    result=prepare(f,'fit',binding)
    cfg=final.verify_frozen(result['config'],result['freeze'],'fit')
    assert cfg['final_training_pipeline']['preflight']==binding
    assert final.read(Path(binding['path'])/'result.json')['batch_singleton_bit_exact'] is False


def test_runtime_metadata_does_not_import_torch():
    import sys
    prior='torch' in sys.modules
    runtime=final.numeric_runtime()
    assert ('torch' in sys.modules)==prior
    assert runtime['device']=='cpu' and runtime['dtype']=='float32' and runtime['threads']==2
    assert runtime['torch_version_file']['sha256']==storage.sha256(runtime['torch_version_file']['path'])


def test_runtime_identity_changed_after_preflight_blocks_fit(synthetic,monkeypatch):
    f=synthetic;binding=initialized(f);f['ready']('fit',binding)
    runtime=deepcopy(f['preview']['identity']['numeric_runtime']);runtime['torch']='different build'
    monkeypatch.setattr(final,'numeric_runtime',lambda:runtime)
    with pytest.raises(ValueError):prepare(f,'fit',binding)


def test_new_numerical_decision_is_immutable(synthetic):
    f=synthetic;final.NUMERICAL_DECISION.write_text('changed contract')
    with pytest.raises(ValueError,match='SHA mismatch'):prepare(f)


def test_changed_initial_weight_rejected(synthetic):
    f=synthetic;binding=initialized(f);f['ready']('fit',binding)
    (Path(binding['path'])/'A/initial/member0.pt').write_bytes(b'changed')
    with pytest.raises(ValueError,match='SHA mismatch'):prepare(f,'fit',binding)


def test_original_design_cannot_be_refreshed(synthetic):
    f=synthetic;final.DESIGN.write_text('{}')
    with pytest.raises(ValueError,match='SHA mismatch'):prepare(f)


def test_changed_code_after_freeze_rejected(synthetic):
    f=synthetic;result=prepare(f);f['code'].write_text('changed runtime')
    with pytest.raises(ValueError,match='SHA mismatch'):final.verify_frozen(result['config'],result['freeze'],'preflight')


def test_archive_content_is_checked(synthetic):
    f=synthetic;result=prepare(f);frozen=final.read(result['freeze']);Path(frozen['code_snapshot']['path']).write_bytes(b'bad archive')
    with pytest.raises(ValueError,match='SHA mismatch'):final.verify_frozen(result['config'],result['freeze'],'preflight')


def test_existing_protocol_not_overwritten(synthetic):
    f=synthetic;prepare(f)
    with pytest.raises(FileExistsError):prepare(f)


def test_live_ready_can_advance_without_changing_frozen_preflight(synthetic):
    f=synthetic;result=prepare(f);put(f['ready_path'],{'new':'not this execution'})
    assert final.verify_frozen(result['config'],result['freeze'],'preflight')['status']=='frozen'


def test_child_audit_seal_mismatch_rejected(synthetic):
    f=synthetic;source=f['preview']['identity']['source_bindings']['development']
    Path(source['pipeline_binding']['input_audit_path']).write_text('{}')
    with pytest.raises(ValueError,match='SHA mismatch'):final.preview_specification(f['binding'])


def test_fit_future_total_or_stage_limit_cannot_be_relaxed(synthetic):
    f=synthetic;binding=initialized(f);ready=f['ready']('fit',binding);ready['final_training']['optimizer_updates_limit']=32001
    put(f['ready_path'],ready)
    with pytest.raises(ValueError,match='limits differ'):prepare(f,'fit',binding)


def test_unrelated_scope_cannot_be_mapped_into_final_config(synthetic):
    f=synthetic;ready=f['ready']();ready['released_scope'].append('p0_anchor_and_native10_diagnostics');put(f['ready_path'],ready)
    with pytest.raises(ValueError,match='Unrelated formal'):prepare(f)


def test_real_bundle_api_synthetic_output_integrates_without_loading_arrays_in_preview(synthetic,tmp_path,monkeypatch):
    """Create a genuine sealed bundle from fake source artifacts, then preview."""
    import importlib.util
    path=Path(__file__).with_name('test_final_input_bundle_v1.py')
    module_spec=importlib.util.spec_from_file_location('synthetic_final_bundle_fixture',path)
    module=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(module)
    parent=tmp_path/'integration';parent.mkdir()
    fixture=module.synthetic.__wrapped__(parent,monkeypatch)
    binding=module.create(fixture)
    contract=fixture['root']/'documents/NATIVE10_FINAL_INPUT_CONTRACT.md'
    monkeypatch.setattr(final,'CONTRACT',contract);monkeypatch.setattr(final,'CONTRACT_SHA',storage.sha256(contract))
    # Failure if metadata preview ever calls the full array deserializer.
    monkeypatch.setattr(module.bundle,'load_bundle',lambda *a,**k:pytest.fail('preview must not deserialize arrays'))
    preview=final.preview_specification(binding)
    sources=preview['identity']['source_bindings']
    assert set(sources['round1_train']['generation_critic']['members'])=={'1041','1042','1043','1044'}
    assert set(sources['round2_train']['generation_critic']['members'])=={'0','1','2','3'}
    assert preview['identity']['input_bundle']==binding
    assert all(row['round'] is None for row in preview['manifest'] if row['split']=='development')
