"""Targeted metadata and /proc review of the exact27 analysis-listed payloads."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import socket
import stat
from preflight import HERE,CAMPAIGN,read,sha,atomic

def now():return datetime.now(timezone.utc).isoformat()

def main():
    source=CAMPAIGN/'manifests/STORAGE_PAYLOAD_REVIEW_V1.json';review=read(source)
    reference=review['source_receipt'];assert sha(CAMPAIGN/reference['path'])==reference['sha256']
    candidates=review['candidates'];assert len(candidates)==27
    start=now();identities=[];by_path={};by_inode={};parents=set()
    for item in candidates:
        expected=item['identity_from_A'];path=Path(expected['path']);resolved=str(path.resolve());parents.add(item['candidate_parent'])
        assert path.is_relative_to(Path('/mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace'))
        try:
            s=path.stat();observed={'path':str(path),'realpath':resolved,'bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'local_device':s.st_dev,'local_inode':s.st_ino,'is_regular_file':stat.S_ISREG(s.st_mode)}
            matches=resolved==expected['realpath'] and s.st_size==expected['bytes'] and s.st_mtime_ns==expected['mtime_ns'] and stat.S_ISREG(s.st_mode)
            by_path[str(path)]=str(path);by_path[resolved]=str(path);by_inode[(s.st_dev,s.st_ino)]=str(path)
        except OSError as exc:
            observed={'path':str(path),'error':repr(exc)};matches=False
        identities.append({'expected_from_A':expected,'observed_on_B':observed,'path_type_size_mtime_match':matches,'sha256_observed_on_B':None,'sha_note':'A verified SHA retained as provenance; B does not rehash18GB, per targeted task. Device/inode are host-local and not compared across hosts.','current_B_dependency':False,'B_future_use_commitment':'Will not open this candidate for current/planned B tasks; if requirements change, inform analysis before access.'})
    matches=[];gaps=[];vanished=0;inspected=0;tools=[]
    for proc in sorted(Path('/proc').iterdir()):
        if not proc.name.isdigit():continue
        pid=int(proc.name);inspected+=1
        try:
            comm=(proc/'comm').read_text().strip()
            cmd=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
            # Only scoped VLA download/restore signals are reported; never emit full argv/environment.
            candidate_args=[p for p in by_path if p in cmd]
            scoped=('vla-baselines' in cmd or 'smolvla' in cmd or 'xvla' in cmd) and any(x in cmd.lower() for x in ['download','resume','queue','train_metaworld'])
            if candidate_args or scoped:tools.append({'pid':pid,'command_basename':comm,'candidate_path_matches':candidate_args,'possible_scoped_download_or_recovery':scoped,'full_argv_saved':False})
        except FileNotFoundError:vanished+=1;continue
        except PermissionError:gaps.append({'pid':pid,'surface':'comm/cmdline'});comm='unreadable'
        try:
            descriptors=list((proc/'fd').iterdir())
            for fd in descriptors:
                try:
                    target=os.readlink(fd);clean=target.removesuffix(' (deleted)');s=fd.stat()
                    hit=by_path.get(clean) or by_inode.get((s.st_dev,s.st_ino))
                    if hit:
                        flags=None
                        try:
                            for line in (proc/'fdinfo'/fd.name).read_text().splitlines():
                                if line.startswith('flags:'):flags=int(line.split()[1],8)
                        except (OSError,ValueError):pass
                        matches.append({'pid':pid,'command_basename':comm,'surface':'fd','fd':fd.name,'candidate':hit,'access_mode':None if flags is None else {0:'read',1:'write',2:'read_write'}.get(flags&3,'unknown')})
                except FileNotFoundError:pass
                except PermissionError:gaps.append({'pid':pid,'surface':'fd_target'})
        except FileNotFoundError:vanished+=1
        except PermissionError:gaps.append({'pid':pid,'surface':'fd_directory'})
        try:
            for line in (proc/'maps').read_text().splitlines():
                fields=line.split(maxsplit=5)
                if len(fields)<6:continue
                hit=by_path.get(fields[5].removesuffix(' (deleted)'))
                if hit:matches.append({'pid':pid,'command_basename':comm,'surface':'memory_map','candidate':hit,'permissions':fields[1]})
        except FileNotFoundError:vanished+=1
        except PermissionError:gaps.append({'pid':pid,'surface':'maps'})
    # Only executable/config inputs and assigned B task briefs, not old inventories or large data.
    old=CAMPAIGN/'work/B/B10_r1_trial-303225685-trialrun-303225685-worker-0_20260919T150956Z'
    documents=list((old/'configs').glob('*.json'))+list((old/'commands').glob('*'))+[HERE/'config.json',CAMPAIGN/'contracts/INVENTORY_DECISIONS_V1.md']
    board=read(CAMPAIGN/'TASK_BOARD.json')
    documents+=[CAMPAIGN/t['brief'] for t in board['tasks'] if t['owner']=='B' and t.get('brief')]
    references=[]
    for doc in sorted(set(documents)):
        if not doc.is_file():continue
        content=doc.read_text();hits=sorted(p for p in by_path if p in content)
        parent_hits=sorted(p for p in parents if p in content)
        if hits or parent_hits:references.append({'path':str(doc),'candidate_files':hits,'candidate_parents':parent_hits})
    for entry in identities:
        path=Path(entry['observed_on_B']['path'])
        try:
            after=path.stat();before=entry['observed_on_B'];entry['unchanged_during_review']=after.st_size==before.get('bytes') and after.st_mtime_ns==before.get('mtime_ns')
        except OSError:entry['unchanged_during_review']=False
    evidence={'started_at_utc':start,'finished_at_utc':now(),'hostname':socket.gethostname(),'visible_processes_inspected':inspected,'pid_race_or_exit_observations':vanished,'permission_gaps':gaps,'candidate_open_or_map_matches':matches,'scoped_download_or_recovery_signals':tools,'B_executable_config_and_task_documents_checked':len(set(documents)),'candidate_dependencies_found_in_scoped_documents':references,'scope':'Current local /proc namespace only, one-time observation; no claim of cross-node lock or future absence. Only27 candidate targets tested; no unrelated file contents/argv/environ emitted.'}
    atomic(HERE/'evidence/STORAGE_LOCAL_PROCESS_CHECK.json',evidence)
    result={'campaign_id':'corrector-sim-20260919','supplement':'STORAGE_DEPENDENCY_REVIEW_V1','role':'B','hostname':socket.gethostname(),'status':'complete_targeted_B_review','started_at_utc':start,'finished_at_utc':now(),'source_manifest':{'path':str(source),'sha256':sha(source)},'candidate_file_count':27,'candidate_parent_count':len(parents),'candidate_logical_bytes':sum(x['identity_from_A']['bytes'] for x in candidates),'candidates':identities,'needed_candidate_files':[],'confirmed_not_needed_by_current_or_planned_B_tasks':[x['identity_from_A']['path'] for x in candidates],'local_process_evidence':{'path':str(HERE/'evidence/STORAGE_LOCAL_PROCESS_CHECK.json'),'sha256':sha(HERE/'evidence/STORAGE_LOCAL_PROCESS_CHECK.json')},'local_open_or_map_match_count':len(matches),'local_permission_gap_count':len(gaps),'possible_download_or_recovery_signals':tools,'actual_scoped_dependency_references':references,'retained_inputs':['Smol050000 and its required recovery files; E8 no historical checkpoint sweep or old100k continuation','X-VLA completed base and seed42 initialization; no dependency on partial downloader state','All small configs/processors/RNG/logs/lineage and published inventory evidence'],'unknowns':['A and other host/container future access is outside B observation; A must recheck immediately before deletion','A candidate SHA trusted via frozen source manifest; B compared exact path/type/size/mtime and did not rehash payloads'],'recommendation':'No planned B input/selection/recovery dependency on the27 exact payloads. Analysis may decide after considering local observations/gaps; only A executes a separate precise deletion release.','B_future_commitment':'B current and planned tasks will not open these27 candidates. If a later requirement changes, B first reports the exact path to analysis before opening/restarting recovery.','deletion_authorized':False,'deleted_bytes':0,'resource_counts':{'model_gpu_inference_calls':0,'simulator_attempts':0,'optimizer_updates':0,'deletions':0}}
    atomic(HERE/'evidence/STORAGE_DEPENDENCY_REVIEW_V1.json',result)
    print(json.dumps({'metadata_matches':sum(x['path_type_size_mtime_match'] for x in identities),'candidate_count':27,'local_matches':len(matches),'permission_gaps':len(gaps),'signals':len(tools),'dependency_references':len(references),'bytes':result['candidate_logical_bytes']}))

if __name__=='__main__':main()
