"""Production publisher of original public episodes and immutable sidecars."""
import copy,hashlib,json
from pathlib import Path
from pool_protocol import raw_group,stream_seed,paired_label
from full_state import signature
from core.contracts import sha,ContractError
def ref(path,format='json'):
    p=Path(path);return dict(path=str(p),sha256=sha(p),format=format)
def emit_sidecar(engine,result):
    cfg=engine.cfg;source=cfg['source'];job=engine.job;name,family,repeat=job
    namespace='normal' if name=='normal' else 'Q_C10' if name.startswith('Q_') else 'G0_C5'
    first_seed=stream_seed(source['master_seed'],source['parent_source_id'],namespace,repeat,0)
    episode=dict(interface_version='corrector-sim-interface/1',synthetic=engine.synthetic,missing_reasons={},
        record_type='episode',identity=engine.identity,episode_id=source['parent_source_id']+'__'+name,
        method=cfg['collection_policy'],environment=dict(name='MetaWorld',version='3.0.0',
            task=engine.task,instruction=source['instruction']),
        source=dict(parent_episode_id=source['parent_source_id'],source_id=source['source_id'],
            initial_state_id=source['parent_source_id']+':s0',branch_id=name,suffix_id=str(repeat)),
        train_seed=None,generation_seed=source['master_seed'],suffix_seed=first_seed,H=10,
        C=5 if namespace=='G0_C5' else 10,split='train',
        success=None if result['outcome']['success'] is None else bool(result['outcome']['success']),
        first_success_step=result['first_success_step'],termination_reason=result['outcome']['reason'],
        technical_status=result['status'],executed_steps=result['controls'],intervened=namespace!='normal',
        cut_step=5 if result['legal_cut_reached'] else None,prefix_id=source['parent_source_id']+':prefix5',
        entry_generation_id=None if name=='normal' else source['parent_source_id']+':bank',
        suffix_run_id=name,reused_from=[],cost_event_refs=['numeric_events.jsonl','initialization_events.jsonl','graphics_events.jsonl'],
        deployment_time_is_reconstructed_estimate=False)
    from public_records import validate_public
    validate_public(episode);engine.store.json('EPISODE_PUBLIC_V1.json',episode)
    template=json.loads((Path(__file__).resolve().parents[1]/'sidecar_v1/synthetic_examples.json').read_text())['examples'][0]['record']
    x=copy.deepcopy(template);x['synthetic']=engine.synthetic;x['record_id']=source['parent_source_id']+'__'+name
    x['record_ref']=ref(engine.out/'EPISODE_PUBLIC_V1.json')
    x['identity']=dict(parent_id=source['parent_source_id'],episode_id=episode['episode_id'],
        source_id=source['source_id'],physical_attempt_id=episode['episode_id'],run_id=engine.identity['run_id'],
        branch_id=name,task=engine.task,split='train',source_manifest_ref=cfg['source_manifest_ref'],
        source_signature=cfg['source_signature'])
    x['protocol']=dict(target_namespace=namespace,cut_step=5 if result['legal_cut_reached'] else None,
        absolute_start_step=0,absolute_end_step=result['controls'],parent_absolute_target_state=300,
        commitment_steps=5 if namespace=='G0_C5' else 10,native_H=10,generated_length=50)
    x['input_signatures']=dict(policy_sha256=cfg['model_sha256'],encoder_sha256=cfg['model_sha256'],
        preprocessing_sha256=cfg['feature_signature'],normalizer_sha256=cfg['normalizer_ref']['sha256'],
        action_representation='raw50_command_and_actual_bounded_float32',action_representation_sha256=cfg['action_signature'])
    x['outcome']=dict(**result['outcome'],last_observed_parent_state=result['controls'],
        first_success_step=result['first_success_step'],terminated=result['terminated'],truncated=result['truncated'],
        missing_reasons=[] if result['outcome']['outcome_complete'] else [result['outcome']['reason']])
    x['repeats']=dict(repeat_id=repeat,planned_repeat_ids=[] if name=='normal' else [0,1],
        complete_repeat_ids=[] if repeat is None or not result['outcome']['outcome_complete'] else [repeat],
        valid_pair_repeat_ids=[],planned=True,entered=True,completed=result['status']=='complete',
        missing=result['status']!='complete',comparison_arms=[],paired_members=[])
    raw=None
    if name!='normal' and result['legal_cut_reached']:
        raw=engine.last_cut_raw if family=='old' else engine.bank[family]
    c5_sha=hashlib.sha256(raw[80:160] if family=='old' else raw[:80]).hexdigest() if raw else None
    x['plans']=dict(candidate_family=family or 'normal',fresh_id=int(family[-1]) if family and family.startswith('fresh') else 0 if family=='a0' else None,
        raw50_ref=engine.plan_refs.get(hashlib.sha256(raw).hexdigest()) if raw else None,
        raw_C10_sha256=raw_group(raw,10) if raw else None,raw_C5_sha256=c5_sha,
        raw_alias_group=(raw_group(raw,10) if namespace=='Q_C10' else c5_sha) if raw else None,
        old_queue_age=5 if result['legal_cut_reached'] else None,old_queue_remaining=5 if result['legal_cut_reached'] else None,
        noise_ref=engine.plan_noise.get(hashlib.sha256(raw).hexdigest()) if raw else None,
        suffix_stream_id=f'{cfg["source_signature"]}/{namespace}/r{repeat}/decision_j',
        local_direction_ref=ref(Path(cfg['_normal_output'])/'bank/local_direction.json') if family in ('local_plus','local_minus') else None,
        physical_alias_of=None)
    verification=getattr(engine,'verification',None)
    x['restoration']=dict(level='not_applicable' if name=='normal' else verification['level'] if verification else 'unknown',
        schema_sha256=cfg['state_contract_sha256'],
        reference_state_ref=ref(Path(cfg['_normal_output'])/'CUT_REFERENCE.json') if result['legal_cut_reached'] else None,
        observed_state_ref=ref(engine.out/'CUT_STATE.json') if (engine.out/'CUT_STATE.json').exists() else None,
        verification_ref=ref(engine.out/'STATE_VERIFICATION.json') if verification else None,
        fields=verification['fields'] if verification else [],unknown_fields=[] if verification else ['no_paired_state_comparison'])
    x['window']=dict(normal_demonstration=False,episode_ids=[],observed_steps=[],
        token_start_step=None,token_end_step=None,token_start_ref=None,token_end_ref=None,token_shape=None,
        token_start_encoder_sha256=None,token_end_encoder_sha256=None,original_action_ref=None,
        original_action_shape=None,original_action_normalizer_sha256=None,executed_action_ref=None,
        executed_action_count=0,executed_action_mapping_verified=False,arrived_future_steps=0,
        feature_signature_verified=True,complete_GAF_target=False)
    x['views']={k:dict(eligible=k=='Q_BCE' and namespace=='Q_C10' and result['outcome']['outcome_complete'],
        missing_reasons=[] if k=='Q_BCE' and namespace=='Q_C10' and result['outcome']['outcome_complete']
        else ['per_attempt_record_not_complete_method_window_or_paired_aggregate'])
        for k in x['views']}
    x['missing_reasons']=['token_tensors_not_persisted_for_new_rollouts','method_windows_require_view_adapter']
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'sidecar_v1'))
    from validator import validate
    validate(x);engine.store.json('SIDECAR_V1.json',x)
def aggregate(parent,store):
    """After group exit, including an early/failed wave. Missing stays masked."""
    parent=Path(parent);records=[];originals={}
    for branch in sorted(parent.iterdir()):
        p=branch/'SIDECAR_V1.json'
        if not p.exists():continue
        x=json.loads(p.read_text());proto=x['protocol'];repeat=x['repeats']['repeat_id']
        if proto['target_namespace']=='normal':continue
        r=dict(arm=x['plans']['candidate_family'],repeat=repeat,parent=x['identity']['parent_id'],
            cut=proto['cut_step'],target=proto['target_namespace'],source_signature=x['identity']['source_signature'],
            context_signature=x['restoration']['reference_state_ref']['sha256'],
            suffix_stream=x['plans']['suffix_stream_id'],outcome_complete=x['outcome']['outcome_complete'],
            success=x['outcome']['success'],restore_level=x['restoration']['level'],
            raw_group=x['plans']['raw_alias_group'],sidecar_ref=ref(p))
        records.append(r)
        originals[(r['target'],r['arm'],r['repeat'])]=x
    labels={}
    q=[r for r in records if r['target']=='Q_C10'];g=[r for r in records if r['target']=='G0_C5']
    for family in ('local_plus','local_minus'):
        labels['gain_'+family]=paired_label(q,[family,'a0'],'gain')
    labels['pair']=paired_label(q,['local_plus','local_minus'],'pair')
    labels['G0']=paired_label(g,['old','fresh0','fresh1','fresh2'],'G0')
    scopes={x['synthetic'] for x in originals.values()}
    if len(scopes)>1:raise ContractError('mixed synthetic scope')
    label_ref=store.json('PAIRED_LABELS.json',dict(records=records,labels=labels,synthetic=scopes.pop() if scopes else False,
        training_loss_unchanged=True,publication_requires_analysis_acceptance=True))
    comparisons={'gain_local_plus':('Q_C10',['local_plus','a0'],'Q_GAIN'),
        'gain_local_minus':('Q_C10',['local_minus','a0'],'Q_GAIN'),
        'pair':('Q_C10',['local_plus','local_minus'],'Q_PAIR'),
        'G0':('G0_C5',['old','fresh0','fresh1','fresh2'],'G0')}
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'sidecar_v1'))
    from validator import validate
    for key,(namespace,arms,view) in comparisons.items():
        selected=[r for r in records if r['target']==namespace and r['arm'] in arms]
        if not selected:continue
        base=copy.deepcopy(originals[(namespace,selected[0]['arm'],selected[0]['repeat'])])
        base['record_id']+='__aggregate_'+key;base['record_ref']=ref(label_ref['path'])
        base['plans']['physical_alias_of']=base['identity']['physical_attempt_id']
        members=[]
        for row in selected:
            original=originals[(namespace,row['arm'],row['repeat'])]
            members.append(dict(arm=row['arm'],repeat_id=row['repeat'],parent_id=row['parent'],cut_step=row['cut'],
                target_namespace=row['target'],source_signature=row['source_signature'],context_signature=row['context_signature'],
                suffix_stream_id=row['suffix_stream'],outcome_complete=row['outcome_complete'],success=row['success'],
                restore_level=row['restore_level'],raw_group=row['raw_group'],
                physical_attempt_id=original['identity']['physical_attempt_id'],sidecar_ref=row['sidecar_ref']))
        base['repeats'].update(repeat_id=None,planned_repeat_ids=[0,1],complete_repeat_ids=labels[key]['valid_pair_repeat_ids'],
            valid_pair_repeat_ids=labels[key]['valid_pair_repeat_ids'],comparison_arms=arms,paired_members=members)
        base['views']={k:dict(eligible=(k==view and labels[key]['target_mask']),
            missing_reasons=[] if k==view and labels[key]['target_mask'] else ['not_this_aggregate_or_pair_ineligible']) for k in base['views']}
        base['missing_reasons']=['logical_aggregate_references_existing_physical_attempts_no_new_attempt']
        validate(base);store.json('SIDECAR_AGGREGATE_'+key+'.json',base)
    return labels
