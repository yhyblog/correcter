"""Sixteen full-Q fits or24 resident C evaluation workers, one reservation."""
import argparse,os,signal,subprocess,sys,time,traceback,secrets,shutil
from pathlib import Path
import paths
from paths import ROOT,WORKSPACE
from qio import read,new_json,atomic_json,utc,process_identity,sha
from common import runtime_command,reservation_fds
from admission import boundary,before_cutoff
from reservation import send_existing_fd,holder_exit_ack
from process_family import drain_group
from operational_hook import consume,record_fault

stopping=False
def stop(*_):
    global stopping
    stopping=True

def worker_env(slot,label):
    cfg=read(ROOT/'config/BASE.json');local=Path('/tmp/corrector_C_FULLQ_r1')/label/str(slot)
    for p in [local,local/'xdg',local/'tmp']:p.mkdir(mode=0o700,parents=True,exist_ok=True)
    env=dict(os.environ,CUDA_VISIBLE_DEVICES=cfg['device_list'][slot%8],CUDA_DEVICE_ORDER='PCI_BUS_ID',
        VLA_RENDERER='mesa',XDG_RUNTIME_DIR=str(local/'xdg'),TMPDIR=str(local/'tmp'),PYTHONDONTWRITEBYTECODE='1',
        PYTHONUNBUFFERED='1',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',LP_NUM_THREADS='4',
        HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',CUDA_CACHE_DISABLE='1')
    for k in ['LD_PRELOAD','MUJOCO_EGL_DEVICE_ID','VLA_EGL_DEVICE_ID']:env.pop(k,None)
    return env

def run_processes(stage,entries,chain,fds):
    folder=ROOT/'stages'/stage;folder.mkdir(parents=True,exist_ok=True);processes=[];begin=time.monotonic();last=0.
    try:
        for slot,label,command,env in entries:
            if stopping:raise RuntimeError('manager stopped before stage launch')
            boundary(True)
            claim=ROOT/'claims'/(stage+'_'+label+'.json')
            new_json(claim,dict(stage=stage,slot=slot,command=command,utc=utc(),manager=process_identity(),automatic_retry=False))
            with (folder/(label+'.log')).open('xb') as log:
                p=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env,pass_fds=fds)
            new_json(folder/(label+'_PROCESS.json'),process_identity(p.pid));processes.append((label,p))
        while any(p.poll() is None for _,p in processes):
            boundary()
            if stopping or not before_cutoff():raise RuntimeError('stage manager stop or wall deadline')
            if time.monotonic()-last>=5:
                atomic_json(chain/'HEARTBEAT.json',dict(utc=utc(),stage=stage,living_workers=sum(p.poll() is None for _,p in processes),
                    exits={label:p.poll() for label,p in processes},holder_policy='all holders off throughout one wave'))
                last=time.monotonic()
            time.sleep(.5)
        rows={label:p.wait() for label,p in processes}
        result=dict(status='complete' if all(rc==0 for rc in rows.values()) else 'failed',stage=stage,exit_codes=rows,utc=utc(),elapsed_seconds=time.monotonic()-begin)
        new_json(folder/'RESULT.json',result);return result
    finally:
        for _,p in processes:
            if p.poll() is None:p.terminate()
        for _,p in processes:
            try:p.wait(timeout=30)
            except subprocess.TimeoutExpired:p.kill();p.wait()

def resident_entries(phase,methods=None):
    from selection import consumed_selection
    consume(ROOT,'evaluation_entry')
    selected=consumed_selection()
    # Mandatory Post-only rule applies before any native evaluation worker/model.
    proof=subprocess.run(['/usr/bin/python','-B','/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_PI05_SELECTED_H40_H50_V1/code/validate_post_choice.py',selected['chosen_loss']],check=True,capture_output=True,text=True,timeout=30)
    new_json(ROOT/'POST_SELECTION_GATE.json',dict(utc=utc(),proof=__import__('json').loads(proof.stdout),no_native_GPU_entry_before_gate=True))
    cfg=read(ROOT/'config/CONFIG.json');sources=read(ROOT/'config/TEST_SOURCES.json')['sources'];entries=[]
    cfg.update(chosen_loss=selected['chosen_loss'],own_Q_assets=selected['own_assets'])
    for slot in range(24):
        out=ROOT/'stages'/phase/'workers'/str(slot)
        job=dict(cfg,slot=slot,phase=phase,output=str(out),base_config=str(ROOT/'config/ENCODER_BASE.json'),
            engine_config=str(ROOT/'config/ENGINE_CONFIG.json'),socket_path=f'/tmp/corrector_C_FULLQ_r1/{phase}_{slot}.sock',ipc_auth=secrets.token_hex(16))
        assert phase=='evaluate'
        job.update(sources=sources,methods=methods)
        cp=ROOT/'jobs'/f'{phase}_{slot}.json';new_json(cp,job)
        entries.append((slot,str(slot),['/usr/bin/python','-B',str(ROOT/'code/gpu_job.py'),'--config',str(cp)],worker_env(slot,phase)))
    return entries

def training_entries():
    entries=[]
    for slot,(loss,member) in enumerate((loss,member) for loss in ['L00','L10','L01','L11'] for member in [1041,1042,1043,1044]):
        command=runtime_command('mw-pi05-legacy','train_fit.py','--loss',loss,'--member',member)
        entries.append((slot,f'{loss}_m{member}',command,worker_env(slot,'train')))
    return entries

def main(chain,stage):
    boundary(True);own=process_identity();fds=reservation_fds()
    if own['pid']!=own['pgid']:raise RuntimeError('manager must own isolated formal group')
    req=read(chain/'REQUEST.json');send_existing_fd(req['socket'],fds[0]);new_json(chain/'HOLDER_EXIT_ACK.json',holder_exit_ack(req))
    new_json(chain/'MANAGER_STARTED.json',dict(process=own,utc=utc(),single_inherited_reservation=True))
    for sig in [signal.SIGINT,signal.SIGTERM,signal.SIGHUP]:signal.signal(sig,stop)
    fatal=None;done=False;begin=time.monotonic()
    try:
        entries=training_entries() if stage=='train' else resident_entries('evaluate',['Post','Velocity'])
        evaluated=run_processes(stage,entries,chain,fds)
        done=evaluated['status']=='complete'
    except BaseException as exc:
        fatal=dict(error=repr(exc),traceback=traceback.format_exc())
        record_fault(ROOT,fatal,unit='evaluation_stage',evidence=[str(chain/'MANAGER_STARTED.json')],continuable=['independent pi05 after reliable native family exit'])
    finally:
        cleanup=drain_group(own['pgid'],own['pid'])
        new_json(chain/'MANAGER_EXIT.json',dict(utc=utc(),fatal=fatal,cleanup=cleanup,all_owned_processes_exited=True,
            all_stages_complete=done,elapsed_seconds=time.monotonic()-begin,auxiliary_holder_launches=0))
    return 0 if done and fatal is None else 3

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--chain',required=True);p.add_argument('--stage',required=True,choices=['train','evaluate']);a=p.parse_args();sys.exit(main(Path(a.chain),a.stage))
