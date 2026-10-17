"""Read final source indexes only; do not load historical experiment trees."""
import csv,collections
from paths import ROOT,CAMPAIGN
from qio import read,new_json,ref,utc

def main():
    n=CAMPAIGN/'work/B/B_D24_E8_POST_V1_r1/VALID_N_INDEX.json'
    rr=CAMPAIGN/'results/C/C_D24_XVLA_MULTI_EVAL_V1/FINAL_EPISODES.csv'
    pv=CAMPAIGN/'deadline_20260924/L11_FINAL_ROLLUP_20260923/FINAL_EPISODES.csv'
    rows=[]
    for r in read(n)['xvla']:
        assert r['K']==10 and r['H']==30 and r['status']=='complete' and type(r['success']) is bool
        rows.append(dict(model='X-VLA',method='N',H=10,source_id=r['source_id'],success=r['success'],status='complete',sampling_calls=r['queries'],flow_calls=r['queries']*10,interventions=0,first_cut=None,elapsed_seconds=r['elapsed_seconds'],source_table=str(n),result_path=r['origin_rows'],reused_H10=True))
    for r in csv.DictReader(rr.open()):
        if r['method']!='R':continue
        assert r['status']=='complete' and r['success'] in ('True','False')
        rows.append(dict(model='X-VLA',method='R',H=10,source_id=r['source_id'],success=r['success']=='True',status='complete',sampling_calls=int(r['policy_queries']),flow_calls=int(r['flow_calls']),interventions=int(r['interventions']),first_cut=r['first_cut'] or None,elapsed_seconds=float(r['elapsed_seconds']),source_table=str(rr),result_path=r['result_path'],reused_H10=True))
    for r in csv.DictReader(pv.open()):
        if r['model']!='X-VLA' or r['H']!='10':continue
        assert r['loss']=='L11' and r['fit_seed']=='9101' and r['success'] in ('True','False')
        rows.append(dict(model='X-VLA',method=r['method'],H=10,source_id=r['source_id'],success=r['success']=='True',status='complete',sampling_calls=int(float(r['sampling_calls'])) if r['sampling_calls'] else None,flow_calls=int(float(r['flow_calls'])) if r['flow_calls'] else None,interventions=int(float(r['interventions'])) if r['interventions'] else None,elapsed_seconds=float(r['elapsed_seconds']),source_table=str(pv),result_path=r['result_path'],loss='L11',fit_seed=9101,reused_H10=True))
    assert len(rows)==2000 and len({(r['method'],r['source_id']) for r in rows})==2000
    for m,s in [('N',403),('R',412),('Post',411),('Velocity',407)]:
        rs=[r for r in rows if r['method']==m];assert len(rs)==500 and sum(r['success'] for r in rs)==s
    new_json(ROOT/'REUSED_H10.json',dict(utc=utc(),rows=rows,source_references=[ref(p) for p in (n,rr,pv)],new_GPU_calls=0,replay_count=0))
    print('H10 reused: 2000 valid, N403 R412 Post411 Velocity407; zero new attempts')
if __name__=='__main__':main()
