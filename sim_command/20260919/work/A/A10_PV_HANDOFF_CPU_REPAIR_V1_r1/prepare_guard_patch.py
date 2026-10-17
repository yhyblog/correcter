"""Private source-only guard patch; never imports or executes the guard."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

ROOT=Path('/mnt/bn/arnold-recommend/yaohaoyang')
B=ROOT/'Corrector/sim_command/20260919'
NEW=B/'results/A/A10_PV_HANDOFF_CPU_REPAIR_V1'
WORK=B/'work/A/A10_PV_HANDOFF_CPU_REPAIR_V1_r1'
SHARED=ROOT/'gpu_occupancy_guard.py'
ORIGINAL_SHA='d499982dff72c3b74ddab0e13e359edccb5f282900c534030b3816b58495fcaf'

def put(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:f.write(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')

def write(path,raw):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f:f.write(raw)

def ref(path):
    raw=path.read_bytes()
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),size_bytes=len(raw))

old=SHARED.read_bytes()
assert hashlib.sha256(old).hexdigest()==ORIGINAL_SHA
source=old.decode()
parser='''def handoff_timeout_seconds():
    raw = os.environ.get('CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS', '90')
    if (not raw or not raw.isascii() or not raw.isdecimal()
            or raw.startswith('0') or len(raw) > 3 or not 1 <= int(raw) <= 300):
        raise ValueError('CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS must be an ASCII integer in [1, 300]')
    return int(raw)


'''
needle='def run_formal(command):\n'
assert source.count(needle)==1
source=source.replace(needle,parser+needle)
source=source.replace("    start()\n    with (STATE / 'formal.lock').open('a') as reservation:","    handoff_seconds = handoff_timeout_seconds()  # validate before start/lock/query\n    start()\n    with (STATE / 'formal.lock').open('a') as reservation:")
old_loop='''        deadline = time.monotonic() + 90
        while True:
            apps = query('pid', 'compute-apps')
            if not apps:
                break
            if time.monotonic() > deadline:
                raise RuntimeError('GPUs still occupied; formal command was not launched')
            time.sleep(1)
'''
new_loop='''        handoff_started = time.monotonic()
        deadline = handoff_started + handoff_seconds
        poll_attempts = 0
        last_observation = None
        reason = 'query_error'
        try:
            while True:
                if time.monotonic() >= deadline:
                    reason = 'handoff_deadline'
                    raise RuntimeError('GPU handoff deadline expired; formal command was not launched')
                query_started = time.monotonic()
                poll_attempts += 1
                reason = 'query_error'
                apps = query('pid', 'compute-apps')
                observed = time.monotonic()
                if not isinstance(apps, list):
                    raise RuntimeError('Invalid compute-apps response; formal command was not launched')
                last_observation = dict(query_started_monotonic=query_started,
                    returned_monotonic=observed, rows=apps[:64], total_rows=len(apps),
                    truncated=len(apps) > 64, pid_namespace='NVML host PID rows; not container holder manager PIDs')
                if observed >= deadline:
                    reason = 'handoff_deadline'
                    raise RuntimeError('GPU handoff deadline expired; formal command was not launched')
                if not apps:
                    break
                time.sleep(min(1, deadline - observed))
        except Exception as error:
            log('HANDOFF_FAILURE_JSON ' + json.dumps(dict(timeout_seconds=handoff_seconds,
                elapsed_seconds=time.monotonic() - handoff_started, reason=reason,
                poll_attempts=poll_attempts, last_observation=last_observation,
                error_type=type(error).__name__, error=str(error)[:2048],
                extra_hardware_queries=0, last_observation_is_not_a_new_deadline_probe=True), sort_keys=True))
            raise
'''
assert source.count(old_loop)==1
source=source.replace(old_loop,new_loop)
new=source.encode()
old_tree,new_tree=ast.parse(old),ast.parse(new)
old_functions={n.name:ast.get_source_segment(old.decode(),n) for n in old_tree.body if isinstance(n,ast.FunctionDef)}
new_functions={n.name:ast.get_source_segment(source,n) for n in new_tree.body if isinstance(n,ast.FunctionDef)}
unchanged=[name for name in old_functions if name!='run_formal']
assert all(old_functions[name]==new_functions[name] for name in unchanged)
assert new_functions['run_formal'].split('        proc = subprocess.Popen',1)[1]==old_functions['run_formal'].split('        proc = subprocess.Popen',1)[1]
original=NEW/'guard_patch/gpu_occupancy_guard.original.py'
patched=NEW/'guard_patch/gpu_occupancy_guard.patched.py'
patch=NEW/'guard_patch/gpu_occupancy_guard.patch'
write(original,old);write(patched,new)
write(patch,''.join(difflib.unified_diff(old.decode().splitlines(True),source.splitlines(True),fromfile=str(SHARED),tofile=str(SHARED))).encode())
spec=dict(environment_variable='CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS',required_value='300',timeout_seconds=300,default_seconds=90,minimum_seconds=1,maximum_seconds=300,guard_path=str(SHARED),guard_expected_sha256=ref(patched)['sha256'],guard_expected_size_bytes=len(new),active_guard_required=True,formal_lock_path='/tmp/gpu_occupancy_guard/formal.lock',poll_sleep_seconds_max=1,existing_query_timeout_seconds=15,failure_last_observation_rows_max=64)
put(NEW/'guard_patch/HANDOFF_SPEC.json',spec)
put(NEW/'guard_patch/PATCH_IDENTITY.json',dict(status='prepared_not_installed',unique_shared_target=str(SHARED),original=ref(original),patched=ref(patched),unified_patch=ref(patch),original_shared_sha256=ORIGINAL_SHA,expected_installed_sha256=ref(patched)['sha256'],shared_current_matches_original=True,shared_installations=0,daemon_restarts=0,unchanged_functions=unchanged,post_spawn_signal_wait_and_lock_tail_byte_identical=True,nominal_timeout_rationale='8*(15+5)=160 seconds of serial stop allowance plus 140 seconds polling/scheduling margin; fixed V3 wait300; not an end-to-end hard deadline',deadline_semantics='No child launch at/after the nominal deadline, including an empty response returned late. One already-entered query retains its existing15s subprocess timeout; OS scheduling/lock acquisition/process drain may exceed nominal bounds.',failure_evidence='One bounded JSON stdout record on handoff error, reuses last existing query result; no extra queries; missing observation=null',handoff_spec=ref(NEW/'guard_patch/HANDOFF_SPEC.json')))
put(WORK/'GUARD_PATCH_STATIC_CHECKS.json',dict(status='passed',original_sha256=ORIGINAL_SHA,patched_sha256=ref(patched)['sha256'],AST_parsed=True,unchanged_function_bytes=unchanged,only_changed_existing_function='run_formal',added_functions=['handoff_timeout_seconds'],post_spawn_signal_wait_and_lock_tail_byte_identical=True,daemon_logic_changed=False,live_guard_imported=False,shared_installations=0,daemon_restarts=0,actual_locks_queries_signals=0))
print(json.dumps(dict(status='private_patch_prepared',original_sha256=ORIGINAL_SHA,patched_sha256=ref(patched)['sha256'],patch=ref(patch)),indent=2))
