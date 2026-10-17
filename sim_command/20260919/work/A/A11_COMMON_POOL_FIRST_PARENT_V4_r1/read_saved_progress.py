"""Read only this run's saved files; no hardware/process/holder probe."""
from pathlib import Path
import datetime
import json

B = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
W = B / 'work/A/A11_COMMON_POOL_FIRST_PARENT_V4_r1'
r = json.loads((B / 'releases/P11_A_COMMON_POOL_FIRST_PARENT_V4.json').read_text())
out = Path(r['paths']['output'])
result = dict(time_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              command_record_present=Path(r['paths']['command_record']).exists(),
              claim_present=Path(r['paths']['claim']).exists(), branches=[])
if out.exists():
    result['lifecycle_requested'] = (out / 'launcher/LIFECYCLE_REQUESTED.json').exists()
    for d in sorted(out.iterdir()):
        if not d.is_dir() or d.name in ('launcher', 'reserved'):
            continue
        row = dict(branch=d.name)
        p = d / 'numeric_events.jsonl'
        if p.exists():
            counts, last = {}, None
            for line in p.read_text().splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue  # Progress only; final audit must reject incomplete records.
                if event.get('phase') == 'entered':
                    last = event['name']
                    for k, v in event['units'].items():
                        counts[k] = counts.get(k, 0) + v
            row['entered_progress_only'] = {k: counts.get(k, 0) for k in (
                'model_initializations', 'language_embedding_forwards', 'vla_sampling_calls',
                'flow_forward_calls', 'env_steps', 'observation_calls', 'full_state_captures',
                'full_state_comparisons', 'completed_rollouts')}
            row['last_numeric_entry'] = last
        for name in ('BRANCH_RESULT.json', 'FAILURE.json'):
            p = d / name
            if p.exists():
                saved = json.loads(p.read_text())
                row[name] = {k: saved[k] for k in ('status', 'controls', 'legal_cut_reached', 'restore_level', 'outcome', 'intervention_evidence', 'type', 'stage', 'message') if k in saved}
        result['branches'].append(row)
    complete = [x for x in result['branches'] if x.get('BRANCH_RESULT.json', {}).get('status') == 'complete']
    result['completed_branch_count'] = len(complete)
    result['completed_branches'] = [x['branch'] for x in complete]
    result['branches'] = [x for x in result['branches'] if x not in complete]
    for rel in ('reserved/WAVE_EXIT.json', 'launcher/LAUNCH_RESULT.json'):
        p = out / rel
        if p.exists():
            result[rel] = json.loads(p.read_text())
for name in ('command.stdout', 'command.stderr'):
    p = W / name
    if p.exists() and p.stat().st_size:
        result[name] = p.read_text(errors='replace')[-2000:]
print(json.dumps(result, ensure_ascii=False))
