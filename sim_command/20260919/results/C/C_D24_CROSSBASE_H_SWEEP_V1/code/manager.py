"""Finite N/Post/R/Velocity horizon sweep, 24 model workers x 8 live contexts."""
import argparse,os,secrets,signal,subprocess,sys,time,traceback
from pathlib import Path
import paths
from paths import ROOT
from qio import read,new_json,atomic_json,utc,process_identity
from admission import authority,before_cutoff,admissions_allowed
from reservation import send_existing_fd,holder_exit_ack
from wave_timing import held_reservation_fds
from process_family import drain_group
from common import runtime_command

def pi_environment(base,work):
    env=dict(os.environ);env.update(base['cuda_environment'])
    env.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HOME=base['hf_home'],OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2',LP_NUM_THREADS='2',TOKENIZERS_PARALLELISM='false',PYTORCH_NVML_BASED_CUDA_CHECK='0',CUDA_CACHE_DISABLE='1',TMPDIR=str(work/'tmp'),XDG_CACHE_HOME=str(work/'cache'),XDG_RUNTIME_DIR=str(work/'xdg'),LD_LIBRARY_PATH=base['LD_LIBRARY_PATH'],MUJOCO_GL='egl',PYOPENGL_PLATFORM='egl',__EGL_VENDOR_LIBRARY_FILENAMES=base['native']['isolation_root']+'/isolation/vendor/10_nvidia.json')
    for k in ['LD_PRELOAD','__EGL_VENDOR_LIBRARY_DIRS','MUJOCO_EGL_DEVICE_ID','PYTHONPATH','LIBGL_ALWAYS_SOFTWARE','MESA_LOADER_DRIVER_OVERRIDE','GALLIUM_DRIVER','EGL_PLATFORM','LIBGL_DRIVERS_PATH']:env.pop(k,None)
    return env

def main(chain):
    authority();own=process_identity();fds=held_reservation_fds();started=time.monotonic()
    if own['pid']!=own['pgid'] or len(fds)!=1:raise RuntimeError('single inherited reservation/group required')
    request=read(chain/'REQUEST.json');send_existing_fd(request['socket'],fds[0])
    new_json(chain/'HOLDER_EXIT_ACK.json',holder_exit_ack(request))
    new_json(chain/'MANAGER_STARTED.json',dict(process=own,utc=utc(),one_formal_reservation=True))
    base=read(ROOT/'config/BASE.json');cfg=read(ROOT/'config/CONFIG.json');units=read(ROOT/'UNIT_INDEX.json')
    children={};stages=[];fatal=None;stopping=False;max_active=0
    def stop(*_):
        nonlocal stopping
        stopping=True
    for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,stop)
    try:
        for index,stage in enumerate(cfg['stages']):
            if stopping or not admissions_allowed():break
            if not admissions_allowed(stage['model']):
                new_json(chain/f'SKIPPED_MODEL_STAGE_{index}.json',dict(utc=utc(),stage=stage,reason='model engineering fault; preserve unfinished units; independent other model continues'))
                continue
            stage_id=f"{index:02d}_{stage['model']}_{stage['method']}_H{stage.get('H','20_30')}";stage_root=chain/'stages'/stage_id;stage_root.mkdir(parents=True,exist_ok=False)
            current=[u for u in units if all(u[k]==v for k,v in stage.items())]
            assert current and len(current)<=1000
            current.sort(key=lambda u:(u['ordinal'],u['task'],u['source_id'],u['H']))
            if stage['model']=='pi05':
                from pi_phase import run
                row=run(chain,stage_root,stage,current,base,fds,pi_environment,lambda:stopping)
                stages.append(row);max_active=max(max_active,row['peak_live_rollout_contexts'])
                if row['cleanup']['status']!='all_formal_group_members_exited':raise RuntimeError('owned pi05 family remains')
                continue
            workers={};stage_started=time.monotonic();last=0.;peak=0
            for slot in range(24):
                wr=stage_root/'workers'/str(slot);wr.mkdir(parents=True,exist_ok=False)
                for name in ['tmp','cache','xdg']:(wr/name).mkdir(mode=0o700)
                selected=current[slot::24]
                config=dict(output=str(wr),slot=slot,branches=8,units=selected)
                if stage['model']=='X-VLA':
                    x=read(ROOT/'config/X_NATIVE.json');config.update(x)
                    config.update(output=str(wr),slot=slot,branches=8,phase='evaluate',methods=[stage['method']],units=selected,encoder_required=stage['method']!='N',sources=[u['runtime_source'] for u in selected],constructor_seeds={u['task']:min(v['env_seed'] for v in current if v['task']==u['task']) for u in current},socket_path=f'/tmp/cHS_{index}_{slot}_{secrets.token_hex(4)}.sock',ipc_auth=secrets.token_hex(16),base_config=str(ROOT/'config/ENCODER_BASE.json'),engine_config=str(ROOT/'config/X_ENGINE.json'))
                    argv=['/usr/bin/python','-B',str(ROOT/'xcode/gpu_job.py'),'--config',str(wr/'CONFIG.json')]
                    env=dict(os.environ,CUDA_DEVICE_ORDER='PCI_BUS_ID',CUDA_VISIBLE_DEVICES=base['device_list'][slot%8]['gpu_uuid'],VLA_CPU_THREADS='2',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',LP_NUM_THREADS='2',PYTHONDONTWRITEBYTECODE='1')
                else:
                    argv=[base['python'],'-B',str(ROOT/'code/pi_worker.py'),'--config',str(wr/'CONFIG.json')];env=pi_environment(base,wr)
                new_json(wr/'CONFIG.json',config)
                with (wr/'stdout.log').open('xb') as so,(wr/'stderr.log').open('xb') as se:
                    proc=subprocess.Popen(argv,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=so,stderr=se,pass_fds=fds,start_new_session=False)
                workers[slot]=dict(proc=proc,root=wr);children[f'{index}_{slot}']=proc
                new_json(wr/'PROCESS_STARTED.json',dict(utc=utc(),process=process_identity(proc.pid),argv=argv,model=stage['model'],GPU=base['device_list'][slot%8],logical_context_target=8,scientific_units=[u['unit_id'] for u in selected]))
            while any(w['proc'].poll() is None for w in workers.values()):
                if stopping or time.time()>=cfg['absolute_wall_deadline_unix']-60:
                    for w in workers.values():
                        if w['proc'].poll() is None:w['proc'].send_signal(signal.SIGTERM)
                    break
                # Only cutoff closes future admissions; already entered finite
                # episodes drain under their original per-episode wall budget.
                if time.monotonic()-last>=5:
                    active=0;ready=0;progress={};alive=0
                    for slot,w in workers.items():
                        running=w['proc'].poll() is None;alive+=running
                        ready+=running and (w['root']/'MODEL_READY.json').exists()
                        path=w['root']/('CONCURRENCY.json' if stage['model']=='X-VLA' else 'PROGRESS.json')
                        if path.exists():
                            row=read(path);progress[str(slot)]=row
                            if running:active+=row.get('active_contexts',0)
                    peak=max(peak,active);max_active=max(max_active,active)
                    record=dict(utc=utc(),stage=stage,stage_id=stage_id,living_workers=alive,loaded_model_workers=ready,active_rollout_contexts=active,peak_active_rollout_contexts=peak,logical_target=192,model_workers_target=24,contexts_per_model_target=8,branch_batch_size=1,concurrency_kind='cooperative independent live environments; model inference serialized within each replica',workers=progress,holder_policy='all8_off_entire_formal_wave')
                    atomic_json(chain/'HEARTBEAT.json',record);atomic_json(stage_root/'CONCURRENCY.json',record)
                    last=time.monotonic()
                if time.monotonic()-stage_started>1200 and any(w['proc'].poll() is None and not (w['root']/'MODEL_READY.json').exists() for w in workers.values()):
                    for slot,w in workers.items():
                        if w['proc'].poll() is None and not (w['root']/'MODEL_READY.json').exists():w['proc'].send_signal(signal.SIGTERM)
                    new_json(stage_root/'LOAD_TIMEOUT.json',dict(utc=utc(),deadline_seconds=1200,extra_scientific_samples=0));break
                time.sleep(1)
            for slot,w in workers.items():
                try:w['proc'].wait(timeout=60)
                except subprocess.TimeoutExpired:w['proc'].kill();w['proc'].wait()
            # Reap every descendant before changing model/method phase.
            cleanup=drain_group(own['pgid'],own['pid'])
            row=dict(utc=utc(),stage=stage,workers={k:w['proc'].returncode for k,w in workers.items()},peak_live_rollout_contexts=peak,cleanup=cleanup,elapsed_seconds=time.monotonic()-stage_started)
            new_json(stage_root/'RESULT.json',row);stages.append(row)
            if any(row['workers'].values()):
                from faults import pause
                pause(stage['model']+'|stage',stage_root/'RESULT.json','formal worker failure; no blind restart')
                new_json(ROOT/'issues'/(stage_id+'.json'),dict(utc=utc(),kind='technical_stage_gaps',stage=stage,evidence=str(stage_root),success=None,original_failures_preserved=True,automatic_blind_retry=False,independent_next_stage_continues=True,analysis_response_deadline_unix=time.time()+1800))
            if cleanup['status']!='all_formal_group_members_exited':raise RuntimeError('owned stage children remain')
    except BaseException as exc:fatal=dict(error=repr(exc),traceback=traceback.format_exc())
    finally:
        for proc in children.values():
            if proc.poll() is None:proc.send_signal(signal.SIGTERM)
        cleanup=drain_group(own['pgid'],own['pid'])
        for proc in children.values():proc.wait()
        new_json(chain/'MANAGER_EXIT.json',dict(utc=utc(),fatal=fatal,stages=stages,peak_live_rollout_contexts=max_active,cleanup=cleanup,all_owned_processes_exited=cleanup['status']=='all_formal_group_members_exited',elapsed_seconds=time.monotonic()-started))
    return 3 if fatal or any(p.returncode for p in children.values()) or any(s.get('error') or any(s['workers'].values()) for s in stages) else 0
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--chain',required=True);p.add_argument('--stage');a=p.parse_args();raise SystemExit(main(Path(a.chain)))
