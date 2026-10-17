"""Finite host-local process family, deterministic stages, durable terminal event."""
import argparse,fcntl,json,os,signal,socket,subprocess,time,traceback
from pathlib import Path
import paths
from paths import CODE,ROOT,WORKSPACE
from common import read,write,seed,uid,identity,check,terminal_path

CHILDREN=[]
def launch(args,log,env=None):
    log.parent.mkdir(parents=True,exist_ok=True)
    with log.open('ab') as f:p=subprocess.Popen(args,cwd=WORKSPACE,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,env=env)
    CHILDREN.append(p);return p
def clean():
    for p in CHILDREN:
        if p.poll() is None:p.terminate()
    end=time.time()+30
    while time.time()<end and any(p.poll() is None for p in CHILDREN):time.sleep(.5)
    for p in CHILDREN:
        if p.poll() is None:p.kill()
    for p in CHILDREN:
        try:p.wait(timeout=10)
        except subprocess.TimeoutExpired:raise RuntimeError('owned child did not exit')

def stage(name,jobs,gpus,env,concurrency=24):
    if not jobs:return dict(stage=name,planned=0,complete=0)
    write(ROOT/('JOBS_'+name+'.json'),jobs)
    pending=[j for j in jobs if not terminal_path(j).exists() and not (ROOT/'claims'/(j['id']+'.json')).exists()]
    width=min(len(pending),len(gpus)*concurrency);procs=[];later=[];first=[]
    for i in range(width):
        group=pending[i::width];slot=gpus[i%len(gpus)];out=ROOT/'workers'/name/str(i)
        cfg=out/'CONFIG.json';write(cfg,dict(slot=slot,branch=f'{name}_{i}',output=str(out),kind=group[0]['kind'],jobs=group))
        args=[read(ROOT/'CONFIG.json')['python'],'-B',str(CODE/'worker.py'),str(cfg)]
        if name=='collect' and i>=len(gpus):later.append((args,out/'worker.log'))
        else:
            procs.append(launch(args,out/'worker.log',env))
            if name=='collect':first.append(group[0])
    if later:
        started=time.time()
        while True:
            check();ok=[]
            for j in first:
                folder=terminal_path(j).parent;p=folder/'FIRST_PLANNED_OBSERVATION.json';rp=terminal_path(j)
                if p.exists():ok.append(read(p)['passed'])
                elif rp.exists() and read(rp)['status']=='complete':ok.append(True)
                else:ok.append(False)
            if all(ok):break
            if any(p.poll() is not None for p in procs) and not all(ok):raise RuntimeError('first planned collection failed before observation validation')
            if time.time()-started>1200:raise TimeoutError('first planned observation 20 minutes')
            write(ROOT/'HEARTBEAT.json',dict(time=time.time(),stage='first_planned_observations',passed=sum(ok),planned=len(first)));time.sleep(5)
        write(ROOT/'FIRST_PLANNED_PROGRESS.json',dict(time=time.time(),passed=True,first_units=[j['id'] for j in first],extra_probe_episodes=0))
        for args,log in later:procs.append(launch(args,log,env))
    while any(p.poll() is None for p in procs):
        check();write(ROOT/'HEARTBEAT.json',dict(time=time.time(),stage=name,workers_active=sum(p.poll() is None for p in procs),planned=len(jobs),target_concurrency=width));time.sleep(10)
    counts={}
    for j in jobs:
        status=read(terminal_path(j))['status'] if terminal_path(j).exists() else 'missing';counts[status]=counts.get(status,0)+1
    r=dict(stage=name,planned=len(jobs),counts=counts,exit_codes=[p.returncode for p in procs]);write(ROOT/'stages'/(name+'.json'),r);return r

def build_closed_jobs():
    import numpy as np
    sources=read(ROOT/'SOURCES.json');test=[s for s in sources if s['split']=='test'];values={k:[] for k in ['G0','D5','risk','nod']}
    for s in sources:
        if s['split']!='validation':continue
        for p in (ROOT/'pool'/s['source_id']).glob('cut*/FINAL_SCORE.json'):
            for k,v in read(p)['score'].items():
                if v is not None:values[k].append(v)
    thresholds={k:[float(np.quantile(v,q)) for q in [.9,.7,.5]] for k,v in values.items() if v}
    write(ROOT/'THRESHOLDS.json',dict(method='predeclared validation-state quantiles .9/.7/.5; no success outcomes used',thresholds=thresholds,validation_state_counts={k:len(v) for k,v in values.items()},test_used=False,random=[.1,.3,.5],periodic=[50,20,10]))
    budget=[];cost=[];seen={}
    def add(dest,s,H,trig,thr,method,package):
        key=uid('closed',s['source_id'],H,trig,thr,method)
        if key in seen:return
        j=dict(id=key,kind='closed',source=s,H=H,trigger=trig,threshold=thr,method=method,package=package);dest.append(j);seen[key]=j
    for s in test:
        for trig,ts in dict(thresholds,random=[.1,.3,.5],periodic=[50,20,10]).items():
            for t in ts:add(budget,s,10,trig,t,'R','B')
        for H in [2,5,10,20,30]:add(cost,s,H,'none',None,'N','E')
        for H in [10,20,30]:
            for method in ['R','Post']:add(cost,s,H,'G0',.05,method,'E')
    return budget,cost

def build_banks():
    jobs=[]
    for s in read(ROOT/'SOURCES.json'):
        if s['split']!='test':continue
        for p in sorted((ROOT/'pool'/s['source_id']).glob('cut*/snapshot/STATE.json')):
            for rep in range(4):jobs.append(dict(id=uid('bank',s['source_id'],read(p)['cut'],rep),kind='bank',source=s,state=str(p),rep=rep))
    return jobs

def build_branches(banks):
    import numpy as np
    jobs=[];aliases=[]
    for b in banks:
        rp=terminal_path(b)
        if not rp.exists() or read(rp)['status']!='complete':continue
        r=read(rp);st=read(b['state']);s=b['source'];rep=b['rep'];metadata=read(r['metadata_path'])
        with np.load(r['bank_path']) as z:plans={k:z[k] for k in z.files}
        for suffix in ['native10','deploy10']:
            seen={}
            for arm in ['continue',*plans]:
                C=10
                j=dict(id=uid('branch',s['source_id'],st['cut'],rep,arm,C,suffix),kind='branch',source=s,state=b['state'],rep=rep,arm=arm,C=C,suffix=suffix,bank_path=r['bank_path'],bank_meta=r['metadata_path'],gradient_calls=int(arm[4:]) if arm in ['grad2','grad4'] else (1 if arm in ['L00','L10','L01','L11','no_metric','unified','radius05','radius2'] else 0))
                key=plans[arm][:C].tobytes() if arm!='continue' else b'continue_queue'
                if key in seen:aliases.append(dict(job=j,reuse_unit=seen[key],reason='exact executed raw prefix and identical suffix/RNG/budget'));continue
                seen[key]=j['id'];jobs.append(j)
            # C5 is only the explicit original-target diagnostic under Native H10.
            if suffix=='native10':jobs.append(dict(id=uid('branch',s['source_id'],st['cut'],rep,'R',5,suffix),kind='branch',source=s,state=b['state'],rep=rep,arm='R',C=5,suffix=suffix,bank_path=r['bank_path'],bank_meta=r['metadata_path'],gradient_calls=0))
    write(ROOT/'ALIASES.json',aliases);return jobs

def supervise():
    cfg=read(ROOT/'CONFIG.json');base=read(ROOT/'BASE.json');env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='2',TOKENIZERS_PARALLELISM='false',HF_HOME=base['hf_home'],HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',MUJOCO_GL='egl',PYOPENGL_PLATFORM='egl',MPLCONFIGDIR=str(ROOT/'plot_cache'))
    isolation=Path(base['native']['isolation_root'])
    env['LD_LIBRARY_PATH']=':'.join([str(isolation/'isolation/lib'),base['native']['python_library_directory'],'/usr/lib/x86_64-linux-gnu','/lib/x86_64-linux-gnu'])
    env.update(base['native']['cuda_environment'])
    env['__EGL_VENDOR_LIBRARY_FILENAMES']=str(isolation/'isolation/vendor/10_nvidia.json')
    for k in ['LD_PRELOAD','__EGL_VENDOR_LIBRARY_DIRS','MUJOCO_EGL_DEVICE_ID']:env.pop(k,None)
    signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt('supervisor terminated')))
    signal.signal(signal.SIGINT,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt('supervisor interrupted')))
    stages=[];error=None;servers={};train=[]
    try:
        # Guard has completed the holder handoff before this process starts.
        snapshot=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader'],text=True)
        if snapshot.strip():raise RuntimeError('unexpected GPU compute context before formal model entry: '+snapshot)
        write(ROOT/'HOLDER_EXIT_CONFIRMED.json',dict(time=time.time(),host=socket.gethostname(),compute_contexts=[],scope='all eight GPUs before any model load'))
        for slot in range(8):servers[slot]=launch([cfg['python'],'-B',str(CODE/'server.py'),str(slot)],ROOT/'servers'/str(slot)/'server.log',env)
        for i,(mode,member) in enumerate([('risk',341),('risk',342),('nod',341),('nod',342)]):
            done=ROOT/'heads'/f'{mode}_{member}'/'RESULT.json'
            if done.exists() and read(done)['status']=='complete':continue
            te=dict(env,CUDA_VISIBLE_DEVICES=base['device_list'][i]['gpu_uuid']);train.append(launch([cfg['python'],'-B',str(CODE/'train_heads.py'),mode,str(member)],ROOT/'heads'/f'{mode}_{member}.log',te))
        started=time.time()
        while any(p.poll() is None and not (ROOT/'servers'/str(g)/'MODEL_READY.json').exists() for g,p in servers.items()):
            check()
            if time.time()-started>1800:raise TimeoutError('model readiness 30 minutes')
            write(ROOT/'HEARTBEAT.json',dict(time=time.time(),stage='model_loading',ready=[g for g in servers if (ROOT/'servers'/str(g)/'MODEL_READY.json').exists()]));time.sleep(5)
        gpus=[g for g,p in servers.items() if p.poll() is None and (ROOT/'servers'/str(g)/'MODEL_READY.json').exists()]
        if not gpus:raise RuntimeError('no model server available')
        stages.append(stage('collect',read(ROOT/'JOBS_collect.json'),gpus,env))
        while any(p.poll() is None for p in train):check();write(ROOT/'HEARTBEAT.json',dict(time=time.time(),stage='head_training',active=sum(p.poll() is None for p in train)));time.sleep(10)
        head_ok=all(p.returncode==0 for p in train) and all((ROOT/'heads'/f'{mode}_{member}'/'RESULT.json').exists() for mode in ['risk','nod'] for member in [341,342])
        if head_ok:
            sj=[dict(id=uid('score',s['source_id']),kind='score',source=s) for s in read(ROOT/'SOURCES.json')]
            stages.append(stage('score',sj,gpus,env,1))
        else:write(ROOT/'HEAD_FAILURE.json',dict(exit_codes=[p.returncode for p in train],independent_A_C_D_E_continue=True))
        banks=build_banks();stages.append(stage('banks',banks,gpus,env,1))
        # Record the complete branch manifest before its first outcome is known.
        branches=build_branches(banks);write(ROOT/'JOBS_local.json',branches)
        budget,cost=build_closed_jobs()
        # A/C/D local units use high throughput. E costs have one environment per GPU,
        # after training and all other requests end, with the same warmed model server.
        stages.append(stage('local',branches,gpus,env))
        stages.append(stage('budget',budget,gpus,env))
        stages.append(stage('cost',cost,gpus,env,1))
        from analyze import main as summarize
        summary=summarize()
        write(ROOT/'FORMAL_RESULT.json',dict(status='complete' if all(not x.get('counts',{}).get('technical_failure') and not x.get('counts',{}).get('missing') for x in stages) and head_ok else 'partial',stages=stages,summary=summary,time=time.time()))
    except BaseException as exc:
        error=dict(error=repr(exc),traceback=traceback.format_exc());write(ROOT/'FORMAL_RESULT.json',dict(status='technical_failure',**error,stages=stages,time=time.time()))
    finally:
        for g in servers:
            (ROOT/'servers'/str(g)/'STOP').touch()
        end=time.time()+30
        while time.time()<end and any(p.poll() is None for p in servers.values()):time.sleep(1)
        clean();write(ROOT/'FAMILY_EXIT.json',dict(time=time.time(),all_owned_children_exited=all(p.poll() is not None for p in CHILDREN),child_exit_codes=[p.returncode for p in CHILDREN]))
    return 3 if error else 0

def outer():
    cfg=read(ROOT/'CONFIG.json');local=Path(cfg['local_dir']);local.mkdir(exist_ok=True)
    with (local/'queue.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        write(ROOT/'PROCESS.json',identity())
        result=subprocess.run([str(WORKSPACE/'gpu_occupancy_lifecycle.sh'),'run','--',cfg['python'],'-B',str(CODE/'supervisor.py'),'supervise'],cwd=WORKSPACE,env=dict(os.environ,CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS='300'))
        formal=read(ROOT/'FORMAL_RESULT.json') if (ROOT/'FORMAL_RESULT.json').exists() else dict(status='formal_not_started')
        write(ROOT/'RESULT.json',dict(status=formal['status'],formal=formal,lifecycle_exit=result.returncode,time=time.time(),thread=cfg['thread']))
        event=dict(**read(ROOT/'EVENT_REGISTRATION.json'),status=formal['status'],time=time.time(),transport_is_handler_ack=False)
        write(ROOT/'outbox/TERMINAL.json',event)
        message='本线程补充机制实验队列已终止。请读取 '+str(ROOT/'RESULT.json')+'，核对真实终局并汇总；写 '+str(ROOT/'outbox/HANDLER_ACK.json')+' 确认处理。不要重复启动已领取的科学单元，不要递归注册回调。'
        try:
            r=subprocess.run(['codex','queue','--thread',cfg['thread'],'--message',message],capture_output=True,text=True,timeout=30)
            write(ROOT/'outbox/TRANSPORT.json',dict(exit_code=r.returncode,stdout=r.stdout[-1500:],stderr=r.stderr[-1500:],accepted_not_ack=r.returncode==0))
        except Exception as e:write(ROOT/'outbox/TRANSPORT.json',dict(error=repr(e),outbox_retained=True))

def start():
    check();cfg=read(ROOT/'CONFIG.json')
    with (ROOT/'LAUNCH_CLAIM.json').open('x') as f:json.dump(identity(),f)
    with (ROOT/'supervisor.log').open('ab') as f:p=subprocess.Popen(['/usr/bin/python','-B',str(CODE/'supervisor.py'),'outer'],cwd=WORKSPACE,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
    write(ROOT/'LAUNCH.json',dict(pid=p.pid,time=time.time(),host=socket.gethostname(),thread=cfg['thread']));print('Detached queue launched:',p.pid)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['start','outer','supervise']);a=p.parse_args();raise SystemExit(globals()[a.action]())
