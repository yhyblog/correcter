"""All data/weights below are synthetic bytes; no live round2 outcomes are read."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.native10_training_20260916 import final_input_bundle_v1 as bundle
from experiments.native10_training_20260916 import dataset, storage
from experiments.native10_training_20260916.protocol import TASKS, canonical_hash, protocol_digest


def digest(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    root=tmp_path/'workflow';root.mkdir();monkeypatch.setattr(storage,'ROOT',root)
    documents={}
    for name in (*dataset.ANALYSIS_SOURCE_NAMES,'NATIVE10_FINAL_INPUT_CONTRACT.md'):
        path=root/'documents'/name;path.parent.mkdir(exist_ok=True);path.write_text('synthetic '+name)
        documents[str(path)]=storage.sha256(path)
    monkeypatch.setattr(bundle,'CONTRACT_SHA',documents[str(root/'documents/NATIVE10_FINAL_INPUT_CONTRACT.md')])
    manifest=[]
    for split,number,start,count in [('train',1,1000,300),('train',2,1300,300),('development',None,1600,100),('calibration',None,1800,100),('heldout',None,1900,100)]:
        for i in range(count):
            task=TASKS[i%5];key=f'{task}__{start+i}'
            manifest.append(dict(episode_id=key,case_id=key,task=task,env_seed=start+i,split=split,round=number,
                source_horizon=10,cut_rule=dict(kind='first_alarm')))
    # One legitimate registered first-source replacement exercises planned vs
    # actual episode grouping without changing the600/100 denominators.
    primary=manifest[0];backup=dict(primary,episode_id=f'{primary["task"]}__9000',case_id=f'{primary["task"]}__9000',
        env_seed=9000,replacement_of=primary['episode_id'],replacement_ordinal=1)
    manifest.append(backup)
    replacements={primary['episode_id']:[backup['episode_id']]}
    features={}
    for suffix in ('ac_tmil/evaluation/metaworld_vla_features.py','ac_tmil/vla_features.py',
                   'ac_tmil/ogg/common.py','ac_tmil/ogg_research/experiment.py',
                   'native10_training_20260916/engine.py','src/corrector/actions.py'):
        p=root/'synthetic_code'/suffix;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('never import '+suffix)
        features[str(p)]=storage.sha256(p)
    post=root/'synthetic_action/policy_postprocessor.json';post.parent.mkdir()
    post.write_text(json.dumps(dict(steps=[dict(state_file='action_quantiles.safetensors',config=dict(norm_map={'ACTION':'QUANTILES'},eps=1e-8))])))
    state=post.parent/'action_quantiles.safetensors';state.write_bytes(b'opaque synthetic bytes, never load tensor')
    features.update({str(p):storage.sha256(p)for p in (post,state)})
    configs={};collection_bindings={}
    for number in (1,2):
        assets=root/f'critic{number}';assets.mkdir();members={};model_files={}
        ids=['1041','1042','1043','1044']if number==1 else ['0','1','2','3']
        for member in ids:
            p=assets/f'models/refit/member_{member}/selected.pt';p.parent.mkdir(parents=True)
            p.write_bytes(f'synthetic checkpoint round{number} member{member}'.encode());members[member]=storage.sha256(p);model_files[str(p)]=members[member]
        for name,value in [('ranking.json',dict(model_hashes=members)),('config.json',dict(horizon=10,projected_dimensions=16))]:
            p=assets/name;p.write_text(json.dumps(value));model_files[str(p)]=storage.sha256(p)
        bank_name=f'round{number}_labels_v1';bank_ids=[r['episode_id']for r in manifest if not r.get('replacement_of')and (r['split']=='train'and r['round']==number or number==1 and r['split']=='development')]
        models=dict(vla=digest('vla'),d=digest('d'),g0=digest('g0'),implementation=digest('code'),**{'critic_'+k:v for k,v in members.items()})
        cfg=dict(status='frozen',episode_manifest=manifest,critic_assets=str(assets),seed_namespace='synthetic_pairing',
            source_horizon=10,prefix_horizon=10,suffix_horizon=10,control_budget=300,guidance={'alpha':10},
            matching={'xyz_rms':.05},command_semantics='native10 raw',model_dependency_groups={'vla':digest('vla')},
            main_collection=dict(replacement_candidates=replacements,banks={bank_name:dict(stage=f'round{number}_labels',
                generation_round=number,kind='labels13',episode_ids=bank_ids,model_hashes=models,critic_member_hashes=members)}),
            analysis_approval=dict(status='approved'))
        cfg['analysis_approval']['protocol_sha256']=protocol_digest(cfg)
        folder=root/f'main_protocols/round{number}';folder.mkdir(parents=True)
        cp=folder/'config.json';cp.write_text(json.dumps(cfg));fp=folder/'freeze.json'
        fp.write_text(json.dumps(dict(files={str(cp):storage.sha256(cp),**features,**model_files},config_sha256=storage.sha256(cp))))
        configs[number]=cfg;collection_bindings[number]=dict(config_path=str(cp),config_sha256=storage.sha256(cp),freeze_path=str(fp),freeze_sha256=storage.sha256(fp))
    ledger=[]
    def attempt(kind,identity,number,stage=None):
        n=len(ledger)+1;ledger.append(dict(number=n,kind=kind,identity=identity,stage=stage or f'round{number}_labels',
            resource='simulator_attempts',amount=1,protocol_sha256=configs[number]['analysis_approval']['protocol_sha256']))
        return n
    sources={}
    for role in bundle.ROLES:
        purpose,number=('development',1)if role=='development'else('train',int(role[5]));cfg=configs[number]
        bank_name=f'round{number}_labels_v1';bank=cfg['main_collection']['banks'][bank_name];protocol=cfg['analysis_approval']['protocol_sha256']
        planned=[r for r in manifest if not r.get('replacement_of')and r['split']==purpose and (purpose=='development'or r['round']==number)]
        records=[];rows=[];parts=[];artifacts=[];referenced=[];resolutions=[]
        for index,base in enumerate(planned):
            actual=backup if role=='round1_train'and index==0 else base;key=actual['episode_id'];slot=base['episode_id']
            rejects=[]
            if actual is backup:
                failed=attempt('source_capture',slot,number);referenced.append(failed)
                rejects=[dict(episode_id=slot,reason='initialization_failed',budget_attempt=failed,source_seal_sha256=digest('rejected'))]
            source_attempt=attempt('source_capture',key,number,'technical_reserve'if actual is backup else None);referenced.append(source_attempt)
            source_path=root/'sources'/key/'complete.json';source_path.parent.mkdir(parents=True);source_path.write_text(json.dumps(dict(status='complete',episode_id=key)))
            source_sha=storage.sha256(source_path);artifacts.append(dict(path=str(source_path),sha256=source_sha,role='source',protocol_sha256=protocol))
            summary=dict(status='complete',case=actual,protocol_sha256=protocol,budget_attempt=source_attempt,
                scene_fingerprint=digest('scene '+key),exact_state_sha256=digest('exact '+key))
            reached=index<20 if purpose=='train'else index<5
            rec=dict(episode_id=key,planned_slot_id=slot,task=actual['task'],env_seed=actual['env_seed'],split=purpose,
                round=actual['round'],source_summary=summary,critic_eligible=reached,status='complete'if reached else'no_cut',
                control_complete=reached,full_episode_outcome_available=not reached,native10_outcome=False if not reached else None,
                missing_reason=None if reached else'no_legal_cut')
            resolutions.append(dict(planned_slot_id=slot,resolved_episode_id=key,preceding_rejections=rejects))
            if reached:
                bank_path=root/'banks'/bank_name/key/'cut005/complete.json';bank_path.parent.mkdir(parents=True);bank_path.write_text(json.dumps(dict(status='complete',episode_id=key)))
                bank_sha=storage.sha256(bank_path);artifacts.append(dict(path=str(bank_path),sha256=bank_sha,role='bank',protocol_sha256=protocol))
                referenced.append(attempt('candidate_restore',str(bank_path.parent.relative_to(root)),number))
                physical=np.asarray([attempt('branch_including_restore',f'{key}/candidate{i}',number)for i in range(52)],np.int64).reshape(13,4)
                controls=[attempt('branch_including_restore',f'{key}/normal{i}',number)for i in range(4)]
                physical_all=physical.ravel().tolist()+controls;referenced.extend(physical_all)
                rec.update(cut_step=5,physical_attempt_ids=physical_all,provenance=dict(source_seal_sha256=source_sha,
                    candidate_bank_sha256=bank_sha,protocol_sha256=protocol,model_hashes=bank['model_hashes'],suffix_seed_namespace='synthetic_pairing'))
                values={k:np.zeros(shape,np.bool_ if k.endswith('_mask')else np.float32)for k,shape in dataset.STATE_SHAPES.items()}
                values['history'].fill(number);values['remaining']=np.asarray(295/300,np.float32)
                values.update(actions=np.zeros((13,10,4),np.float32),raw_actions=np.zeros((13,10,4),np.float32),
                    outcomes=np.zeros((13,4),np.bool_),candidate_weights=np.full(13,1/13,np.float32),gain_weights=np.zeros(13,np.float32),
                    pair_indices=dataset.PAIR_INDICES.copy(),pair_weights=np.zeros(5,np.float32),alias_indices=np.zeros(13,np.int64),
                    group_ids=np.zeros(13,np.int64),physical_attempt_ids=physical,control_outcomes=np.zeros(4,np.bool_),control_valid=np.ones(4,np.bool_))
                for field,value in dict(episode_id=key,planned_slot_id=slot,split=purpose,task=actual['task']).items():values[field]=np.asarray(value)
                values['cut_step']=np.asarray(5,np.int64);values['round']=np.asarray(actual['round']or 0,np.int64)
                rows.append(dict(actual,planned_slot_id=slot));parts.append(values)
            records.append(rec)
        values={k:np.stack([p[k]for p in parts])for k in parts[0]}
        metadata=dict(schema='native10_dataset13_v1',purpose=purpose,manifest_sha256=canonical_hash(manifest),
            complete_critic_groups=len(rows),planned_episode_count=len(planned),records=records,
            complete_planned_selection_evidence=True,analysis_sources=documents,repeats=4,
            candidate_order=list(bundle.CANDIDATE_ORDER),a0_slot=0,normal_control_is_separate=True)
        packed=dict(rows=rows,arrays=values,metadata=metadata);path=dataset.save_new_dataset(role,packed)
        af=root/'dataset_audits'/role;af.mkdir(parents=True);lp=af/'budget_snapshot.jsonl'
        lp.write_text(''.join(json.dumps(r)+'\n'for r in ledger));artifacts.append(dict(path=str(lp),sha256=storage.sha256(lp),role='budget_snapshot'))
        audit=dict(schema='native10_input_artifact_audit_v1',status='passed',purpose=purpose,protocol_sha256=protocol,
            manifest_sha256=canonical_hash(manifest),dataset_seal_sha256=storage.sha256(path/'complete.json'),
            episode_ids=[r['episode_id']for r in planned],bank_versions=[bank_name],missing_artifacts=[],
            checks=dict.fromkeys(bundle.CHECKS,True),artifacts=artifacts,ledger_snapshot_sha256=storage.sha256(lp),
            referenced_attempts=referenced,slot_resolutions=resolutions,completed_collections_only=role=='round2_train',
            completed_collection_slot_ids=[r['episode_id']for r in planned]if role=='round2_train'else [])
        storage.dump(af/'input_audit.json',audit);storage.seal(af)
        binding=dict(path=str(path),seal_sha256=storage.sha256(path/'complete.json'),input_audit_path=str(af/'input_audit.json'),
            input_audit_sha256=storage.sha256(af/'input_audit.json'),input_protocol_sha256=protocol)
        sources[role]=dict(dataset_binding=binding,collection=collection_bindings[number],bank_version=bank_name)
        if role=='round2_train':
            completion=root/'round2_dataset_reviews/synthetic';completion.mkdir(parents=True)
            (completion/'budget_snapshot.jsonl').write_bytes(lp.read_bytes())
            storage.dump(completion/'evidence.json',{str(af/'input_audit.json'):storage.sha256(af/'input_audit.json')})
            result=dict(schema='native10_round2_dataset_completion_audit_v1',status='passed',dataset_binding=binding,
                collection=dict(collection_bindings[number],bank_version=bank_name,protocol_sha256=protocol),
                wave_gate=dict(all_300_disposed=True,loaded_workers=32,wave_exited=True,
                    planned_slot_ids=[r['episode_id']for r in planned],missing_slot_ids=[]),
                ledger=dict(all_attempts_charged=True,new_optimizer_updates=0,snapshot_sha256=storage.sha256(lp)),
                coverage=dict(planned_slot_count=300,complete_planned_selection_evidence=True,unresolved_or_exhausted_slot_ids=[]),
                generation_critic=dict(member_hashes=bank['critic_member_hashes'],assets=cfg['critic_assets']),
                contract=dict(path=str(root/'documents/NATIVE10_FINAL_INPUT_CONTRACT.md'),sha256=bundle.CONTRACT_SHA))
            storage.dump(completion/'result.json',result);storage.seal(completion)
            sources[role]['completion_audit']=dict(path=str(completion),seal_sha256=storage.sha256(completion/'complete.json'),result_sha256=storage.sha256(completion/'result.json'))
    return dict(sources=sources,analysis_sources=documents,root=root,manifest=manifest)


def create(fixture,version='synthetic_bundle'):
    return bundle.create_bundle(version,**fixture['sources'],analysis_sources=fixture['analysis_sources'])


def test_sealed600_bundle_keeps_true_protocols_old_teacher_ids_and_null_dev_round(synthetic):
    binding=create(synthetic);loaded=bundle.load_bundle(binding)
    assert set(binding)=={'path','seal_sha256','input_bundle_sha256'}
    assert loaded['summary']['train_planned']==600 and loaded['summary']['train_effective']==40
    assert loaded['summary']['development_planned']==100 and loaded['summary']['development_effective']==5
    assert set(loaded['metadata']['sources']['round1_train']['generation_critic']['members'])=={'1041','1042','1043','1044'}
    assert set(loaded['metadata']['sources']['round2_train']['generation_critic']['members'])=={'0','1','2','3'}
    for role in bundle.ROLES:assert loaded['metadata']['sources'][role]['pipeline_binding']==synthetic['sources'][role]['dataset_binding']
    assert all(r['round']is None for r in loaded['development']['rows'])
    assert np.all(loaded['train']['arrays']['history'][:20]==1) and np.all(loaded['train']['arrays']['history'][20:]==2)
    assert np.array_equal(loaded['train']['arrays']['raw_deltas'],np.zeros((40,13,10,4),np.float32))
    assert loaded['train']['rows'][0]['episode_id']!=loaded['train']['rows'][0]['planned_slot_id']
    assert len(loaded['bundle_manifest']['planned_provenance'])==700
    assert not any(row['split']in ('calibration','heldout')for row in loaded['bundle_manifest']['planned_provenance'])
    assert bundle.validate_bundle(binding)['status']=='passed'
    with pytest.raises(FileExistsError):create(synthetic)


def test_actual_loaded_bundle_integrates_with_final_prepare(synthetic):
    from experiments.native10_training_20260916 import final_prepare_v1 as final
    binding=create(synthetic);loaded=bundle.load_bundle(binding)
    design=json.loads((final.CODE/'training_design_v2.json').read_text())
    result=final.build_specification(loaded,bundle_binding=binding,design=design,
        design_binding={'path':'synthetic_design','sha256':digest('design')},
        contract_binding={'path':'synthetic_contract','sha256':bundle.CONTRACT_SHA},seed_namespace='synthetic_pairing')
    assert result['coverage']['train']['planned']==600 and result['preprocessing']['B']['fit_source_count']==40
    assert result['sampling_recipe']['total_draws']==40
    assert result['source_protocols']['round1_train']!=result['source_protocols']['round2_train']
    assert result['source_protocols']['development']==result['source_protocols']['round1_train']
    assert not any(result['execution'].values())


@pytest.mark.parametrize('mutation',['missing_completion','rewritten_protocol','wrong_bank','contract','feature_pca'])
def test_contract_or_provenance_mismatch_rejected(synthetic,mutation):
    f=deepcopy(synthetic)
    if mutation=='missing_completion':del f['sources']['round2_train']['completion_audit']
    elif mutation=='rewritten_protocol':f['sources']['round2_train']['dataset_binding']['input_protocol_sha256']=f['sources']['round1_train']['dataset_binding']['input_protocol_sha256']
    elif mutation=='wrong_bank':f['sources']['round2_train']['bank_version']='policy5'
    elif mutation=='contract':f['analysis_sources'][str(f['root']/'documents/NATIVE10_FINAL_INPUT_CONTRACT.md')]=digest('wrong')
    else:
        features=bundle.canonical_feature_contract(f['sources']['round1_train']['collection']);features['state_shapes']['history']=[5,16]
        with pytest.raises(bundle.BundleError,match='Canonical'):bundle.create_bundle('reject',**f['sources'],analysis_sources=f['analysis_sources'],feature_contract=features)
        return
    with pytest.raises(ValueError):create(f,'reject')
    assert not (f['root']/'input_bundles/reject').exists()


def rewrite_audit(fixture,role,change):
    source=fixture['sources'][role];binding=source['dataset_binding'];path=Path(binding['input_audit_path'])
    value=json.loads(path.read_text());change(value);path.write_text(json.dumps(value));binding['input_audit_sha256']=storage.sha256(path)


@pytest.mark.parametrize('mutation',['partial300','failed_check','reordered','duplicate_attempt','future_artifact'])
def test_incomplete_or_future_evidence_rejected(synthetic,mutation):
    role='round1_train'
    def change(audit):
        if mutation=='partial300':audit['episode_ids'].pop()
        elif mutation=='failed_check':audit['checks']['complete_labels']=False
        elif mutation=='reordered':audit['episode_ids'].reverse()
        elif mutation=='duplicate_attempt':audit['referenced_attempts'].append(audit['referenced_attempts'][0])
        else:audit['artifacts'].append(dict(path=str(synthetic['root']/'sources/heldout__999/summary.json'),sha256=digest('missing'),role='source'))
    rewrite_audit(synthetic,role,change)
    with pytest.raises(bundle.BundleError):create(synthetic)


def test_bundle_tampering_and_wrong_independent_hash_rejected(synthetic):
    binding=create(synthetic)
    with pytest.raises(bundle.BundleError):bundle.load_bundle(binding,expected_sha256=digest('wrong'))
    path=Path(binding['path'])/'train/rows.json';path.write_text('[]')
    with pytest.raises(bundle.BundleError):bundle.load_bundle(binding)


def test_completed_only_round2_needs_all_original_slots(synthetic):
    rewrite_audit(synthetic,'round2_train',lambda audit:audit['completed_collection_slot_ids'].pop())
    # Preserve completion binding to test the child300 check rather than SHA drift.
    source=synthetic['sources']['round2_train'];directory=Path(source['completion_audit']['path'])
    result=json.loads((directory/'result.json').read_text());result['dataset_binding']=source['dataset_binding']
    evidence=json.loads((directory/'evidence.json').read_text());p=source['dataset_binding']['input_audit_path'];evidence[p]=storage.sha256(p)
    (directory/'evidence.json').write_text(json.dumps(evidence))
    (directory/'result.json').write_text(json.dumps(result));(directory/'complete.json').unlink();storage.seal(directory)
    source['completion_audit'].update(seal_sha256=storage.sha256(directory/'complete.json'),result_sha256=storage.sha256(directory/'result.json'))
    with pytest.raises(bundle.BundleError,match='Complete unfiltered'):create(synthetic)


def test_unfinished_wave_rejected_before_dataset_read(synthetic,monkeypatch):
    del synthetic['sources']['round2_train']['completion_audit']
    monkeypatch.setattr(bundle,'load_saved_dataset',lambda *a,**k:pytest.fail('dataset read before whole-wave gate'))
    with pytest.raises(bundle.BundleError,match='complete-wave'):create(synthetic)


@pytest.mark.parametrize('mutation',['pca_array','unknown_no_cut','technical_missing','loss_weights','scene_leakage'])
def test_invalid_canonical_or_coverage_content_is_rejected(synthetic,mutation):
    binding=synthetic['sources']['round1_train']['dataset_binding'];path=Path(binding['path'])
    if mutation in ('pca_array','loss_weights'):
        with np.load(path/'arrays.npz',allow_pickle=False) as archive:arrays={k:archive[k]for k in archive.files}
        if mutation=='pca_array':arrays['history']=arrays['history'][...,:16]
        else:arrays['candidate_weights'].fill(1)
        (path/'arrays.npz').unlink();storage.arrays(path/'arrays.npz',**arrays)
    else:
        meta=json.loads((path/'metadata.json').read_text())
        if mutation=='unknown_no_cut':meta['records'][25]['native10_outcome']=None
        elif mutation=='technical_missing':meta['records'][25]['status']='source_failed'
        else:meta['records'][5]['source_summary']['scene_fingerprint']=meta['records'][0]['source_summary']['scene_fingerprint']
        (path/'metadata.json').write_text(json.dumps(meta))
    (path/'complete.json').unlink();storage.seal(path,schema='native10_dataset13_v1')
    binding['seal_sha256']=storage.sha256(path/'complete.json')
    rewrite_audit(synthetic,'round1_train',lambda audit:audit.update(dataset_seal_sha256=binding['seal_sha256']))
    with pytest.raises(bundle.BundleError):create(synthetic)
