"""CPU-only preparation. Sources and controls are frozen before outcomes."""
import json,os,shutil,socket,time
from pathlib import Path
import paths
from paths import CODE,ROOT,LEGACY,QROOT,CAMPAIGN,TRAIN_ROOT
from common import seed,uid,read,write,identity

def main():
    if (ROOT/'CONFIG.json').exists():raise RuntimeError('already prepared; do not overwrite frozen protocol')
    ROOT.mkdir(parents=True,exist_ok=True);(CODE/'vendor').mkdir(exist_ok=True)
    for name in ['numeric_engine.py','counts.py','qio.py','resident_egl.py','render_context.py']:
        shutil.copy2(LEGACY/'code'/name,CODE/'vendor'/name)
    # The old renderer used per-job caps; this finite campaign reuses processes.
    p=CODE/'vendor/resident_egl.py';s=p.read_text()
    s=s.replace('self.renderer_reported = False',"""self.journal.caps.update({k:2000000 for k in self.journal.caps})
        original_call=self.journal.call
        frequent={'egl_make_current_calls','egl_error_queries','mujoco_scene_updates','render_calls','rgb_readback_calls','mujoco_set_buffer_calls','mujoco_render_context_creations','mujoco_render_context_frees','offscreen_viewer_creations'}
        def counted(key,fn,*,check=None,cleanup=False):
            if key not in frequent or self.journal.counts.get(key,0)<2:
                return original_call(key,fn,check=check,cleanup=cleanup)
            self.journal.counts[key]+=1
            value=fn()
            if check is not None and not check(value):raise RuntimeError('graphics call failed: '+key)
            return value
        self.journal.call=counted
        self.renderer_reported = False""")
    s=s.replace('super().finish()',"new_json(self.destination/'GRAPHICS_AGGREGATE_COUNTS.json',dict(counts=self.journal.counts,per_frame_ledger=False,startup_ledger_only=True))\n        super().finish()")
    p.write_text(s)
    base=read(LEGACY/'config/BASE.json');engine=read(LEGACY/'config/PI_ENGINE.json')
    # Observe this host's device identities without entering CUDA.
    import subprocess
    rows=subprocess.check_output(['nvidia-smi','--query-gpu=index,name,uuid,pci.bus_id,driver_version,memory.total','--format=csv,noheader,nounits'],text=True)
    devices=[]
    for row in rows.splitlines():
        i,name,uuid,pci,driver,mem=[v.strip() for v in row.split(',')]
        devices.append(dict(gpu_index=int(i),gpu_model=name,gpu_uuid=uuid,pci_bus_id=pci.lower().replace('00000000:','0000:'),driver=driver,memory_mib=int(mem)))
    assert len(devices)==8
    base['device_list']=devices;base['device']=devices[0];base['native']['device']=devices[0]
    base['native']['cuda_environment']['CUDA_VISIBLE_DEVICES']=','.join(d['gpu_uuid'] for d in devices)
    # Reuse the established read-only local driver-library isolation. No shared edits.
    write(ROOT/'BASE.json',base);write(ROOT/'ENGINE.json',engine)
    for loss in ['L00','L10','L01','L11']:assert (QROOT/(loss+'_s9101')/'ranking.json').exists()
    old=read(CAMPAIGN/'results/A/A_D24_FULL_Q_LOSS_SELECTION_V1/SOURCE_INDEX.json')['source_sets']
    taskinfo={s['task']:s['instruction'] for s in old['DEV']};assert len(taskinfo)==5
    known={(s['task'],int(s['env_seed'])) for rows0 in old.values() for s in rows0}
    for split in ['train','validation','test']:
        for p in (TRAIN_ROOT/'branches'/split).glob('*'):
            try:t,n=p.name.rsplit('__',1);known.add((t,int(n)))
            except ValueError:pass
    sources=[]
    for split,n in [('validation',10),('test',20)]:
        for j in range(n):
            for t,ins in sorted(taskinfo.items()):
                e=seed('environment',split,t,j)%(2**31-1)
                assert (t,e) not in known;known.add((t,e))
                sources.append(dict(source_id=f'MECH1_{split}_{t}_{j:03d}',parent_episode_id=f'{t}__{e}',task=t,instruction=ins,env_seed=e,policy_seed=seed('policy',split,t,j),split=split,ordinal=j,cuts=[5,25,75]))
    write(ROOT/'SOURCES.json',sources)
    config=dict(version=1,host=socket.gethostname(),thread=os.environ['CODEX_THREAD_ID'],prepared=time.time(),deadline_unix=time.time()+96*3600,source_counts={'validation':50,'test':100},max_cut_count=450,plan_draws=4,suffixes=['native10','deploy10'],random_sign_seeds=[0,1,2],target_branches_per_gpu=24,gpu_count=8,total_episode_budget=300,threshold_quantiles=[.9,.7,.5],max_attempts_per_unit=2,wall_hours=96,python=base['python'],local_dir='/tmp/corrector_mechanism_20260924_'+os.environ['CODEX_THREAD_ID'][:8])
    write(ROOT/'CONFIG.json',config);write(ROOT/'IDENTITY.json',dict(**identity(),devices=devices))
    write(ROOT/'AUTHORIZATION.json',dict(authority='Current user explicitly requested implementing and running experiment packages A–E in this thread',thread=config['thread'],historical_deadline_superseded_for_these_new_units_only=True,scope='pi05 five-task independent mechanism/trigger/cost supplement; no old main/SFT/475 collection reruns',shared_dispatch_modified=False,final_Q='L11_s9101',training=['risk_341','risk_342','nod_341','nod_342'],status='authorized',limits=config))
    jobs=[dict(id=uid('collect',s['source_id']),kind='collect',source=s) for s in sources]
    write(ROOT/'JOBS_collect.json',jobs)
    write(ROOT/'SPLIT_CHECK.json',dict(status='passed',unique_parent_sources=len(known),new_sources=len(sources),overlap_with_checked_historical_sources=0,checked=['prior D/G0 branch source directories train/validation/test','D24 full Q development/main/ablation source index'],limitation='Independent reset seeds and parent episodes on the same five tasks; not unseen-task or VLA zero-shot transfer. No claim of full simulator-state inequality.',split_unit='parent episode; never candidates'))
    write(ROOT/'EVENT_REGISTRATION.json',dict(event_id='MECH1_TERMINAL_'+config['thread'],original_executor_thread=config['thread'],trigger='entire finite supervisor exits, success or failure',result_path=str(ROOT/'RESULT.json'),outbox=str(ROOT/'outbox/TERMINAL.json'),ack_path=str(ROOT/'outbox/HANDLER_ACK.json'),transport_acceptance_is_ack=False,recursive_callbacks=False))
    print(json.dumps(dict(root=str(ROOT),collect_jobs=len(jobs),test_sources=100,validation_sources=50,gpus=len(devices))))

if __name__=='__main__':main()
