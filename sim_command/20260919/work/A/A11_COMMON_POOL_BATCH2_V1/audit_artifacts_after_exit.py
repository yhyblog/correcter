"""Hash saved runtime artifacts and audit published references; CPU/stdlib only."""
from pathlib import Path
import collections,datetime,hashlib,json,os,stat,sys
from audit_saved_helpers import load,digest,ref,save
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
W=B/'work/A/A11_COMMON_POOL_BATCH2_V1';P=B/'results/A/A11_COMMON_POOL_BATCH2_V1'
PREP=B/'results/A/A11_MT50_CONTINUATION_CPU_V1'
if not (B/'results/A/A11_COMMON_POOL_BATCH2_V1/OUTER_EXIT.json').exists():raise SystemExit('Formal command still active')
release=load(W/'authorization/P11_A_COMMON_POOL_BATCH2_V1.json')
run=Path(release['paths']['output']);cache=Path(release['paths']['cache'])
errors=[];files={};unique={};by_parent={};external={};documents=[]
def issue(kind,**kw):errors.append(dict(kind=kind,**kw))
def references(v):
    if type(v) is dict:
        if type(v.get('path')) is str and type(v.get('sha256')) is str:yield v
        for x in v.values():yield from references(x)
    elif type(v) is list:
        for x in v:yield from references(x)
expected_external={}
for parent in release['parents']:
    cfg=load(parent['config']['path'])
    for r in references(cfg):expected_external.setdefault(r['path'],set()).add(r['sha256'])
    for r in (parent['config'],parent['source_ref']):expected_external.setdefault(r['path'],set()).add(r['sha256'])
manifest=P/'RUNTIME_FILES.jsonl'
with manifest.open('x') as stream:
    if run.exists():
        for directory,dirs,names in os.walk(run,followlinks=False):
            dirs.sort();names.sort()
            for name in names:
                path=Path(directory)/name;s=path.lstat();relative=path.relative_to(run)
                if not stat.S_ISREG(s.st_mode):issue('nonregular_runtime_artifact',path=str(path));continue
                key=(s.st_dev,s.st_ino);alias='.partial_' in name
                row=dict(path=str(path),relative=str(relative),sha256=digest(path),size_bytes=s.st_size,
                    device=s.st_dev,inode=s.st_ino,nlink=s.st_nlink,reported_blocks_bytes=s.st_blocks*512,
                    partial_hardlink_alias=alias,mtime_ns=s.st_mtime_ns)
                files[str(path)]=row;unique.setdefault(key,row)
                parent_key=relative.parts[0];bucket=by_parent.setdefault(parent_key,dict(paths=0,logical_path_bytes=0,inodes={},canonical_paths=0,partial_alias_paths=0))
                bucket['paths']+=1;bucket['logical_path_bytes']+=s.st_size;bucket['inodes'].setdefault(key,row)
                bucket['partial_alias_paths' if alias else 'canonical_paths']+=1
                if not alias and path.suffix=='.json':documents.append(path)
                stream.write(json.dumps(row,sort_keys=True)+'\n')
                if len(files)%20000==0:print(json.dumps(dict(runtime_paths_hashed=len(files),unique_inodes=len(unique))),flush=True)
for bucket in by_parent.values():
    values=bucket.pop('inodes').values();bucket['unique_inodes']=len(values)
    bucket['unique_inode_bytes']=sum(x['size_bytes'] for x in values)
    bucket['unique_inode_reported_blocks_bytes']=sum(x['reported_blocks_bytes'] for x in values)
ref_counts=collections.Counter();schema_counts=collections.Counter();ref_errors=[];identity_errors=[]
def check_ref(r,origin):
    path=r['path'];sha=r['sha256'];ref_counts['total']+=1
    if path in files:
        ref_counts['current_run']+=1
        if files[path]['sha256']!=sha:ref_errors.append(dict(origin=origin,reference=r,reason='runtime SHA mismatch'))
        return
    target=Path(path)
    if target.is_relative_to(run):
        ref_errors.append(dict(origin=origin,reference=r,reason='runtime reference absent from manifest'));return
    key=(path,sha)
    if key not in external:
        metadata_expected=sha in expected_external.get(path,set())
        # Checkpoint payloads are never opened or rehashed by this audit.
        if path.startswith(('/proc/','/sys/','/dev/')):
            external[key]=dict(path=path,sha256=sha,mode='saved_host_identity_reference_not_requeried',payload_rehashed=False)
        elif target.suffix in ('.safetensors','.pt','.pth','.bin'):
            external[key]=dict(path=path,sha256=sha,mode='frozen_config_reference_only',metadata_matches=metadata_expected,payload_rehashed=False)
        elif target.exists() and target.is_file() and target.stat().st_size<=16*1024**2:
            actual=digest(target);external[key]=dict(path=path,sha256=sha,actual_sha256=actual,mode='small_dependency_file',matches=actual==sha,payload_rehashed=True)
        else:
            external[key]=dict(path=path,sha256=sha,mode='unverified_external',payload_rehashed=False,metadata_matches=metadata_expected)
    evidence=external[key];ref_counts[evidence['mode']]+=1
    if evidence.get('matches') is False or evidence.get('metadata_matches') is False:
        ref_errors.append(dict(origin=origin,reference=r,reason='external reference mismatch or not frozen'))
sys.path.insert(0,str(PREP/'code'));import inheritance
from public_records import validate_public
sys.path.insert(0,str(inheritance.SIDECAR));from validator import validate as validate_sidecar
parents={p['parent_key']:p for p in release['parents']}
banks={key:load(run/key/'normal/BANK.json') for key in parents}
configs={key:load(parent['config']['path']) for key,parent in parents.items()}
families={'normal':None,**{f'Q_{a}_r{r}':a for a in ('a0','local_plus','local_minus') for r in (0,1)},
    **{f'G0_{a}_r{r}':a for a in ('old','fresh0','fresh1','fresh2') for r in (0,1)}}
transition_steps=collections.defaultdict(list);observation_steps=collections.defaultdict(list)
shared_plan_counts=collections.Counter();schema_errors=[]
for path in documents:
    try:doc=load(path)
    except (ValueError,UnicodeError) as e:issue('invalid_JSON',path=str(path),error=str(e));continue
    for r in references(doc):check_ref(r,str(path))
    if type(doc) is not dict:continue
    relative=path.relative_to(run);parts=relative.parts;parent=parents.get(parts[0])
    if parent is None:continue
    source=parent['source'];role=parts[1] if len(parts)>1 else None
    branch_root=run/parts[0]/role
    try:
        if doc.get('record_type') in ('episode','transition'):
            validate_public(doc);schema_counts[doc['record_type']]+=1
            if doc['synthetic'] is not False or doc['split']!='train':raise ValueError('synthetic/split')
            if any(doc['identity'].get(k)!=v for k,v in parent['identity'].items()):raise ValueError('task/run/release identity')
            if doc['identity']['config_sha256']!=parent['config']['sha256']:raise ValueError('config SHA identity')
            s=doc['source']
            if s['source_id']!=source['source_id'] or s['parent_episode_id']!=source['parent_source_id'] or s['branch_id']!=role:raise ValueError('source/parent/branch identity')
            if doc['environment']['task']!=source['task']:raise ValueError('task identity')
            if doc['record_type']=='transition':
                transition_steps[(parts[0],role)].append(doc['step'])
                if doc['candidate_family']!=families[role]:raise ValueError('candidate family differs from frozen branch')
                if not 0<=doc['step']<doc['next_step']<=300:raise ValueError('step bounds')
                for key in ('observation_ref','next_observation_ref'):
                    if not Path(doc[key]['path']).is_relative_to(branch_root):raise ValueError('cross-branch observation')
                chunk=doc['generated_chunk_ref'];chunk_path=Path(chunk['path'])
                if chunk_path.is_relative_to(branch_root):shared_plan_counts['branch_local']+=1
                else:
                    bank=banks[parts[0]]
                    family=families[role];commit=10 if role.startswith('Q_') else 5
                    if family not in bank['plans'] or not source['cut']<=doc['step']<source['cut']+commit:raise ValueError('shared plan outside its frozen commitment')
                    item=bank['plans'][family];expected=item['raw50_ref']
                    if item['plan_key']!=family or chunk['path']!=expected['path'] or chunk['sha256']!=expected['sha256']:raise ValueError('shared plan key/path/SHA mismatch')
                    if bank['source_id']!=source['source_id'] or bank['parent_source_id']!=source['parent_source_id'] or bank['cut']!=source['cut'] or bank['source_manifest_ref']['sha256']!=parent['source_ref']['sha256']:raise ValueError('shared BANK identity')
                    if bank['source_manifest_ref']['path']!=parent['source_ref']['path'] or bank['source_signature']!=configs[parts[0]]['source_signature'] or bank['run_id']!=parent['identity']['run_id']:raise ValueError('shared BANK manifest/signature/run identity')
                    shared_plan_counts['same_parent_normal_BANK']+=1
            else:
                result=load(branch_root/'BRANCH_RESULT.json')
                if result:
                    e=result['intervention_evidence']
                    expected=bool(e['commitment_entered'] and e['plan_replaced'] and e['returned_commitment_steps']>0)
                    if doc['intervened']!=expected:raise ValueError('intervention marker differs from actual entry')
        elif doc.get('schema_version')=='common_pool_sidecar_v1':
            validate_sidecar(doc);schema_counts['sidecar']+=1
            if doc['synthetic'] is not False:raise ValueError('synthetic sidecar')
            if doc['identity']['source_id']!=source['source_id'] or doc['identity']['parent_id']!=source['parent_source_id']:raise ValueError('sidecar source')
            if doc['identity']['run_id']!=parent['identity']['run_id'] or doc['identity']['source_signature']!=configs[parts[0]]['source_signature']:raise ValueError('sidecar run/source signature')
            if doc['identity']['source_manifest_ref']['path']!=parent['source_ref']['path'] or doc['identity']['source_manifest_ref']['sha256']!=parent['source_ref']['sha256']:raise ValueError('sidecar source manifest')
            if role!='reserved':
                expected_id=source['parent_source_id']+'__'+role
                expected_repeat=None if role=='normal' else int(role[-1])
                if doc['identity']['branch_id']!=role or doc['identity']['episode_id']!=expected_id or doc['identity']['physical_attempt_id']!=expected_id:raise ValueError('physical sidecar episode/branch identity')
                if doc['repeats']['repeat_id']!=expected_repeat:raise ValueError('physical sidecar repeat identity')
                namespace='normal' if role=='normal' else 'Q_C10' if role.startswith('Q_') else 'G0_C5'
                if doc['protocol']['target_namespace']!=namespace:raise ValueError('sidecar target namespace')
            if doc['plans']['physical_alias_of'] is not None:raise ValueError('physical alias claim')
            rawref=doc['plans']['raw50_ref']
            if rawref is not None:
                if rawref['path'] not in files:raise ValueError('raw50 outside runtime artifact manifest')
                payload=Path(rawref['path']).read_bytes()
                if len(payload)!=800:raise ValueError('raw50 byte count')
                c10=hashlib.sha256(payload[:160]).hexdigest()
                c5=hashlib.sha256(payload[80:160] if doc['plans']['candidate_family']=='old' else payload[:80]).hexdigest()
                if doc['plans']['raw_C10_sha256']!=c10 or doc['plans']['raw_C5_sha256']!=c5:raise ValueError('C10/C5 raw byte digest mismatch')
                alias=c10 if doc['protocol']['target_namespace']=='Q_C10' else c5
                if doc['plans']['raw_alias_group']!=alias:raise ValueError('alias group differs from actual raw bytes')
                schema_counts['raw50_C10_C5_byte_digest']+=1
        if role!='reserved' and len(parts)==4 and parts[2]=='observations' and path.suffix=='.json':
            observation_steps[(parts[0],role)].append(doc['step']);schema_counts['observation_bundle']+=1
    except Exception as e:schema_errors.append(dict(path=str(path),type=type(e).__name__,message=str(e)))
for key,steps in transition_steps.items():
    if sorted(steps)!=list(range(len(steps))):identity_errors.append(dict(parent=key[0],role=key[1],reason='transition sequence not contiguous from0'))
    obs=observation_steps.get(key,[])
    if sorted(obs)!=list(range(len(steps)+1)):identity_errors.append(dict(parent=key[0],role=key[1],reason='observation count/sequence mismatch; retain partial failure'))
save(P/'ARTIFACT_REFERENCE_AUDIT.json',dict(schema_counts=dict(schema_counts),reference_counts=dict(ref_counts),
    runtime_files_manifest=ref(manifest),runtime_paths=len(files),unique_runtime_inodes=len(unique),
    shared_plan_references=dict(shared_plan_counts),schema_errors=schema_errors,reference_errors=ref_errors,
    sequence_errors=identity_errors,external_dependencies=list(external.values()),large_weight_payload_rehashes=0,
    partial_aliases_retained_but_excluded_from_samples=True,artifact_errors=errors,
    no_model_environment_or_hardware_imports=True))
monitor_path=run/'launcher/STORAGE_MONITOR.jsonl'
monitor_rows=0;monitor_peaks={};minimum_available=None;minimum_inodes=None;last_monitor=None
monitor_errors=[]
if monitor_path.exists():
    with monitor_path.open() as f:
        for line in f:
            try:row=json.loads(line)
            except ValueError as e:monitor_errors.append(str(e));continue
            monitor_rows+=1;last_monitor=row
            c=row['capacity'];v=c['available_bytes'];n=c['available_inodes']
            minimum_available=v if minimum_available is None else min(minimum_available,v)
            minimum_inodes=n if minimum_inodes is None else min(minimum_inodes,n)
            for p in row['parents']:
                peak=monitor_peaks.setdefault(p['parent_key'],dict(logical_file_bytes=0,entries=0))
                peak['logical_file_bytes']=max(peak['logical_file_bytes'],p['logical_file_bytes'])
                if type(p.get('entries')) is int:peak['entries']=max(peak['entries'],p['entries'])
# Cache metadata only: never read a model or cache payload.
cache_rows=[];cache_inode={};cache_paths=0
if cache.exists():
    for directory,dirs,names in os.walk(cache,followlinks=False):
        for name in names:
            path=Path(directory)/name;s=path.lstat();cache_paths+=1
            row=dict(path=str(path),size_bytes=s.st_size,mode=s.st_mode,device=s.st_dev,inode=s.st_ino,
                payload_hashed=False,symlink=stat.S_ISLNK(s.st_mode))
            cache_rows.append(row);cache_inode.setdefault((s.st_dev,s.st_ino),row)
save(P/'SAVED_STORAGE_AUDIT.json',dict(runtime_manifest=ref(manifest),
    final_output_paths=len(files),final_output_unique_inodes=len(unique),
    final_output_logical_path_bytes=sum(x['size_bytes'] for x in files.values()),
    final_output_unique_inode_bytes=sum(x['size_bytes'] for x in unique.values()),
    final_output_unique_inode_reported_blocks_bytes=sum(x['reported_blocks_bytes'] for x in unique.values()),
    per_top_directory=by_parent,final_output_is_not_global_peak=True,
    saved_admission=load(run/'launcher/STORAGE_ADMISSION.json'),monitor_ref=ref(monitor_path) if monitor_path.exists() else None,
    saved_monitor_polls=monitor_rows,saved_monitor_errors=monitor_errors,
    sampled_private_cache_peaks=monitor_peaks,sampled_minimum_filesystem_available_bytes=minimum_available,
    sampled_minimum_filesystem_available_inodes=minimum_inodes,last_saved_monitor=last_monitor,
    final_cache_paths=cache_paths,final_cache_unique_inode_bytes=sum(x['size_bytes'] for x in cache_inode.values()),
    final_cache_metadata=cache_rows,cache_payload_rehashes=0,
    exact_global_peak_bytes=None,project_quota_bytes=None,outside_root_temporary_bytes=None,
    unlinked_bytes=None,between_monitor_overshoot_bytes=None,process_RSS_peak_bytes=None,VRAM_peak_bytes=None,
    new_capacity_or_hardware_queries=0,logical_IO_actual_bytes=None,physical_IO_actual_bytes=None,
    quoted_IO_scope='about1.148TB known-size logical checksum subtotal only;116 unknown-size files; not strict upper',
    strict_total_IO_upper_bytes=None,remaining_storage_guaranteed=False))
print(json.dumps(dict(status='SAVED_ARTIFACTS_AUDITED',paths=len(files),unique_inodes=len(unique),
    schema_errors=len(schema_errors),reference_errors=len(ref_errors),sequence_errors=len(identity_errors),
    monitor_polls=monitor_rows)),flush=True)
