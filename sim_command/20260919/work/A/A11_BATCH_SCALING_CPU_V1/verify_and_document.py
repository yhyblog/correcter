"""Final narrow CPU validation/documentation. Never invokes a real launcher."""
from pathlib import Path
import ast,copy,datetime,hashlib,json,socket,subprocess,sys,time
ROOT=Path('/mnt/bn/arnold-recommend/yaohaoyang');B=ROOT/'Corrector/sim_command/20260919'
P=B/'results/A/A11_BATCH_SCALING_CPU_V1';W=B/'work/A/A11_BATCH_SCALING_CPU_V1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):
    p=Path(p).resolve();return dict(path=str(p),realpath=str(p),sha256=sha(p),size_bytes=p.stat().st_size)
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n')
proposal=read(P/'proposal/PROPOSAL.json');capacity=read(P/'CAPACITY_AND_THROUGHPUT.json')
checks=[]
def check(name,value,detail=None):
    checks.append(dict(name=name,passed=bool(value),detail=detail));assert value,name
control=read(B/'CONTROL.json');board=read(B/'TASK_BOARD.json')
release=B/'releases/P00_A_BATCH_SCALING_CPU_V1.json'
check('active_CPU_release_SHA',sha(release)=='cbeb5c201ef19c82e45cdb50337f24123224bc1f090da9dfb6a7466b9a77e515')
check('host',socket.gethostname()==proposal['owner_host'])
check('CONTROL45_zero_compute',control['revision']==45 and control['mode']=='prepare' and control['formal_gpu_runs_enabled'] is False and all(v==0 for v in control['current_compute_limits'].values()))
row=next(t for t in board['tasks'] if t['id']=='A11_BATCH_SCALING_CPU_V1')
check('TASK_BOARD52_CPU_ready',board['revision']==52 and row['revision']==1 and row['status']=='ready')
check('four_future_runtime_paths_absent',all(not Path(v).exists() for v in proposal['paths'].values()),proposal['paths'])
check('future_compute_release_absent',not(B/'releases/P11_A_COMMON_POOL_BATCH1_V1.json').exists())
for name in ['code/CODE_MANIFEST.json','CONFIG_MANIFEST.json','EXTERNAL_SOURCE_MANIFEST.json']:
    m=read(P/name)
    for r in m['files']:
        path=Path(r['path'])
        if path.stat().st_size>2*1024**2:raise ValueError('unexpected large input in narrow source check')
        check('bound_small_file:'+str(path),sha(path)==r['sha256'] and path.stat().st_size==r['size_bytes'])
for r in read(P/'code/CODE_MANIFEST.json')['files']:ast.parse(Path(r['path']).read_text(),filename=r['path'])
check('overlay_AST_all27',len(read(P/'code/CODE_MANIFEST.json')['files'])==27)
commands=[]
for shell in sorted((P/'commands').glob('*.sh')):
    cmd=['bash','-n',str(shell)];start=time.monotonic();r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
    commands.append(dict(argv=cmd,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr,elapsed_seconds=time.monotonic()-start));check('shell_syntax:'+shell.name,r.returncode==0)
staged=P/'checks/publication_staged';staged.mkdir(exist_ok=False)
candidate=read(P/'proposal/CANDIDATE_PUBLICATION_DOCUMENTS.json')
for key in ('CONTROL','TASK_BOARD','RELEASE'):write(staged/(key+'.json'),candidate[key])
cfg=read(proposal['parents'][0]['config']['path'])
cmd=['bash',str(P/'commands/check_publication_metadata.sh'),'--control',str(staged/'CONTROL.json'),
    '--board',str(staged/'TASK_BOARD.json'),'--release',str(staged/'RELEASE.json')]
start=time.monotonic();r=subprocess.run(cmd,cwd=P,capture_output=True,text=True,timeout=30)
record=dict(argv=cmd,cwd=str(P),exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr,
    elapsed_seconds=time.monotonic()-start,only_JSON_metadata=True,compute_authorization=False)
write(P/'checks/PUBLICATION_ENTRY_RESULT.json',record);check('actual_pure_JSON_shell_entry',r.returncode==0,r.stdout)
check('candidate_retains_B_board_bytes',
    [t for t in candidate['TASK_BOARD']['tasks'] if t['owner']=='B']==[t for t in board['tasks'] if t['owner']=='B'])
check('candidate_keeps_B_CPU_allowed','B11_COMMON_POOL_VIEWS_CPU_V1' in candidate['CONTROL']['allowed_task_ids'])
check('RELEASE_TEMPLATE_still_UNAUTHORIZED',read(P/'proposal/RELEASE_TEMPLATE.json')['status']=='UNAUTHORIZED_TEMPLATE')
check('active_CONTROL_BOARD_bytes_unchanged',sha(B/'CONTROL.json')=='04acf5638aa0418ccdc8bbfb92ba1aff815ec2334953bcfded07f3177e7432d5' and sha(B/'TASK_BOARD.json')=='9376ee5626300c9f89447b3eab178cb1d7c26884f0152ac369dcddfbc7f821dd')
write(P/'checks/STATIC_AND_ENTRY_CHECKS.json',dict(status='PASS',checks=checks,commands=commands,
    count=len(checks),real_hardware_model_environment_holder_launcher_claim_operations=0,large_weight_hashes=0))

first=read(P/'checks/run01/CHECK_RESULT.json');final=read(P/'checks/run04_publication_metadata/CHECK_RESULT.json')
backend=read(P/'checks/process05_final/CHECK_RESULT.json');delta=read(P/'checks/scheduler_delta02/CHECK_RESULT.json')
assert first['status']=='FAIL' and all(c['passed'] for c in first['checks']) and 'pre-gate metadata fields' in first['failure']
assert all(x['status']=='PASS' for x in (final,backend,delta))
unique={}
for group in (first,final,backend,delta):
    for item in group['checks']:unique[item['name']]=item
assert all(x['passed'] for x in unique.values())
attempts=[]
for path in sorted((P/'checks').glob('*/CHECK_RESULT.json')):
    d=read(path);attempts.append(dict(ref=ref(path),status=d['status'],checks=len(d['checks']),
        failure=d.get('failure'),synthetic_counts=d.get('synthetic_counts'),synthetic_only=True))
index=dict(status='PASS_WITH_RETAINED_CPU_FIXTURE_FAILURES',unique_behavior_checks=len(unique),
    behavior_checks=list(unique.values()),runs=attempts,
    retained_failure_explanation=[
      'run01:122 successful checks, then fixture supplied {synthetic:true} to exact pre-gate claim schema; corrected to the frozen fields with SYNTHETIC run_id. Metadata-only follow-ups pass; no production claim created.',
      'process01/process02: fixture omitted frozen handoff300 then NVIDIA visibility in its fake environment; the actual environment guard rejected both before fake process creation. Corrected fake environment only; process05_final passes19 checks.',
      'process03 was a process-only synthetic fixture whose production publisher default marked the private index false. Scope is entirely synthetic; process04/05 explicitly wrap the same real publisher with synthetic=True. No runtime source/seed/claim existed in any fixture.'],
    selected_final_evidence=[ref(P/'checks/run01/CHECK_RESULT.json'),ref(P/'checks/run04_publication_metadata/CHECK_RESULT.json'),
        ref(P/'checks/process05_final/CHECK_RESULT.json'),ref(P/'checks/scheduler_delta02/CHECK_RESULT.json'),ref(P/'checks/STATIC_AND_ENTRY_CHECKS.json')],
    synthetic_controller_counts=first['synthetic_counts'],all_synthetic_claim_records=3,
    original_public_sidecar_and_supplement_v2_unchanged=True,old80_104_133_suites_executed=False,
    real_operations=dict(model=0,environment=0,hardware=0,holder_query=0,holder_stop=0,real_launcher=0,real_claim=0,
        actual_collection_sources=0,training=0,install=0,deletion=0,large_weight_hash=0))
write(P/'CHECK_INDEX.json',index)

baselines=[B/'results/A/A11_OBSERVATION_PHASE_CPU_REPAIR_V1/code',B/'results/A/A11_COLLECTOR_CONTRACT_CPU_REPAIR_V1/code',B/'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code']
diff=[]
for path in sorted((P/'code').rglob('*.py')):
    relative=path.relative_to(P/'code');old=next((r/relative for r in baselines if (r/relative).exists()),None)
    diff.append(dict(relative_path=str(relative),current=ref(path),baseline=ref(old) if old else None,
        kind='new_isolated' if old is None else 'byte_identical_copy' if sha(path)==sha(old) else 'isolated_parameterization_or_batch_adapter'))
write(P/'MINIMAL_DIFF.json',dict(files=diff,baseline_files_modified=False,shared_driver_library_guard_modified=False,
    unchanged_numerics=['H10','absolute_s300','15 sequential cold policy branches per parent','Q a0/local_plus/local_minus each2 repeats',
        'G0 old+3fresh each2 repeats','native10flow per sample','own symmetric local C10 construction','no Q acceptance gate','no D/G0/Q forward','no train/seed retries'],
    changes=['five task/cut55 validation and static initialization manifests','parent-target GPU RNG state',
        'parent-scoped public/BANK/sidecar identities','finite multi-parent scheduler under one inherited lock/group',
        'whole-group exit before publication; preserve primary and secondary publication traceback',
        'independent batch storage/control/auth paths and capacity quote'],
    inherited_immutable_code_manifest=proposal['code_manifest'],no_code_import_for_diff=True))
init_rows=[]
for x in read(P/'TASK_SOURCE_EVIDENCE.json')['tasks']:
    u=x['per_attempt_initialization_caps'];init_rows.append(f"|{x['task']}|{u['environment_reset_calls']}|{u['reset_model_calls']}|{u['initialization_physics_substeps']}|{u['initialization_mj_forward_calls']}|")
source_rows=[]
for x in proposal['parents']:
    s=x['source'];source_rows.append(f"|{s['task']}|{s['ordinal']}|{s['cut']}|{s['env_seed']}|{s['master_seed']}|{x['device']['gpu_index']}|")
resource_rows=[]
for x in capacity['concurrency_options']:
    resource_rows.append(f"|{x['concurrency']}|{x['host_RAM_planning_bytes']/2**30:.0f} GiB|{x['active_private_cache_threshold_bytes']/2**30:.0f} GiB|{x['concurrent_cold_hash_plus_checkpoint_logical_bytes']/2**30:.2f} GiB|{x['same_speed_no_contention_reference_seconds']/3600:.2f} h|")
(P/'RESOURCE_QUOTE.md').write_text('''仅 CPU 报价，Batch1 未获计算授权。候选并发2；实测仅并发1。并发2依据既有单父源完成、8张独立H100身份、每worker64GiB规划及宿主可见充足RAM提出；容器内存限、RSS/VRAM峰值和共享IO未测，分析可改为1后重新冻结，运行端不得临时切并发。

|并发|RAM规划，非硬上限|活动私有cache阈值|同期单轮hash+checkpoint逻辑字节|同速无争用算术情景，非预测|
|---:|---:|---:|---:|---:|
'''+ '\n'.join(resource_rows)+'''

所有并发选项都为同一8父源，数据不删除。新整批准入93,415,604,224 B（约87.0001 GiB），另留512MiB floor，实际要求93,952,475,136 B与564,096可用inode；正式入口届时核容量。每父源10.8125GiB加8KiB门前元数据上界，8份加512MiB批次辅助。至多120个attempt，各512MiB/2048逻辑文件/4096含保留硬链接目录项；私有cache各2GiB监测阈值，整批保留16GiB。launcher受控256MiB、reserved64MiB、lifecycle stdout/stderr64MiB与两份门前JSON8192B纳辅助512MiB，不重复沿用单父源的风险接受。

5秒扫描私有已链接文件并复查容量floor，非原子quota；项目配额、共享/原生路径外临时量、unlinked、采样间/清理超调及RSS硬限均未知。保留平台限制，不设RLIMIT_AS。宿主MemAvailable记录约1.64TiB；容器未挂载memory控制器，不能据此推成容器无限RAM。GPU仅复用保存的8xH100 80GB型号/UUID，未查询可用显存或峰值。

保存的单父源墙钟4337.168725s（72.29分钟）；15 child墙钟合计4217.034017s，差120.134708s含入口/交接/发布/恢复等，不能仅归因某一阶段。policy load区间合计1877.357978s；原生采样区间153.052295s、control70.435619s、格式化观测109.317867s。它们是已有CPU monotonic区间，可能嵌套/异步，不是GPU秒；详见SAVED_TIMING_ANALYSIS.json。本轮不引入常驻模型或新增profile。

按继承manifest大小和实际完整校验路径报价：1次launcher+最多120次child完整校验，逻辑hash读取约1.148TB；120次checkpoint状态文件逻辑载入约1.122TB，页缓存/映射/实际磁盘网络流量未知，不能把这两项当实测带宽。小文件JSON授权检查与状态/图像输出还会增加元数据IO。未重hash任何大模型。

每parent数值上限：15attempt、453sample、4530flow、4500control、4515obs；整批为120/3624/36240/36000/36120。完整116项按逐任务逐branch推导求和，额外调度caps另表，不用V4实耗384sample乘8。所有Q/D/G0前向、梯度、训练、重试和删除为0。

每attempt静态初始化推导（未声称其他任务或cut55已实测）：

|task|native reset|reset_model|初始化物理子步|初始化显式mj_forward|
|---|---:|---:|---:|---:|
'''+ '\n'.join(init_rows)+'''

MT1一实例50reset，wrapper第二实例1reset，诊断1reset；每native reset经任务base/Gymnasium两次reset_model，五个路径各调用_reset_hand(50)，每次5子步。每环境构造显式forward1次；pick-place-wall reset_model仅一个set_state forward，其余四任务各两个。reset内随机拒绝循环无新增物理推进，但迭代次数未知，由child墙钟中止，不自行重试。每次策略控制按绝对时钟floor步进，最多4000物理子步/300控制及300显式forward。未知task字段/插件/回调/MJB不满足闭包即拒绝；在同一计划parent内验证，不加诊断轨迹。

8源、固定种子提案（GPU号仅便于阅读，授权绑定完整UUID）：

|task|train ordinal|cut|env seed|master seed|GPU index|
|---|---:|---:|---:|---:|---:|
'''+ '\n'.join(source_rows)+'''

SOURCE_AND_SEED_PROPOSALS.json保留确定SHA种子推导、完整source/UUID及与已接受shelf0的去重。500覆盖计划仍只接受1个独立train父源；这8个槽位及剩余覆盖数不保证有效样本或训练充分。原shelf0不重采，stick-push ordinal1留后续，其余45任务保留总体计划但本包拒绝运行。
''')
(P/'PROTOCOL_AND_LIFECYCLE.md').write_text('''本包只准备A11_COMMON_POOL_BATCH1_V1。每父源绑定一个UUID；normal→Q a0/plus/minus各2→G0 old/fresh0/1/2各2，始终15个顺序cold子进程。同一parent不拆GPU，Q仅执行C10、G0仅执行C5，丢弃raw尾部后恢复H10，到父源绝对s300或合法成功终局；无在线G0/Q调用或接受门。

launcher只调用一次既有occupancy lifecycle，显式handoff300、完整输入SHA和host/source/config检查；8holder统一预约。reserved拥有单进程组并继承同一formal.lock，parent worker不再调用lifecycle。最多2个parent槽位（实现上限8）；每slot一次仅一个GNU timeout1800+30的cold子进程，parent27900s，候选2并发波次111900s另30s grace。子timeout使用foreground，不分组/不释放重拿锁。根进程按PID+start_ticks跟踪后代，leader退出仍有后代时不得启动下一branch。

普通已记账模型/状态/前cut终止只结束本parent，不补seed/额度；共享身份/储存、任一cleanup异常、未留下child账本、未知同组进程或CONTROL停止终止owned wave。primary和publication异常栈分别保留。仅向既有隔离组内且即时复核PID身份的成员TERM/KILL；与其它进程组无交互。30s TERM后KILL仍要等内核报告无活成员，清理等待无硬上界，预约不提前释放。

整组退出是计算屏障。之后每个已启动parent通过真实publisher发布coverage、独立私有成本索引和配对sidecar；缺branch/repeat继续mask，complete不代表样本验收。发布总共300s用共享deadline/ITIMER_REAL覆盖实际调用，且不延长原wave alarm。发布期间仍由同一外层预约持有，reserved退出后才由guard一次恢复全部holder；没有闲置GPU子集holder。B不参与。

入口preparation900s、lock等待未知、handoff名义300s、child1800+30、parent27900s、wave111900+30、publication300、restoration观察120分别记录。监测poll上限包含handoff/wave/grace/名义TERM窗口，额外强制清理不伪称有界。raw成功handoff轮询数若未保存仍null，不补硬件查询。临时file/RSS/quota风险详见RESOURCE_QUOTE；新batch明确接受才可发布release。

五任务实例类严格白名单，源/class/XML SHA独立冻结。full_state_verified只表示新冻结字段/MJB闭包下逐字相同；physical_equality_proven仍null，真实资格在各自计划parent内决定。cut55使用step0..55同源前缀与自身目标GPU RNG，不使用其它GPU的默认cuda0状态。公共v1/sidecar_v1/supplement_v2原文件不改，public cost_event_refs为空并保留原因；私有成本不伪造公共UUID桥。
''')
future_release=str(B/'releases/P11_A_COMMON_POOL_BATCH1_V1.json')
(P/'proposal/README.md').write_text('''这是未授权运行包；当前CONTROL45/TASK_BOARD52计算全0。RELEASE_TEMPLATE保持UNAUTHORIZED_TEMPLATE。CANDIDATE_PUBLICATION_DOCUMENTS及checks/publication_staged是完整拟发布JSON的CPU检查材料，未写入活动CONTROL/BOARD/releases，不授予计算权限。B板条目和既有CPU许可保持。

分析独立核验并发布计算release后，唯一候选命令（当前未执行）：

```bash
bash '''+str(P/'commands/run_proposed_batch1.sh')+' '+future_release+'''
```

cwd为本包目录。脚本绑定handoff300，首行元数据校验后最多两份4KiB门前command/claim记录，正式入口再完整SHA和新batch容量检查。任何命令/claim失败均不得自行重跑。

纯JSON发布入口可传完整暂存文件（不会hash大权重/创建claim/执行计算）：

```bash
bash '''+str(P/'commands/check_publication_metadata.sh')+' --control CONTROL.json --board TASK_BOARD.json --release RELEASE.json'+'''
```

冻结并发2及8个UUID/source/seed；如分析决定改并发或来源，需要新的同源元数据与校验，执行端不能运行时改。旧12份计算release不复用。
''')
supp=P/'supplement_batch_v1'
(supp/'README.md').write_text('''本补充只说明5任务、cut5/55批量输出路径和身份。public interface_v1、sidecar_v1、supplement_v2不改。episode/source/parent/branch语义与旧版一致，cut字段/anchor/prefix/绝对窗口以实际配置5或55为准；old queue年龄与剩余均为5。所有paired aggregate仍限同parent/cut/source/context、两个完整repeat及full_state_verified闭包。每parent输出位于batch output/parent_key；私有成本在该parent/reserved/PRIVATE_COST_INDEX.json，根launcher/scheduler账本独立。真实数据资格待计划parent和分析验收，当前仅合成检查。未修改B代码、任务或dispatch。
''')
write(supp/'READY.json',dict(status='CPU_INTERFACE_NOT_COLLECTION_READY',schema='common_pool_batch_supplement_v1',
    public_sidecar_unchanged=proposal['sidecar_ready'],notes=ref(supp/'README.md'),tasks=list(dict.fromkeys(p['source']['task'] for p in proposal['parents'])),
    cuts=[5,55],actual_collected_new_parents=0,physical_equality_proven=None))
write(P/'CPU_READY.json',dict(task_id='A11_BATCH_SCALING_CPU_V1',revision=1,owner='A',status='CPU_READY_UNAUTHORIZED_BATCH1',
    at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),proposal=ref(P/'proposal/PROPOSAL.json'),
    checks=ref(P/'CHECK_INDEX.json'),static_and_publication_entry=ref(P/'checks/STATIC_AND_ENTRY_CHECKS.json'),
    capacity=ref(P/'CAPACITY_AND_THROUGHPUT.json'),runtime_proposal_task='A11_COMMON_POOL_BATCH1_V1',
    recommended_concurrency=2,measured_concurrency=1,parent_count=8,actual_compute_authorized=False,
    actual_future_paths_created=False,new_seed_source_shard_values='proposed JSON only',
    unresolved=['new task/cut55 real state/MJB qualification','container RAM limit and peak RSS/VRAM','shared IO/pagecache',
        'batch quota/outside temp/unlinked/overshoot risk requires new explicit acceptance','cleanup/end-to-end wall bound unknown'],
    CPU_implementation_blockers=[],physical_equality_proven=None,real_operations=index['real_operations'],
    next='analysis review only; do not automatically collect/train/evaluate'))
(P/'REPORT.md').write_text(f'''A11_BATCH_SCALING_CPU_V1 revision1 已完成CPU准备；新Batch1包未获计算授权。

隔离支持5任务/cut5或55，固定8个A train槽位及确定source/seed/UUID提案。保持每parent15个顺序cold分支与原监督；跳过已接受shelf0。新增有界多parent调度，同一外层预约/同组同锁，所有正式进程退出后发布并一次恢复8holder。其他45任务默认拒绝，仍保留在500覆盖计划。

{len(unique)}项不重复定向行为检查已覆盖真实recorder/controller/BANK/public/sidecar、并发1/2/4/8、错误隔离、进程退出屏障、301阶段和授权/容量边界；真实后端用fake PID/Popen/timer组合。CPU fixture的3次起步失败和一次合成index标记修正均保留，最终相应检查通过；没有重跑旧全集。纯JSON实际shell入口和新代码AST/shell检查通过。

完整116caps逐任务求和：120attempt、3624sample/36240flow、36000control/36120obs；pick-place-wall初始化forward独立报价。详细逐源/逐worker表、72.29分钟保存计时与并发1/2/4/8估算见RESOURCE_QUOTE.md及对应JSON。候选并发2是条件性工程建议，实测仅1；新批次需要约87.0001GiB准入+512MiB floor/564096 inode，不把单parent接受当批quota。

真实新任务/cut55状态资格、RAM/VRAM峰值/容器内存限、IO及监测缺口保留未知；physical_equality_proven=null。无CPU代码阻塞，是否放行及并发/存储风险由分析决定。正式release/run/claim/cache未创建，模型/环境/硬件/holder/真实launcher/采集/训练/安装/删除/大权重hash均0。旧12计算release未复用，原public/sidecar/supplement、V4数据和B/dispatch未改；停止等待分析验收。
''')
print(json.dumps(dict(status='CPU_READY_UNAUTHORIZED_BATCH1',unique_behavior_checks=len(unique),static_checks=len(checks),proposal_sha256=sha(P/'proposal/PROPOSAL.json'),publication_entry_exit=r.returncode,real_operations=0)))
