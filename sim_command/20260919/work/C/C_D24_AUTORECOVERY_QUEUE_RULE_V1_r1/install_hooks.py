"""Install only future subprocess entry hooks; never reload a healthy queue."""
import ast,json,sys
from pathlib import Path
from c_recovery_policy import ROOT,C,X,P,consume,live_identity
from ops_io import read,ref,new_json,utc
W=Path(__file__).resolve().parent

def patch(root,name,changes):
    p=root/'code'/name;s=p.read_text();old=s
    for needle,replacement in changes:
        if s.count(needle)!=1:raise ValueError('Unexpected future interface: '+str(p)+' / '+needle[:80])
        s=s.replace(needle,replacement)
    ast.parse(s,filename=str(p));backup=W/'backups'/root.name/name;backup.parent.mkdir(parents=True,exist_ok=True);backup.write_text(old);p.write_text(s)
    return dict(before=ref(backup),after=ref(p))

def main():
    rows=[]
    for root in [X,P]:
        owner=read(root/'PROCESS.json');heart=read(root/'HEARTBEAT.json')
        if not live_identity(owner) or heart['status'] not in ['selection_dependency','dependency_wait'] or (root/'chains/evaluate').exists():raise RuntimeError('Future evaluation already entered; do not alter live stage')
    wrapper=f'''"""C CPU operational rules; GPU/scientific ownership stays in original task."""
import sys
from pathlib import Path
sys.path.insert(0,{str(W)!r})
from c_recovery_policy import consume,record_fault,legal_terminal,prepare_resume,repair_gate
from ops_io import read
def reject_completed_terminal(path):
    p=Path(path)
    if p.is_file() and legal_terminal(read(p)):
        raise RuntimeError('Existing legal scientific terminal, including success=false, must not replay')
'''
    for root in [X,P]:
        p=root/'code/operational_hook.py';p.write_text(wrapper);rows.append(dict(new_hook=ref(p)))
        consume(root,'queue_prepare')
    rows.append(patch(X,'manager.py',[
        ('from process_family import drain_group\n','from process_family import drain_group\nfrom operational_hook import consume,record_fault\n'),
        ('    selected=consumed_selection()\n',"    consume(ROOT,'evaluation_entry')\n    selected=consumed_selection()\n"),
        ('    except BaseException as exc:fatal=dict(error=repr(exc),traceback=traceback.format_exc())',"    except BaseException as exc:\n        fatal=dict(error=repr(exc),traceback=traceback.format_exc())\n        record_fault(ROOT,fatal,unit='evaluation_stage',evidence=[str(chain/'MANAGER_STARTED.json')],continuable=['independent pi05 after reliable native family exit'])")]))
    rows.append(patch(X,'common.py',[
        ('from admission import boundary,AdmissionStop\n','from admission import boundary,AdmissionStop\nfrom operational_hook import reject_completed_terminal\n'),
        ('    boundary(admission=True);LOCAL.mkdir(exist_ok=True)\n',"    boundary(admission=True);LOCAL.mkdir(exist_ok=True)\n    if extra.get('phase')=='evaluate':reject_completed_terminal(ROOT/'evaluation'/identity/'RESULT.json')\n")]))
    rows.append(patch(P,'manager.py',[
        ('from process_family import drain_group\n','from process_family import drain_group\nfrom operational_hook import consume,record_fault\n'),
        ("    authority();own=process_identity();fds=held_reservation_fds()", "    authority();consume(ROOT,'evaluation_entry');own=process_identity();fds=held_reservation_fds()"),
        ("    except BaseException as exc:fatal=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())", "    except BaseException as exc:\n        fatal=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())\n        record_fault(ROOT,fatal,unit='evaluation_stage',evidence=[str(chain/'MANAGER_STARTED.json')],continuable=['next independent eligible C task'])")]))
    rows.append(patch(P,'admission.py',[
        ('from process_family import group_members\n','from process_family import group_members\nfrom operational_hook import reject_completed_terminal\n'),
        ("    uid=unit_id(source,job)\n", "    uid=unit_id(source,job)\n    reject_completed_terminal(ROOT/'runs'/job['job_id']/'episodes'/source['source_id']/'RESULT.json')\n")]))
    new_json(ROOT/'HOOK_DEPLOYMENT.json',dict(utc=utc(),status='CPU_policy_consumed_by_queue_preparation_and_installed_at_future_evaluation_entries',entries=rows,live_queue_processes_restarted=0,live_queue_service_files_changed=False,scientific_config_and_claims_changed=False,new_GPU_calls=0,actual_future_manager_consumption=False,reason='both unique parent queues still wait for selection; fresh evaluation subprocesses import hooks on normal launch'))
    print('INSTALLED_FUTURE_CPU_HOOKS',len(rows))

if __name__=='__main__':main()
