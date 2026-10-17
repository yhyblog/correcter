"""Read only saved planned-unit evidence; no model, environment or new rendering."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
units=[json.loads(x) for x in (ROOT/'UNITS.jsonl').read_text().splitlines()]
names={'D24_NEW_TEST_assembly-v3_00','D24_NEW_TEST_bin-picking-v3_00','D24_NEW_TEST_button-press-topdown-v3_00'}
rows=[]
for u in units:
    if u['method']!='Post' or u['mode']!='G0-multi' or u['source_id'] not in names:continue
    ep=ROOT/'episodes'/u['uid_hash'];p=ep/'RESULT.json';old=Path(u['original_source']['result_path']);held=Path(u['prior_result'])
    row=dict(source_id=u['source_id'],unit_id=u['unit_id'],recovery_result=str(p),prior_legitimate_source_reference=str(old),prior_quality_hold_result=str(held),status='pending_planned_unit',scientific_compute=0)
    if p.exists():
        a=json.loads(p.read_text());b=json.loads(old.read_text());c=json.loads(held.read_text())
        if a['status']!='complete':row.update(status=a['status'],failure=a.get('technical_failure'))
        else:
            assert a['env_seed']==b['env_seed']==c['env_seed'] and a['policy_seed']==b['policy_seed']==c['policy_seed']
            def monitor(x,t):return next((e for e in x['events'] if e['step']==t),None)
            gates={str(t):dict(recovery=monitor(a,t)['gate'] if monitor(a,t) else None,prior_reference=monitor(b,t)['gate'] if monitor(b,t) else None,held=monitor(c,t)['gate'] if monitor(c,t) else None) for t in (0,5)}
            aa=np.load(ep/'trajectory.npz');bb=np.load(old.parent/'trajectory.npz')
            noise=lambda x:next(q for q in x['plans'] if q['kind']=='natural')['stats']['noise_sha256']
            row.update(status='saved_planned_terminal',source_identity_matches=True,first_noise_sha_equal=noise(a)==noise(b),pre_Q_first5_action_max_abs=float(np.max(np.abs(aa['actions'][:5]-bb['actions'][:5]))),pre_Q_first5_reward_max_abs=float(np.max(np.abs(aa['rewards'][:5]-bb['rewards'][:5]))),saved_G0=gates,not_method_effect_selection=True)
            row['frame_evidence']=[]
            for t in (0,5):
                meta=json.loads((ep/f'RGB_step{t}.json').read_text());pixels=np.load(ep/f'RGB_step{t}.npy')
                assert hashlib.sha256(pixels.tobytes()).hexdigest()==meta['rgb_sha256'] and meta['unit_id']==u['unit_id']
                row['frame_evidence'].append(dict(step=t,path=str(ep/f'RGB_step{t}.png'),sha256=meta['rgb_sha256'],client_pid=meta['client']['pid'],extra_render_calls=0))
    rows.append(row)
print(json.dumps(dict(scientific_compute=0,source_count=len(rows),rows=rows,scope='only three analysis-designated pre-Q path checks from original planned units; no replay or full-state assertion'),indent=2))
