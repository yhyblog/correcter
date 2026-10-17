"""Native K5/D2 age2 collector and Full controller on the exact frozen sources."""
import argparse
import collections
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import traceback
import d24_common as d
from batch import reservation_fds

def main(config_path):
    import numpy as np
    from libero.libero import benchmark
    from openpi_client import image_tools
    from openpi_client.websocket_client_policy import WebsocketClientPolicy
    from context import context,legal_age2
    sys.path.insert(0,str(d.ROOT/'embodied-ai-workspace/projects/upstream/openpi-215abfb'))
    from examples.libero.main import _get_libero_env,_quat2axisangle,LIBERO_DUMMY_ACTION
    cfg=d.load(config_path);d.authorize(admission=True)
    out=Path(cfg['output']);pipeline=d.R;trainer=None;monitor=None
    suite=benchmark.get_benchmark_dict()[cfg['suite']]()
    client=WebsocketClientPolicy('127.0.0.1',cfg['port']);meta=client.get_server_metadata()
    if meta['checkpoint']!=cfg['checkpoint'] or meta['H']!=10 or meta['NFE']!=10:raise ValueError('Native base identity')
    status=dict(status='development',worker=cfg['worker_index'],server=meta,dev_complete=0,test_complete=0,
                physical_attempts=0,technical_failures=0,utc=d.utc())
    d.atomic(out/'status.json',status)

    def boundary():
        d.authorize()
        if (pipeline/'PIPELINE_FAILED.json').exists():raise RuntimeError('A formal pipeline failure')

    def state(obs):
        value=np.concatenate((obs['robot0_eef_pos'],_quat2axisangle(obs['robot0_eef_quat'].copy()),obs['robot0_gripper_qpos']))
        if value.shape!=(8,) or not np.isfinite(value).all():raise ValueError('Native state8')
        return value

    def request(obs,instruction,step,mode,seed=None):
        images=[image_tools.convert_to_uint8(image_tools.resize_with_pad(
            np.ascontiguousarray(obs[key][::-1,::-1]),224,224)) for key in ('agentview_image','robot0_eye_in_hand_image')]
        if any(im.shape!=(224,224,3) or im.dtype!=np.uint8 for im in images):raise ValueError('Native RGB format')
        message={'observation/image':images[0],'observation/wrist_image':images[1],
            'observation/state':state(obs),'prompt':str(instruction),'d24_control':dict(mode=mode,step=step)}
        if seed is not None:message['d24_policy_seed']=seed
        return client.infer(message)

    def collect(sources,phase):
        rows=[]
        for source in sources:
            boundary();d.episode_claim(out,source,phase,phase)
            ep=out/'episodes'/phase/source['source_id'];ep.mkdir(parents=True,exist_ok=False)
            row=dict(source,phase=phase,method='G0-supervision-'+source['branch'] if phase=='development' else phase+' native-LIBERO',
                suite=cfg['suite'],H=10,K=5,D_horizon=2,G0_reference_commit=3,corrector_commit=5,
                status='entered',success=None,steps=0,sampling_calls=0,flow_calls=0,feature_calls=0,
                interventions=0,G0_triggered=False,cut_step=None,cut_data=None,elapsed_seconds=None,
                inference_seconds=0.,environment_seconds=0.,monitor_seconds=0.,corrector_seconds=0.,
                started_utc=d.utc(),technical_failure=None,threshold=.05)
            d.exclusive(ep/'ENTERED.json',row);status['physical_attempts']+=1
            env=None;features=[];actions=[];chunk_starts=[];monitors=[];proposals=[];tick=time.monotonic()
            before=dict(monitor.counts) if monitor is not None else {}
            try:
                with d.episode_deadline():
                    np.random.seed(source['reset_seed']);random.seed(source['reset_seed'])
                    task=suite.get_task(source['task_id'])
                    env,instruction=_get_libero_env(task,256,source['reset_seed'])
                    controller=env.robots[0].controller
                    if not controller.use_delta or not np.allclose(controller.output_max[:3],.05) or not np.allclose(controller.output_min[:3],-.05):
                        raise ValueError('Frozen XYZ .05m command scale invalid')
                    if not np.allclose(controller.input_max,1) or not np.allclose(controller.input_min,-1):raise ValueError('Native command bounds')
                    np.random.seed(source['reset_seed']);random.seed(source['reset_seed']);env.seed(source['reset_seed'])
                    obs=env.reset()
                    d.exclusive(ep/'SOURCE.json',dict(source,initial_state=np.asarray(env.get_sim_state()).tolist(),
                        initial_source_policy=cfg['initial_source_policy'],cold_environment=True))
                    for _ in range(cfg['settle_steps']):obs,_,_,_=env.step(LIBERO_DUMMY_ACTION)
                    pending=collections.deque();chunk_start=None;predicted=None;used=False;done=False
                    def encode(step):
                        t=time.monotonic();reply=request(obs,instruction,step,'features')
                        row['inference_seconds']+=time.monotonic()-t;row['feature_calls']+=reply['feature_calls']
                        f=np.asarray(reply['d24_feature'],np.float32)
                        if f.shape!=(329,) or not np.isfinite(f).all():raise ValueError('Actual native329 feature')
                        return f
                    def sample(step,mode):
                        t=time.monotonic();reply=request(obs,instruction,step,mode,
                            source['policy_seed'] if row['sampling_calls']==0 else None)
                        row['inference_seconds']+=time.monotonic()-t
                        row['sampling_calls']+=int(reply['sampling_calls']);row['flow_calls']+=int(reply['flow_calls'])
                        row['feature_calls']+=int(reply['feature_calls'])
                        value=np.asarray(reply['actions'],np.float32)
                        if value.shape!=(10,7) or not np.isfinite(value).all():raise ValueError('Native raw10/action7')
                        proposals.append(dict(step=step,mode=mode,sampling_calls=reply['sampling_calls']))
                        return value,reply
                    for step in range(cfg['max_steps']):
                        boundary();features.append(encode(step))
                        if not pending:
                            raw,reply=sample(step,'sample');pending.extend(raw[:5]);chunk_start=step
                            chunk_starts.append(step)
                            if monitor is not None and not used:
                                predicted=monitor.predict(context(features,actions,step),raw[:2])
                        if legal_age2(step,chunk_start,pending,cfg['max_steps'],used):
                            old3=np.asarray(pending,np.float32).copy();observed=context(features,actions,step)
                            if phase=='development':
                                # One fixed first age2 pair; this is supervised data, not a G0 trigger.
                                used=True;row['cut_step']=step
                                cut=ep/'cut.npz';np.savez_compressed(str(cut),**observed,feature=features[-1],
                                    old3=old3,prefix_actions=np.asarray(actions,np.float32),prefix_features=np.asarray(features,np.float32))
                                row['cut_data']=str(cut)
                                if source['branch']=='fresh':
                                    fresh,reply=sample(step,'sample');pending=collections.deque(fresh[:3]);row['interventions']=1
                                row['development_forced_branch']=source['branch'];row['G0_triggered']=False
                            else:
                                t=time.monotonic();decision=monitor.monitor(observed,old3,predicted,features[-1]);row['monitor_seconds']+=time.monotonic()-t
                                decision.update(step=step,age=2,synthetic=False);monitors.append(decision)
                                if decision['gate']>.05:
                                    corrected,reply=sample(step,'Post' if phase=='Full-Post' else 'Velocity')
                                    ref=np.asarray(reply['d24_reference'],np.float32)
                                    if not np.array_equal(corrected[:,3:6],ref[:,3:6]) or not np.array_equal(corrected[5:],ref[5:]):
                                        raise ValueError('Frozen rotations/tail violated')
                                    pending=collections.deque(corrected[:5]);used=True
                                    row.update(interventions=1,G0_triggered=True,cut_step=step,post_info=reply['d24_post_info'])
                                    row['corrector_seconds']+=float(reply['d24_corrector_seconds'])
                                    row['correction_tail_discarded']=5
                        action=pending.popleft();actions.append(action.copy())
                        t=time.monotonic();obs,_,done,_=env.step(action.tolist());row['environment_seconds']+=time.monotonic()-t
                        row['steps']=step+1
                        if step%5==0:
                            status.update(status=phase,latest_source=source['source_id'],latest_step=step+1,utc=d.utc());d.atomic(out/'status.json',status)
                        if done:break
                    # True final observation needed for D2 targets; no extra action/reset/render.
                    features.append(encode(row['steps']))
                    row.update(status='complete',success=bool(done),terminal_reason='success' if done else 'step_cap')
            except Exception as exc:
                status['technical_failures']+=1
                row.update(status='technical_failure',success=None,technical_failure=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()))
                traceback.print_exc()
            finally:
                if env is not None:
                    try:env.close()
                    except Exception as exc:
                        row['cleanup_error']=repr(exc);d.atomic(pipeline/'PIPELINE_FAILED.json',dict(reason='owned environment cleanup failed',error=repr(exc),utc=d.utc()))
            row.update(elapsed_seconds=time.monotonic()-tick,finished_utc=d.utc(),
                counters={k:v-before.get(k,0) for k,v in monitor.counts.items()} if monitor else {})
            # Small causal features/actions only, no videos/whole-state hashes.
            np.savez_compressed(str(ep/'trajectory.npz'),features=np.asarray(features,np.float32),
                actions=np.asarray(actions,np.float32),chunk_starts=np.asarray(chunk_starts,np.int32))
            row['trajectory']=str(ep/'trajectory.npz');row['valid_D_feature_clock']=len(features)==len(actions)+1
            row['monitor_events']=monitors;row['proposal_events']=proposals
            d.atomic(ep/'RESULT.json',row);d.append(out/(phase+'.jsonl'),row);rows.append(row)
            if row['status']=='complete':status['dev_complete' if phase=='development' else 'test_complete']+=1
            status.update(utc=d.utc(),latest_status=row['status']);d.atomic(out/'status.json',status)
            print(json.dumps({k:row[k] for k in ['source_id','phase','status','success','steps','sampling_calls','interventions','cut_step']}),flush=True)
            if status['technical_failures']>=3:raise RuntimeError('Three technical failures; stop for diagnosis, no replay')
        return rows

    try:
        dev=collect(cfg['development'],'development')
        d.atomic(out/'DEV_DONE.json',dict(planned=len(cfg['development']),recorded=len(dev),utc=d.utc()))
        status.update(status='waiting_for_true_supervision_and_fixed_fit',utc=d.utc());d.atomic(out/'status.json',status)
        while not (pipeline/'MODEL_READY.json').exists() and not (pipeline/'SCIENTIFIC_GAP.json').exists():
            boundary()
            if cfg['worker_index']==0 and trainer is None and all((Path(p)/'DEV_DONE.json').exists() for p in cfg['worker_outputs']):
                with (pipeline/'fit.log').open('a') as log:
                    trainer=subprocess.Popen([str(d.ROOT/'.miniforge3/envs/lerobot/bin/python'),'-B',str(d.W/'train_full.py')],
                        env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4'),stdin=subprocess.DEVNULL,
                        stdout=log,stderr=subprocess.STDOUT,pass_fds=reservation_fds())
                d.atomic(pipeline/'FIT_PROCESS.json',d.identity(trainer.pid))
            if trainer is not None and trainer.poll() is not None and trainer.returncode:
                raise RuntimeError('Native fitting failed: '+str(trainer.returncode))
            time.sleep(2)
        if trainer is not None and trainer.wait(timeout=30):raise RuntimeError('Fitter exit failure')
        if (pipeline/'SCIENTIFIC_GAP.json').exists():
            status.update(status='scientific_gap_no_Full_eval',reason=d.load(pipeline/'SCIENTIFIC_GAP.json'));return
        from runtime_small import Monitor
        monitor=Monitor()
        for phase in ['Full-Post','Full-Velocity']:
            rows=collect(cfg['episodes'],phase)
            d.atomic(out/(phase+'_DONE.json'),dict(episodes=len(rows),technical_failures=sum(x['status']!='complete' for x in rows),utc=d.utc()))
            if phase=='Full-Post':
                while not all((Path(p)/(phase+'_DONE.json')).exists() for p in cfg['worker_outputs']):boundary();time.sleep(2)
        status.update(status='complete' if status['technical_failures']==0 else 'partial')
    except BaseException as exc:
        status.update(status='failed',error=repr(exc))
        if not (pipeline/'PIPELINE_FAILED.json').exists():d.exclusive(pipeline/'PIPELINE_FAILED.json',dict(worker=cfg['worker_index'],error=repr(exc),utc=d.utc()))
        raise
    finally:
        if trainer is not None and trainer.poll() is None:
            trainer.terminate()
            try:trainer.wait(timeout=20)
            except subprocess.TimeoutExpired:trainer.kill();trainer.wait(timeout=10)
        status.update(utc=d.utc());d.atomic(out/'status.json',status)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);main(p.parse_args().config)
