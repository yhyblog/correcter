"""Prepare a fresh, bounded recovery without modifying prior claims/results."""
import collections
import datetime
import hashlib
import json
import shutil
from pathlib import Path

C = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
P = C/'results/B/B_D24_POST_TRIGGER_MODES_V1'
R = P/'recovery_r2'
N = P/'recovery_r3'

def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x') as f: json.dump(value, f, ensure_ascii=False, indent=2); f.write('\n')

assert not N.exists(), 'fresh recovery only'
history = [P, R]
lineage = collections.defaultdict(list)
physical = 0
for origin in history:
    terminal = read(origin/'RESULT.json')
    assert terminal['all_owned_descendants_exited'] and terminal['publication_completed']
    for entered in sorted((origin/'runs').glob('*/episodes/*/ENTERED.json')):
        physical += 1
        result = entered.with_name('RESULT.json')
        assert result.exists(), ('unknown execution; cannot automatically replay', entered)
        row = read(result)
        key = (row['mode'], row['H'], row['source_id'])
        lineage[key].append((row, str(result)))
    for result in (origin/'runs').glob('*/RESULT.json'):
        row = read(result)
        assert not (row.get('exceptions') and not row.get('episodes')), 'account for init failure first'
for key, rows in lineage.items():
    assert len(rows) <= 2 and all(x[0]['status'] != 'complete' for x in rows[:-1]), key
valid = sorted(key for key, rows in lineage.items() if rows[-1][0]['status'] == 'complete')
retry = sorted(key for key, rows in lineage.items() if rows[-1][0]['status'] != 'complete')
assert all(len(lineage[key]) == 1 for key in retry), 'one corrected retry per source only'
assert (physical, len(valid), len(retry)) == (505, 496, 2)

N.mkdir()
shutil.copytree(R/'code', N/'code', ignore=shutil.ignore_patterns('__pycache__'))
(N/'config').mkdir()
for name in ['BASE.json','TEST_SOURCES_V1.json','RANDOM_ONCE_SCHEDULE_V1.json']:
    shutil.copy2(R/'config'/name, N/'config'/name)
for name in ['claims','failures','outbox','deployments','evidence','jobs','cell_publications']:
    (N/name).mkdir()

cfg = read(R/'config/CONFIG.json')
cfg.update(recovery_revision=3, history_roots=list(map(str,history)), prior_stage_attempts=physical,
           valid_retained=len(valid), corrected_retries=len(retry), remaining_physical_entries=5000-len(valid))
write(N/'config/CONFIG.json', cfg)
valid_set, retry_set = set(valid), set(retry)
jobs = {}
for source in sorted((P/'jobs').glob('*.json')):
    job = read(source)
    sources = [s for s in job['sources'] if (job['mode'],job['H'],s['source_id']) not in valid_set]
    if not sources: continue
    retry_ids = [s['source_id'] for s in sources if (job['mode'],job['H'],s['source_id']) in retry_set]
    job.update(sources=sources,retry=int(bool(retry_ids)),retry_source_ids=retry_ids,
               configuration_sha256=sha(N/'config/CONFIG.json'))
    write(N/'jobs'/source.name, job)
    jobs[job['job_id']] = dict(sources=sources,retry_source_ids=retry_ids,prior_job=str(source))
entries = sum(len(j['sources']) for j in jobs.values())
assert entries == 4504 and physical+entries <= cfg['stage_attempt_cap']
plan = dict(revision=3,original_root=str(P),history_roots=list(map(str,history)),
    failure='transient ENOENT during supervisor read of own atomic shared-file heartbeat; orderly shutdown',
    correction='bounded transient JSON read retry; optional progress snapshot read failures are reported without aborting science; authority is always read fresh',
    retained_valid_units=valid,corrected_retry_units=retry,
    corrected_retry_evidence=[dict(unit=key,result=lineage[key][-1][1],fatal=lineage[key][-1][0].get('fatal')) for key in retry],
    prior_physical_attempts=physical,planned_entries=entries,new_unstarted_entries=entries-len(retry),
    new_corrected_retry_entries=len(retry),combined_expected_attempts=physical+entries,
    cumulative_expected_B_attempts=cfg['planned_prior_attempts']+physical+entries,
    original_stage_started_unix=cfg['original_stage_started_unix'],
    absolute_wall_deadline_unix=cfg['absolute_wall_deadline_unix'],jobs=jobs)
write(N/'config/RECOVERY_PLAN.json',plan)

for name in ['service.py','manager.py']:
    p=N/'code'/name
    p.write_text(p.read_text().replace('D24_B_POST_TRIGGER_MODES_r2','D24_B_POST_TRIGGER_MODES_r3'))
p=N/'code/qio.py'; text=p.read_text().replace('import datetime\n','import datetime\nimport errno\n')
text=text.replace('CAMPAIGN = PACKAGE.parents[2]',f'CAMPAIGN = Path({str(C)!r})')
old="""def read(path, maximum=64 * 1024**2):
    p = Path(path)
    if p.stat().st_size > maximum:
        raise ValueError('JSON size limit: ' + str(p))
    return json.loads(p.read_text())
"""
new="""def read(path, maximum=64 * 1024**2, retry_seconds=30.0):
    # One open avoids the stat/open race. No cached contents or permissions.
    p = Path(path)
    deadline = time.monotonic() + retry_seconds
    while True:
        try:
            with p.open('rb') as stream:
                raw = stream.read(maximum + 1)
            if len(raw) > maximum:
                raise ValueError('JSON size limit: ' + str(p))
            return json.loads(raw)
        except (OSError, json.JSONDecodeError) as error:
            if isinstance(error, OSError) and error.errno not in (errno.ENOENT, errno.ESTALE, errno.EIO, errno.EINTR):
                raise
            if time.monotonic() >= deadline:
                raise
            time.sleep(min(.25, max(0, deadline - time.monotonic())))


def optional_snapshot(path):
    # Telemetry is not a scientific stop condition. Never supply stale progress.
    try:
        return read(path, retry_seconds=.75)
    except (OSError, json.JSONDecodeError) as error:
        if isinstance(error, OSError) and error.errno not in (errno.ENOENT, errno.ESTALE, errno.EIO, errno.EINTR):
            raise
        return dict(status='snapshot_temporarily_unavailable', path=str(path),
                    error_type=type(error).__name__, error=str(error), utc=utc())
"""
assert old in text; p.write_text(text.replace(old,new))
p=N/'code/service.py'; text=p.read_text()
text=text.replace('from qio import read,new_json','from qio import optional_snapshot,read,new_json')
text=text.replace("progress=read(chain/'HEARTBEAT.json') if (chain/'HEARTBEAT.json').exists() else None", "progress=optional_snapshot(chain/'HEARTBEAT.json')")
p.write_text(text)
p=N/'code/admission.py'; text=p.read_text()
start=text.index('def read_control(path):'); end=text.index('\ndef authority():',start)
text=text[:start]+"def read_control(path):\n    return read(path, retry_seconds=30.0)\n"+text[end:]
p.write_text(text)
p=N/'code/publish_trigger.py'; text=p.read_text()
text=text.replace("        by={};attempt_rows=[]", "        by={};attempt_rows=[];source_attempts=Counter()")
text=text.replace("                assert str(p).startswith(str(ROOT)+'/runs/'),'invalid recovery ordering'", "                assert source_attempts[sid] == 1, 'more than one corrected retry'\n            source_attempts[sid] += 1")
p.write_text(text)
frozen=read(R/'METHOD_FROZEN.json')
frozen.update(recovery_plan=str(N/'config/RECOVERY_PLAN.json'),prior_attempt_roots=list(map(str,history)),
              run_id='D24_B_POST_TRIGGER_MODES_r3',recovery_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
write(N/'METHOD_FROZEN.json',frozen)
manifest=dict(task_id=cfg['task_id'],files={str(p.relative_to(N)):sha(p) for p in sorted((N/'code').glob('*.py'))},
              configuration_sha256=sha(N/'config/CONFIG.json'))
write(N/'CODE_MANIFEST.json',manifest)
print(json.dumps({k:v for k,v in plan.items() if k not in ['jobs','retained_valid_units']},ensure_ascii=False))
