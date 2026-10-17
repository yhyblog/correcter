"""Bounded CPU check of the actual nested controller and recorder; no simulation/model."""
import ast,collections,contextlib,tempfile,time,traceback,json,copy
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import paths
from paths import ROOT
from qio import read,new_json,atomic_json,utc,sha
from admission import AdmissionStop
from projector import project_solo
from experiments.native10_training_20260916.protocol import seed_for
from report import validate_episode

def main():
    for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text())
    cfg=read(ROOT/'config/CONFIG.json');sources=read(ROOT/'config/TEST_SOURCES.json')['sources']
    assert len(sources)==len({s['source_id'] for s in sources})==500
    assert cfg['planned_prior_attempts']==10443 and cfg['stage_attempt_cap']==1650 and cfg['small_network_update_cap']==0
    for k in ['test_sources','source_index','method_frozen','frozen_heads']:
        assert sha(cfg[k]['path'])==cfg[k]['sha256']
    tree=ast.parse((ROOT/'code/native_client.py').read_text())
    node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='evaluate_source')
    code=compile(ast.Module(body=[node],type_ignores=[]),'<actual_C_multi_evaluate_source>','exec')
    matching=read(ROOT/'config/ENGINE_CONFIG.json')['matching'];checks=[]
    for gate,stop_at,label in [(1.,300,'always_positive'),(.05,300,'strict_threshold'),(1.,3,'early_terminal')]:
        for method in ['R','Post','Velocity']:
            with tempfile.TemporaryDirectory(prefix='C_multi_controller_CPU_',dir='/tmp') as tmp:
                root=Path(tmp);out=root/'worker';out.mkdir();source=copy.deepcopy(sources[0])
                counts=collections.Counter();enc=collections.Counter();context={'step':None,'objective':None};queries=[]
                env=SimpleNamespace(task_description='CPU fixture',t=0,actions=[])
                def obs():return dict(pixels=np.ones((2,2,3),dtype=np.uint8)*(env.t%256),agent_pos=np.ones(4,dtype=np.float32)*env.t)
                def reset(e,s):return obs(),dict(timestep=.0025,frame_skip=5,action_scale=.01),None
                def step_env(e,raw):
                    e.actions.append(np.asarray(raw).copy());e.t+=1;counts['environment_steps']+=1
                    return obs(),0.,e.t>=stop_at,False,dict(success=False)
                def rpc(kind,**fields):
                    if kind=='begin':
                        before=dict(enc);enc['language_encoder_calls']+=1
                        return dict(counters_before=before,counters=dict(enc))
                    if kind=='monitor':
                        context['step']=fields['step'];enc['D_forward_calls']+=2;enc['G0_forward_calls']+=2
                        enc['visual_encoder_calls']+=len(fields['observations'])
                        assert np.array_equal(fields['props'][-1],np.ones(4)*fields['step'])
                        return dict(gate=gate,member_gates=[gate,gate])
                    if kind=='objective':
                        assert fields['step']==context['step'];context['objective']=fields['step'];return {}
                    if kind=='gradient':
                        assert fields['step']==context['step']==context['objective']
                        enc['Q_ensemble_forward_calls']+=1;enc['action_gradient_calls']+=1
                        return dict(post_direction=np.ones((10,4))*.01,gradient=np.ones((10,4))*.01,Post_metric='fixture')
                    if kind=='snapshot':return dict(counters=dict(enc))
                    raise AssertionError(kind)
                def generate(o,instruction,candidate_seed=None,gradient=None):
                    queries.append((env.t,candidate_seed,gradient is not None))
                    counts['policy_queries']+=1;counts['policy_flow_calls']+=10
                    counts['candidate_queries' if candidate_seed is not None else 'natural_queries']+=1
                    raw=np.tile(np.arange(30,dtype=np.float32)[:,None]*.001,(1,4))
                    if candidate_seed is not None:raw+=.1
                    if gradient is not None:
                        for _ in range(3):gradient(raw[:10])
                        raw[:10]+=.01
                    return raw,dict(noise_sha256=str(candidate_seed),flow_calls=10)
                namespace=dict(ROOT=root,np=np,collections=collections,counters=counts,time=time,traceback=traceback,
                    cfg=cfg,out=out,matching=matching,project_solo=project_solo,seed_for=seed_for,
                    claim_attempt=lambda *a,**k:'CPU_fixture_no_scientific_claim',new_json=new_json,atomic_json=atomic_json,utc=utc,
                    episode_deadline=contextlib.nullcontext,reset=reset,rpc=rpc,observation=lambda x:x,
                    generate=generate,step_env=step_env,check=lambda *a:None,terminal=lambda value:bool(value[2]),AdmissionStop=AdmissionStop)
                exec(code,namespace)
                ep=root/'evaluation'/method/source['source_id']
                try:namespace['evaluate_source'](env,source,method)
                except Exception as exc:raise AssertionError(read(ep/'RESULT.json')) from exc
                row=read(ep/'RESULT.json');validate_episode(row,source)
                assert row['status']=='complete' and row['success'] is False and row['steps']==stop_at
                cuts=[e['step'] for e in row['events'] if e['trigger']]
                expected=list(range(5,291,15)) if label=='always_positive' else []
                assert cuts==expected and row['first_cut']==(5 if expected else None)
                assert row['encoder_counters']['language_encoder_calls']==1
                if expected:
                    # All ten committed commands execute before the next natural plan.
                    for cut in cuts:
                        assert not any(cut<t<cut+10 for t,seed,_ in queries)
                        if cut+10<stop_at:assert any(t==cut+10 and seed is None for t,seed,_ in queries)
                    assert len(list(ep.glob('intervention_cut_*.npz')))==(0 if method=='R' else len(cuts))
                    for event in [e for e in row['events'] if e['trigger']]:
                        assert event['candidate_seed']==seed_for('D24_designated_a0',source['source_id'],source['policy_seed'],event['step'],namespace=cfg['seed_namespace'])
                    assert [e['intervention_index'] for e in row['events'] if e['trigger']]==list(range(1,21))
                checks.append(dict(method=method,scenario=label,interventions=len(cuts),first_cut=row['first_cut'],steps=row['steps']))
    # Exercise the real exclusive attempt counter in an isolated CPU fixture.
    import common
    with tempfile.TemporaryDirectory(prefix='C_multi_admission_CPU_',dir='/tmp') as tmp:
        common.ROOT=Path(tmp);common.LOCAL=Path(tmp)/'local';common.boundary=lambda **kw:None
        new_json(Path(tmp)/'config/CONFIG.json',dict(stage_attempt_cap=2,planned_prior_attempts=10443,node_cumulative_attempt_cap=14000))
        common.claim_attempt('fixture_one')
        try:common.claim_attempt('fixture_one');raise AssertionError('duplicate permitted')
        except RuntimeError as exc:assert 'existing attempt' in str(exc)
        common.claim_attempt('fixture_two')
        try:common.claim_attempt('fixture_three');raise AssertionError('budget overrun')
        except AdmissionStop:pass
        assert read(Path(tmp)/'ATTEMPT_COUNTER.json')['cumulative_C_reserved']==10445
    row=dict(status='passed',utc=utc(),CPU_only=True,GPU_calls=0,simulator_rollouts=0,optimizer_updates=0,
        actual_controller_scenarios=checks,exclusive_claim_duplicate_and_budget_checked=True,
        serializer_and_report_validator='actual evaluate_source and validate_episode; temp fixtures only',
        random_stream='same source/policy_seed/absolute_cut key, no branch/count term',
        unchanged_native_bridge_sha256=sha(ROOT/'code/native_velocity.py'),method_sha256=sha(ROOT/'METHOD_FROZEN.json'))
    atomic_json(ROOT/'CPU_CHECK.json',row);print(json.dumps(row))

if __name__=='__main__':main()
