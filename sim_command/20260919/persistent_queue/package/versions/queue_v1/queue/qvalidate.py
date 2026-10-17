"""Post-exit CPU technical acceptance; not scientific/result-ranking acceptance."""
import hashlib
import json
import os
from pathlib import Path
from qio import read, ref, verify, new_json, canonical, under, utc
from audit_support import audit_journal, fields_comparison, independent_label, add
from pool_protocol import ARMS, classify_outcome
from budget import numeric_caps, attempt_caps
from task_profiles import initialization_caps
from audit_indices import verify_member, validate_aggregate_index


class ValidationFault(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ValidationFault(message)


def failure_signature(error):
    if not error:
        return None
    # Paths, varying steps and tensor values never split one technical category.
    fields = {k:error.get(k) for k in ('type','stage','category')}
    frames = error.get('traceback')
    fields['message_class'] = str(error.get('message',error.get('error',''))).split(':',1)[0][:160]
    return hashlib.sha256(canonical(fields)).hexdigest()


def check_branch(parent, branch, *, synthetic=False):
    root = Path(parent['paths']['output'])/branch
    cfg = read(parent['config']['path']); source = parent['source']
    ledger = read(root/'RESOURCE_LEDGER.json')
    require(ledger.get('synthetic') is synthetic, 'mixed production/synthetic ledger')
    caps = attempt_caps(branch,source['task'],source['cut'])
    require(ledger['caps']==caps,'per-attempt cap drift')
    journals = [audit_journal(root/'numeric_events.jsonl','numeric',numeric_caps(branch,source['cut'])),
        audit_journal(root/'initialization_events.jsonl','initialization',initialization_caps(source['task'],source['cut'])),
        audit_journal(root/'graphics_events.jsonl','graphics',cfg['native']['graphics_caps'])]
    entered = dict.fromkeys(caps,0)
    for j in journals:
        require(j['present'] and j['counts_complete'] and j['within_caps'] and not j['incomplete_ids'],
                'missing, open or corrupt private ledger: '+str(j['path']))
        add(entered,j['entered'])
    require(entered==ledger['total_entered'],'saved/independent private resource sum differs')
    require(all(entered[k]<=caps[k] for k in caps),'attempt cap exceeded')
    require(not ledger['cleanup'],'cleanup error is a node fault')
    primary=ledger['primary']
    if primary and primary.get('failure_scope')=='wave':
        raise ValidationFault('systemic child fault: '+str(primary.get('stage')))
    result=read(root/'BRANCH_RESULT.json') if (root/'BRANCH_RESULT.json').exists() else None
    closure=None;side=None
    if primary is None:
        require(ledger['status']=='complete' and result is not None,'successful branch evidence absent')
        require(not any(j['failed'] for j in journals),'failed event in successful attempt')
        require(result['synthetic'] is synthetic and result['role']==branch,'branch identity drift')
        require(type(result['controls']) is int and 0<=result['controls']<=300,'absolute terminal range')
        expected=classify_outcome(result['controls'],result['outcome']['success']==1,result['terminated'],result['truncated'])
        require(expected==result['outcome'] and expected['outcome_complete'],'illegal terminal classification')
        require(result['full_target_is_parent_absolute'] is True,'relative rather than absolute s300')
        if result['outcome']['success']==1:
            require(result['first_success_step']==result['controls'],'first success/end mismatch')
        public=read(root/'EPISODE_PUBLIC_V1.json')
        require(public['synthetic'] is synthetic and public['split']==source['split'] and public['environment']['task']==source['task'], 'public split/task identity')
        require(public['source']['source_id']==source['source_id'],'source identity')
        require(read(root/'NVML_IDENTITY.json')['target']==parent['device'],'saved actual physical GPU identity')
        require(public['identity']['config_sha256']==parent['config']['sha256'],'exact per-parent config identity')
        require(public['identity']['model_sha256']==cfg['model_sha256'],'policy identity')
        require(public['cost_event_refs']==[],'private costs must not be public UUID events')
        if branch=='normal' or result['legal_cut_reached']:
            side=read(root/'SIDECAR_V1.json');verify_member(side)
            require(side['identity']['source_signature']==cfg['source_signature'] and side['identity']['split']==source['split'],'sidecar source/split')
            if branch!='normal':
                anchor=read(Path(parent['paths']['output'])/'normal/CUT_REFERENCE.json')
                closure=fields_comparison(anchor['state'],read(root/'CUT_STATE.json'))
                v=read(root/'STATE_VERIFICATION.json')
                require(closure['exact_equal'] is True and v['level']=='full_state_verified' and v['physical_equality_proven'] is None,'frozen closure qualification failed')
        iv=result['intervention_evidence']
        if branch=='normal' or branch.startswith('G0_old'):
            require(iv['plan_replaced'] is False and public['intervened'] is False,'old/normal mislabeled intervention')
        if iv['commitment_entered']:
            require(iv['online_G0_triggered'] is False,'collection forced cut is not a G0 alarm')
    return dict(branch=branch,entered=entered,private_scopes=journals,result=result,
                closure=closure,sidecar_ref=ref(root/'SIDECAR_V1.json') if side else None,
                technical_failure_signature=failure_signature(primary),primary=primary)


def validate_parent(parent, *, synthetic=False):
    out=Path(parent['paths']['output']);reserved=out/'reserved'
    require(read(reserved/'PROCESS_GROUP_EXIT.json')['status']=='all_formal_group_members_exited','missing parent exit barrier')
    coverage=read(reserved/'ATTEMPT_COVERAGE.json')['planned']
    require([r['role'] for r in coverage]==[x[0] for x in ARMS],'coverage branch order')
    indices=[i for i,r in enumerate(coverage) if r['started']]
    require(indices==list(range(len(indices))) and indices,'non-prefix or empty started branches')
    entries=[];total=dict.fromkeys(parent['resource_caps'],0)
    # One pre-child fixed identity query is charged to this parent's 16-query cap.
    total['native_nvml_identity_queries']=1
    for i in indices:
        branch=ARMS[i][0]
        exit_row=read(reserved/(branch+'_EXIT.json'))
        require(exit_row['cleanup_complete'] is True and exit_row['remaining_group']==[],'branch descendants not exited')
        item=check_branch(parent,branch,synthetic=synthetic);entries.append(item);add(total,item['entered'])
        require((exit_row['returncode']==0)==(item['primary'] is None),'exit/ledger classification mismatch')
    require(all(total[k]<=parent['resource_caps'][k] for k in total),'parent cap exceeded')
    labels_doc=read(reserved/'PAIRED_LABELS.json')
    recomputed={}
    for key,arms,kind in [('gain_local_plus',['local_plus','a0'],'gain'),('gain_local_minus',['local_minus','a0'],'gain'),
                          ('pair',['local_plus','local_minus'],'pair'),('G0',['old','fresh0','fresh1','fresh2'],'G0')]:
        rows=[r for r in labels_doc['records'] if r['target']==('G0_C5' if kind=='G0' else 'Q_C10')]
        recomputed[key]=independent_label(rows,arms,kind)
        require(recomputed[key]==labels_doc['labels'][key],'independent pair label differs: '+key)
        index=reserved/('AGGREGATE_INDEX_'+key+'.json')
        if index.exists():validate_aggregate_index(read(index))
    cost=read(reserved/'PRIVATE_COST_INDEX.json')
    require(cost['public_UUID_bridge'] is False and cost['public_cost_event_refs']==[],'private cost namespace')
    for row in cost['attempts']:
        for reference in row['files']:verify(reference)
    primary=next((r['primary'] for r in entries if r['primary']),None)
    normal=entries[0]['result'];eligible=sum(x['target_mask'] for x in recomputed.values())
    disposition=('technical_failure_not_negative_sample' if primary else 'normal_only_before_cut' if normal and not normal['legal_cut_reached'] else
                 'paired_full_targets' if eligible==4 else 'paired_partial_targets')
    return dict(source_key=parent['source_key'],parent_key=parent['parent_key'],source=parent['source'],
                device=parent['device'],started_attempts=len(entries),entered=total,branches=entries,
                independently_recomputed_labels=recomputed,target_count=eligible,disposition=disposition,
                technical_failure_signature=failure_signature(primary),physical_equality_proven=None)


def artifact_manifest(root, output, *, file_cap=550000, byte_cap=256*1024**2):
    """Streams this new job's files only; never hashes input models/old inventory."""
    root=Path(root);count=0;written=0;logical=0;unique=0;seen=set()
    with Path(output).open('xb') as stream:
        for directory,dirs,files in os.walk(root,followlinks=False):
            dirs.sort();files.sort()
            for name in files:
                path=Path(directory)/name
                if path==output:continue
                under(path,root);st=path.stat();count+=1
                if count>file_cap:raise ValidationFault('job evidence file cap')
                row=ref(path);raw=canonical(row);written+=len(raw)
                if written>byte_cap:raise ValidationFault('job manifest byte cap')
                stream.write(raw);logical+=st.st_size
                inode=(st.st_dev,st.st_ino)
                if inode not in seen:seen.add(inode);unique+=st.st_size
        stream.flush();os.fsync(stream.fileno())
    return dict(manifest=ref(output),files=count,logical_bytes=logical,unique_inode_bytes=unique,
                strict_actual_backend_IO_bytes=None,project_quota=None)


def validate_batch(proposal, wave, *, synthetic=False):
    require(wave['cleanup']['status']=='all_formal_group_members_exited','whole group exit not proven')
    require(not wave['publication_failures'],'publication failed')
    require(wave['primary'] is None,'scheduler/system fault cannot continue')
    parents=[];total=dict.fromkeys(proposal['resource_caps'],0)
    for p in proposal['parents']:
        require(Path(p['paths']['output']).exists(),'unstarted source consumed; explicit reconciliation required')
        r=validate_parent(p,synthetic=synthetic);parents.append(r);add(total,r['entered'])
    require(all(total[k]<=proposal['resource_caps'][k] for k in total),'aggregate cap exceeded')
    return dict(schema='queue_machine_validation_v1',created_utc=utc(),synthetic=synthetic,
                status='machine_validated',analysis_scientific_acceptance=False,job_id=proposal['job_id'],
                source_dispositions={p['source_key']:p['disposition'] for p in parents},parents=parents,
                entered=total,resource_caps=proposal['resource_caps'],process_exit_proven=True,publication_complete=True,
                restoration='deferred_to_queue',physical_equality_proven=None,public_UUID_bridge=False)
