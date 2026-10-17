"""CPU-only audit of existing r4 records; no rollout, model import, or GPU API."""
import collections
import hashlib
import json
import subprocess
import sys
from pathlib import Path

C = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
R = C / 'results/C/C_D24_L11_RETEST_V1'
RUN = R / 'continuations/r4'
EVENT = 'C_4834113fcd0b6f4d5d6f6ba9fff7b341'
OUT = R / 'event_audits' / EVENT
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(RUN / 'code'))
from qio import read, new_json, ref, utc


def main():
    manifest = C / 'deadline_20260924/L11_RETEST_V1/prepared_by_analysis/NEW_UNITS_C.jsonl'
    auth = C / 'deadline_20260924/L11_RETEST_V1/AUTHORIZATION.json'
    assert ref(manifest)['sha256'] == '3a10369107ac2c9a57c30099158e21b7c5879026dc27bfa3b171f2cc61778715'
    assert ref(auth)['sha256'] == 'a978519ba24dfb3aba22cf5ce8472d9b855e788e44266a28e0d006be876d5e87'
    units = [json.loads(s) for s in manifest.open()]
    assert len(units) == len({u['unit_id'] for u in units}) == 2500
    assert all(u['owner'] == 'C' and u['Q_loss'] == 'L11' and u['Q_fit_seed'] == 9101 and u['Q_members'] == [1041, 1042, 1043, 1044] for u in units)
    event_path = C / 'persistent_queue/nodes/C/wakeup/outbox' / (EVENT + '.json')
    event = read(event_path)
    assert event['job']['claim_identity'] == ref(RUN / 'CLAIM.json')
    assert event['result'] == read(RUN / 'RESULT.json')
    assert event['executor_thread_id'] == '01a0c793-10d2-7791-a250-fd65d88e1ccb'
    cells = collections.defaultdict(collections.Counter)
    source_rows = []
    outcomes = {}
    for u in units:
        if u['model'] != 'pi05':
            continue
        cell = 'pi05_' + u['method'] + '_H' + str(u['H']) + '_L11'
        path = RUN / 'pi_evaluation' / cell / u['source_id'] / 'RESULT.json'
        v = read(path)
        key = hashlib.sha256(u['unit_id'].encode()).hexdigest()
        cp = RUN / 'claims/units' / (key + '.json')
        claim = read(cp)
        assert claim['unit_id'] == u['unit_id'] and claim['attempt'] == 1 and claim['retry'] is False
        assert all(not (p / 'claims/units' / (key + '.json')).exists() for p in [R, R / 'continuations/r2', R / 'continuations/r3', R / 'continuations/r5'])
        for k in ['unit_id', 'source_id', 'env_seed', 'policy_seed', 'task', 'H', 'method', 'mode']:
            assert v[k] == u[k], (u['unit_id'], k)
        assert v['loss'] == 'L11' and v['fit_seed'] == 9101 and v['status'] == 'complete' and type(v['success']) is bool
        assert v['technical_failure'] is None and v['terminal'] is True
        events = v['events']
        cuts = [e for e in events if e.get('intervention_executed')]
        assert [e['step'] for e in cuts] == v['intervention_cuts']
        assert len(cuts) == v['interventions']
        assert v['first_cut'] == (cuts[0]['step'] if cuts else None)
        assert v['last_cut'] == (cuts[-1]['step'] if cuts else None)
        for n, e in enumerate(cuts):
            t = e['step']
            assert e['legal_cut'] and e['gate'] > .05 and e['intervention_index'] == n + 1
            assert e['commit_until'] == t + 10 and e['C10_steps_executed'] == min(10, v['steps'] - t)
            assert e['C10_complete'] == (v['steps'] >= t + 10)
            assert not any(t < m['step'] < t + 10 for m in events)
            if v['steps'] > t + 10:
                assert e['native_H_restored'] and e['native_restore_step'] == t + 10 and e['restore_native_H'] == u['H']
            else:
                assert e.get('restore_not_executed_reason', '').startswith('episode_terminal:')
        cnt = v['counters']
        plan_sampling = sum(p['stats']['policy_calls'] for p in v['plans'])
        assert plan_sampling == v['sampling_calls'] == cnt['sampling']
        assert plan_sampling * 10 == v['flow_calls'] == cnt['flow']
        assert cnt['contexts'] == len(events)
        assert cnt['D_forward'] == cnt['G0_forward'] == 2 * len(events)
        assert cnt['interventions'] == len(cuts)
        assert cnt['Q_ensemble_forward'] == sum(e['generation']['objective']['objective_forward_calls'] for e in cuts)
        assert cnt['action_gradients'] == sum(e['generation']['objective']['objective_backward_calls'] for e in cuts)
        assert v['render_context']['owning_renderer_bind_count'] >= v['steps'] + 1
        current = cells[cell]
        current.update(raw_terminals=1, raw_successes=int(v['success']), raw_false=int(not v['success']),
                       monitored_contexts=len(events), physical_steps=v['steps'],
                       elapsed_seconds=v['elapsed_seconds'], environment_seconds=v['environment_seconds'],
                       inference_seconds=v['inference_seconds'], **cnt)
        old = read(u['original_source']['result_path'])
        assert old['source_id'] == u['source_id'] and old['env_seed'] == u['env_seed'] and old['policy_seed'] == u['policy_seed']
        current.update(old_L01_successes=int(old['success']), raw_rescued=int(v['success'] and not old['success']), raw_harmed=int(old['success'] and not v['success']))
        outcomes[u['unit_id']] = dict(numeric=v['numeric_counters'], counters=cnt, steps=v['steps'])
        source_rows.append(dict(unit_id=u['unit_id'],cell_id=cell,claim=str(cp),result=str(path),raw_success=v['success'],
                                first_cut=v['first_cut'],cut_count=len(cuts),disposition='execution_integrity_unverified',
                                legal_terminal_replay_authorized=False))
    assert len(outcomes) == 1500 and all(c['raw_terminals'] == 500 for c in cells.values())
    worker_rows = []
    numeric = collections.Counter()
    numeric_seconds = collections.Counter()
    load = collections.Counter()
    load_seconds = collections.Counter()
    observed_ids = set()
    for path in sorted((RUN / 'chains/evaluate/stages').glob('*/workers/*/WORKER_RESULT.json')):
        w = read(path)
        ready = read(path.parent / 'MODEL_READY.json')
        progress = read(path.parent / 'PROGRESS.json')
        assert w['status'] == 'complete' and w['fatal'] is None and not w['pending_units']
        assert w['peak_active_contexts'] == 8 and w['batch_size'] == 1 and w['model_replicas'] == 1
        ids = {e['unit_id'] for e in w['completed']}
        assert not (ids & observed_ids)
        observed_ids |= ids
        assert w['physical_step_advances'] == sum(outcomes[i]['steps'] for i in ids)
        for uid, v in w['numeric_by_context'].items():
            assert not v['failed'] and v['entered'] == v['returned']
            if uid == 'resident_load':
                load.update(v['entered']); load_seconds.update(v['seconds'])
            else:
                assert uid in ids and v['entered'] == outcomes[uid]['numeric']
                assert v['entered']['flow_forward_calls'] == outcomes[uid]['counters']['flow']
                assert v['entered']['prefix_transformer_forwards'] == outcomes[uid]['counters']['sampling']
                numeric.update(v['entered']); numeric_seconds.update(v['seconds'])
        worker_rows.append(dict(path=str(path), GPU=ready['GPU'], model_load_seconds=ready['model_load_seconds'],
                                worker_elapsed_seconds=w['elapsed_seconds'],completed=len(ids),peak_contexts=w['peak_active_contexts'],
                                peak_allocated_GPU_bytes=progress['peak_GPU_bytes'], RSS_high_water_KiB=progress['RSS_high_water_KiB']))
    assert len(worker_rows) == 72 and observed_ids == set(outcomes)
    costs = dict(utc=utc(), scope='All 1500 raw r4 attempts, including records withheld from scientific validity; no historical costs copied.',
                 episode_counters=dict(numeric), episode_seconds_by_nested_operation=dict(numeric_seconds),
                 model_load_counters=dict(load),model_load_seconds_by_nested_operation=dict(load_seconds),
                 cells={k:dict(v) for k,v in cells.items()},workers=worker_rows,
                 numeric_entered_returned_equal=True,per_source_and_worker_costs_agree=True,
                 timing_note='Nested timers overlap; episode wall time includes cooperative scheduling wait. Do not sum into GPU kernel time.',
                 graphics_note='graphics_receipt render_calls=0 is uninstrumented, not zero actual rendering; physical step/render binding counts remain separate.')
    new_json(OUT / 'PROCESS_COSTS.json', costs)
    new_json(OUT / 'SOURCE_DISPOSITIONS.json',source_rows)
    new_json(OUT / 'RECORD_AUDIT.json',dict(utc=utc(),event=ref(event_path),authorization=ref(auth),manifest=ref(manifest),
             event_claim_matches=True,unique_C_units=2500,r4_unique_claims=1500,raw_terminals=1500,per_source_attempts=1,
             existing_terminal_replays=0,L11_fit9101_members_verified=True,source_seeds_verified=True,C10_first_cut_cost_invariants_verified=True,
             scientific_validity='withheld_pending_preintervention_execution_integrity_issue',costs=ref(OUT/'PROCESS_COSTS.json'),
             cells={k:dict(v) for k,v in cells.items()},raw_summary=ref(RUN/'FINAL_SUMMARY.json'),new_GPU_calls=0,new_scientific_units=0))
    # Targeted pre-Q comparison, selected independently of outcome: first ten
    # lexicographic tasks at source ordinal zero, using already saved arrays.
    import numpy as np
    prefix=[]
    chosen=sorted([u for u in units if u['model']=='pi05' and u['method']=='Post' and u['ordinal']==0],key=lambda u:u['source_id'])[:10]
    for u in chosen:
        p=RUN/'pi_evaluation/pi05_Post_H40_L11'/u['source_id']/'RESULT.json';old=Path(u['original_source']['result_path'])
        a,b=read(p),read(old)
        with np.load(p.parent/'trajectory.npz') as aa,np.load(old.parent/'trajectory.npz') as bb:
            actions=float(np.max(np.abs(aa['actions'][:5]-bb['actions'][:5])))
            rewards=float(np.max(np.abs(aa['rewards'][:5]-bb['rewards'][:5])))
        ae=next(e for e in a['events'] if e['step']==5);be=next(e for e in b['events'] if e['step']==5)
        prefix.append(dict(source_id=u['source_id'],new_result=str(p),old_result=str(old),first_five_actions_linf=actions,
                           first_five_rewards_linf=rewards,step0_gate_new=a['events'][0]['gate'],step0_gate_old=b['events'][0]['gate'],
                           step5_gate_new=ae['gate'],step5_gate_old=be['gate'],new_first_cut=a['first_cut'],old_first_cut=b['first_cut'],
                           first_plan_noise_equal=a['plans'][0]['stats']['noise_sha256']==b['plans'][0]['stats']['noise_sha256']))
    assert all(x['first_five_actions_linf']==0 and x['first_five_rewards_linf']==0 and x['step0_gate_new']==x['step0_gate_old'] and x['step5_gate_new']!=x['step5_gate_old'] for x in prefix)
    binary=C.parents[2]/'embodied-ai-workspace/environments/lerobot/lib/python3.12/site-packages/mujoco/libmujoco.so.3.6.0'
    for symbol in ['mjr_render','mjr_readPixels','mjr_setBuffer']:
        disassembly=subprocess.run(['objdump','-d','--no-show-raw-insn','--disassemble='+symbol,str(binary)],check=True,capture_output=True,text=True).stdout
        (OUT/(symbol+'.disassembly.txt')).write_text(disassembly)
    new_json(OUT/'PREINTERVENTION_DIAGNOSTIC.json',dict(utc=utc(),comparison=prefix,selection='first10 lexicographic tasks, ordinal0; not selected by success',
             confirmed='First-five-step actions and rewards and step0 G0 identical; step5 frozen G0 differs before any Q intervention in either run.',
             loss_attribution_invalid=True,
             suspected_cause='Shared EGL context with separate MjrContext objects: render_context binds the same GL context but does not restore the per-viewer framebuffer before drawing. Later renderer shadow/readback bindings do not prove correct pre-draw framebuffer contents.',
             root_cause_runtime_confirmed=False,frames_not_saved=True,repair_GPU_validated=False,
             numeric_engine_unchanged=ref(RUN/'code/numeric_engine.py')['sha256']==ref(C/'results/C/C_D24_PI05_SELECTED_H40_H50_V1/code/numeric_engine.py')['sha256'],
             code=[ref(RUN/'code/pi_worker.py'),ref(RUN/'code/resident_egl.py'),ref(RUN/'code/render_context.py')],
             all_raw_results_preserved=True,new_GPU_calls=0,new_rollouts=0))
    print(json.dumps(dict(raw_terminals=1500,scientific_validity='withheld',per_source_C10_cost_checks=True,workers=72,prefix_divergences=len(prefix))))

if __name__=='__main__':main()
