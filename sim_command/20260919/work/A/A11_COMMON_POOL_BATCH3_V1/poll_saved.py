"""Read only this wave's saved metadata. No hardware/process/holder queries."""
from pathlib import Path
import datetime,json,re
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
W=B/'work/A/A11_COMMON_POOL_BATCH3_V1'
release=json.loads((W/'authorization/P11_A_COMMON_POOL_BATCH3_V1.json').read_text())
root=Path(release['paths']['output'])
def read(path):return json.loads(path.read_text())
def tail(path,limit=12000):
    if not path.exists():return []
    with path.open('rb') as f:f.seek(max(0,path.stat().st_size-limit));raw=f.read()
    result=[]
    for line in raw.splitlines():
        try:result.append(json.loads(line))
        except (ValueError,UnicodeError):pass
    return result
parents=[]
for p in release['parents']:
    out=Path(p['paths']['output']);reserved=out/'reserved'
    if not reserved.exists():continue
    started=[];exited=[];active=[]
    for start in sorted(reserved.glob('*_START.json')):
        name=start.name.removesuffix('_START.json');started.append(name);exit_path=reserved/(name+'_EXIT.json')
        if exit_path.exists():
            x=read(exit_path);v=x.get('result') or {}
            exited.append(dict(branch=name,returncode=x['returncode'],failure_scope=x['failure_scope'],
                controls=v.get('controls'),outcome=v.get('outcome'),cut=v.get('legal_cut_reached')))
        else:
            numeric=tail(out/name/'numeric_events.jsonl');events=tail(out/name/'events.jsonl')
            ns=[x for x in numeric if x.get('phase')=='entered']
            stepfiles=[int(f.stem.removeprefix('step')) for f in (out/name/'observations').glob('step*.json') if re.fullmatch(r'step\d+',f.stem)]
            failure=read(out/name/'FAILURE.json') if (out/name/'FAILURE.json').exists() else None
            active.append(dict(branch=name,last_numeric_entered=ns[-1].get('name') if ns else None,
                last_saved_observation=max(stepfiles) if stepfiles else None,last_event=events[-1] if events else None,
                failure=failure))
    parents.append(dict(parent_key=p['parent_key'],started=started,exited=exited,active=active))
aux_path=W/'OCCUPANCY_OVERRIDE/STATUS.json'
aux=read(aux_path) if aux_path.exists() else None
aux_exit_path=W/'OCCUPANCY_OVERRIDE/SUPERVISOR_EXIT.json'
aux_exit=read(aux_exit_path) if aux_exit_path.exists() else None
value=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='saved metadata only; no new runtime probe',
    occupancy_override_status=aux,occupancy_override_exit=aux_exit,parents=parents,launch_result_present=(root/'launcher/LAUNCH_RESULT.json').exists(),
    wave_exit_present=(root/'reserved/WAVE_EXIT.json').exists(),outer_result_present=(B/'results/A/A11_COMMON_POOL_BATCH3_V1/OUTER_EXIT.json').exists())
with (W/'SAVED_PROGRESS.jsonl').open('a') as f:f.write(json.dumps(value,ensure_ascii=False)+'\n')
print(json.dumps(dict(at_utc=value['at_utc'],outer_result_present=value['outer_result_present'],aux_holders=sorted((aux or {}).get('holders',{})),aux_updated=(aux or {}).get('at_utc'),aux_exited=aux_exit is not None,
    launch_result_present=value['launch_result_present'],wave_exit_present=value['wave_exit_present'],
    totals=dict(parents_started=len(parents),branches_started=sum(len(p['started']) for p in parents),
        branches_exited=sum(len(p['exited']) for p in parents),nonzero_exits=sum(e['returncode']!=0 for p in parents for e in p['exited'])),
    active=[dict(parent_key=p['parent_key'],branch=a['branch'],phase=a['last_numeric_entered'],last_saved_observation=a['last_saved_observation'],
        failure=(a['failure'] or {}).get('message')) for p in parents for a in p['active']]),ensure_ascii=False))
