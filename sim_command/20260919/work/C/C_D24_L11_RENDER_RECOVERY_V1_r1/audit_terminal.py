"""CPU-only audit of referenced terminal records; no experiment/model imports."""
from pathlib import Path
from collections import Counter,defaultdict
import csv,json,sys,hashlib,datetime
C=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
R=C/'results/C/C_D24_L11_RENDER_RECOVERY_V1';OLD=R.parent/'C_D24_L11_RETEST_V1'
EID='C_789594321516138f017292900ce238df';OUT=R/'event_audits'/EID
sys.path.insert(0,str(R/'code'))
from qio import read,new_json,atomic_json,ref,sha,utc
from report import table,counters,result_path
sys.path.insert(0,str(C.parents[2]/'Corrector'))
from experiments.native10_training_20260916.protocol import seed_for

def add(dst,value):
    for k,v in value.items():
        if type(v) in (int,float):dst[k]+=v

def main():
    event=read(C/'persistent_queue/nodes/C/wakeup/outbox'/(EID+'.json'));assert event['job']['task_id']=='C_D24_L11_RENDER_RECOVERY_V1' and not event['synthetic']
    assert sha(event['job']['claim_identity']['path'])==event['job']['claim_identity']['sha256']
    auth=C/'deadline_20260924/L11_RECOVERY_V1/AUTHORIZATION.json';assert sha(auth)=='ca6f92258260815495a016d8c25eb079e9e0949a38a2c5ece6b836c2ef6d0ccc'
    manifest=C/'deadline_20260924/L11_RECOVERY_V1/RECOVERY_UNITS_C.jsonl';assert sha(manifest)=='bf441704d624bd914319ac2d4599ee157c8864e2a6db8556fd06f10c681277bd'
    authorized={u['unit_id']:u for u in map(json.loads,manifest.read_text().splitlines())}
    units={u['unit_id']:u for u in read(R/'UNIT_INDEX.json')};allunits={u['unit_id']:u for u in read(OLD/'UNIT_INDEX.json')}
    protected=read(R/'PROTECTED_VALID_UNITS.json');keep=set(protected['unit_ids'])
    assert sha(protected['source']['path'])==protected['source']['sha256']
    assert len(units)==1764 and set(units)==set(authorized) and len(keep)==736 and not set(units)&keep and set(units)|keep==set(allunits)
    for k,u in authorized.items():assert all(units[k][field]==value for field,value in u.items())
    claims={p.stem:read(p) for p in (R/'claims/units').glob('*.json')};assert len(claims)==1764
    assert {x['unit_id'] for x in claims.values()}==set(units) and sorted(x['stage_ordinal'] for x in claims.values())==list(range(1,1765))
    assert all(x['attempt']==1 and x['authorization_sha256']==sha(auth) for x in claims.values())
    freeze=read(R/'CODE_FROZEN.json');assert all(sha(x['path'])==x['sha256'] for x in freeze['files'])
    oldrows={x['unit_id']:x for x in csv.DictReader((OLD/'task_summary/EPISODES.csv').open())}
    current={x['unit_id']:x for x in csv.DictReader((R/'EPISODES.csv').open())};assert len(current)==2500 and set(current)==set(allunits)
    attempts=list(csv.DictReader((R/'ATTEMPTS_ALL.csv').open()));assert len(attempts)==4514
    attempt_keys=[(x['unit_id'],x['run']) for x in attempts];assert len(set(attempt_keys))==4514
    prior=list(csv.DictReader((OLD/'task_summary/ATTEMPTS_ALL.csv').open()));assert len(prior)==2750
    assert all(all(attempts[i][k]==v for k,v in row.items()) for i,row in enumerate(prior))
    lineage=read(R/'ATTEMPT_LINEAGE.json');assert len(lineage)==1764
    for l in lineage:
        u=units[l['unit_id']];cl=claims[u['storage_key']]
        assert cl['lifetime_attempt']==len(l['prior_attempts'])+1==u['prior_attempt_count']+1
        for old in l['prior_attempts']:assert sha(old['claim']['path'])==old['claim']['sha256'] and Path(old['result_path']).exists()
    count=read(R/'ATTEMPT_COUNTER.json');assert count['count']==1764 and count['cumulative_C_reserved']==17693+1764==19457
    assert count['count']<=2000 and count['cumulative_C_reserved']<=20750
    cells=defaultdict(Counter);newcells=defaultdict(Counter);cost_rows=[];normalized_zero=[];source_rows=[];numeric_pi=defaultdict(Counter)
    cut_count=0;cut_short=0;pairs=defaultdict(Counter);q_gradient=0
    for uid,orig in allunits.items():
        u=units.get(uid,orig);is_new=uid in units;p=result_path(u) if is_new else Path(oldrows[uid]['result_path']);row=read(p)
        assert row['unit_id']==uid and row['status']=='complete' and type(row['success']) is bool
        assert row['source_id']==u['source_id'] and row['policy_seed']==u['policy_seed'] and row.get('env_seed',row.get('reset_seed'))==u['env_seed']
        assert row['mode']=='G0-multi' and row.get('loss',row.get('Q_loss'))=='L11' and row.get('fit_seed',row.get('Q_fit_seed'))==9101
        assert current[uid]['result_path']==str(p) and current[uid]['disposition']=='valid' and (current[uid]['success']=='True')==row['success']
        if is_new:assert row['claim']==claims[u['storage_key']]
        else:assert not (R/'claims/units'/(u['storage_key']+'.json')).exists()
        events=row['events'];cuts=[e for e in events if e.get('trigger',e.get('intervention_executed',False))]
        assert row['interventions']==len(cuts) and row['first_cut']==(cuts[0]['step'] if cuts else None)
        previous=-10
        for e in events:
            t=e['step'];assert isinstance(t,int) and t%5==0 and t>=previous+10
            triggered=e.get('trigger',e.get('intervention_executed',False));assert triggered==bool(e['legal_cut'] and e['gate']>.05)
            if not triggered:continue
            assert t>=5 and t+10<=300 and e['queue_age']>0 and e['commit_until']==t+10
            assert e.get('candidate_seed',e.get('seed'))==seed_for('D24_designated_a0',u['source_id'],u['policy_seed'],t,namespace='corrector_native10_training_20260916_v1')
            executed=min(10,row['steps']-t);assert executed>=1
            if u['model']=='pi05':
                assert e['C10_steps_executed']==executed and e['C10_complete']==(executed==10) and e['restore_native_H']==u['H']
                assert not e['generation']['Q_acceptance_gate']
            else:assert e['restore_native_K']==10 and not e['Q_acceptance_gate']
            if executed<10:cut_short+=1
            cut_count+=1;previous=t
        cc=counters(row);zero=[]
        if row['interventions']==0:
            for k in ('Q_ensemble_forward','Q_member_forward','action_gradient_calls'):
                if cc[k] is None:cc[k]=0;zero.append(k)
        assert all(v is not None for v in cc.values())
        # Sparse Counter zeros have a direct complete-terminal/zero-cut proof.
        if zero:normalized_zero.append(dict(unit_id=uid,fields=zero,reason='complete terminal, zero interventions, no gradient RPC reachable',raw_preserved=str(p)))
        assert cc['flow_calls']==10*cc['sampling_calls'] and cc['D_forward']==cc['G0_forward']==2*len(events)
        expected_grad=(1 if u['method']=='Post' else 3)*len(cuts)
        assert cc['action_gradient_calls']==expected_grad
        expected_q=expected_grad if u['model']=='X-VLA' else (3 if u['method']=='Post' else 8)*len(cuts)
        assert cc['Q_ensemble_forward']==expected_q and cc['Q_member_forward']==4*expected_q
        cell=cells[u['cell_id']];cell['valid']+=1;cell['successes']+=row['success'];cell['preserved_valid']+=not is_new;cell['cuts']+=len(cuts);cell['physical_steps']+=row['steps'];add(cell,cc)
        if is_new:
            nc=newcells[u['cell_id']];nc['valid']+=1;nc['successes']+=row['success'];nc['cuts']+=len(cuts);nc['physical_steps']+=row['steps'];add(nc,cc)
            if u['model']=='pi05':add(numeric_pi[u['method']],row['numeric_counters'])
        cost_rows.append(dict(unit_id=uid,cell_id=u['cell_id'],method=u['method'],model=u['model'],recovery=is_new,result_path=str(p),**cc))
        source_rows.append(dict(unit_id=uid,cell_id=u['cell_id'],source_id=u['source_id'],env_seed=u['env_seed'],policy_seed=u['policy_seed'],L11_success=row['success'],recovery=is_new,lifetime_attempt=int(current[uid]['attempt_count']),result_path=str(p)))
        previous_result=read(u['original_source']['result_path']);assert previous_result['status']=='complete' and type(previous_result['success']) is bool
        pair=pairs[u['cell_id']];pair['n']+=1;pair['L11_successes']+=row['success'];pair['L01_successes']+=previous_result['success'];pair['rescued']+=row['success'] and not previous_result['success'];pair['harmed']+=previous_result['success'] and not row['success']
    expected={x['cell_id']:x for x in read(R/'FINAL_SUMMARY.json')['cells']}
    assert all(c['valid']==500 and c['successes']==expected[k]['successes'] for k,c in cells.items())
    assert cut_count==read(R/'CUT_PROTOCOL_AUDIT.json')['actual_cuts']
    table(OUT/'UNIQUE_USABLE_RESULTS.csv',source_rows);table(OUT/'NORMALIZED_EPISODE_COSTS.csv',cost_rows)
    atomic_json(OUT/'SPARSE_COUNTER_ZERO_PROOFS.json',dict(rows=normalized_zero,count=len(normalized_zero),scientific_results_changed=False))
    atomic_json(OUT/'SOURCE_AND_PROTOCOL_AUDIT.json',dict(utc=utc(),grant=ref(auth),manifest=ref(manifest),claim=event['job']['claim_identity'],unique_scientific_units=2500,unique_new_claims=1764,protected_valid_not_replayed=736,all_valid_terminals=2500,missing_technical_or_unknown=0,prior_attempts_retained=2750,all_attempt_rows=4514,historical_C_attempts=17693,new_attempts=1764,cumulative_C_attempts=19457,stage_cap=2000,node_cap=20750,cells={k:dict(v) for k,v in cells.items()},recovery_cells={k:dict(v) for k,v in newcells.items()},paired_L01={k:dict(v) for k,v in pairs.items()},cuts=cut_count,terminal_short_C10=cut_short,C10_reentry_errors=0,first_cut_errors=0,candidate_seed_errors=0,frozen_files_unchanged=True,new_scientific_computation=0))
    # Model/encoder counts and timings are separate from episode counters.
    roots=R/'chains/evaluate/stages';worker_totals=defaultdict(Counter);nested_seconds=defaultdict(Counter);graphics=Counter();graphic_workers=0;proofs=[];loadstats=[]
    for stage in sorted(roots.iterdir()):
        model='X-VLA' if 'X-VLA' in stage.name else 'pi05';method='Post' if 'Post' in stage.name else 'Velocity'
        if model=='X-VLA':
            for w in sorted((stage/'workers').iterdir()):
                cl=read(w/'CLIENT_RESULT.json');enc=read(w/'encoder/RESULT.json');assert cl['status']==enc['status']=='complete' and not cl['fatal'] and not enc['fatal']
                add(worker_totals['X_native'],cl['counters']);add(worker_totals['X_encoder'],enc['counts'])
                for key,meter in enc['meter_by_context'].items():
                    assert meter['entered']==meter['returned'] and not meter['failed'];kind='X_encoder_load' if key=='resident_load' else 'X_encoder_episode';add(worker_totals[kind],meter['entered']);add(nested_seconds[kind],meter['seconds'])
                ready=read(w/'MODEL_READY.json');loadstats.append(dict(model='X-VLA',slot=read(w/'CONFIG.json')['slot'],load_seconds=ready['load_seconds'],peak_bytes=cl['peak_allocated_bytes']))
        else:
            servers=list(stage.glob('model_*'));assert len(servers)==8
            whole=Counter()
            for server in servers:
                n=read(server/'SERVER_RESULT.json')['numeric'];assert n['entered']==n['returned'] and not n['failed'];add(whole,n['entered']);add(nested_seconds['pi05_'+method],n['seconds'])
                asset=read(server/'AUXILIARY_IDENTITY.json');assert asset['full_Q']['member_hashes']==read(R/'config/PI_ENGINE.json')['selected_model']['member_hashes']
                ready=read(server/'MODEL_READY.json');assert ready['loss']=='L11' and ready['fit_seed']==9101
                loadstats.append(dict(model='pi05',method=method,slot=ready['slot'],load_seconds=ready['load_seconds'],GPU_allocated_bytes=ready['GPU_allocated_bytes']))
            for k,v in numeric_pi[method].items():
                if 'load' not in k and k!='model_initializations':assert whole[k]==v,(method,k,whole[k],v)
            overhead={k:v-numeric_pi[method].get(k,0) for k,v in whole.items() if v!=numeric_pi[method].get(k,0)}
            assert all(v==8 and ('load' in k or k=='model_initializations') for k,v in overhead.items()),overhead
            add(worker_totals['pi05_'+method+'_episode'],numeric_pi[method]);add(worker_totals['pi05_'+method+'_model_load'],overhead)
            for branch in stage.glob('branch_*'):
                cfg=read(branch/'CONFIG.json');cl=read(branch/'CLIENT_RESULT.json');assert cl['status']=='complete' and cl['technical_failures']==0
                actual=read(branch/'renderer_identity.json')['physical_device'];assert actual==read(R/'config/BASE.json')['device_list'][cfg['slot']]
                gp=read(branch/'graphics_receipt.json');assert not gp['failed'] and not gp['incomplete'];add(graphics,gp['entered_budget_usage']);graphic_workers+=1
                assert not read(branch/'graphics_cleanup.json')['errors'] and not read(branch/'RESIDENT_GRAPHICS_CLEANUP.json')['errors']
        samples=list(stage.glob('workers/*/FIRST_PLANNED_OBSERVATION.json'))+list(stage.glob('branch_*/FIRST_PLANNED_OBSERVATION.json'));assert len(samples)==8
        for p in samples:
            v=read(p);assert v['passed'] and [x['step'] for x in v['checks']]==[0,5];u=units[v['unit_id']]
            for check in v['checks']:
                assert check['source_id']==u['source_id'] and check['env_seed']==u['env_seed'] and check['policy_seed']==u['policy_seed'] and check['actual_frame'] and check['pre_Q'] and check['gate_absolute_difference']==0
                assert check['extra_render_calls']==check['extra_model_calls']==0 and Path(check['pixels_path']).exists()
            proofs.append(dict(stage=stage.name,unit_id=v['unit_id'],evidence=ref(p)))
    newX=newcells['X-VLA_Post_H10_L11'];assert worker_totals['X_native']['policy_queries']==newX['sampling_calls'] and worker_totals['X_native']['policy_flow_calls']==newX['flow_calls']
    assert worker_totals['X_encoder']['Q_member_forward_calls']==newX['Q_member_forward'] and worker_totals['X_encoder']['D_forward_calls']==newX['D_forward']
    atomic_json(OUT/'OBSERVATION_AUDIT.json',dict(utc=utc(),planned_episodes_checked=24,actual_saved_frames=48,all_source_seed_process_attributions_valid=True,step0_and5_gate_max_absolute_difference=0,extra_scientific_units=0,checks=proofs,root_cause_scope='process isolation and per-environment context ownership validated; previous GL root cause remains an engineering inference'))
    # Recover known zero/full-ensemble member costs without inventing unavailable
    # historical partial-call counters. Old raw rows are never overwritten.
    normalized_attempts=[];by_uid={x['unit_id']:x for x in cost_rows}
    for a in attempts:
        out=dict(a)
        if a['run']==str(R):out.update({k:by_uid[a['unit_id']][k] for k in ('sampling_calls','flow_calls','Q_ensemble_forward','Q_member_forward','action_gradient_calls','D_forward','G0_forward')})
        elif out.get('Q_ensemble_forward') not in ('',None):out['Q_member_forward']=4*float(out['Q_ensemble_forward'])
        normalized_attempts.append(out)
    keys=('sampling_calls','flow_calls','Q_ensemble_forward','Q_member_forward','action_gradient_calls','D_forward','G0_forward')
    whole_cost={k:dict(recorded_sum=sum(float(a[k]) for a in normalized_attempts if a.get(k) not in ('',None)),unavailable_partial_records=sum(a.get(k) in ('',None) for a in normalized_attempts)) for k in keys}
    table(OUT/'ATTEMPT_COSTS_WITH_PROVEN_DERIVATIONS.csv',normalized_attempts)
    atomic_json(OUT/'CALL_COST_AUDIT.json',dict(utc=utc(),recovery_scientific_costs={k:dict(v) for k,v in newcells.items()},all_valid_scientific_costs={k:dict(v) for k,v in cells.items()},all_attempt_costs=whole_cost,process_numeric_counters={k:dict(v) for k,v in worker_totals.items()},process_nested_seconds={k:dict(v) for k,v in nested_seconds.items()},model_load_records=loadstats,graphics_api_measured=dict(graphics),graphics_client_processes=graphic_workers,graphics_scope='EGL/cleanup counters measured; receipt render_calls/rgb_readback_calls zeros are uninstrumented, not zero actual rendering; physical steps and saved frames reported separately',sampling_flow_and_critic_counts_reconciled=True,pi05_source_numeric_vs_server_counts_agree=True,sparse_zero_episode_records=len(normalized_zero),old_worker_audit=ref(OLD/'event_audits/C_4834113fcd0b6f4d5d6f6ba9fff7b341/PROCESS_COSTS.json'),old_X_velocity_worker_audit=ref(OLD/'event_audits/C_4834113fcd0b6f4d5d6f6ba9fff7b341/R5_EXISTING_RESULT_AUDIT.json'),timing_scope='operation timings are nested and must not be summed as wall time; model/RPC queue and CPU contention included in episode elapsed; epoch sums overlap wall time',no_unavailable_cost_assumed_zero=True))
    print(json.dumps(dict(valid=2500,recovered=1764,protected=736,cells={k:dict(v) for k,v in cells.items()},cuts=cut_count,observation_checks=len(proofs),new_cost_zero_record_repairs=len(normalized_zero),audit_directory=str(OUT))))
if __name__=='__main__':main()
