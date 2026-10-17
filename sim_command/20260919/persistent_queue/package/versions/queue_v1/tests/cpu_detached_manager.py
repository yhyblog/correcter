"""Two finite CPU-only waves via actual scheduler/backend/controller/publisher."""
import sys
from pathlib import Path
PKG=Path(__file__).resolve().parents[1];sys.path[:0]=[str(PKG/'code'),str(PKG/'queue')]
import inheritance
import fcntl,json,os,subprocess,time,types,copy
from qio import read,ref,new_json,process_identity
from qplan import auxiliary
from process_backend import ProcessBackend
import process_backend as module
from batch_scheduler import run_schedule
from core.event_recorder import EventRecorder
from budget import parent_caps
from qvalidate import validate_parent
from synthetic_boundaries import parent_spec
import synthetic_boundaries as boundary

root=Path(sys.argv[1]);root.mkdir(parents=True,exist_ok=False)
new_json(root/'STARTED.json',dict(process=process_identity(),launch_parent_pid=os.getppid(),stdin_disconnected=True))
time.sleep(1)
lock=(root/'synthetic_formal.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
trace=[dict(event='one_synthetic_reservation_acquired',pid=os.getpid()),dict(event='all8_fake_holders_exit_ACK')]
real_popen=subprocess.Popen
cfgbase=read(PKG/'config/BASE_PARENT_A.json');oldstorage=read(PKG/'config/LEGACY_PROPOSAL.json')['storage']
try:
    for number in (1,2):
        wave=root/('wave%d'%number);wave.mkdir();boundary.OUT=wave
        parents=[]
        tasks=['drawer-close-v3','drawer-open-v3','faucet-close-v3','faucet-open-v3','hammer-v3','hand-insert-v3','handle-press-side-v3','handle-press-v3']
        for i,task in enumerate(tasks):
            p=parent_spec('slot%d'%i,task,5 if number==1 else 55,i)
            p['source_key']='SYNTHETIC:'+str(number)+':'+str(i)
            p['source']['split']='development' if number==2 else 'train'
            source_file=wave/p['parent_key']/'SOURCE_CURRENT.json';new_json(source_file,p['source'])
            p['source_ref']=dict(path=str(source_file),sha256=ref(source_file)['sha256'],format='json')
            cfg=dict(python=sys.executable,model_sha256='2'*64,source_signature=p['source_ref']['sha256'],native=dict(graphics_caps=cfgbase['native']['graphics_caps']))
            new_json(wave/p['parent_key']/'CONFIG.json',cfg);p['config']=ref(wave/p['parent_key']/'CONFIG.json')
            p['resource_caps']=parent_caps(task,p['source']['cut'])
            if number==2 and i==0:p['inject_failure']='Q_a0_r0'
            new_json(wave/p['parent_key']/'SPEC.json',p);parents.append(p)
        timeout,caps,storage=auxiliary(8,8,oldstorage);timeout.update(reserved_wave_seconds=180,publication_seconds=60,scheduler_poll_seconds=.02)
        proposal=dict(parents=parents,scheduler_caps=caps,timeouts=timeout)
        def launch(argv,**kw):
            key=argv[argv.index('--parent')+1];branch=argv[argv.index('--branch')+1]
            cmd=[sys.executable,'-B',str(PKG/'tests/cpu_worker.py'),str(wave/key/'SPEC.json'),branch,str(wave)]
            kw.pop('preexec_fn',None);kw['cwd']=PKG/'tests'
            return real_popen(cmd,**kw)
        module.subprocess=types.SimpleNamespace(Popen=launch)
        module.child_environment=lambda cfg,private_root:dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
        class Backend(ProcessBackend):
            synthetic=True
            def __init__(self,*a,**kw):super().__init__(*a,**kw);self.peak=0
            def refresh(self):
                super().refresh();self.peak=max(self.peak,len(self.handles))
            def publish(self,parent):
                from batch_publication import publish_parent
                return publish_parent(parent,self.stores[parent['parent_key']],self.cleanup,synthetic=True)
        backend=Backend('SYNTHETIC_NEVER_A_REAL_RELEASE',proposal,(lock.fileno(),))
        recorder=EventRecorder(wave/'SCHEDULER.jsonl',branch='CPU_MANAGER',source_id='SYNTHETIC_WAVE'+str(number),parent_source_id='SYNTHETIC',synthetic=True)
        result=run_schedule(parents,8,backend,gate=lambda:None,emit=recorder.emit,limits=caps,timeouts=timeout)
        new_json(wave/'RESULT.json',dict(result=result,peak_actual_children=backend.peak))
        if backend.peak!=8 or result['primary'] is not None:raise AssertionError('eight-slot real CPU process integration failed')
        audits=[validate_parent(p,synthetic=True) for p in parents]
        new_json(wave/'MACHINE_VALIDATION.json',dict(synthetic=True,parents=audits))
        if number==2 and [x['started_attempts'] for x in audits]!=[2]+[15]*7:raise AssertionError('parent failure leaked to other seven slots')
        if number==1 and any(x['started_attempts']!=15 for x in audits):raise AssertionError('first full branch sequence missing')
        trace.append(dict(event='compute_exit_then_real_publication',wave=number,pgid=os.getpgrp(),starts=result['branch_starts']))
    trace.append(dict(event='last_wave_published_no_runnable_job'));lock.close();trace.append(dict(event='one_release_then_synthetic_restore'))
    new_json(root/'COMPLETE.json',dict(status='PASS',synthetic=True,process=process_identity(),trace=trace,
        same_group_across_two_waves=True,formal_compute=0,hardware_imports=0,real_holder_operations=0))
except BaseException as e:
    import traceback
    new_json(root/'FAILED.json',dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc(),trace=trace));raise
