"""CPU metadata only. Refs to inherited manifests never follow weight files."""
import copy,difflib,hashlib,json,os,socket,sys,time
from pathlib import Path
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
P=B/'results/A/A11_COLLECTOR_CONTRACT_CPU_REPAIR_V1'
O=B/'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1'
W=B/'work/A/A11_COLLECTOR_CONTRACT_CPU_REPAIR_V1_r1'
sys.path.insert(0,str(P/'code'))
import inheritance
from budget import TOTAL,STORAGE,TIMEOUTS
from storage_admission import capacity
def read(p):return json.loads(Path(p).read_text())
def ref(p):
    p=Path(p);raw=p.read_bytes()
    return dict(path=str(p),realpath=str(p.resolve()),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def write(p,value):Path(p).write_text(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n')
old=read(O/'proposal/PROPOSAL.json');config=read(O/'config/CONFIG.json')
assert TOTAL==old['resource_caps'] and len(TOTAL)==116 and TIMEOUTS==old['timeouts']
closure=read(O/'STATE_FIELD_CLOSURE.json')
closure['repair_decision_ref']=ref(B/'contracts/COMMON_POOL_COLLECTOR_REPAIR_DECISIONS_V1.md')
closure['Box_bound_metadata']='exact runtime gymnasium.spaces.Box low/high numeric ndarray only; dtype/shape/raw bytes retained including +/-inf; NaN and all nonfinite physical arrays/scalars rejected; exact Dict traversed'
closure['unresolved_for_future_parent']=[x for x in closure['unresolved_for_future_parent'] if 'RLIMIT_AS' not in x and 'project quota/reservation' not in x]
closure['unresolved_for_future_parent'].append('first-parent capacity observation and finite private temp/cache monitoring do not prove project quota, shared cache writes, or bounded native write overshoot')
write(P/'STATE_FIELD_CLOSURE.json',closure)
config['state_contract_sha256']=ref(P/'STATE_FIELD_CLOSURE.json')['sha256']
write(P/'config/CONFIG.json',config)

storage=copy.deepcopy(STORAGE)
storage.update(nominal_uncompressed_RGB_bytes=old['storage']['nominal_uncompressed_RGB_bytes'],
    hard_limit_scope='Store payload/record/file counters plus inherited RLIMIT_FSIZE32MiB logs; gate-before metadata exactly two JSONs <=4096 each. Retained hardlink partials do not double payload; filesystem allocation overhead is planning only.',
    third_party_temp_scope='2GiB threshold monitored under private cache root; not a filesystem/project/cgroup hard quota; shared HF cache and native outside-path writes unknown',
    batch_plan_scope='2.08TiB whole-batch planning is not a first-parent admission requirement',
    timeout_scope='original timers unchanged; finite 6000 storage polls includes pre-entry and final check; monitor exhaustion fails then preserves original process drain barrier',
    actual_capacity_evidence='runtime fresh statvfs on nearest existing output/cache ancestors; shared filesystem and inode floor checked before NVML/holder entry; no reservation')
write(P/'STORAGE_ADMISSION_CONTRACT.json',dict(status='UNAUTHORIZED_TEMPLATE',storage=storage,
    old_first_parent_planning_bytes=old['storage']['required_reserved_bytes'],
    first_parent_planning_delta_bytes=storage['first_parent_admission_bytes']-old['storage']['required_reserved_bytes'],
    delta_components=dict(two_pre_gate_JSON_bytes=8192,private_temp_cache_monitoring_budget_bytes=2*1024**3),
    controlled_output_extra_capacity_bytes=0,index_and_monitor_payloads_use_existing_64MiB_parent_envelope=True,
    additional_CPU_operations=dict(transition_reference_SHA_checks_max=13500,transition_SHA_rule='3 refs per control, <=4500 controls; each file bounded by existing Store',
        supplemental_index_reference_and_schema_SHA_upper=1024,member_qualification_passes_max=35,logical_aggregate_indices_max=4,private_cost_indices_max=2,
        Box_NaN_array_scans_upper=30720,Box_scan_rule='<=2048 state fields per capture x15; each existing ndarray <=8MiB; only float Box low/high scanned',
        new_model_or_physics_calls=0,counts_are_static_loop_upper_bounds_not_new_public_UUID_events=True),
    monitor_CPU_limits=dict(polls=6000,directory_entries_per_poll=4096,statvfs_per_monitor_poll=1,
        admission_statvfs=2,interval_seconds=5,read_syscall_wall_time_limit_seconds=None),
    unknowns=['project quota','exclusive reservation','unlinked-open temp file bytes','shared HF cache writes',
        'native writes ignoring environment paths','between-scan/cleanup overshoot','real process-group resident-memory peak'],
    actions_on_error='metadata invalid before create; command/claim are one-shot bounded exclusive files; low space/statvfs/write errors stop; after lifecycle entry the owned process waits for full drain then restores occupancy; no retry/deletion/auto-relaxation'))
points=[
 dict(chain='numeric_setup initialize: strict local policy state/normalizer/projection reads',path='inherited frozen checkpoint and projection paths',setting='read inputs; current CPU repair does not hash/load them',writes='library side effects outside explicit read paths remain unknown'),
 dict(chain='features/preprocessor/tokenizer from_pretrained and HF loader',path=config['hf_home'],setting='HF_HOME unchanged; HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1',writes='shared cache may create locks/metadata or library-managed artifacts; not monitored, not proved zero, permissions unchanged'),
 dict(chain='Python tempfile and native libraries honoring TMPDIR',path='<private_cache>/temporary',setting='TMPDIR',writes='included in 2GiB private threshold; unlinked-open files can evade directory scan'),
 dict(chain='XDG and Torch Hub cache writers',path='<private_cache>/cache',setting='XDG_CACHE_HOME/TORCH_HOME',writes='private directory monitor; no proof all libraries honor settings'),
 dict(chain='CUDA driver disk cache',path='<private_cache>/cache/cuda',setting='CUDA_CACHE_DISABLE=1 plus CUDA_CACHE_PATH',writes='disabled request not proof zero; any linked private file is monitored'),
 dict(chain='TorchInductor/Triton optional cache writers',path='<private_cache>/cache/inductor or triton',setting='TORCHINDUCTOR_CACHE_DIR/TRITON_CACHE_DIR',writes='no extra compiler call enabled; optional writes redirected and monitored if honored'),
 dict(chain='Python bytecode',path='module-adjacent paths',setting='-B and PYTHONDONTWRITEBYTECODE=1',writes='Python bytecode request disabled; native library writes separate unknown'),
 dict(chain='foreign libraries ignoring cache/temp environment',path='unknown including /tmp/home/shared inputs',setting='no permission or platform changes',writes='unknown; outside private-directory monitoring')]
write(P/'THIRD_PARTY_WRITE_POINTS.json',dict(status='STATIC_CHAIN_NOT_RUNTIME_TRACE',points=points,strict_third_party_hard_quota=False,requires_future_analysis_risk_admission=True))
evidence=dict(time=time.time(),host=socket.gethostname(),scope='this CPU process plus scoped statvfs only; no GPU/holder/process-tree inspection',capacity=[capacity(P),capacity(W)],project_quota_known=False,exclusive_reservation=False,
    proc_self_limits=Path('/proc/self/limits').read_text(),proc_self_cgroup=Path('/proc/self/cgroup').read_text(),future_process_group_RSS_peak_bytes=None)
for name in ('memory.max','memory.current','memory.peak'):
    path=Path('/sys/fs/cgroup')/name
    evidence['cgroup_'+name]=dict(path=str(path),text=path.read_text().strip() if path.is_file() else None,
        scope='visible current cgroup, not exclusive future wave; absence is unknown')
write(P/'CPU_CAPACITY_MEMORY_EVIDENCE.json',evidence)

budget=read(O/'proposal/RESOURCE_BUDGET.json');budget['storage']=storage
budget['extra_CPU_storage_delta']=read(P/'STORAGE_ADMISSION_CONTRACT.json')
budget['timeout_notes'].append('Private directory/capacity monitor has separate finite6000 poll budget. Slow syscalls, shared writes, cleanup and final process drain remain unbounded; no hard end-to-end promise.')
write(P/'proposal/RESOURCE_BUDGET.json',budget)
# Never manufacture new source, seed or actual shard. This exact source proposal was never executed.
(P/'proposal/SOURCE_PROPOSAL.json').write_bytes((O/'proposal/SOURCE_PROPOSAL.json').read_bytes())

files=[];diff=[];patches=[]
oldmanifest=read(O/'code/CODE_MANIFEST.json');oldrows={r['path']:r for r in oldmanifest['files']}
for f in sorted((P/'code').rglob('*.py')):
    files.append(ref(f));rel=f.relative_to(P/'code');original=O/'code'/rel
    prior=oldrows.get(str(original))
    if original.exists():
        raw=original.read_bytes();actual=hashlib.sha256(raw).hexdigest()
        assert not prior or actual==prior['sha256']
        changed=actual!=files[-1]['sha256']
        if changed:patches.extend(difflib.unified_diff(raw.decode().splitlines(True),f.read_text().splitlines(True),fromfile='old/'+str(rel),tofile='new/'+str(rel)))
        diff.append(dict(relative_path=str(rel),change='modified' if changed else 'copied_bytes_unchanged',old_sha256=actual,new_sha256=files[-1]['sha256']))
    else:diff.append(dict(relative_path=str(rel),change='new_overlay_helper',old_sha256=None,new_sha256=files[-1]['sha256']))
write(P/'code/CODE_MANIFEST.json',dict(files=files,inherited_manifests=[ref(O/'code/CODE_MANIFEST.json')],
    import_order='new overlay before frozen base; core.__path__ extends base, unchanged native/vendor loader paths refer to base',
    current_followed_large_weights=False,base_code_count=len(oldmanifest['files'])))
write(P/'CODE_DIFF.json',dict(base_manifest_ref=ref(O/'code/CODE_MANIFEST.json'),files=diff,unlisted_base_bytes_untouched=True))
(P/'MINIMAL.patch').write_text(''.join(patches))
write(P/'INPUT_MANIFEST.json',dict(files=[],inherited_manifests=[ref(O/'INPUT_MANIFEST.json')],current_large_weight_hashes=0))
write(P/'EXTERNAL_SOURCE_MANIFEST.json',dict(files=[],inherited_manifests=[ref(O/'EXTERNAL_SOURCE_MANIFEST.json')],current_driver_library_probes=0))
prep=[B/'tasks/A11_COLLECTOR_CONTRACT_CPU_REPAIR_V1.md',B/'contracts/COMMON_POOL_COLLECTOR_REPAIR_DECISIONS_V1.md',
    B/'releases/P00_A_COLLECTOR_CONTRACT_CPU_REPAIR_V1.json',B/'manifests/COMMON_POOL_COLLECTOR_CPU_V1_REVIEW.json',
    P/'supplement_v1/READY.json',P/'supplement_v1/README.md',P/'supplement_v1/aggregate_index.schema.json',
    P/'STORAGE_ADMISSION_CONTRACT.json',P/'THIRD_PARTY_WRITE_POINTS.json']
write(P/'PREPARATION_INPUT_MANIFEST.json',dict(files=[ref(f) for f in prep],inherited_manifests=[ref(O/'PREPARATION_INPUT_MANIFEST.json')]))

proposal=copy.deepcopy(old);task='A11_COMMON_POOL_FIRST_PARENT_V2';release='P11_A_COMMON_POOL_FIRST_PARENT_V2'
proposal['task_id']=task;proposal['authorization_identity'].update(task_id=task,release_id=release,
    run_id='PROPOSED_A11_shelf_train0000_parent_V2',wave_id='PROPOSED_A11_first_parent_A_only_V2',shard_id='PROPOSED_A11_shelf_train_cut5_parent0000_V2')
for key,value in proposal['paths'].items():proposal['paths'][key]=value.replace('P11_COMMON_POOL_V1','P11_COMMON_POOL_V2').replace('FIRST_PARENT_V1','FIRST_PARENT_V2').replace('parent_V1','parent_V2')
assert all(not Path(v).exists() for v in proposal['paths'].values())
proposal.update(cwd=str(P),storage=storage,current_future_readiness='NOT_RELEASED; finite capacity/monitoring risks require explicit release admission; real full_state/MJB qualification remains embedded in the same planned parent',
    supplementary_protocol_ref=ref(P/'supplement_v1/READY.json'))
for key,rel in [('config','config/CONFIG.json'),('budget','proposal/RESOURCE_BUDGET.json'),('code_manifest','code/CODE_MANIFEST.json'),
    ('input_manifest','INPUT_MANIFEST.json'),('external_manifest','EXTERNAL_SOURCE_MANIFEST.json'),('closure','STATE_FIELD_CLOSURE.json'),('preparation_manifest','PREPARATION_INPUT_MANIFEST.json'),('command_ref','commands/run_proposed_first_parent.sh')]:proposal[key]=ref(P/rel)
proposal['command']=['bash',str(P/'commands/run_proposed_first_parent.sh'),str(B/'releases'/(release+'.json'))]
proposal['command_sha256']=proposal['command_ref']['sha256']
write(P/'proposal/PROPOSAL.json',proposal)
rt=read(O/'proposal/RELEASE_TEMPLATE.json')
rt.update(status='UNAUTHORIZED_TEMPLATE',identity=proposal['authorization_identity'],release_id=release,task_ids=[task],
    paths=proposal['paths'],storage=storage,proposal_sha256=ref(P/'proposal/PROPOSAL.json')['sha256'],
    storage_admission=dict(mode='bounded_first_parent',run_id=proposal['authorization_identity']['run_id'],project_quota_known=False,exclusive_reservation=False,accepts_monitoring_gaps=True))
write(P/'proposal/RELEASE_TEMPLATE.json',rt)
control=read(O/'proposal/CONTROL_TEMPLATE.json');control.update(active_compute_release='releases/'+release+'.json',active_compute_release_id=release,active_compute_task_ids=[task],allowed_task_ids=[task],per_task_compute_limits={task:TOTAL})
write(P/'proposal/CONTROL_TEMPLATE.json',control)
board=read(O/'proposal/BOARD_TEMPLATE.json');row=board['tasks'][0];row.update(id=task,release='releases/'+release+'.json',**{k:proposal['authorization_identity'][k] for k in ('run_id','wave_id','shard_id')})
write(P/'proposal/BOARD_TEMPLATE.json',board)
write(P/'CAPS_DIFF.json',dict(status='PASS',original_numerical_caps_count=116,unchanged_count=116,changed_count=0,
    per_cap=[dict(name=k,old=old['resource_caps'][k],new=TOTAL[k],unchanged=True) for k in sorted(TOTAL)],
    source_exact_equal=old['source']==proposal['source'],source_file_byte_equal=(P/'proposal/SOURCE_PROPOSAL.json').read_bytes()==(O/'proposal/SOURCE_PROPOSAL.json').read_bytes(),
    timeout_exact_equal=old['timeouts']==proposal['timeouts'],new_identity_paths_disjoint=all(v not in old['paths'].values() for v in proposal['paths'].values()),
    additional_CPU_storage_budget_ref=ref(P/'STORAGE_ADMISSION_CONTRACT.json')))
print(json.dumps(dict(status='FROZEN_UNAUTHORIZED',code_overlay_files=len(files),unchanged_caps=116,proposal_sha256=ref(P/'proposal/PROPOSAL.json')['sha256'],first_parent_admission_bytes=storage['first_parent_admission_bytes'])))
