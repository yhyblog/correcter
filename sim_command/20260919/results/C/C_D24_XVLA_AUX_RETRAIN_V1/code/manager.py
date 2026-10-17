"""Finite C collection -> eight scratch fits -> new evaluations, one reservation."""
import argparse,os,signal,subprocess,sys,time,traceback,secrets,shutil
from pathlib import Path
import paths
from paths import ROOT,WORKSPACE
from qio import read,new_json,atomic_json,utc,process_identity,sha
from common import runtime_command,reservation_fds
from admission import boundary,before_cutoff
from reservation import send_existing_fd,holder_exit_ack
from process_family import drain_group

stopping=False
def stop(*_):
    global stopping
    stopping=True

def worker_env(slot,label):
    cfg=read(ROOT/'config/BASE.json');local=Path('/tmp/corrector_C_XVLA_AUX_r1')/label/str(slot)
    for p in [local,local/'xdg',local/'tmp']:p.mkdir(mode=0o700,parents=True,exist_ok=True)
    env=dict(os.environ,CUDA_VISIBLE_DEVICES=cfg['device_list'][slot],CUDA_DEVICE_ORDER='PCI_BUS_ID',
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
            if stage=='fit' and any(label.startswith('D_') and p.poll() not in (None,0) for label,p in processes):
                raise RuntimeError('paired D fit failed; stop dependent G0 instead of waiting indefinitely')
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
    cfg=read(ROOT/'config/CONFIG.json');parents=read(ROOT/'SOURCE_MANIFEST.json')['parents'];sources=read(ROOT/'config/TEST_SOURCES.json')['sources'];entries=[]
    for slot in range(8):
        out=ROOT/'stages'/phase/'workers'/str(slot)
        job=dict(cfg,slot=slot,phase=phase,output=str(out),base_config=str(ROOT/'config/ENCODER_BASE.json'),
            engine_config=str(ROOT/'config/ENGINE_CONFIG.json'),socket_path=f'/tmp/corrector_C_XVLA_AUX_r1/{phase}_{slot}.sock',ipc_auth=secrets.token_hex(16))
        if phase=='collect':job['parents']=parents
        else:job.update(sources=sources,methods=methods)
        cp=ROOT/'jobs'/f'{phase}_{slot}.json';new_json(cp,job)
        entries.append((slot,str(slot),['/usr/bin/python','-B',str(ROOT/'code/gpu_job.py'),'--config',str(cp)],worker_env(slot,phase)))
    return entries

def publish_fit():
    cfg=read(ROOT/'config/CONFIG.json');data=read(ROOT/'DATA_SUMMARY.json');fits={};updates=0
    for kind in ['D','G0','Q']:
        for seed in cfg[kind+'_seeds']:
            p=ROOT/'fits'/f'{kind}_{seed}'/'RESULT.json'
            row=read(p) if p.exists() else dict(status='not_fitted',updates=0,reason='supervision gap or technical failure')
            fits[f'{kind}_{seed}']=row;updates+=row['updates']
    if updates>32000:raise RuntimeError('small network update cap exceeded')
    ok=lambda kind:all(fits[f'{kind}_{s}']['status']=='complete' and fits[f'{kind}_{s}']['updates']==4000 for s in cfg[kind+'_seeds'])
    dready=ok('D');gready=dready and ok('G0');qready=ok('Q')
    if qready:
        selected=ROOT/'models/Q_selected';hashes={}
        for i,s in enumerate(cfg['Q_seeds']):
            if fits[f'Q_{s}']['parameters']!=7058:raise RuntimeError('Q parameter budget differs')
            p=selected/'models/refit'/f'member_{i}'/'selected.pt';p.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/'fits'/f'Q_{s}'/'final.pt',p);hashes[str(i)]=sha(p)
        new_json(selected/'ranking.json',dict(horizon=10,model_hashes=hashes,selection='fixed4000 all new X models',seed_group=cfg['Q_seeds']))
        new_json(selected/'config.json',dict(training='B full 7058 parameters each, X train only',loss='L11',updates_each=4000))
    result=dict(status='complete' if dready and gready and qready else 'scientific_gap_or_partial',utc=utc(),members=fits,updates=updates,
        D_ready=dready,G0_ready=gready,Q_ready=qready,base_updates=0,external_encoder_updates=0,
        all_from_scratch=True,seed_group_is_one_ensemble=True,scientific_gaps=data['scientific_gaps'],checkpoint_selection='fixed4000, dev descriptive only')
    atomic_json(ROOT/'FIT_SUMMARY.json',result);return result

def main(chain):
    boundary(True);own=process_identity();fds=reservation_fds()
    if own['pid']!=own['pgid']:raise RuntimeError('manager must own isolated formal group')
    req=read(chain/'REQUEST.json');send_existing_fd(req['socket'],fds[0]);new_json(chain/'HOLDER_EXIT_ACK.json',holder_exit_ack(req))
    new_json(chain/'MANAGER_STARTED.json',dict(process=own,utc=utc(),single_inherited_reservation=True))
    for sig in [signal.SIGINT,signal.SIGTERM,signal.SIGHUP]:signal.signal(sig,stop)
    fatal=None;done=False;begin=time.monotonic()
    try:
        collect=run_processes('collect',resident_entries('collect'),chain,fds)
        prep=run_processes('prepare',[(0,'dataset',runtime_command('mw-pi05-legacy','prepare_data.py'),worker_env(0,'prepare'))],chain,fds)
        if collect['status']!='complete' or prep['status']!='complete':raise RuntimeError('collection/preparation technical gap; preserve results and notify before fit')
        data=read(ROOT/'DATA_SUMMARY.json');cfg=read(ROOT/'config/CONFIG.json');entries=[]
        for slot,(kind,seed) in enumerate([('D',2241),('D',2242),('Q',29301),('Q',29302),('Q',29303),('Q',29304),('G0',2341),('G0',2342)]):
            if not data[kind+'_ready']:continue
            entries.append((slot,f'{kind}_{seed}',runtime_command('mw-pi05-legacy','train_head.py','--kind',kind,'--seed',seed),worker_env(slot,'fit')))
        if entries:run_processes('fit',entries,chain,fds)
        fit=publish_fit()
        methods=(['R']+(['Post','Velocity'] if fit['Q_ready'] else [])) if fit['G0_ready'] else []
        if methods:
            evaluated=run_processes('evaluate',resident_entries('evaluate',methods),chain,fds)
            done=evaluated['status']=='complete' and methods==['R','Post','Velocity'] and data['counts'].get('parent_complete',0)==250
        else:
            new_json(ROOT/'stages/evaluate/RESULT.json',dict(status='scientific_gap',utc=utc(),methods_admitted=[],reason='new G0 unavailable; no forced triggers'))
    except BaseException as exc:fatal=dict(error=repr(exc),traceback=traceback.format_exc())
    finally:
        cleanup=drain_group(own['pgid'],own['pid'])
        new_json(chain/'MANAGER_EXIT.json',dict(utc=utc(),fatal=fatal,cleanup=cleanup,all_owned_processes_exited=True,
            all_stages_complete=done,elapsed_seconds=time.monotonic()-begin,auxiliary_holder_launches=0))
    return 0 if done and fatal is None else 3

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--chain',required=True);sys.exit(main(Path(p.parse_args().chain)))
