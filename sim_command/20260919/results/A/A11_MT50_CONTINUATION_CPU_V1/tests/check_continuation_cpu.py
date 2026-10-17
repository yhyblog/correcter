"""Only changed MT50/Batch2 paths: real components with explicit synthetic boundaries."""
from pathlib import Path
import ast,copy,hashlib,json,sys,traceback,types
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'code'))
FORBIDDEN={'torch','numpy','mujoco','gymnasium','metaworld','pynvml','OpenGL','pycuda'}
blocked=[]
def guard(event,args):
    if event=='import' and args[0].split('.')[0] in FORBIDDEN:raise AssertionError('forbidden import '+args[0])
    if event in ('ctypes.dlopen','ctypes.dlsym','subprocess.Popen','os.system','os.kill','os.killpg'):
        raise AssertionError('forbidden real runtime '+event)
    if event=='open' and isinstance(args[0],str):
        path=args[0]
        if path.startswith(('/proc/','/sys/','/dev/')) or path.endswith(('.safetensors','.pt','.pth')):
            raise AssertionError('forbidden live hardware/weight access '+path)
sys.addaudithook(guard)
import inheritance
from core.contracts import ContractError,read,sha
from task_profiles import PROFILES,TABLE,FIXED_SLOTS,profile,initialization_caps,validate_config
from source_plan import processed_keys,select_next_slots,source_identity,check_source_seed
from authorization import check_parent_documents,check_documents
from budget import batch_caps,batch_timeouts,scheduler_caps,parent_caps
from pool_protocol import ARMS,stream_seed,paired_label
from native.initialization import InitializationAudit
from batch_scheduler import run_schedule
from core.event_recorder import EventRecorder
from batch_publication import publish_parent
from storage import Store
import synthetic_boundaries as f
OUT=Path(sys.argv[1]).resolve();OUT.mkdir(parents=True,exist_ok=False);f.OUT=OUT
checks=[];initialization_fixture_invocations=0
def check(name,ok,detail=None):
    checks.append(dict(name=name,passed=bool(ok),detail=detail))
    if not ok:raise AssertionError(name)
def reject(name,fn):
    try:fn()
    except (ContractError,ValueError,TypeError) as exc:check(name,True,str(exc));return
    raise AssertionError(name+' did not reject')
def write(name,obj):f.write(OUT/name,obj)

def metadata():
    proposal=read(P/'proposal/PROPOSAL.json');proposal['_sha256']=sha(P/'proposal/PROPOSAL.json')
    parents=proposal['parents'];configs=[read(p['config']['path']) for p in parents]
    dispositions=read(proposal['processed_source_dispositions']['path']);accepted=read(proposal['accepted_parent_index']['path'])
    expected=['assembly-v3','basketball-v3','bin-picking-v3','box-close-v3','button-press-topdown-v3','button-press-topdown-wall-v3','button-press-v3','button-press-wall-v3']
    check('exact50_and_distinct_task_language_indices',len(PROFILES)==50 and TABLE['known_task_count']==50 and
        PROFILES['push-v3']['wrapper_environment_id']!=PROFILES['push-back-v3']['wrapper_environment_id'] and
        PROFILES['push-v3']['demonstration_language_index']==PROFILES['push-back-v3']['demonstration_language_index']==40)
    check('ASCII_fixed8_not_outcome_selected',[x[0] for x in FIXED_SLOTS]==expected and FIXED_SLOTS==select_next_slots(list(PROFILES),dispositions))
    check('all_processed_excluded_including_p04_and_shelf0',len(processed_keys(dispositions))==9 and
        ('disassemble-v3','train',1,55) in processed_keys(dispositions) and ('shelf-place-v3','train',0,5) in processed_keys(dispositions) and
        not any(p['source']['source_id'] in {x['source']['source_id'] for x in dispositions['parents']} for p in parents))
    check('real_parent_authority_for_new8',check_parent_documents(proposal,configs,accepted)['status']=='PASS')
    for p in parents:
        s=p['source'];check_source_seed(s);validate_config(read(p['config']['path']))
        refseed=f"common_pool_batch_source_v1|{s['task']}|train|0|cut5"
        check(s['task']+'_independent_seed_formula',s['env_seed']==int.from_bytes(hashlib.sha256((refseed+'|env').encode()).digest()[:4],'little')%2147483647 and
            s['master_seed']==int.from_bytes(hashlib.sha256((refseed+'|master').encode()).digest()[:8],'little')%9223372036854775807)
        seeds=[stream_seed(s['master_seed'],s['parent_source_id'],ns,r,0,cut=5) for ns in ('Q_C10','G0_C5') for r in (0,1)]
        check(s['task']+'_two_repeat_C10_C5_streams_isolated',len(set(seeds))==4 and
            stream_seed(s['master_seed'],s['parent_source_id'],'prefix',0,0)==stream_seed(s['master_seed'],s['parent_source_id'],'prefix',1,0))
    for row in dispositions['parents']:
        s=row['source']
        if 'ordinal' in s:
            check('prior_seed_rule_preserved_'+s['source_id'],all(s[k]==v for k,v in source_identity(s['task'],s['split'],s['ordinal'],s['cut']).items()))
    check('116_full120_budgets_not106_shortcut',len(batch_caps(parents))==116 and proposal['resource_caps']['policy_model_loads']==120 and
        proposal['resource_caps']['vla_sampling_calls']==3624 and proposal['resource_caps']['flow_forward_calls']==36240 and
        proposal['resource_caps']['env_steps']==36000 and proposal['resource_caps']['observation_calls']==36120 and
        proposal['resource_caps']['initialization_physics_substeps']==7*15*26000+15*(26000+104*5) and
        proposal['resource_caps']['initialization_mj_forward_calls']==120*(2+104))
    for c in (1,4,8,True):reject('non2_concurrency_'+str(c),lambda c=c:batch_timeouts(c))
    changed=copy.deepcopy(proposal);changed['concurrency']=1
    reject('parent_authority_refuses_concurrency_downgrade',lambda:check_parent_documents(changed,configs,accepted))
    changed=copy.deepcopy(proposal);changed['parents'][0]['source']['master_seed']+=1
    reject('seed_mutation_refused',lambda:check_parent_documents(changed,configs,accepted))
    changed=copy.deepcopy(proposal);changed['parents'][0]['source']=copy.deepcopy(dispositions['parents'][-1]['source'])
    reject('p04_not_refilled',lambda:check_parent_documents(changed,configs,accepted))
    old=PROFILES['box-close-v3']['static_cap_status'];PROFILES['box-close-v3']['static_cap_status']='unknown'
    try:
        reject('unknown_cap_rejected_by_real_parent_path',lambda:check_parent_documents(proposal,configs,accepted))
        check('unknown_cap_does_not_change_selected_slots',FIXED_SLOTS==select_next_slots(list(PROFILES),dispositions))
    finally:PROFILES['box-close-v3']['static_cap_status']=old
    exhausted=copy.deepcopy(dispositions)
    for task in list(PROFILES):
        if (task,'train',0,5) not in processed_keys(exhausted):
            s=dict(source_identity(task,'train',0,5),task=task,split='train',ordinal=0,cut=5)
            exhausted['parents'].append(dict(source=s));exhausted['processed_planned_parent_slots']+=1
    reject('insufficient_slots_no_node_ordinal_cut_fill',lambda:select_next_slots(list(PROFILES),exhausted))
    docs=read(P/'proposal/CANDIDATE_PUBLICATION_DOCUMENTS.json');rel=docs['RELEASE']
    reject('actual_unauthorized_template_rejected',lambda:check_documents(docs['CONTROL'],docs['TASK_BOARD'],rel,proposal,proposal['owner_host']))
    released=copy.deepcopy(rel);released['status']='released'
    reject('released_without_new_Batch2_storage_decision_rejected',lambda:check_documents(docs['CONTROL'],docs['TASK_BOARD'],released,proposal,proposal['owner_host']))
    # Explicit synthetic future approval fixture, never installed in live release/CONTROL.
    released['storage_admission']['accepts_monitoring_gaps']=True
    for status in ('ready','running'):
        board=copy.deepcopy(docs['TASK_BOARD']);next(x for x in board['tasks'] if x['id']==proposal['task_id'])['status']=status
        check('future_metadata_'+status,check_documents(docs['CONTROL'],board,released,proposal,proposal['owner_host'])['status']=='PASS')
    oldrisk=copy.deepcopy(released);oldrisk['storage_admission']['mode']='bounded_batch1'
    reject('Batch1_risk_not_reusable',lambda:check_documents(docs['CONTROL'],docs['TASK_BOARD'],oldrisk,proposal,proposal['owner_host']))
    write('FUTURE_PUBLICATION_FIXTURE.json',dict(synthetic=True,grants_permission=False,CONTROL=docs['CONTROL'],TASK_BOARD=docs['TASK_BOARD'],RELEASE=released))
    write('TEMPLATE_REFUSALS.json',dict(synthetic=True,current_template='UNAUTHORIZED_TEMPLATE',actual_storage_accepted=False,
        future_check_pass_requires_independent_release_and_explicit_Batch2_storage_decision=True))

def native_hooks():
    nonlocal_counts={'native_calls':0,'fail':False}
    def step(*args,**kw):
        nonlocal_counts['native_calls']+=1
        if nonlocal_counts['fail']:raise RuntimeError('synthetic physics failure')
        return 'synthetic'
    mj=types.SimpleNamespace(mj_forward=lambda *a:None,mj_step=step)
    class Gym:
        def do_simulation(self,ctrl,n_frames):return mj.mj_step('synthetic_model','synthetic_data',nstep=n_frames)
    class Base(Gym):
        def reset(self):self.reset_model();self.reset_model()
    class Native(Base):
        def __init__(self):pass
        def reset_model(self):pass
    class Wrapper:
        def __init__(self):pass
        def _make_envs_task(self):pass
    module=types.SimpleNamespace(_make_tasks=lambda:None)
    audit=InitializationAudit(OUT/'SYNTHETIC_initialization.jsonl',initialization_caps('box-close-v3'),task='box-close-v3',cut=5)
    original=(mj.mj_step,mj.mj_forward,Gym.do_simulation)
    audit.install(module,Native,Base,Gym,Wrapper);audit.install_native_functions(mj)
    e=object.__new__(Native)
    try:
        with audit.scope('diagnostic_reset'):
            e.do_simulation([-1,1],5);mj.mj_step('synthetic_model','synthetic_data');mj.mj_step('synthetic_model','synthetic_data')
            check('nested_native_steps_not_double_charged',audit.used['initialization_physics_substeps']==7 and audit.used['initialization_do_simulation_calls']==1)
            reject('direct_mj_step_changed_ABI_denied',lambda:mj.mj_step('model','data',nstep=1))
            for _ in range(8):mj.mj_step('model','data')
            reject('direct_stage_overrun_denied_before_entry',lambda:mj.mj_step('model','data'))
        with audit.scope('policy_control'):
            e.do_simulation([0,0],13)
            check('unchanged_30Hz_physics',audit.used['policy_physics_substeps']==13)
            reject('policy_unmetered_direct_call_denied',lambda:mj.mj_step('model','data'))
        with audit.scope('wrapper_initialization'):
            nonlocal_counts['fail']=True
            try:e.do_simulation([0,0],5)
            except RuntimeError:pass
            check('failed_do_simulation_restores_depth',audit._simulation_depth==0)
            try:mj.mj_step('model','data')
            except RuntimeError:pass
            check('failed_direct_entry_consumed_once',audit._direct_steps_by_stage['wrapper_initialization']==1 and audit.used['initialization_physics_substeps']==21)
            nonlocal_counts['fail']=False
    finally:audit.uninstall()
    check('fake_patches_restored',(mj.mj_step,mj.mj_forward,Gym.do_simulation)==original)
    summary=audit.summary();check('real_initialization_journal_failure_pairs',summary['failed_events']==2 and not summary['incomplete_event_ids'])
    write('SYNTHETIC_INITIALIZATION_SUMMARY.json',dict(synthetic=True,real_runtime=False,summary=summary,native_fake_invocations=nonlocal_counts['native_calls']))
    other=InitializationAudit(OUT/'SYNTHETIC_non_direct_task.jsonl',initialization_caps('assembly-v3'),task='assembly-v3',cut=5)
    other.install_native_functions(mj)
    try:
        with other.scope('diagnostic_reset'):reject('task_without_direct_path_denied',lambda:mj.mj_step('model','data'))
    finally:other.uninstall()
    tree=ast.parse((P/'code/native/initialization.py').read_text())
    real=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='install_real')
    check('real_native_install_calls_tested_hook',any(isinstance(n,ast.Call) and ast.unparse(n.func)=='self.install_native_functions' and ast.unparse(n.args[0])=='mujoco' for n in ast.walk(real)))

def components():
    parent=f.parent_spec('new_box_combo','box-close-v3',5)
    normal=f.SyntheticBoundary(parent,ARMS[0],success_at=25);f.drive(normal)
    outcomes={};engines={}
    for job in ARMS[1:]:
        name,family,repeat=job
        terminal=8 if name.startswith('Q_a0') else 15 if name.startswith('Q_local_plus') else 9 if name.startswith('G0_old') else 10 if name.startswith('G0_fresh0') else 17
        e=f.SyntheticBoundary(parent,job,success_at=terminal);r=f.drive(e,normal.reference);outcomes[name]=r;engines[name]=e
        ns='Q_C10' if name.startswith('Q_') else 'G0_C5';commit=10 if ns=='Q_C10' else 5
        suffix=[x for x in e.trace if x['kind']=='sample' and x['namespace']==ns]
        check(name+'_legal_terminal_and_actual_H10_semantics',r['legal_cut_reached'] and r['outcome']['outcome_complete'] and
            r['intervention_evidence']['returned_commitment_steps']==min(commit,terminal-5) and
            (not suffix if terminal<=5+commit else suffix[0]['step']==5+commit))
        events=[json.loads(line) for line in (e.out/'events.jsonl').read_text().splitlines()]
        check(name+'_real_recorder_identity',all(x['synthetic'] is True and x['branch']==name for x in events))
    store=Store(Path(parent['paths']['output'])/'reserved',byte_limit=8*1024**2,record_limit=1024**2)
    pub=publish_parent(parent,store,dict(status='all_formal_group_members_exited',synthetic=True),synthetic=True)
    check('complete_double_repeats_with_legal_commit_terminals',all(x['target_mask'] and x['valid_pair_repeat_ids']==[0,1] for x in pub['labels'].values()))
    pre=f.parent_spec('new_pre_cut','assembly-v3',5,1);e=f.SyntheticBoundary(pre,ARMS[0],success_at=3);r=f.drive(e)
    check('before_cut_success_retained_no_bank_no_intervention',r['outcome']['success']==1 and r['outcome']['outcome_complete'] and
        not r['legal_cut_reached'] and not r['intervention_evidence']['commitment_entered'] and not (e.out/'BANK.json').exists())
    store=Store(Path(pre['paths']['output'])/'reserved',byte_limit=8*1024**2,record_limit=1024**2)
    pub=publish_parent(pre,store,dict(status='all_formal_group_members_exited',synthetic=True),synthetic=True)
    check('precut_pair_targets_null_and_mask_false',all(x['target'] is None and x['target_mask'] is False for x in pub['labels'].values()))
    ps=[f.parent_spec('scheduler_new'+str(i),t,cut,i+2) for i,(t,ordinal,cut) in enumerate(FIXED_SLOTS)]
    class Backend(f.VirtualBackend):
        def poll(self,h):
            row=super().poll(h)
            if row is not None and h['parent']==ps[0] and h['job'][0]=='normal':row['result']=r
            return row
    backend=Backend();tick=[0.];rec=EventRecorder(OUT/'SYNTHETIC_scheduler.jsonl',branch='synthetic_batch2',source_id='SYNTHETIC_BATCH2',parent_source_id='SYNTHETIC_BATCH2_PARENT',split='train',synthetic=True)
    result=run_schedule(ps,2,backend,gate=lambda:None,emit=rec.emit,limits=scheduler_caps(2),timeouts=batch_timeouts(2),clock=lambda:tick[0],pause=lambda x:tick.__setitem__(0,tick[0]+x))
    check('real_scheduler_fixed8_with_pre_cut_stop_only',result['branch_starts']==106 and backend.max_active==2 and result['status']=='partial_or_failed' and
        len(backend.started[ps[0]['parent_key']])==1 and all(len(backend.started[p['parent_key']])==15 for p in ps[1:]))
    check('same_UUID_per_parent_and_no_fill',all({x[3] for x in backend.trace if x[0]=='start' and x[1]==p['parent_key']}=={p['device']['gpu_uuid']} for p in ps))
    kinds=[x[0] for x in backend.trace];check('publication_follows_owned_wave_exit',max(i for i,x in enumerate(kinds) if x=='exit')<kinds.index('drain')<kinds.index('publish'))
    write('SYNTHETIC_SCHEDULER_RESULT.json',dict(synthetic=True,result=result,trace=backend.trace))

try:
    metadata();native_hooks();components()
    result=dict(status='PASS',checks=checks,passed=len(checks),synthetic_counts=f.counts,
        real_runtime_operations=0,real_hardware_holder_launcher_claim_operations=0,
        old_suites_executed=0,blocked_import_modules=sorted(FORBIDDEN),all_artifacts_in_this_fixture_synthetic=True)
except BaseException as exc:
    result=dict(status='FAIL',checks=checks,error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()),synthetic_counts=f.counts,real_runtime_operations=0)
    write('CHECK_RESULT.json',result);print(json.dumps(result,ensure_ascii=False));raise
write('CHECK_RESULT.json',result);print(json.dumps(dict(status=result['status'],checks=result['passed'],synthetic_counts=f.counts,real_runtime_operations=0)),flush=True)
