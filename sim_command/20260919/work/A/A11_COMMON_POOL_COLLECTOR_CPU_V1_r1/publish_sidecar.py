from pathlib import Path
import json,hashlib,datetime
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
P=B/'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/sidecar_v1'
P.mkdir()
def obj(properties):return dict(type='object',properties=properties,required=list(properties),additionalProperties=False)
def arr(items,**kw):return dict(type='array',items=items,**kw)
S={'type':'string'};I={'type':'integer','minimum':0};BOOL={'type':'boolean'}
SHA=dict(type='string',pattern='^[0-9a-f]{64}$')
def nullable(v):return {'anyOf':[v,{'type':'null'}]}
REF=obj(dict(path=S,sha256=SHA,format=S))
REASONS=arr(S)
FIELD=obj(dict(name=S,classification={'enum':['captured','recomputed','immutable','irrelevant','unknown']},
    verdict={'enum':['equal','mismatch','unknown','not_applicable']},basis=S,
    reference_sha256=nullable(SHA),observed_sha256=nullable(SHA)))
VIEW=obj(dict(eligible=BOOL,missing_reasons=REASONS))
MEMBER=obj(dict(arm=S,repeat_id={'enum':[0,1]},parent_id=S,cut_step=I,
    target_namespace={'enum':['Q_C10','G0_C5']},source_signature=SHA,
    context_signature=SHA,suffix_stream_id=S,outcome_complete=BOOL,
    success=nullable({'enum':[0,1]}),restore_level=S,raw_group=S,
    physical_attempt_id=S,sidecar_ref=nullable(REF)))
schema=obj(dict(
    schema_version={'const':'common_pool_sidecar_v1'},schema_sha256=SHA,synthetic=BOOL,
    record_id=S,record_ref=nullable(REF),
    identity=obj(dict(parent_id=S,episode_id=S,source_id=S,physical_attempt_id=S,
        run_id=S,branch_id=S,task=S,split={'enum':['train','development']},
        source_manifest_ref=nullable(REF),source_signature=SHA)),
    protocol=obj(dict(target_namespace={'enum':['normal','Q_C10','G0_C5','normal_demo']},
        cut_step=nullable(I),absolute_start_step=I,absolute_end_step=I,
        parent_absolute_target_state=nullable({'const':300}),
        commitment_steps=nullable({'enum':[5,10]}),native_H={'const':10},
        generated_length=nullable({'const':50}))),
    input_signatures=obj(dict(policy_sha256=nullable(SHA),encoder_sha256=nullable(SHA),
        preprocessing_sha256=nullable(SHA),normalizer_sha256=nullable(SHA),
        action_representation=S,action_representation_sha256=nullable(SHA))),
    outcome=obj(dict(success=nullable({'enum':[0,1]}),outcome_complete=BOOL,
        reason={'enum':['success','absolute_s300_complete','frozen_absorbing_failure',
            'technical_failure','timeout','quota_exhausted','unknown_timelimit','missing_observation',
            'short_stage_only','not_evaluated','not_applicable']},
        last_observed_parent_state=I,first_success_step=nullable(I),
        terminated=nullable(BOOL),truncated=nullable(BOOL),missing_reasons=REASONS)),
    repeats=obj(dict(repeat_id=nullable({'enum':[0,1]}),
        planned_repeat_ids=arr({'enum':[0,1]},uniqueItems=True),
        complete_repeat_ids=arr({'enum':[0,1]},uniqueItems=True),
        valid_pair_repeat_ids=arr({'enum':[0,1]},uniqueItems=True),
        planned=BOOL,entered=BOOL,completed=BOOL,missing=BOOL,
        comparison_arms=arr(S),paired_members=arr(MEMBER))),
    plans=obj(dict(candidate_family=S,fresh_id=nullable({'enum':[0,1,2]}),
        raw50_ref=nullable(REF),raw_C10_sha256=nullable(SHA),raw_C5_sha256=nullable(SHA),
        raw_alias_group=nullable(S),old_queue_age=nullable(I),old_queue_remaining=nullable(I),
        noise_ref=nullable(REF),suffix_stream_id=nullable(S),local_direction_ref=nullable(REF),
        physical_alias_of=nullable(S))),
    restoration=obj(dict(level={'enum':['full_state_verified','independent_replay_observable_match',
            'unknown','failed','not_applicable']},schema_sha256=nullable(SHA),
        reference_state_ref=nullable(REF),observed_state_ref=nullable(REF),
        verification_ref=nullable(REF),fields=arr(FIELD),unknown_fields=arr(S))),
    window=obj(dict(normal_demonstration=BOOL,episode_ids=arr(S),observed_steps=arr(I),
        token_start_step=nullable(I),token_end_step=nullable(I),
        token_start_ref=nullable(REF),token_end_ref=nullable(REF),
        token_shape=nullable(arr(I,minItems=2,maxItems=2)),
        token_start_encoder_sha256=nullable(SHA),token_end_encoder_sha256=nullable(SHA),
        original_action_ref=nullable(REF),original_action_shape=nullable(arr(I)),
        original_action_normalizer_sha256=nullable(SHA),
        executed_action_ref=nullable(REF),executed_action_count=I,executed_action_mapping_verified=BOOL,
        arrived_future_steps=I,feature_signature_verified=BOOL,complete_GAF_target=BOOL)),
    views=obj({k:VIEW for k in ['LVM','D5','GAF','Q_BCE','Q_GAIN','Q_PAIR','G0']}),
    missing_reasons=REASONS))
schema.update({'$schema':'https://json-schema.org/draft/2020-12/schema',
    '$id':'urn:corrector:common_pool_sidecar_v1',
    'title':'Common pool per-record evidence sidecar; eligibility claims must be independently checked'})
def write(name,d):
    with (P/name).open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
write('schema.json',schema)
sha=hashlib.sha256((P/'schema.json').read_bytes()).hexdigest()
def reference(label):return dict(path='SYNTHETIC_ONLY/'+label,sha256=hashlib.sha256(label.encode()).hexdigest(),format='synthetic_metadata')
base=dict(schema_version='common_pool_sidecar_v1',schema_sha256=sha,synthetic=True,
    record_id='SYNTHETIC_LVM_NO_TERMINAL',record_ref=reference('original_record'),
    identity=dict(parent_id='SYNTHETIC_DEMO_0',episode_id='SYNTHETIC_DEMO_0',source_id='SYNTHETIC_DEMO_0',
        physical_attempt_id='SYNTHETIC_DEMO_0',run_id='SYNTHETIC',branch_id='normal_demo',
        task='shelf-place-v3',split='train',source_manifest_ref=reference('demo_source'),source_signature='1'*64),
    protocol=dict(target_namespace='normal_demo',cut_step=None,absolute_start_step=0,absolute_end_step=10,
        parent_absolute_target_state=None,commitment_steps=None,native_H=10,generated_length=None),
    input_signatures=dict(policy_sha256=None,encoder_sha256='2'*64,preprocessing_sha256='3'*64,
        normalizer_sha256='4'*64,action_representation='B_original_action_t',action_representation_sha256='5'*64),
    outcome=dict(success=None,outcome_complete=False,reason='not_applicable',last_observed_parent_state=10,
        first_success_step=None,terminated=None,truncated=None,missing_reasons=['terminal_flags_unknown']),
    repeats=dict(repeat_id=None,planned_repeat_ids=[],complete_repeat_ids=[],valid_pair_repeat_ids=[],
        planned=False,entered=False,completed=False,missing=False,comparison_arms=[],paired_members=[]),
    plans=dict(candidate_family='normal_demo',fresh_id=None,raw50_ref=None,raw_C10_sha256=None,
        raw_C5_sha256=None,raw_alias_group=None,old_queue_age=None,old_queue_remaining=None,
        noise_ref=None,suffix_stream_id=None,local_direction_ref=None,physical_alias_of=None),
    restoration=dict(level='not_applicable',schema_sha256=None,reference_state_ref=None,
        observed_state_ref=None,verification_ref=None,fields=[],unknown_fields=[]),
    window=dict(normal_demonstration=True,episode_ids=['SYNTHETIC_DEMO_0']*11,
        observed_steps=list(range(11)),token_start_step=0,token_end_step=10,
        token_start_ref=reference('token0'),token_end_ref=reference('token10'),token_shape=[256,2048],
        token_start_encoder_sha256='2'*64,token_end_encoder_sha256='2'*64,
        original_action_ref=reference('action_t'),original_action_shape=[4],
        original_action_normalizer_sha256='4'*64,executed_action_ref=None,executed_action_count=0,
        executed_action_mapping_verified=False,arrived_future_steps=10,feature_signature_verified=True,
        complete_GAF_target=False),
    views={k:dict(eligible=k=='LVM',missing_reasons=[] if k=='LVM' else ['not_admitted_for_this_view'])
        for k in ['LVM','D5','GAF','Q_BCE','Q_GAIN','Q_PAIR','G0']},missing_reasons=['terminal_flags_unknown'])
examples=[dict(name='normal_LVM_terminal_unknown',expected_admitted=['LVM'],record=base)]
def clone():return json.loads(json.dumps(base))
x=clone();x['record_id']='SYNTHETIC_LVM_MISSING_TOKEN';x['window']['token_end_ref']=None
x['views']['LVM']=dict(eligible=False,missing_reasons=['token_end_missing'])
examples.append(dict(name='missing_LVM_endpoint',expected_admitted=[],record=x))
x=clone();x['record_id']='SYNTHETIC_Q_OBSERVABLE_ONLY'
x['identity'].update(parent_id='SYNTHETIC_PARENT',episode_id='SYNTHETIC_PARENT',source_id='SYNTHETIC_PARENT',branch_id='Q/local_plus')
x['protocol'].update(target_namespace='Q_C10',cut_step=5,absolute_start_step=5,absolute_end_step=300,
    parent_absolute_target_state=300,commitment_steps=10,generated_length=50)
x['outcome'].update(success=0,outcome_complete=True,reason='absolute_s300_complete',
    last_observed_parent_state=300,truncated=True,missing_reasons=[])
x['repeats'].update(repeat_id=0,planned_repeat_ids=[0,1],complete_repeat_ids=[0],valid_pair_repeat_ids=[],
    planned=True,entered=True,completed=True,comparison_arms=['local_plus','local_minus'])
x['plans'].update(candidate_family='local_plus',raw_C10_sha256='6'*64,raw_alias_group='SYNTHETIC_RP')
x['restoration'].update(level='independent_replay_observable_match',unknown_fields=['full_state_closure'])
x['window'].update(normal_demonstration=False,executed_action_count=10,executed_action_mapping_verified=True,
    complete_GAF_target=True,executed_action_ref=reference('executed10'))
x['views']={k:dict(eligible=k=='Q_BCE',missing_reasons=[] if k=='Q_BCE' else ['example_not_admitted']) for k in x['views']}
x['missing_reasons']=['full_state_closure']
examples.append(dict(name='Q_observable_only_no_pair',expected_admitted=['Q_BCE'],record=x))
write('synthetic_examples.json',dict(schema_sha256=sha,synthetic=True,
    example_semantics='contract-only fixtures; references are symbolic, no real data or state proof',
    examples=examples))
readme="""# Common pool sidecar v1

Immutable A-published schema for B11 CPU consumers. Public interface_v1 is unchanged.
READY.json binds exact schema/README/examples/validator bytes. All examples are synthetic.

One sidecar extends one original record via record_ref and immutable input/source signatures.
Nullable fields mean missing/not-applicable, never synthesized values. Real publications require
existing path/SHA/format references; synthetic references deliberately do not exist.

Identity parent_id/episode_id/source_signature and protocol cut/target namespace are pairing keys.
run_id/branch_id/physical_attempt_id distinguish executions and are excluded from physical state
equality. physical_alias_of is null in collector v1 (no normal or raw dedup optimization).

Outcome target for new Q/G0/normal is parent absolute s300 inclusive. complete failure requires
absolute_s300_complete or pre-frozen absorbing semantics; technical/quota/timeouts remain null.
Q uses C10; G0 uses C5; fresh0/a0 generation identity never licenses sharing physical outcomes.

repeats.planned_repeat_ids is [0,1] for new paired data. valid_pair_repeat_ids is the aligned
complete intersection across comparison_arms; both IDs are required. paired_members records
the parent/cut/protocol/source/context/stream/outcome/restore/raw-group evidence for each arm
and repeat. Match suffix streams within the same repeat and protocol, not across repeats.
Any unknown/mismatched restoration field prevents full_state_verified. Proof references and
field classification/verdict are retained. Privileged restoration fields are audit-only.

views.*.eligible is an assertion, not a substitute for B recomputing admissibility from window,
outcome, input_signatures, repeats, plans and restoration. It must not be blindly trusted.
LVM needs normal_demonstration, one episode and continuous observed t..t+10, both actual token
refs, shape[256,2048], matching encoder/preprocessing and original action_t/normalizer identities.
It does not require terminal flags or complete_GAF_target. D5 needs a true five-step arrived
window/executed mapping; GAF needs ten actual actions and its complete target. No short-window
padding. Q BCE may use its own complete repeats; gain/pair/G0 need full-state plus both repeats.
Alias key for Q is first C10 raw bytes in the same parent/cut/protocol; clamped equality is not
raw alias. plus/minus identical raw group gives no pair; alias-to-a0 gives no gain. No extra
training weight from logical references, duplicate tails or normal roles.

validator.py performs structural and basic protocol validation using stdlib only. It does not
prove referenced bytes exist or physically restore state. B must bind READY and independently
validate method-specific semantics. No A/B integration success is claimed before B feedback.
No real seed/shard/claim/compute was produced. Future schema changes require a new version.
"""
with (P/'README.md').open('x') as f:f.write(readme)
print(str(P))
