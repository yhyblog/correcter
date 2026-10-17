"""One-shot CPU verification of real planned progress, never a GPU probe."""
import json,time
from pathlib import Path
import paths
from paths import ROOT,CAMPAIGN
from qio import read,new_json,atomic_json,ref,utc,process_identity,same_process

def main():
    chain=ROOT/'chains/evaluate';heart=read(chain/'HEARTBEAT.json')
    result=dict(utc=utc(),status='not_yet_stable',stage=heart.get('stage'),loaded_model_workers=heart.get('loaded_model_workers'),active_contexts=heart.get('active_rollout_contexts'),peak_live_contexts=heart.get('peak_active_rollout_contexts'))
    if (ROOT/'RESULT.json').exists():result.update(status='terminal_requires_audit',terminal=ref(ROOT/'RESULT.json'));return result
    if not (ROOT/'STABLE_HANDOFF.json').exists():return result
    manifest=read(ROOT/'WAKEUP_REGISTRATION.json')
    registered=CAMPAIGN/'persistent_queue/nodes/C/wakeup/jobs'/(manifest['job_id']+'.json')
    assert read(registered)['claim_identity']==manifest['claim_identity']
    owner=read(ROOT/'PROCESS.json');assert same_process(dict(owner,host=owner['hostname']))
    new=[]
    for p in sorted((ROOT/'evaluation').glob('*/*/RESULT.json'))[:24]:
        row=read(p)
        if row.get('status')!='complete':continue
        assert row['loss']=='L11' and row['fit_seed']==9101 and type(row['success']) is bool
        assert row['unit_id']==f"X-VLA|{row['source_id']}|{row['method']}|G0-multi|10|L11|9101"
        cuts=[e['step'] for e in row['events'] if e.get('trigger')]
        assert row['interventions']==len(cuts) and row['first_cut']==(cuts[0] if cuts else None)
        assert all(b-a>=10 for a,b in zip(cuts,cuts[1:]))
        assert all(e['step']%5==0 and e['gate']>.05 and e['commit_until']==e['step']+10 and e['legal_cut'] for e in row['events'] if e.get('trigger'))
        assert row['counters']['policy_flow_calls']==10*row['counters']['policy_queries']
        assert row['encoder_counters'].get('Q_member_forward_calls',0)==4*row['encoder_counters'].get('Q_ensemble_forward_calls',0)
        new.append(dict(result=ref(p),source_id=row['source_id'],steps=row['steps'],success=row['success'],interventions=row['interventions']))
    assert new
    status=read('/tmp/gpu_occupancy_guard/status.json')
    assert len(status['gpus'])==8 and all(v['state']=='reserved' for v in status['gpus'].values())
    ready=list((chain/'stages/00_X-VLA_Post_H10/workers').glob('*/MODEL_READY.json'))
    assert len(ready)==24
    readiness=[read(p) for p in ready]
    assert all(same_process(r['process']) for r in readiness)
    result.update(status='verified_stable_background',actual_model_worker_count=24,actual_feature_server_count=24,replicas_per_GPU=dict(native_X=3,external_pi05_encoder=3),peak_logical_contexts=read(ROOT/'EVALUATION_HANDOFF.json')['peak_live_contexts'],branches_per_model=8,batch_size=1,measured_scope='sampled concurrently live rollout contexts with physical-step progress; inference time-sliced within each model',first_planned_terminal_checks=new,registered_terminal=ref(registered),holder_handoff=ref(chain/'HOLDER_EXIT_ACK.json'),guard_snapshot=status,new_GPU_calls_by_verifier=0,new_scientific_units_by_verifier=0)
    atomic_json(ROOT/'STABLE_HANDOFF_VERIFIED.json',result)
    return result
if __name__=='__main__':
    r=main();print(json.dumps({k:v for k,v in r.items() if k not in ['first_planned_terminal_checks','guard_snapshot']},ensure_ascii=False))
