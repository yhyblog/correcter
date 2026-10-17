"""Bounded synthetic heldout guards; no real checkpoints or environment."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from . import heldout_collection_v1 as cal, storage, engine, main_collection, main_runner
from .protocol import TASKS, canonical_hash, candidate_seed
from .main_collection import POLICY_METHODS, SPLIT_REPLICATES, select_cut


@pytest.fixture
def prepared(tmp_path,monkeypatch):
    root=tmp_path/'outputs';monkeypatch.setattr(cal,'ROOT',root);monkeypatch.setattr(storage,'ROOT',root)
    cases=[];backups=[];replacements={}
    seeds=list(range(2026111750,2026111800))+list(range(2026111850,2026111900))
    for i,seed in enumerate(seeds):
        task=TASKS[i%5];identity=f'{task}__{seed}'
        case=dict(task=task,env_seed=seed,episode_id=identity,case_id=identity,split='heldout',round=None,
            source_horizon=10,cut_rule={'kind':'first_alarm'})
        cases.append(case);replacements[identity]=[]
        for ordinal in (1,2):
            backup_seed=2026120000+2*i+ordinal;backup=f'{task}__{backup_seed}'
            backups.append(dict(case,env_seed=backup_seed,episode_id=backup,case_id=backup,
                replacement_of=identity,replacement_ordinal=ordinal));replacements[identity].append(backup)
    models=dict(vla='a'*64,d='b'*64,g0='c'*64,implementation='d'*64)
    old=dict(status='pending',episode_manifest=cases+backups,seed_namespace='synthetic_heldout',
        source_horizon=10,prefix_horizon=10,suffix_horizon=10,control_budget=300,gate_threshold=.05,
        guidance=dict(alpha=10,times=[.3,.2,.1]),matching=dict(xyz_rms=.05,gripper_rms=.1,xyz_linf=.15,
            gripper_linf=.4,boundary_clearance=.05,tolerance=1e-6,zero_threshold=1e-10),
        cpu=dict(worker_threads=4,critic_threads=2),scene_identity={'schema':'synthetic'},command_semantics={'raw_a0':True},
        split_replicates=dict(SPLIT_REPLICATES),methods=list(POLICY_METHODS),
        analysis_approval={'protocol_sha256':'e'*64},main_collection=dict(concurrency={'workers_per_gpu':4},
            replacement_capture_stage='technical_reserve',replacement_candidates=replacements,
            banks={'calibration_policy_v1':dict(model_hashes=models,random_seed_domain='original')}))
    oldpath=root/'old/config.json';freezepath=root/'old/freeze.json'
    storage.dump(oldpath,old);storage.dump(freezepath,{'files':{str(oldpath):storage.sha256(oldpath)}})
    trained=root/'models/final/final_fit_v1';selected=trained/'selected';hashes={}
    for m in range(4):
        path=selected/f'models/refit/member_{m}/selected.pt';path.parent.mkdir(parents=True)
        path.write_bytes(f'opaque synthetic checkpoint {m}'.encode());hashes[str(m)]=storage.sha256(path)
    storage.dump(selected/'ranking.json',dict(horizon=10,a0_slot=0,model_hashes=hashes))
    storage.dump(selected/'config.json',{'synthetic':True})
    storage.seal(selected,role='four_member_critic_export',model_hashes=hashes)
    selectedsha=storage.sha256(selected/'complete.json');monkeypatch.setattr(cal,'FINAL_SELECTED_SEAL',selectedsha)
    storage.dump(trained/'result.json',dict(status='complete',phase='final',selection=dict(path='A',step=4000),
        optimizer_updates=32000,simulator_calls=0,selected_assets=str(selected),model_hashes=hashes))
    checks=('feature_cache_bit_exact','thirteen_candidate_member_probability_bit_exact','member_and_ensemble_gradient_bit_exact',
        'a0_anchor_exactly_zero','state_and_anchor_immutable')
    storage.dump(trained/'selected_reload_audit.json',dict(status='passed',source_count=3,
        episode_ids=['synthetic_old_dev_a','synthetic_old_dev_b','synthetic_old_dev_c'],members_checked=4,
        gradient_slots=[0,11],**dict.fromkeys(checks,True)))
    storage.seal(trained,role='native10_final_two_path_training',phase='final',model_hashes=hashes)
    trainsha=storage.sha256(trained/'complete.json');monkeypatch.setattr(cal,'FINAL_MODEL_SEAL',trainsha)
    review_path=root/'review.json';reloadsha=storage.sha256(trained/'selected_reload_audit.json')
    review=dict(schema='native10_final_trained_model_independent_review_v1',status='passed',blockers=[],model_hashes=hashes,
        selection=dict(path='A',step=4000),bindings=dict(model_directory=str(trained),selected_directory=str(selected),
            model_complete_sha256=trainsha,model_result_sha256=storage.sha256(trained/'result.json'),
            selected_complete_sha256=selectedsha,selected_reload_audit_sha256=reloadsha,
            selected_config_sha256=storage.sha256(selected/'config.json'),selected_ranking_sha256=storage.sha256(selected/'ranking.json')),
        selected_models=[dict(member=m,path=str(selected/f'models/refit/member_{m}/selected.pt'),sha256=hashes[str(m)],
            exact_tensor_match_to_A4000_checkpoint=True) for m in range(4)])
    storage.dump(review_path,review)
    config=deepcopy(old);config['critic_assets']=str(selected)
    config['stage_release_scopes']={cal.STAGE:cal.SCOPE,cal.REPLACEMENT_STAGE:cal.REPLACEMENT_SCOPE}
    config['budget']=dict(hard_total=50000,training_update_total=51200,count_failures=True,count_retries=True,
        stages={cal.STAGE:dict(simulator_attempts=2200,training_updates=0),cal.REPLACEMENT_STAGE:dict(simulator_attempts=1200,training_updates=0)})
    config['main_collection']['banks']={cal.BANK:dict(stage=cal.STAGE,kind='policy5',generation_round=2,generation_phase='heldout',
        episode_ids=[r['episode_id'] for r in cases],cut_selection_policy='analysis_lead_v1',random_seed_domain='original',
        model_hashes=dict(models,**{'critic_'+m:h for m,h in hashes.items()}),critic_member_hashes=hashes)}
    config['heldout_collection']=dict(schema=cal.SCHEMA,effective_cut_policy=deepcopy(cal.EFFECTIVE_CUT_POLICY),
        global_acceptance=deepcopy(cal.GLOBAL_ACCEPTANCE),fixed_primary_comparison='post_minus_alarm_replan10',
        selection_after_heldout_allowed=False,requested_cut_rules_sha256=canonical_hash({r['episode_id']:r['cut_rule'] for r in cases}),
        original_collection=dict(config_path=str(oldpath),config_sha256=storage.sha256(oldpath),freeze_path=str(freezepath),
            freeze_sha256=storage.sha256(freezepath),bank_version='calibration_policy_v1'),
        selected_training=dict(path=str(trained),seal_sha256=trainsha,selected_seal_sha256=selectedsha,
            selected_reload_audit_sha256=reloadsha,model_review=dict(path=str(review_path),sha256=storage.sha256(review_path))))
    live=root/'scene_registry/entries.jsonl';snapshot=root/'preparation/scenes.jsonl'
    for path in (live,snapshot): path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'{"synthetic":true}\n')
    config['heldout_preparation']=dict(scene_registry_before=dict(live_path=str(live),snapshot_path=str(snapshot),
        sha256=storage.sha256(snapshot),bytes=snapshot.stat().st_size,records=1))
    selection_dir=root/'final_selections/final_selection_v1'
    member_files=[dict(path=str(selected/f'models/refit/member_{m}/selected.pt'),sha256=hashes[str(m)]) for m in range(4)]
    selection=dict(status='sealed',schema='native10_final_selection_v1',stage='calibration_selection_seal',scope='calibration_selection_seal',
        method='post',post_enabled_on_alarm=True,primary_comparison='post_minus_alarm_replan10',physical_methods=list(POLICY_METHODS),
        scientific_parameters={k:config[k] for k in cal.SCIENTIFIC_KEYS},heldout_release=False,
        fixed_critic=dict(path='A',step=4000,members=4,selected_directory=str(selected),selected_seal={'path':str(selected/'complete.json'),'sha256':selectedsha},
            selected_reload_audit={'path':str(trained/'selected_reload_audit.json'),'sha256':reloadsha},member_checkpoints=member_files))
    storage.dump(selection_dir/'result.json',selection);storage.seal(selection_dir,role='native10_final_selection_metadata_v1')
    config['heldout_collection']['final_selection']=dict(path=str(selection_dir),seal_sha256=storage.sha256(selection_dir/'complete.json'),result_sha256=storage.sha256(selection_dir/'result.json'))
    monkeypatch.setattr(cal,'_load_selection',lambda binding,**kwargs:json.loads((Path(binding['path'])/'result.json').read_text()))
    from .heldout_prepare_v1 import statistics_contract
    config['heldout_statistics']=statistics_contract(config)
    return config,cases,root


def test_exact_heldout100_and_200_ordered_backups(prepared):
    config,cases,root=prepared;out=cal.validate_heldout_inputs(config)
    assert len(out['episode_ids'])==100 and len(out['cases'])==300
    assert out['new_heldout_capture_allowed'] and not out['cross_bank_a0_identity_required']
    assert out['expected_max_attempts']==2200 and out['expected_max_branches']==2000
    assert out['selected_training']['selection']==dict(path='A',step=4000)
    assert not out['heldout_selection_execution_authorized'] and not (root/'sources').exists()


def test_no_alarm_has_no_training_fallback(prepared):
    _,cases,_=prepared
    result=select_cut(cases[0],[5,15],None)
    assert result['actual_cut'] is None and result['selection_reason']=='no_alarm_policy_common_outcome'
    assert not result['selection_audit']['training_fallback_allowed']
    assert select_cut(cases[0],[5,15],15)['actual_cut']==15


@pytest.mark.parametrize('key,value',[('guidance',{'alpha':20}),('gate_threshold',.1),('source_horizon',50),
    ('split_replicates',dict(SPLIT_REPLICATES,heldout=2)),('command_semantics',{'raw_a0':False})])
def test_science_unchanged(prepared,key,value):
    config,_,_=prepared;config[key]=value
    with pytest.raises(ValueError,match='semantics'):cal.validate_heldout_inputs(config)


def test_new_source_protocol_no_old_dev_reuse(prepared):
    config,_,_=prepared;config['main_collection']['banks'][cal.BANK]['allowed_source_protocol_sha256']=['e'*64]
    with pytest.raises(ValueError,match='new source protocol'):cal.validate_heldout_inputs(config)


def test_old_scope_does_not_release_replacement(prepared):
    config,_,_=prepared;config['stage_release_scopes'][cal.REPLACEMENT_STAGE]='preregistered_initialization_replacements'
    with pytest.raises(ValueError,match='exact scopes'):cal.validate_heldout_inputs(config)


def test_pending_factory_denies_before_engine(prepared,monkeypatch):
    config,_,root=prepared
    monkeypatch.setattr(engine,'create_engine',lambda *x:pytest.fail('No model allowed in preparation'))
    with pytest.raises(ValueError):cal.create_heldout_collector(config)
    assert not (root/'sources').exists()


def test_release_checks_both_scopes_before_assets(prepared,monkeypatch):
    config,_,_=prepared;seen=[]
    def gate(cfg,stage):
        seen.append(stage)
        if stage==cal.REPLACEMENT_STAGE:raise ValueError('replacement not separately released')
    monkeypatch.setattr(cal,'require_stage_budget',gate)
    monkeypatch.setattr(cal,'_selected',lambda *a:pytest.fail('Gate must precede assets'))
    with pytest.raises(ValueError,match='separately'):cal.validate_heldout_inputs(config,require_release=True)
    assert seen==[cal.STAGE,cal.REPLACEMENT_STAGE]


@pytest.mark.parametrize('change',['arm','round','phase','order','acceptance','budget','critic'])
def test_contract_changes_rejected(prepared,change):
    config,_,_=prepared;bank=config['main_collection']['banks'][cal.BANK]
    if change=='arm':config['methods'].pop()
    elif change=='round':bank['generation_round']='heldout'
    elif change=='phase':bank['generation_phase']='calibration'
    elif change=='order':bank['episode_ids'].reverse()
    elif change=='acceptance':config['heldout_collection']['global_acceptance']['rule']='best_of_three'
    elif change=='budget':config['budget']['stages'][cal.STAGE]['training_updates']=1
    elif change=='critic':bank['critic_member_hashes']['0']='f'*64
    with pytest.raises(ValueError):cal.validate_heldout_inputs(config)


def test_scene_registry_append_allowed_prefix_change_rejected(prepared):
    config,_,_=prepared;path=Path(config['heldout_preparation']['scene_registry_before']['live_path'])
    path.write_bytes(path.read_bytes()+b'{"later":true}\n');cal.validate_heldout_inputs(config)
    path.write_bytes(b'X'+path.read_bytes()[1:])
    with pytest.raises(ValueError,match='prefix'):cal.validate_heldout_inputs(config)


def test_backups_order_cannot_be_rewritten(prepared):
    config,cases,_=prepared;config['main_collection']['replacement_candidates'][cases[0]['episode_id']].reverse()
    with pytest.raises(ValueError,match='replacement registration'):cal.validate_heldout_inputs(config)


def test_ledger_exact_capture_bank_arms_repeats(prepared):
    config,cases,_=prepared;inputs=cal.validate_heldout_inputs(config);calls=[]
    delegate=SimpleNamespace(reserve=lambda *a,**kw:calls.append((a,kw)))
    ledger=cal._HeldoutLedger(delegate,inputs);identity=cases[0]['episode_id']
    backup=config['main_collection']['replacement_candidates'][identity][0]
    ledger.reserve(cal.STAGE,'source_capture',identity)
    ledger.reserve(cal.REPLACEMENT_STAGE,'source_capture',backup)
    ledger.reserve(cal.STAGE,'candidate_restore',f'banks/{cal.BANK}/{identity}/cut005')
    for name in POLICY_METHODS:
        for repeat in range(4): ledger.reserve(cal.STAGE,'branch_including_restore',f'rollouts/{cal.STAGE}/{cal.BANK}/{identity}/cut005/{name}/repeat_{repeat}')
    assert len(calls)==23
    for stage,kind,path,kwargs in [
        (cal.STAGE,'source_capture',backup,{}),(cal.REPLACEMENT_STAGE,'source_capture',identity,{}),
        (cal.STAGE,'source_capture','held__123',{}),(cal.STAGE,'source_capture',identity,{'resource':'training_updates'}),
        (cal.STAGE,'source_capture',identity,{'requested':2}),
        (cal.STAGE,'branch_including_restore',f'rollouts/{cal.STAGE}/{cal.BANK}/{identity}/cut005/post/repeat_4',{}),
        (cal.STAGE,'candidate_restore',f'banks/{cal.BANK}/{identity}/cut010',{})]:
        with pytest.raises(ValueError):ledger.reserve(stage,kind,path,**kwargs)


def bank_fixture(matching):
    raw=np.zeros((50,4),np.float32);raw[:,3]=1.5
    plans={name:raw.copy() for name in POLICY_METHODS[1:]}
    for index,name in enumerate(POLICY_METHODS[2:]):plans[name][:10,index]+=.01
    base=np.clip(raw,-1,1);mask=1-np.abs(base[:10].astype(float))>=matching['boundary_clearance']
    formal=dict(raw_a0=raw,critic_a0=base,mask=mask,post_command_gradient=np.zeros((10,4),np.float32),
        post_internal_metric_direction=np.zeros((10,4),np.float32))
    directions=dict(raw_a0=raw,critic_a0=base,critic_candidates=np.stack([np.clip(plans[m],-1,1) for m in POLICY_METHODS[1:]]))
    noise='1'*64
    generation=dict(noise_hashes=dict(replan=noise,velocity=noise,direct=noise),base_generation={'noise_sha256':noise},
        same_noise=True,a0_slot=0,saved_queue_unchanged=True,saved_before_any_branch=True,
        bank_predictions={'alarm_replan10':{'mean_gain':0}},post_gradient={'value':0},guidance={m:{'updates':[]} for m in ('velocity','direct')})
    dependencies=dict(replan=raw,velocity_matched=plans['velocity'],direct_matched=plans['direct'],post_matched=plans['post'])
    reverse=raw.copy();reverse[:10]=2*raw[:10]-plans['direct'][:10]
    random=raw.copy();random[:10,0]-=.01
    dependencies.update(reverse_matched=reverse,random_matched=random)
    for name,plan in dependencies.items():
        formal[name+'_actual_delta']=plan[:10].astype(float)-raw[:10].astype(float)
        formal[name+'_critic_commands']=np.clip(plan[:10],-1,1)
    return plans,formal,directions,generation


def test_same_new_bank_no_old_anchor(prepared):
    config,_,_=prepared;out=cal.audit_heldout_commands(*bank_fixture(config['matching']),config['matching'])
    assert out['status']=='passed' and not out['old_development_a0_compared']
    assert out['matched_rms']['status']=='passed'


@pytest.mark.parametrize('change',['tail','mask','clipped_anchor','critic','rms','noise','gradient','slot','a0score','outsidegrad'])
def test_same_bank_invariants_reject_changes(prepared,change):
    config,_,_=prepared;plans,formal,directions,generation=bank_fixture(config['matching'])
    if change=='tail':plans['post'][20,0]=.01
    elif change=='mask':formal['mask'][0,3]=True
    elif change=='clipped_anchor':plans['alarm_replan10']=np.clip(plans['alarm_replan10'],-1,1)
    elif change=='critic':directions['critic_candidates'][1,0,0]+=.1
    elif change=='rms':plans['post'][:10,:3]*=2;directions['critic_candidates'][3]=np.clip(plans['post'],-1,1)
    elif change=='noise':generation['noise_hashes']['direct']='2'*64
    elif change=='gradient':formal['post_command_gradient'][0,0]=np.nan
    elif change=='slot':generation['a0_slot']=1
    elif change=='a0score':generation['bank_predictions']['alarm_replan10']['mean_gain']=.001
    elif change=='outsidegrad':generation['guidance']['velocity']['updates']=[dict(mode='velocity',direct_gradient_outside_mask=1,objective_semantics='maximize_mean_member_relative_success_probability')]
    with pytest.raises((ValueError,AssertionError)):cal.audit_heldout_commands(plans,formal,directions,generation,config['matching'])


def test_slot_entry_uses_original_resolver(prepared,monkeypatch):
    config,cases,_=prepared;collector=object.__new__(cal.HeldoutCollector)
    collector.heldout_inputs=cal.validate_heldout_inputs(config)
    calls=[];monkeypatch.setattr(main_runner,'resolve_slot',lambda c,p:calls.append((c,p)) or {'synthetic':'resolved'})
    assert cal.collect_heldout_slot(collector,cases[0])=={'synthetic':'resolved'}
    assert calls[0][1] is cases[0]
    backup=config['episode_manifest'][100]
    with pytest.raises(ValueError):cal.collect_heldout_slot(collector,backup)


def test_pending_selection_never_authorizes_real_execution(prepared,monkeypatch):
    config,_,root=prepared;folder=root/'selection_preparation/pending'
    storage.dump(folder/'payload.json',{'status':'pending_selection_seal'})
    storage.seal(folder,role='native10_final_selection_pending_v1')
    pending=dict(status='pending_selection_seal',expected_directory=str(root/'final_selections/final_selection_v1'),
        preparation=dict(path=str(folder),seal_sha256=storage.sha256(folder/'complete.json')),
        payload=dict(path=str(folder/'payload.json'),sha256=storage.sha256(folder/'payload.json')))
    config['heldout_collection']['final_selection']=pending
    monkeypatch.setattr(cal,'_load_selection',lambda binding,**kw:{'status':'pending_selection_seal'})
    assert cal.validate_heldout_inputs(config)['final_selection']['status']=='pending_selection_seal'
    monkeypatch.setattr(cal,'require_stage_budget',lambda *a:None)
    monkeypatch.setattr(engine,'create_engine',lambda *a:pytest.fail('Placeholder cannot create engine'))
    with pytest.raises(ValueError,match='Actual final selection seal'):cal.create_heldout_collector(config)


@pytest.mark.parametrize('change',['method','scientific','member','reload','release'])
def test_changed_actual_selection_payload_rejected(prepared,change):
    config,_,_=prepared;binding=config['heldout_collection']['final_selection'];path=Path(binding['path']);record=json.loads((path/'result.json').read_text())
    if change=='method':record['method']='velocity'
    elif change=='scientific':record['scientific_parameters']['guidance']['alpha']=20
    elif change=='member':record['fixed_critic']['member_checkpoints'][0]['sha256']='f'*64
    elif change=='reload':record['fixed_critic']['selected_reload_audit']['sha256']='f'*64
    elif change=='release':record['heldout_release']=True
    (path/'result.json').write_text(json.dumps(record));(path/'complete.json').unlink();storage.seal(path,role='native10_final_selection_metadata_v1')
    binding.update(seal_sha256=storage.sha256(path/'complete.json'),result_sha256=storage.sha256(path/'result.json'))
    with pytest.raises(ValueError,match='Final selection'):cal.validate_heldout_inputs(config)


@pytest.mark.parametrize('field,value',[('primary_comparison','velocity_minus_alarm_replan10'),('replicates',2),('source_denominator',99),('draws',1000),('no_method_selection_after_heldout',False)])
def test_fixed_heldout_statistics_no_reselection(prepared,field,value):
    config,_,_=prepared;config['heldout_statistics'][field]=value
    with pytest.raises(ValueError,match='statistics must freeze'):cal.validate_heldout_inputs(config)


@pytest.mark.parametrize('change',['missing_random','changed_reverse','unequal_random'])
def test_complete_matching_dependencies_cannot_be_dropped_or_changed(prepared,change):
    config,_,_=prepared;plans,formal,directions,generation=bank_fixture(config['matching'])
    if change=='missing_random':formal.pop('random_matched_actual_delta')
    elif change=='changed_reverse':formal['reverse_matched_critic_commands'][0,0]=.5
    elif change=='unequal_random':
        formal['random_matched_actual_delta'][:,:3]*=2
        raw=formal['raw_a0'];plan=raw.copy();plan[:10]=(raw[:10].astype(float)+formal['random_matched_actual_delta']).astype(np.float32)
        formal['random_matched_actual_delta']=plan[:10].astype(float)-raw[:10].astype(float)
        formal['random_matched_critic_commands']=np.clip(plan[:10],-1,1)
    with pytest.raises((ValueError,AssertionError,KeyError)):cal.audit_heldout_commands(plans,formal,directions,generation,config['matching'])


def test_matching_dependency_reconstruction_preserves_signed_zero(prepared):
    config,_,_=prepared;plans,formal,directions,generation=bank_fixture(config['matching'])
    for plan in plans.values():plan[:10,3]=-0.0
    raw=plans['alarm_replan10'];base=np.clip(raw,-1,1)
    formal.update(raw_a0=raw,critic_a0=base,mask=1-np.abs(base[:10].astype(float))>=config['matching']['boundary_clearance'])
    dependencies=dict(replan=raw,velocity_matched=plans['velocity'],direct_matched=plans['direct'],post_matched=plans['post'])
    reverse=raw.copy();reverse[:10,1]=-.01
    random=raw.copy();random[:10,0]=-.01
    dependencies.update(reverse_matched=reverse,random_matched=random)
    for name,plan in dependencies.items():
        formal[name+'_actual_delta']=plan[:10].astype(float)-raw[:10].astype(float)
        formal[name+'_critic_commands']=np.clip(plan[:10],-1,1)
    directions.update(raw_a0=raw,critic_a0=base,critic_candidates=np.stack([np.clip(plans[m],-1,1) for m in POLICY_METHODS[1:]]))
    result=cal.audit_heldout_commands(plans,formal,directions,generation,config['matching'])
    assert result['dependency_raw_audit']['anchor_bit_identical']
