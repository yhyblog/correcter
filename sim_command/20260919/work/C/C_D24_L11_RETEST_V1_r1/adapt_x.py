"""Private mechanical adaptation: physical-step yields and per-source state."""
from pathlib import Path
C=Path(__file__).resolve().parents[3];R=C/'results/C/C_D24_L11_RETEST_V1';X=C/'results/C/C_D24_FULL_Q_LOSS_REFRESH_V1'
def change(s,a,b):
    assert s.count(a)==1,(a,s.count(a));return s.replace(a,b)
s=(X/'code/native_client.py').read_text()
s=change(s,'torch.set_num_threads(4)','torch.set_num_threads(2)')
s=change(s,"row=dict(source,method=method,status='entered'", "row=dict(source,unit_id=claim['unit_id'],loss='L11',fit_seed=9101,method=method,status='entered'")
s=change(s,"                    check();observed=observation(obs)","                    check()\n                    if time.monotonic()-begin>1800:raise AdmissionStop('episode wall deadline')\n                    observed=observation(obs)")
s=change(s,"                    if terminal(result) or t==299:","                    yield dict(step=t+1,source_id=sid)\n                    if terminal(result) or t==299:")
s=change(s,"rpc('snapshot')['counters']","rpc('snapshot',source_id=sid)['counters']")
s=change(s,"        if row['status']!='complete':raise RuntimeError('recorded evaluation error; no implicit replay')","        return row")
start=s.index("        for method in cfg['methods']:");end=s.index("        new_json(out/'CLIENT_COMPUTE_DONE.json',",start)
s=s[:start]+'''        from cooperative import capture_rng,restore_rng
        active=[];queue=list(cfg['sources']);completed=[];peak=0;last=0.;ticks=0;all_counters=collections.Counter()
        while active or queue:
            while queue and len(active)<cfg['branches'] and not stopping:
                try:check(True)
                except AdmissionStop:break
                source=queue.pop(0)
                seed=cfg['constructor_seeds'][source['task']];random.seed(seed);np.random.seed(seed)
                env=MetaworldEnv(task=source['task'],obs_type='pixels_agent_pos')
                gen=evaluate_source(env,source,cfg['methods'][0])
                active.append(dict(source=source,env=env,generator=gen,rng=capture_rng(),counters=collections.Counter(),step=0))
            peak=max(peak,len(active))
            if not active:break
            for branch in list(active):
                restore_rng(branch['rng']);counters=branch['counters']
                try:
                    progress=next(branch['generator']);branch['step']=progress['step'];ticks+=1
                except StopIteration as done:
                    completed.append(dict(source_id=branch['source']['source_id'],status=done.value['status']))
                    branch['env'].close();active.remove(branch);all_counters.update(counters)
                finally:branch['rng']=capture_rng()
            if time.monotonic()-last>=5:
                atomic_json(out/'CONCURRENCY.json',dict(at_utc=utc(),slot=cfg['slot'],active_contexts=len(active),peak_contexts=peak,advancing_contexts=[dict(source_id=b['source']['source_id'],step=b['step']) for b in active],completed=len(completed),pending=len(queue),physical_step_advances=ticks,model_replicas=1,external_encoder_replicas=1,batch_size=1,peak_GPU_bytes=int(torch.cuda.max_memory_allocated()),RSS_high_water_KiB=__import__('resource').getrusage(__import__('resource').RUSAGE_SELF).ru_maxrss));last=time.monotonic()
        counters=all_counters
        new_json(out/'CONTEXTS_COMPLETE.json',dict(at_utc=utc(),completed=completed,pending_sources=[s['source_id'] for s in queue],peak_active_contexts=peak,physical_step_advances=ticks))
''' +s[end:]
# Cooperative contexts cannot share the process-wide SIGALRM. The explicit
# wall-clock guard inside each source loop replaces that timer at equal budget.
s=change(s,'with episode_deadline():','with contextlib.nullcontext():')
s=change(s,"    fatal=None\n    try:","    fatal=None;active=[]\n    try:")
s=change(s,"    finally:\n        connection.close();", "    finally:\n        for branch in active:\n            try:branch['generator'].close();branch['env'].close()\n            except BaseException:pass\n        connection.close();")
(R/'xcode/native_client.py').write_text(s)

s=(X/'code/feature_server.py').read_text()
s=change(s,'torch.set_num_threads(4)','torch.set_num_threads(2)')
s=change(s,'meter=Counts();start=',"from cooperative import ContextMeter\n    meter=ContextMeter();start=")
s=change(s,'    fatal=None\n    try:', '    fatal=None;sessions={}\n    try:')
s=change(s,"                    kind=req['kind']",'''                    kind=req['kind']
                    if kind!='close':
                        sid=req['source_id']
                        if kind=='begin':
                            if sid in sessions:raise ValueError('source context already initialized')
                            sessions[sid]=dict(language=None,context=None,step=None,objective=None,counts=Counter(),instruction=req['instruction'])
                        saved=sessions[sid];source=sid
                        language,context,step,objective,counts=(saved[k] for k in ['language','context','step','objective','counts'])
                        features._instruction=saved['instruction'];meter.activate(sid)''')
s=change(s,'                    connection.send(dict(ok=True,seconds=', '''                    if kind!='close':sessions[source].update(language=language,context=context,step=step,objective=objective,counts=counts)
                    connection.send(dict(ok=True,seconds=''')
s=change(s,"        listener.close()", "        listener.close()\n        counts=Counter()\n        for saved in sessions.values():counts.update(saved['counts'])")
s=change(s,'counts=dict(counts),meter=meter.snapshot(),identity=identity','counts=dict(counts),meter_by_context=meter.all(),identity=identity')
(R/'xcode/feature_server.py').write_text(s)
s=(X/'code/gpu_job.py').read_text()
s=change(s,'out.mkdir(parents=True,exist_ok=False)','out.mkdir(parents=True,exist_ok=True)')
(R/'xcode/gpu_job.py').write_text(s)
print('X cooperative adapters prepared')
