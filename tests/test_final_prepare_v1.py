"""Synthetic final-interface coverage/gate checks; no model or real data fit."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from experiments.native10_training_20260916 import final_prepare_v1 as final
from experiments.native10_training_20260916.protocol import TASKS, canonical_hash, episode_key


def fixture_view():
    manifest=[]
    for split,round_number,start,count in [('train',1,1000,300),('train',2,1300,300),('development',None,1600,100)]:
        for i in range(count):
            task=TASKS[i%5];seed=start+i
            manifest.append(dict(episode_id=episode_key(task,seed),task=task,env_seed=seed,split=split,round=round_number))
    result=dict(manifest=manifest,input_bundle_sha256='b'*64)
    for purpose in ('train','development'):
        planned=[row for row in manifest if row['split']==purpose]
        # Deliberately unequal valid task counts and missing cuts in both rounds.
        missing={planned[0]['episode_id'],planned[5]['episode_id'],planned[-2]['episode_id']}
        records=[dict(row,planned_slot_id=row['episode_id'],critic_eligible=row['episode_id'] not in missing,
            control_complete=row['episode_id'] not in missing,status='no_cut' if row['episode_id'] in missing else 'complete',
            full_episode_outcome_available=True) for row in planned]
        rows=[dict(row,planned_slot_id=row['episode_id']) for row in planned if row['episode_id'] not in missing]
        result[purpose]=dict(rows=rows,arrays={},metadata=dict(purpose=purpose,planned_episode_count=len(planned),
            manifest_sha256=canonical_hash(manifest),complete_planned_selection_evidence=True,records=records))
    result['metadata']=dict(sources={name:dict(pipeline_binding=dict(input_protocol_sha256=protocol))
        for name,protocol in [('round1_train','1'*64),('round2_train','2'*64),('development','1'*64)]})
    return result


def plan(loaded=None):
    design=json.loads((final.CODE/'training_design_v2.json').read_text())
    return final.build_specification(loaded or fixture_view(),bundle_binding=dict(input_bundle_sha256='b'*64),
        design=design,design_binding=dict(path='synthetic_design',sha256='a'*64),
        contract_binding=dict(path='synthetic_contract',sha256='c'*64),seed_namespace='synthetic_final_interface')


def test_legitimate_no_cut_keeps_600_plan_but_597_rows():
    spec=plan()
    assert spec['coverage']['train']['planned']==600
    assert spec['coverage']['train']['effective']==597
    assert len(spec['preprocessing']['B']['fit_episode_ids'])==597
    assert len(set(spec['preprocessing']['B']['fit_episode_ids']))==597
    assert spec['sampling_recipe']['total_draws']==597
    assert spec['sampling_recipe']['task_draw_counts'][TASKS[0]]==118
    assert all(not value for value in spec['purpose_intersections'].values())


def test_original_child_protocols_remain_distinct_and_unmodified():
    loaded=fixture_view();before=deepcopy(loaded)
    spec=plan(loaded)
    assert loaded==before
    assert spec['source_protocols']==dict(round1_train='1'*64,round2_train='2'*64,development='1'*64)
    assert spec['future_execution']['single_protocol_pipeline_allowed'] is False


def test_development_keeps_null_episode_round_despite_round1_bank_origin():
    loaded=fixture_view()
    assert all(row['round'] is None for row in loaded['development']['rows'])
    spec=plan(loaded)
    assert spec['coverage']['development']['planned']==100
    assert spec['coverage']['development']['effective']==97
    assert all(row['round'] is None for row in loaded['development']['rows'])


def test_selection_purpose_keeps_full_dev_denominator_separate_from_inference():
    spec=plan()
    assert len(spec['purpose_episode_ids']['checkpoint_selection'])==100
    assert len(spec['purpose_episode_ids']['checkpoint_inference'])==97
    assert spec['development_selection']['planned_denominator']==100
    assert len(spec['development_selection']['common_outcome_ids'])==3
    assert spec['development_selection']['include_common_outcomes_in_full_denominator'] is True


@pytest.mark.parametrize('mutation', ['coverage_flag','technical_status','unknown_no_cut','duplicate_source','changed_order','wrong_round','unregistered_source'])
def test_incomplete_or_replaced_sources_rejected(mutation):
    v=fixture_view();p=v['train']
    if mutation=='coverage_flag':p['metadata']['complete_planned_selection_evidence']=False
    elif mutation=='technical_status':p['metadata']['records'][0]['status']='missing'
    elif mutation=='unknown_no_cut':p['metadata']['records'][0]['full_episode_outcome_available']=False
    elif mutation=='duplicate_source':p['rows'][1]=deepcopy(p['rows'][0])
    elif mutation=='changed_order':p['metadata']['records'].reverse()
    elif mutation=='wrong_round':p['rows'][0]['round']=2
    elif mutation=='unregistered_source':p['rows'][0]['episode_id']='unregistered'
    with pytest.raises(ValueError):plan(v)


def test_development_cannot_be_inserted_in_train_sampling():
    v=fixture_view();rows=v['train']['rows']+[v['development']['rows'][0]]
    with pytest.raises(ValueError):final.sampling_recipe(rows,'test')


def test_sampling_counts_respond_to_valid_task_counts_not_round_or_teacher():
    v=fixture_view();rows=v['train']['rows'];s=final.sampling_recipe(rows,'test')
    changed=[dict(row,teacher='different',round=99,Q=999,success=False) for row in rows]
    assert final.sampling_recipe(changed,'test')==s
    assert sum(s['task_draw_counts'].values())==len(rows)
    assert s['bootstrap_draws_materialized'] is False
    assert s['materialize_after_unique_train_pca'] is True


def test_pending_spec_cannot_release_pca_or_initialization_or_training():
    spec=plan()
    assert spec['status']=='prepared_pending_final_preflight_release'
    assert not any(spec['execution'].values())
    assert spec['future_execution']['max_optimizer_updates']==32000
    assert spec['future_execution']['fixed_checkpoints']==[200,400,800,1600,2400,3200,4000]
    assert spec['old_weight_import']['files']
    assert spec['scientific_parameters']['paths']['A']['learning_rate']==1e-4
    assert spec['scientific_parameters']['paths']['B']['learning_rate']==3e-4


@pytest.mark.parametrize('which', ['round2_train','development'])
def test_forged_common_or_changed_dev_protocol_rejected(which):
    v=fixture_view()
    v['metadata']['sources'][which]['pipeline_binding']['input_protocol_sha256']='1'*64 if which=='round2_train' else '2'*64
    with pytest.raises(ValueError):plan(v)


def test_insufficient_pca_unique_train_rows_rejected():
    v=fixture_view();p=v['train'];keep={row['episode_id'] for row in p['rows'][:16]}
    p['rows']=p['rows'][:16]
    for record in p['metadata']['records']:
        if record['episode_id'] not in keep:
            record.update(critic_eligible=False,status='no_cut',full_episode_outcome_available=True)
    with pytest.raises(ValueError,match='Too few'):plan(v)


def test_prepare_rejects_unbound_contract_before_bundle_read(tmp_path,monkeypatch):
    contract=tmp_path/'contract.md';contract.write_text('unapproved')
    # No bundle loader or weights are reached by an unbound contract.
    with pytest.raises(ValueError,match='SHA differs'):
        final.prepare(bundle_binding={'path':'missing'},version='synthetic',contract_path=contract)


def test_unsafe_output_version_rejected_before_filesystem_work():
    with pytest.raises(ValueError,match='safe'):
        final.prepare(bundle_binding={},version='../overwrite')


def test_prepare_consumes_bundle_interface_and_writes_only_new_pending_seal(tmp_path,monkeypatch):
    from experiments.native10_training_20260916 import final_input_bundle_v1 as bundle
    project=tmp_path/'project';project.mkdir();output=project/'outputs';output.mkdir()
    monkeypatch.setattr(final.storage,'PACKAGE',project)
    monkeypatch.setattr(final.storage,'ROOT',output)
    cfg=project/'collection.json';cfg.write_text(json.dumps(dict(seed_namespace='synthetic_final_interface')))
    loaded=fixture_view()
    for source in loaded['metadata']['sources'].values():
        source['collection']=dict(config_path=str(cfg))
    calls=[]
    def fake_load(binding):
        calls.append(deepcopy(binding));return loaded
    monkeypatch.setattr(bundle,'load_bundle',fake_load)
    contract=project/'contract.md';contract.write_text('synthetic approved contract')
    monkeypatch.setattr(final,'CONTRACT_SHA',final.storage.sha256(contract))
    design=json.loads((final.CODE/'training_design_v2.json').read_text())
    ranking=project/'ranking.json';ranking.write_text('{}')
    weights=project/'old.weights';weights.write_bytes(b'identity-only dummy; cannot deserialize')
    design['old_weight_import']=dict(ranking='ranking.json',ranking_sha256=final.storage.sha256(ranking),
        files={'old.weights':final.storage.sha256(weights)},read_only=True)
    dpath=project/'design.json';dpath.write_text(json.dumps(design))
    monkeypatch.setattr(final,'DESIGN',dpath);monkeypatch.setattr(final,'DESIGN_SHA',final.storage.sha256(dpath))
    binding=dict(path='synthetic_bundle',seal_sha256='s'*64,input_bundle_sha256='b'*64)
    result=final.prepare(bundle_binding=binding,version='cpu',contract_path=contract)
    assert calls==[binding]
    dest=Path(result['path']);seal=json.loads((dest/'complete.json').read_text())
    assert seal['not_execution_release'] is True
    assert set(seal['files'])=={'specification.json'}
    assert seal['files']['specification.json']==final.storage.sha256(dest/'specification.json')
    spec=json.loads((dest/'specification.json').read_text())
    assert not any(spec['execution'].values())
    assert spec['input_bundle']==binding
    with pytest.raises(FileExistsError):
        final.prepare(bundle_binding=binding,version='cpu',contract_path=contract)
