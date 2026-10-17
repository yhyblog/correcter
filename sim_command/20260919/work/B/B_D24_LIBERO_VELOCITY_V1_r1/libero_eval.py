"""Frozen-head native Velocity evaluation on the original400 sources; no collection or fit."""
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
    cfg=d.load(config_path);d.authorize(admission=True)
    out=Path(cfg['output']);pipeline=Path(cfg['pipeline_output'])
    status=dict(status='initializing_simulator',job_id=cfg['job_id'],suite=cfg['suite'],
        planned_development=len(cfg['development']),planned_test=len(cfg['episodes']),
        dev_complete=0,test_complete=0,technical_failures=0,H=10,K=5,at_utc=d.utc())
    d.atomic(out/'status.json',status);begun=time.monotonic();trainer=None
    try:
        import numpy as np
        from libero.libero import benchmark
        from openpi_client import image_tools
        from openpi_client.websocket_client_policy import WebsocketClientPolicy
        sys.path.insert(0,str(d.ROOT/'embodied-ai-workspace/projects/upstream/openpi-215abfb'))
        from examples.libero.main import _get_libero_env,_quat2axisangle,LIBERO_DUMMY_ACTION
        suite=benchmark.get_benchmark_dict()[cfg['suite']]()
        client=WebsocketClientPolicy('127.0.0.1',cfg['port'])
        meta=client.get_server_metadata()
        assert meta['checkpoint']==cfg['checkpoint'] and meta['H']==10 and meta['NFE']==10
        status['server']=meta

        def boundary(admission=False):
            d.authorize(admission=admission)
            if (pipeline/'PIPELINE_FAILED.json').exists():
                raise RuntimeError('Pipeline stopped at recorded failure: '+str(pipeline/'PIPELINE_FAILED.json'))

        def state(obs):
            result=np.concatenate((obs['robot0_eef_pos'],_quat2axisangle(obs['robot0_eef_quat'].copy()),obs['robot0_gripper_qpos']))
            if result.shape!=(8,) or not np.isfinite(result).all():
                raise ValueError('Expected finite native state8')
            return result

        def collect(sources,phase):
            rows=[];groups=collections.OrderedDict()
            for source in sources:groups.setdefault(source['task_id'],[]).append(source)
            for task_id,task_sources in groups.items():
                boundary(admission=True)
                task=suite.get_task(task_id)
                np.random.seed(task_sources[0]['reset_seed']);random.seed(task_sources[0]['reset_seed'])
                # Exactly the previously used native construction/reset ordering.
                with d.episode_deadline():
                    env,instruction=_get_libero_env(task,256,task_sources[0]['reset_seed'])
                try:
                    controller=env.robots[0].controller
                    if not controller.use_delta or not np.allclose(controller.output_max[:3],.05) or not np.allclose(controller.output_min[:3],-.05):
                        raise ValueError('Native XYZ command-to-metre assumption invalid')
                    if not np.allclose(controller.input_max,1) or not np.allclose(controller.input_min,-1):
                        raise ValueError('Native OSC command bounds changed')
                    d.atomic(out/'NATIVE_INTERFACE.json',dict(action_dim=7,state_dim=8,H=10,K=5,control_delta=True,
                        input_min=np.asarray(controller.input_min).tolist(),input_max=np.asarray(controller.input_max).tolist(),
                        output_min=np.asarray(controller.output_min).tolist(),output_max=np.asarray(controller.output_max).tolist(),
                        control_freq=env.env.control_freq,rotations='never modified',at_utc=d.utc()))
                    for source in task_sources:
                        boundary(admission=True);d.episode_claim(out,source)
                        tick=time.monotonic();ep=out/'episodes'/source['source_id'];ep.mkdir(parents=True,exist_ok=False)
                        row=dict(source,phase=phase,method='development-candidate' if phase=='development' else 'Velocity-operator-transfer-native-LIBERO',
                            suite=cfg['suite'],task=instruction,H=10,K=5,checkpoint=cfg['checkpoint'],
                            status='running',success=None,steps=0,queries=0,interventions=0,cut_data=None,
                            inference_seconds=0.,corrector_seconds=0.,environment_seconds=0.,preprocessing_seconds=0.)
                        actions_log=[];states=[]
                        status.update(status=phase,latest_source=source['source_id'],latest_step=0,at_utc=d.utc())
                        d.atomic(out/'status.json',status)
                        try:
                            with d.episode_deadline():
                                np.random.seed(source['reset_seed']);random.seed(source['reset_seed'])
                                env.seed(source['reset_seed']);obs=env.reset()
                                d.exclusive(out/'sources'/(source['source_id']+'.json'),dict(source,
                                    task=instruction,initial_sim_state=np.asarray(env.get_sim_state()).tolist(),
                                    source_policy=cfg['initial_source_policy']))
                                for _ in range(cfg['settle_steps']):obs,_,_,_=env.step(LIBERO_DUMMY_ACTION)
                                pending=collections.deque();done=False
                                for step in range(cfg['max_steps']):
                                    d.authorize()
                                    if not pending:
                                        t=time.monotonic()
                                        images=[image_tools.convert_to_uint8(image_tools.resize_with_pad(
                                            np.ascontiguousarray(obs[key][::-1,::-1]),224,224))
                                            for key in ('agentview_image','robot0_eye_in_hand_image')]
                                        for image in images:
                                            if image.shape!=(224,224,3) or image.dtype!=np.uint8 or float(image.std())<1 or not image.any():
                                                raise ValueError('Invalid actual LIBERO RGB observation')
                                        request={'observation/image':images[0],'observation/wrist_image':images[1],
                                            'observation/state':state(obs),'prompt':str(instruction)}
                                        if row['queries']==0:
                                            request['d24_policy_seed']=source['policy_seed']
                                            np.savez_compressed(str(ep/'first_observation.npz'),image=images[0],wrist=images[1],state=request['observation/state'])
                                        if step==cfg['adaptation']['intervention_step']:
                                            request['d24_post']=dict(mode='development' if phase=='development' else 'Velocity',step=step)
                                            if phase=='development':request['d24_post'].update(candidate_id=source['candidate_id'],candidate_seed=source['candidate_seed'])
                                        row['preprocessing_seconds']+=time.monotonic()-t
                                        row['queries']+=1;t=time.monotonic();response=client.infer(request)
                                        row['inference_seconds']+=time.monotonic()-t
                                        actions=np.asarray(response['actions'],dtype=np.float32)
                                        if actions.shape!=(10,7) or not np.isfinite(actions).all():raise ValueError('Invalid native action7/H10')
                                        if 'd24_post' in request:
                                            ref=np.asarray(response['d24_reference']);feature=np.asarray(response['d24_feature'])
                                            if feature.shape!=(329,) or not np.array_equal(actions[:,3:6],ref[:,3:6]) or not np.array_equal(actions[5:],ref[5:]):
                                                raise ValueError('Native Velocity observation/action contract mismatch')
                                            cut=ep/'cut.npz'
                                            np.savez_compressed(str(cut),feature=feature,reference=ref,candidate=actions,
                                                state=request['observation/state'],image=images[0],wrist=images[1],
                                                guided_raw=np.asarray(response['d24_guided_raw']),flow_log=np.asarray(response['d24_flow_log']))
                                            row.update(cut_data=str(cut),interventions=int(response['d24_post_info']['applied']),
                                                post_info=response['d24_post_info'],intervention_step=step)
                                            row['corrector_seconds']+=float(response['d24_corrector_seconds'])
                                            row['guided_flow_calls']=int(row.get('guided_flow_calls',0))+1
                                            row['flow_gradient_calls']=int(row.get('flow_gradient_calls',0))+int(response['d24_post_info']['guided_flow_steps'])
                                        pending.extend(actions[:5])
                                        status.update(latest_step=step,at_utc=d.utc());d.atomic(out/'status.json',status)
                                    action=pending.popleft();states.append(state(obs));actions_log.append(action)
                                    t=time.monotonic();obs,_,done,_=env.step(action.tolist())
                                    row['environment_seconds']+=time.monotonic()-t;row['steps']=step+1
                                    if done:break
                                row.update(status='complete',success=bool(done),terminal_reason='success' if done else 'step_cap')
                        except Exception as exc:
                            status['technical_failures']+=1
                            row.update(status='technical_failure',success=None,error=repr(exc));traceback.print_exc()
                        row.update(elapsed_seconds=time.monotonic()-tick,at_utc=d.utc())
                        np.savez_compressed(str(ep/'trajectory.npz'),actions=np.asarray(actions_log),states=np.asarray(states))
                        d.atomic(ep/'RESULT.json',row)
                        d.append(out/('development.jsonl' if phase=='development' else 'episodes.jsonl'),row)
                        rows.append(row)
                        if row['status']=='complete':status['dev_complete' if phase=='development' else 'test_complete']+=1
                        status.update(latest_source=source['source_id'],at_utc=d.utc());d.atomic(out/'status.json',status)
                        print(json.dumps(row),flush=True)
                        if status['technical_failures']>=3:raise RuntimeError('Three technical failures; diagnosis required, no automatic replay')
                finally:env.close()
            return rows

        ready=d.load(cfg['frozen_head_ready'])
        status.update(native_head=cfg['frozen_head_ready'],native_head_updates=0)
        collect(cfg['episodes'],'test')
        status['status']='complete' if status['technical_failures']==0 else 'partial'
    except BaseException as exc:
        status.update(status='failed',error=repr(exc))
        try:d.exclusive(pipeline/'PIPELINE_FAILED.json',dict(job_id=cfg['job_id'],error=repr(exc),at_utc=d.utc()))
        except FileExistsError:pass
        raise
    finally:
        if trainer is not None and trainer.poll() is None:
            trainer.terminate()
            try:trainer.wait(timeout=20)
            except subprocess.TimeoutExpired:trainer.kill();trainer.wait(timeout=10)
        status.update(elapsed_seconds=time.monotonic()-begun,at_utc=d.utc());d.atomic(out/'status.json',status)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True)
    main(p.parse_args().config)
