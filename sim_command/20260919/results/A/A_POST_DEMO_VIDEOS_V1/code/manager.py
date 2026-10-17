"""One all8 reservation, frozen candidate arms, incremental video publication."""
import argparse,json,os,secrets,signal,subprocess,sys,time,traceback
from pathlib import Path
from collections import Counter
from paths import ROOT,TASK,CONFIG,OUTPUT
from qio import read,new_json,atomic_json,utc,process_identity
from admission import authority,admissions_allowed,before_cutoff,worker_environment,original_exit_verified,frozen_units,AdmissionClosed
from reservation import send_existing_fd,holder_exit_ack
from wave_timing import held_reservation_fds
from process_family import drain_group
from publication import publish
from demo_video import compare_initial

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--chain',required=True);args=ap.parse_args();chain=Path(args.chain)
    authority();original_exit_verified();own=process_identity();fds=held_reservation_fds()
    if own['pid']!=own['pgid'] or len(fds)!=1:raise ValueError('single inherited formal reservation required')
    req=read(chain/'REQUEST.json');send_existing_fd(req['socket'],fds[0]);new_json(chain/'HOLDER_EXIT_ACK.json',holder_exit_ack(req))
    new_json(chain/'MANAGER_STARTED.json',dict(utc=utc(),process=own,single_reservation=True,purpose='finite real paired qualitative video capture'))
    base=read(ROOT/'config/BASE.json');units=list(frozen_units().values());by_pair={}
    for u in units:by_pair.setdefault(u['candidate_id'],{})[u['method']]=u
    candidates=sorted(map(json.loads,(ROOT/'CANDIDATES.jsonl').read_text().splitlines()),key=lambda c:(c['task_rank'],c['task']))
    local=Path(CONFIG['local_dir']);local.mkdir(exist_ok=True);auth=secrets.token_hex(24)
    servers=[];all_clients=[];pairs={};encoders=[];fatal=None;stopping=False;peak=0;last_pub=0.;lastbeat=0.;ramped=False;first=[]
    limit=read(ROOT/'RESOURCE_ADMISSION.json')['capacity_pairs']
    def request_stop(*_):
        nonlocal stopping
        stopping=True
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,request_stop)
    def check():
        if stopping or not before_cutoff():raise AdmissionClosed('owned finite demo stop/deadline')
        if any(x['proc'].poll() is not None for x in servers):raise RuntimeError('shared model process exited; drain owned wave')
    def launch(script,cfg,kind):
        out=Path(cfg['output']);out.mkdir(parents=True,exist_ok=False)
        for n in ('tmp','cache','xdg'):(out/n).mkdir(mode=0o700)
        cp=out/'CONFIG.json';new_json(cp,cfg)
        with (out/'stdout.log').open('xb') as so,(out/'stderr.log').open('xb') as se:
            p=subprocess.Popen([base['python'],'-B',str(ROOT/'code'/script),'--config',str(cp)],cwd=ROOT,env=worker_environment(base,out),stdin=subprocess.DEVNULL,stdout=so,stderr=se,pass_fds=fds,start_new_session=False)
        new_json(out/'PROCESS.json',process_identity(p.pid));return dict(proc=p,root=out,cfg=cfg,kind=kind)
    def start_arm(pair,method,attempt=1):
        unit=by_pair[pair['candidate']['candidate_id']][method];g=pair['slot'];folder=pair['root']/method/('attempt_%d'%attempt)
        c=dict(unit=unit,attempt=attempt,slot=g,branch_id=unit['uid_hash']+'_a'+str(attempt),output=str(folder),socket_path=str(local/f'model_{g}.sock'),ipc_auth=auth)
        x=launch('demo_client.py',c,'recording');all_clients.append(x);pair['arms'][method]=x
    def start_pair(c):
        loads=Counter(p['slot'] for p in pairs.values() if p['state']=='active');g=min(range(8),key=lambda i:(loads[i],i))
        folder=ROOT/'pairs'/c['candidate_id'];folder.mkdir(parents=True,exist_ok=False)
        new_json(folder/'CANDIDATE.json',c);pair=dict(candidate=c,root=folder,slot=g,arms={},state='active');pairs[c['candidate_id']]=pair
        start_arm(pair,'N');start_arm(pair,'Post');return pair
    def arm_path(x,name):return ROOT/'episodes'/x['cfg']['unit']['uid_hash']/('attempt_%d'%x['cfg']['attempt'])/name
    def state_check(pair):
        gate=pair['root']/'INITIAL_CHECK.json'
        if gate.exists():return
        a,b=(arm_path(pair['arms'][m],'INITIAL.json') for m in ('N','Post'))
        if a.exists() and b.exists():
            aa,bb=read(a),read(b);d=compare_initial(aa,bb);d.update(N_initial=str(a),Post_initial=str(b),N_initial_rgb_sha256=aa['rgb_sha256'],Post_initial_rgb_sha256=bb['rgb_sha256']);new_json(gate,d)
        elif any(x['proc'].poll() is not None for x in pair['arms'].values()):
            new_json(gate,dict(utc=utc(),passed=False,reason='peer technical failure before pair initial check',verified_before_first_policy_call=True))
    def snapshot(force=False):
        nonlocal peak,last_pub
        active=Counter();steps=0
        for x in all_clients:
            if x['proc'].poll() is not None:continue
            p=x['root']/'PROGRESS.json';d=read(p) if p.exists() else {}
            if d.get('active_environment'):active[x['cfg']['slot']]+=1;steps+=d.get('step',0)
        count=sum(active.values());peak=max(peak,count)
        beat=dict(utc=utc(),manager=own,status='formal_demo_recording',model_ready=sum((x['root']/'MODEL_READY.json').exists() for x in servers),active_recording_arms=count,active_by_GPU=dict(active),peak_active_arms=peak,ordinary_capacity_arm_limit=2*limit,logical_target=192,model_replicas=8,observed_steps=steps,started_pairs=len(pairs),published_pairs=sum((OUTPUT/p['candidate']['task']/p['candidate']['candidate_id']/'metadata.json').exists() for p in pairs.values()),holders='all8_off_including_loading_encoding_tail')
        atomic_json(chain/'HEARTBEAT.json',beat)
        if force or time.monotonic()-last_pub>=15:
            publish();last_pub=time.monotonic()
        if beat['model_ready']==8 and steps>=5 and not (ROOT/'STABLE_HANDOFF.json').exists():
            d=dict(beat,task_id=TASK,status='STABLE_HANDOFF',utc=utc(),background_continues=True,no_LLM_gate=True,completion_event=str(ROOT/'outbox/chain_terminal.json'),first_preview_event=str(ROOT/'outbox/first_preview.json'),callback_thread='01a0b91f-7443-71b1-915d-6cdb6d6a1a13',scientific_success_rate_update=False)
            new_json(ROOT/'STABLE_HANDOFF.json',d);new_json(ROOT/'outbox/startup_progress.json',dict(event_id=TASK+'_startup_progress_v1',kind='startup_progress',synthetic=False,utc=utc(),result=str(ROOT/'STABLE_HANDOFF.json')))
    try:
        if not admissions_allowed():raise AdmissionClosed('demo V2 is not active')
        for g in range(8):servers.append(launch('pi_server.py',dict(slot=g,output=str(chain/'models'/str(g)),socket_path=str(local/f'model_{g}.sock'),ipc_auth=auth),'model'))
        end=time.monotonic()+1200
        while not all((x['root']/'MODEL_READY.json').exists() for x in servers):
            check();atomic_json(chain/'HEARTBEAT.json',dict(utc=utc(),status='model_loading',model_ready=sum((x['root']/'MODEL_READY.json').exists() for x in servers),holders='all8_off'))
            if time.monotonic()>end:raise TimeoutError('actual planned model load deadline')
            time.sleep(2)
        new_json(ROOT/'MODELS_READY.json',dict(utc=utc(),count=8,model_services=[str(x['root']/'MODEL_READY.json') for x in servers],L11_fit9101=True))
        while True:
            check()
            for pair in list(pairs.values()):
                if pair['state']!='active':continue
                state_check(pair)
                if any(x['proc'].poll() is None for x in pair['arms'].values()):continue
                rows={};retried=False
                for m,x in list(pair['arms'].items()):
                    p=arm_path(x,'RESULT.json')
                    if p.exists():rows[m]=read(p)
                    else:rows[m]=dict(status='technical_failure',success=None,terminal=False,reason='client exited without terminal record',exit_code=x['proc'].returncode)
                    if rows[m].get('retry_allowed') and x['cfg']['attempt']==1 and admissions_allowed():start_arm(pair,m,2);retried=True
                if retried:continue
                pair['rows']=rows
                good=all(x.get('status')=='complete' and x.get('terminal') and x.get('video') and not x.get('recording_incomplete') and not x.get('cleanup') for x in rows.values())
                qualified=good and rows['N']['success'] is False and rows['Post']['success'] is True
                pair['qualified_recordings']=qualified;pair['state']='awaiting_encode' if qualified else 'done'
                if not qualified:
                    status='unqualified' if good or all(r['status']=='initial_state_rejected' for r in rows.values()) else 'technical_missing'
                    new_json(pair['root']/'PAIR_RESULT.json',dict(utc=utc(),status=status,candidate=pair['candidate'],N=rows['N'],Post=rows['Post'],retries_not_allowed_for_valid_outcome=True))
            for pair in pairs.values():
                if pair['state']!='awaiting_encode' or sum(x['proc'].poll() is None for x in encoders)>=2:continue
                cfg=dict(output=str(ROOT/'encoders'/pair['candidate']['candidate_id']),candidate=pair['candidate'],N=str(arm_path(pair['arms']['N'],'RESULT.json')),Post=str(arm_path(pair['arms']['Post'],'RESULT.json')))
                x=launch('compose_pair.py',cfg,'CPU_composition');encoders.append(x);pair['encoder']=x;pair['state']='encoding'
            for pair in pairs.values():
                if pair['state']=='encoding' and pair['encoder']['proc'].poll() is not None:
                    p=pair['root']/'ENCODE_RESULT.json';result=read(p) if p.exists() else dict(status='publication_error',reason='encoder exited without result')
                    new_json(pair['root']/'PAIR_RESULT.json',dict(utc=utc(),status='qualified' if result['status']=='published' else 'publication_error',candidate=pair['candidate'],encoding=result,N_result=str(arm_path(pair['arms']['N'],'RESULT.json')),Post_result=str(arm_path(pair['arms']['Post'],'RESULT.json'))))
                    pair['state']='done';snapshot(True)
            if not ramped and len(first)==8:
                ramped=all(all((x['root']/'PROGRESS.json').exists() and (read(x['root']/'PROGRESS.json').get('step',0)>=5 or x['proc'].poll() is not None) for x in p['arms'].values()) for p in first)
                if ramped:new_json(chain/'FIRST_PLANNED_PROGRESS.json',dict(utc=utc(),planned_pairs=8,extra_GPU_preflight=0,all_pair_initial_checks_saved=True))
            slots=limit if ramped else 8
            if admissions_allowed():
                for c in candidates:
                    if c['candidate_id'] in pairs:continue
                    task_pairs=[p for p in pairs.values() if p['candidate']['task']==c['task']]
                    qualified=sum(p.get('qualified_recordings',False) for p in task_pairs)
                    # Reserves are admitted only to replace a concluded unqualified
                    # candidate. Three active/qualified pairs is the task maximum.
                    inflight=sum(p['state']!='done' and not p.get('qualified_recordings',False) for p in task_pairs)
                    if qualified>=3:
                        folder=ROOT/'pairs'/c['candidate_id'];folder.mkdir(parents=True,exist_ok=False);new_json(folder/'PAIR_RESULT.json',dict(utc=utc(),status='not_needed',reason='three qualified recording pairs already completed; any pending encoding remains CPU-only',candidate=c));pairs[c['candidate_id']]=dict(candidate=c,root=folder,state='done',slot=-1,arms={});continue
                    if qualified+inflight>=3:continue
                    if sum(p['state']=='active' for p in pairs.values())>=slots:break
                    p=start_pair(c)
                    if len(first)<8:first.append(p)
            if time.monotonic()-lastbeat>=3:snapshot();lastbeat=time.monotonic()
            if len(pairs)==len(candidates) and all(p['state']=='done' for p in pairs.values()):break
            if not admissions_allowed() and all(p['state']=='done' for p in pairs.values()):break
            time.sleep(.3)
    except BaseException as exc:
        fatal=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc());new_json(chain/'FAILURE.json',dict(utc=utc(),fatal=fatal))
    finally:
        for x in all_clients+encoders:
            if x['proc'].poll() is None:x['proc'].terminate()
        end=time.monotonic()+30
        while any(x['proc'].poll() is None for x in all_clients+encoders) and time.monotonic()<end:time.sleep(.2)
        for x in all_clients+encoders:
            if x['proc'].poll() is None:x['proc'].kill()
            x['proc'].wait();new_json(x['root']/'PROCESS_EXIT.json',dict(utc=utc(),exit_code=x['proc'].returncode))
        for x in servers:atomic_json(x['root']/'STOP.json',dict(utc=utc(),reason='all recording and composition processes exited'))
        end=time.monotonic()+90
        while any(x['proc'].poll() is None for x in servers) and time.monotonic()<end:time.sleep(.3)
        for x in servers:
            if x['proc'].poll() is None:x['proc'].terminate()
        cleanup=drain_group(own['pgid'],own['pid'])
        for x in servers:x['proc'].wait()
        publication=publish(terminal=True);summary=read(ROOT/'SUMMARY.json') if (ROOT/'SUMMARY.json').exists() else None
        new_json(chain/'MANAGER_EXIT.json',dict(utc=utc(),fatal=fatal,clients=[dict(path=str(x['root']),exit_code=x['proc'].returncode) for x in all_clients],encoders=[dict(path=str(x['root']),exit_code=x['proc'].returncode) for x in encoders],servers=[dict(path=str(x['root']),exit_code=x['proc'].returncode) for x in servers],cleanup=cleanup,all_owned_processes_exited=cleanup['status']=='all_formal_group_members_exited',summary=summary,peak_active_arms=peak,publication=publication))
    return 3 if fatal else 0

if __name__=='__main__':raise SystemExit(main())
