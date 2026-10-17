"""Valid Post lock -> native X's existing metadata inlet, preserving live PID."""
import os,time,uuid
from pathlib import Path
from c_recovery_policy import C,ROOT,X,P,POST_SHA,AUTH,authority,snapshot,live_identity
from ops_io import read,new_json,atomic_json,utc,ref,sha,verify,canonical
from post_choice_validator import validate_selection
from legacy_selection_snapshot import validate_selection as legacy_validator
A=C/'results/A/A_D24_FULL_Q_LOSS_SELECTION_V1'

def locked_post_choice():
    selection=A/'SELECTION.json';lock_path=A/'SELECTION_LOCK.json'
    if not selection.is_file() or not lock_path.is_file():return None
    row=read(selection);lock=read(lock_path);sref=ref(selection)
    if lock.get('immutable') is not True or lock['selection']['sha256']!=sref['sha256'] or Path(lock['selection']['path'])!=selection:raise ValueError('Post selection lock mismatch')
    chosen=validate_selection(row)
    return dict(chosen_loss=chosen,row=row,selection_ref=sref,lock_ref=ref(lock_path))

def create_record(target,row):
    """Atomic visible no-replace publication; never overwrites either consumer."""
    target=Path(target);tmp=target.with_name('.'+target.name+'.CPU_post_'+uuid.uuid4().hex)
    new_json(tmp,row)
    try:
        try:os.link(tmp,target)
        except OSError as exc:
            if isinstance(exc,FileExistsError):return False
            if exc.errno not in [1,18,38,95]:raise
            with target.open('xb') as out:
                out.write(canonical(row));out.flush();os.fsync(out.fileno())
        return True
    finally:tmp.unlink(missing_ok=True)

def maybe_adapt_native():
    choice=locked_post_choice()
    if choice is None:return dict(status='awaiting_A_Post_only_lock',metadata_adaptations=0)
    target=X/'SELECTION_CONSUMED.json'
    if target.exists():
        old=read(target)
        if old['chosen_loss']!=choice['chosen_loss'] or old['A_selection']['sha256']!=choice['selection_ref']['sha256']:raise ValueError('native consumed selection conflicts with current Post lock; preserve original, no overwrite')
        verify(old['own_ranking'],base=C)
        return dict(status='existing_native_selection_valid',record=str(target),metadata_adaptations=0)
    try:
        legacy_validator(choice['row'])
        # If the live validator accepts this exact choice, let its sole writer act.
        return dict(status='native_legacy_validator_accepts_same_Post_choice',metadata_adaptations=0)
    except (ValueError,KeyError,TypeError) as error:legacy_error=repr(error)
    authority();owner=read(X/'PROCESS.json');heart=read(X/'HEARTBEAT.json')
    if not live_identity(owner) or heart['status']!='selection_dependency':return dict(status='native_not_in_idle_dependency_phase',metadata_adaptations=0)
    deadline=read(X/'STAGE_DEADLINE.json')
    if time.time()>=deadline['deadline_unix']:return dict(status='original_native_wait_deadline_expired_not_extended',metadata_adaptations=0)
    if (X/'chains/evaluate').exists() or (X/'ATTEMPT_COUNTER.json').exists():raise ValueError('native scientific phase already entered; metadata repair forbidden')
    candidate=read(X/'CANDIDATES_READY.json');own=candidate['ensembles'][choice['chosen_loss']]
    if candidate['status']!='CANDIDATES_READY' or candidate['fits']!=16 or candidate['actual_optimizer_updates']!=64000:raise ValueError('native completed candidate evidence mismatch')
    if Path(own['assets'])!=X/'ensembles'/f"{choice['chosen_loss']}_s9101" or own['loss']!=choice['chosen_loss'] or own['fit_seed']!=9101 or len(own['members'])!=4 or {m['member'] for m in own['members']}!={1041,1042,1043,1044}:raise ValueError('own X ensemble mismatch')
    verify(own['ranking'],base=C);ranking=read(own['ranking']['path'])
    if ranking['model_hashes']!={str(m['member']):m['sha256'] for m in own['members']}:raise ValueError('X member/ranking mismatch')
    row=dict(task_id=X.name,utc=utc(),chosen_loss=choice['chosen_loss'],fixed_fit_seed=9101,A_selection=choice['selection_ref'],A_lock=choice['lock_ref'],own_assets=own['assets'],own_members=own['members'],own_ranking=own['ranking'],A_pi05_weights_loaded=False,local_test_used=False,selection_immutable=True,Post_selection_override=ref(C/'deadline_20260924/POST_LED_SELECTION_OVERRIDE_V1.json'),CPU_compatibility_authorization=ref(AUTH),native_waiter_preserved=owner)
    # The copied legacy code deterministically rejects this row, so it cannot race
    # us to a different legitimate consumption. Recheck immutable inputs at commit.
    verify(choice['selection_ref'],base=C);verify(choice['lock_ref'],base=C)
    installed=create_record(target,row)
    actual=read(target)
    if actual['chosen_loss']!=row['chosen_loss'] or actual['A_selection']!=row['A_selection'] or actual['own_assets']!=row['own_assets']:raise ValueError('native consumption concurrent identity mismatch')
    proof=dict(utc=utc(),status='adapted_native_metadata_without_restart',installed=installed,old_validator_error=legacy_error,actual_prior_rejection=snapshot(X/'SELECTION_REJECTED.json') or None,Post_only_selection=choice['selection_ref'],candidate=ref(X/'CANDIDATES_READY.json'),consumed=ref(target),original_waiter=owner,original_claim=ref(X/'CLAIM.json'),original_deadline=deadline,training_updates_repeated=0,new_science_or_GPU_calls=0,actual_fault_recovery_tested=False,scope='scientific selection publication compatibility; no worker restart')
    atomic_json(ROOT/'NATIVE_SELECTION_COMPAT_APPLIED.json',proof)
    return dict(status=proof['status'],metadata_adaptations=int(installed),record=str(target))
