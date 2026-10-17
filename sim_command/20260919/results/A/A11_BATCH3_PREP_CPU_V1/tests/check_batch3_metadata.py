"""Synthetic metadata tests only; no launcher, runtime gate, claim or capacity call."""
from pathlib import Path
import ast,contextlib,copy,datetime,hashlib,io,json,sys
P=Path(__file__).resolve().parents[1];B=P.parents[2];W=B/'work/A/A11_BATCH3_PREP_CPU_V1'
def guard(event,args):
    if event=='import' and args[0].split('.')[0] in {'torch','mujoco','metaworld','pynvml','OpenGL'}:
        raise AssertionError('forbidden CPU-test import '+args[0])
    if event in {'ctypes.dlopen','subprocess.Popen','os.system','os.kill','os.fork'}:
        raise AssertionError('forbidden CPU-test operation '+event)
sys.addaudithook(guard)
sys.path.insert(0,str(P/'code'));import inheritance
from authorization import check_documents,check_parent_documents,GlobalFault
from core.contracts import ContractError,read,sha
from source_plan import processed_keys,select_next_slots,check_source_seed
from observation_phase import validate_observation_config
from batch_storage import check_admission_document
import publication_check
rows=[]
def test(name,fn,reject=False):
    try:
        value=fn()
        if reject:raise AssertionError('unexpected metadata acceptance')
    except (ContractError,GlobalFault,ValueError,TypeError) as e:
        if not reject:raise
        rows.append(dict(name=name,status='PASS',expected='reject',exception=type(e).__name__,message=str(e),synthetic=True));return
    rows.append(dict(name=name,status='PASS',expected='accept',value=value,synthetic=True))
def require(value):
    assert value
    return True
proposal=read(P/'proposal/PROPOSAL.json');proposal['_sha256']=sha(P/'proposal/PROPOSAL.json')
staged=read(P/'proposal/CANDIDATE_PUBLICATION_DOCUMENTS.json')
c=staged['CONTROL'];board=staged['TASK_BOARD'];template=staged['RELEASE']
host=proposal['owner_host'];configs=[read(x['config']['path']) for x in proposal['parents']]
accepted=read(proposal['accepted_parent_index']['path']);done=read(proposal['processed_source_dispositions']['path'])
catalog=read(P/'config/MT50_TASK_TABLE.json');names=[x['task'] for x in catalog['rows']]
expected=['coffee-button-v3','coffee-pull-v3','coffee-push-v3','dial-turn-v3','door-close-v3','door-lock-v3','door-open-v3','door-unlock-v3']
positive=copy.deepcopy(template);positive['status']='released';positive['storage_admission']['accepts_monitoring_gaps']=True
test('new_fixed8_parent_documents',lambda:check_parent_documents(proposal,configs,accepted,done))
test('exact17_exclusion_including_normal_only',lambda:require(len(processed_keys(done))==17 and
    ('disassemble-v3','train',1,55) in processed_keys(done) and accepted['accepted_parent_count']==16 and
    len([x for x in done['parents'] if x['status']!='paired_accepted'])==1))
test('exact_remaining_ASCII_first8',lambda:require(select_next_slots(names,done)==[(t,0,5) for t in expected]))
test('processed_snapshot_exact_V2',lambda:require(sha(P/'evidence/PROCESSED_SOURCE_DISPOSITIONS.json')==sha(W/'authorization/COMMON_POOL_SOURCE_DISPOSITIONS_V2.json')))
test('accepted_index_exact_V3',lambda:require(sha(proposal['accepted_parent_index']['path'])=='62fdb2d17a7b43be4ab5861671b80557ce7213a65326102689ac821d97fc37ad'))
damaged=copy.deepcopy(done);damaged['parents']=[x for x in damaged['parents'] if x['status']=='paired_accepted']
test('missing_normal_only_with17_contract_rejected',lambda:processed_keys(damaged),True)
prior_seeds={s['source']['env_seed'] for s in done['parents']}
devices=read(P/'evidence/SAVED_GPU_IDENTITIES.json')['devices']
seed_rows=[]
for i,(parent,cfg) in enumerate(zip(proposal['parents'],configs,strict=True)):
    s=parent['source'];rule=f"common_pool_batch_source_v1|{s['task']}|train|0|cut5"
    expected_env=int(hashlib.sha256((rule+'|env').encode('ascii')).digest()[:4][::-1].hex(),16)%(2**31-1)
    expected_master=int(hashlib.sha256((rule+'|master').encode('ascii')).digest()[:8][::-1].hex(),16)%(2**63-1)
    test(f'fixed_source_seed_UUID_{i}',lambda s=s,i=i,parent=parent:require(
        s['task']==expected[i] and s['split']=='train' and s['ordinal']==0 and s['cut']==5 and
        s['env_seed']==expected_env and s['master_seed']==expected_master and
        s['env_seed'] not in prior_seeds and parent['device']==devices[i]))
    test(f'CONFIG301_{i}',lambda cfg=cfg:validate_observation_config(cfg))
    seed_rows.append(dict(task=s['task'],source_id=s['source_id'],env_seed=s['env_seed'],master_seed=s['master_seed'],GPU_UUID=parent['device']['gpu_uuid']))
badseed=copy.deepcopy(configs[0]['source']);badseed['env_seed']+=1
test('changed_seed_rejected',lambda:check_source_seed(badseed),True)
badcfgs=copy.deepcopy(configs);badcfgs[0]['native']['observation_phases'].pop()
test('new_CONFIG_missing_step300_rejected',lambda:check_parent_documents(proposal,badcfgs,accepted,done),True)
for name,key,value in [('cut','cut',55),('owner_split','split','development')]:
    bad=copy.deepcopy(proposal);bad['parents'][0]['source'][key]=value
    test('changed_'+name+'_rejected',lambda bad=bad:check_parent_documents(bad,configs,accepted,done),True)
bad=copy.deepcopy(proposal);bad['parents'][0]['paths']['output']=bad['parents'][1]['paths']['output']
test('parent_output_collision_rejected',lambda:check_parent_documents(bad,configs,accepted,done),True)
badcfgs=copy.deepcopy(configs);badcfgs[0]['device']=copy.deepcopy(devices[1])
test('wrong_bound_config_device_rejected',lambda:check_parent_documents(proposal,badcfgs,accepted,done),True)
budget=read(P/'proposal/RESOURCE_BUDGET.json');keys=set(proposal['resource_caps']);total=dict.fromkeys(keys,0)
for parent in budget['parents']:
    summed={k:sum(a[k] for a in parent['attempt_caps'].values()) for k in keys};summed['native_nvml_identity_queries']+=1
    test('parent116_sum_'+parent['parent_key'],lambda summed=summed,parent=parent:require(summed==parent['caps']))
    for k in keys:total[k]+=summed[k]
test('batch116_full120_sum',lambda:require(len(keys)==116 and total==proposal['resource_caps'] and
    (total['simulator_attempts'],total['vla_sampling_calls'],total['flow_forward_calls'],total['env_steps'],total['observation_calls'])==(120,3624,36240,36000,36120)))
test('new_task_specific_initialization_quote',lambda:require(
    total['environment_reset_calls']==6240 and total['reset_model_calls']==12480 and
    total['initialization_physics_substeps']==3127800 and total['initialization_mj_forward_calls']==9600 and
    next(p for p in budget['parents'] if p['task']=='door-lock-v3')['caps']['initialization_physics_substeps']==15*(26000+520)))
test('template_refused',lambda:check_documents(c,board,template,proposal,host),True)
not_accepted=copy.deepcopy(template);not_accepted['status']='released'
test('independent_Batch3_risk_false_refused',lambda:check_documents(c,board,not_accepted,proposal,host),True)
no_risk=copy.deepcopy(positive);no_risk.pop('storage_admission')
test('absent_Batch3_risk_refused',lambda:check_documents(c,board,no_risk,proposal,host),True)
prior_risk=copy.deepcopy(positive);prior_risk['storage_admission']['mode']='bounded_batch2'
test('Batch2_risk_mode_refused',lambda:check_documents(c,board,prior_risk,proposal,host),True)
prior_scope=copy.deepcopy(positive);prior_scope['storage_admission']['acceptance_scope']='this_Batch2_eight_parent_wave_only_not_Batch1_or_500_parent_quota'
test('Batch2_risk_scope_refused',lambda:check_admission_document(prior_scope,proposal),True)
test('synthetic_complete_ready_metadata',lambda:check_documents(c,board,positive,proposal,host))
running=copy.deepcopy(board);next(x for x in running['tasks'] if x['id']==proposal['task_id'])['status']='running'
test('synthetic_complete_running_metadata',lambda:check_documents(c,running,positive,proposal,host))
released_board=copy.deepcopy(board);next(x for x in released_board['tasks'] if x['id']==proposal['task_id'])['status']='released'
test('board_released_refused',lambda:check_documents(c,released_board,positive,proposal,host),True)
closed=read(W/'authorization/CONTROL.json')['closed_compute_releases'];assert len(closed)==14
for old in closed:
    bad=copy.deepcopy(positive);bad['release_id']=old['release_id']
    test('old_closed_identity_'+old['release_id'],lambda bad=bad:check_documents(c,board,bad,proposal,host),True)
for flag in ('closed','consumed'):
    bad=copy.deepcopy(positive);bad[flag]=True
    test('future_release_'+flag+'_refused',lambda bad=bad:check_documents(c,board,bad,proposal,host),True)
bad=copy.deepcopy(positive);bad['authorization_identity']['shard_id']+='bad'
test('release_shard_binding_refused',lambda:check_documents(c,board,bad,proposal,host),True)
diff=read(P/'MINIMAL_DIFF.json')
for row in diff['unchanged']:
    assert sha(row['new']['path'])==row['previous']['sha256']==row['new']['sha256']
test('25_reused_code_SHA_equal_no_old_fixtures',lambda:require(len(diff['unchanged'])==25))
replacements={
    'authorization.py':[('A11_COMMON_POOL_BATCH2_V1','A11_COMMON_POOL_BATCH3_V1'),('P11_A_COMMON_POOL_BATCH2_V1','P11_A_COMMON_POOL_BATCH3_V1'),('Batch2','Batch3')],
    'budget.py':[('bounded_batch2','bounded_batch3'),('Batch2 freezes concurrency2','Batch3 freezes concurrency2')],
    'batch_storage.py':[('bounded_batch2','bounded_batch3'),('this_Batch2_eight_parent_wave_only_not_Batch1_or_500_parent_quota','this_Batch3_eight_parent_wave_only_not_Batch1_Batch2_or_500_parent_quota')]}
for row in diff['changed']:
    old=Path(row['previous']['path']).read_text();new=Path(row['new']['path']).read_text()
    for a,b in replacements[row['relative']]:old=old.replace(a,b)
    test('only_allowed_string_AST_'+row['relative'],lambda old=old,new=new:require(ast.dump(ast.parse(old))==ast.dump(ast.parse(new))))
checkdir=P/'checks/metadata';checkdir.mkdir()
for name,value in [('CONTROL',c),('BOARD_READY',board),('BOARD_RUNNING',running),('RELEASE_SYNTHETIC_ACCEPTED',positive)]:
    with (checkdir/(name+'.json')).open('x') as f:json.dump(value,f,indent=2);f.write('\n')
for status in ('READY','RUNNING'):
    buf=io.StringIO();prior_args=sys.argv
    sys.argv=['publication_check.py','--control',str(checkdir/'CONTROL.json'),'--board',str(checkdir/('BOARD_'+status+'.json')),
        '--release',str(checkdir/'RELEASE_SYNTHETIC_ACCEPTED.json')]
    with contextlib.redirect_stdout(buf):publication_check.main()
    sys.argv=prior_args
    test('pure_JSON_publication_entry_'+status,lambda buf=buf:json.loads(buf.getvalue()))
test('all_proposed_real_roots_still_absent',lambda:require(all(not Path(v).exists() and not Path(v).parent.exists() for v in proposal['paths'].values())))
result=dict(task_id='A11_BATCH3_PREP_CPU_V1',status='PASS',checks=len(rows),rows=rows,seed_cross_table=seed_rows,
    real_operations=0,synthetic_only=True,old_fixture_suite_runs=0,actual_source_seed_shard_or_claim_created=False,
    public_acceptance_fixtures_are_synthetic_not_releases=True,actual_hardware_queries=0)
with (checkdir/'CHECK_RESULT.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps(dict(status='PASS',checks=len(rows),real_operations=0,result=str(checkdir/'CHECK_RESULT.json')),ensure_ascii=False))
