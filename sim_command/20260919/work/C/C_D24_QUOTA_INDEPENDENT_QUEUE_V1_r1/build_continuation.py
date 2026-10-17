"""Prepare ordinary evaluation entries now; instantiate only after proven exit."""
import ast, hashlib, shutil
from queue_common import *

def replace_once(text,old,new):
    if text.count(old)!=1:raise ValueError('private adapter target changed: '+old[:120])
    return text.replace(old,new,1)

def prepare_templates():
    records=[]
    for original,label in [(X,'X'),(P,'P')]:
        dest=WORK/('template_'+label);dest.mkdir(exist_ok=True)
        for src in sorted((original/'code').glob('*.py')):
            if src.name in ['service.py','train_fit.py']:continue
            target=dest/src.name;shutil.copyfile(src,target)
            records.append(dict(source=ref(src),copy=str(target)))
        path=dest/'paths.py';path.write_text(path.read_text()+f'\nSCIENCE_ROOT=Path({str(original)!r})\n')
        original_admission=(dest/'admission.py').read_text()
        # All numerical gates and original job validation still use the original
        # root and grant. Only run paths, deduplication and continuation differ.
        insertion=original_admission.index('\nfrom qio import')
        original_admission=original_admission[:insertion]+ '\nfrom paths import SCIENCE_ROOT\nROOT=SCIENCE_ROOT\n'+original_admission[insertion:]
        (dest/'base_admission.py').write_text(original_admission)
        (dest/'admission.py').write_text('from base_admission import *\nfrom continuation_adapter import authority,before_cutoff,admissions_allowed,boundary,admit_episode\n')
        for name in ['continuation_adapter.py','atomic_json_commit.py','resume_service.py']:shutil.copyfile(WORK/name,dest/name)
        (dest/'operational_hook.py').write_text('from paths import SCIENCE_ROOT,CAMPAIGN\nimport sys\nsys.path.append(str(CAMPAIGN/"work/C/C_D24_AUTORECOVERY_QUEUE_RULE_V1_r1"))\nimport c_recovery_policy as p\ndef consume(root,component):return p.consume(SCIENCE_ROOT,"quota_continuation_"+component)\ndef record_fault(root,error,**kwargs):return p.record_fault(SCIENCE_ROOT,error,**kwargs)\ndef reject_completed_terminal(path):\n    if path.exists() and p.legal_terminal(p.read(path)):raise RuntimeError("completed terminal cannot replay")\n')
        q=dest/'qio.py';s=q.read_text();start=s.index('def new_json(');end=s.index('\ndef atomic_json',start)
        s=s[:start]+'''def new_json(path,value,limit=32*1024**2):
    from atomic_json_commit import exclusive_commit
    return exclusive_commit(path,value,canonical,sync_dir,limit)
\n'''+s[end:];q.write_text(s)
        if label=='X':
            f=dest/'common.py';s=f.read_text();start=s.index('def claim_attempt(');end=s.index('\ndef claim_work',start)
            f.write_text(s[:start]+'from continuation_adapter import claim_attempt\n\n'+s[end:])
            f=dest/'native_client.py';s=f.read_text()
            s=replace_once(s,"            for source in cfg['sources']:grouped.setdefault(source['task'],[]).append(source)","            from continuation_adapter import allowed\n            for source in cfg['sources']:\n                if allowed(method+'/'+source['source_id']):grouped.setdefault(source['task'],[]).append(source)")
            f.write_text(s)
            f=dest/'selection.py';s=f.read_text().replace('from paths import ROOT,SELECTION,TASK','from paths import ROOT,SELECTION,TASK,SCIENCE_ROOT')
            s=replace_once(s,"is_relative_to(ROOT/'ensembles')","is_relative_to(SCIENCE_ROOT/'ensembles')");f.write_text(s)
            f=dest/'manager.py';s=f.read_text();s=replace_once(s,"entries=training_entries() if stage=='train' else resident_entries('evaluate',['Post','Velocity'])","assert stage=='evaluate', 'continuation never trains'\n        entries=resident_entries('evaluate',['Post','Velocity'])")
            s=s.replace("/tmp/corrector_C_FULLQ_r1/{phase}_{slot}.sock","/tmp/{ROOT.name}_{slot}.sock")
            # Linux AF_UNIX pathname limit: the full task name is intentionally
            # replaced by a short hash, still unique to the continuation.
            s=s.replace("f'/tmp/{ROOT.name}_{slot}.sock'","f'/tmp/Cq_{__import__(\"hashlib\").sha256(str(ROOT).encode()).hexdigest()[:12]}_{slot}.sock'")
            f.write_text(s)
        else:
            f=dest/'resident_worker.py';s=f.read_text()
            s=replace_once(s,"payload=read(command);job=read(payload['job']);validate_job(job);authority()","payload=read(command);job=read(payload['job']);validate_job(job);authority()\n            from continuation_adapter import allowed\n            effective_sources=[v for v in job['sources'] if allowed(job['cell_id']+'__'+v['source_id'])]")
            s=replace_once(s,"for source in job['sources']:","for source in effective_sources:")
            s=replace_once(s,"len(result['episodes'])==len(job['sources'])","len(result['episodes'])==len(effective_sources)");f.write_text(s)
        for p in dest.glob('*.py'):ast.parse(p.read_text(),filename=str(p))
    atomic_json(ROOT/'PREPARED_ENTRYPOINTS.json',dict(utc=utc(),original_sources=records,templates={label:[ref(p) for p in sorted((WORK/('template_'+label)).glob('*.py'))] for label in ['X','P']},scientific_probe_calls=0))

def instantiate(original,units,issue_row,fix,ordinal):
    original=Path(original);qc=__import__('queue_common')
    if not all_original_owners_exited():raise ValueError('healthy original queue has priority')
    prior_runs=runs(original)[1:]
    if any(not family(r)['exited'] for r in prior_runs):raise ValueError('prior continuation still alive')
    label='X' if original==X else 'P';run=C/'results/C'/(original.name+'_quota_cont'+str(ordinal))
    run.mkdir(exist_ok=False)
    templates=read(ROOT/'PREPARED_ENTRYPOINTS.json')['templates'][label]
    (run/'code').mkdir()
    for r in templates:shutil.copyfile(verify(r,base=C),run/'code'/Path(r['path']).name)
    shutil.copytree(original/'config',run/'config')
    for name in ['SOURCE_INDEX.json','SELECTION_CONSUMED.json','SOURCE_PROVENANCE.json','TRANSFER_CONSUMED.json','PREDECESSOR_EXIT.json','PLANNED_JOB_INDEX.json']:
        if (original/name).exists():shutil.copyfile(original/name,run/name)
    shutil.copyfile(original/'CLAIM.json',run/'ORIGINAL_CLAIM.json')
    if original==P:
        jids={u['job_id'] for u in units};index=read(original/'JOB_INDEX.json')
        new_json(run/'JOB_INDEX.json',dict(index,jobs=[r for r in index['jobs'] if r['job_id'] in jids]))
        new_json(run/'DEPENDENCIES_SATISFIED.json',dict(utc=utc(),inherited=ref(original/'TRANSFER_CONSUMED.json'),CPU_continuation=True))
    deadline=snapshot(original/'STAGE_DEADLINE.json')
    # A CPU-only dependency timeout may be carried to the original global cutoff.
    # Once an evaluation stage exists, preserve its original scientific deadline.
    end=min(CUTOFF,time.time()+43200,deadline['deadline_unix'] if deadline.get('stage')=='evaluate' else CUTOFF)
    if end<=time.time():raise ValueError('original scientific stage deadline expired')
    new_json(run/'STAGE_DEADLINE.json',dict(stage='evaluate',deadline_unix=end,original=deadline,maximum_seconds=43200,utc=utc()))
    manifest=dict(utc=utc(),science_root=str(original),run_root=str(run),units=units,original_claim=ref(original/'CLAIM.json'),config=ref(original/'config/CONFIG.json'),selection=ref(original/'SELECTION_CONSUMED.json'),earlier_runs=list(map(str,prior_runs)),issue_id=issue_row['issue_id'],correction=fix,original_sources_seeds_models_unchanged=True,new_unique_scientific_units=0,new_training_updates=0,per_failed_source_corrected_retry_cap=1,notification_or_LLM_dependency=False)
    new_json(run/'CONTINUATION.json',manifest)
    record=ROOT/'continuations'/(run.name+'.json');new_json(record,dict(science_root=str(original),run_root=str(run),manifest=ref(run/'CONTINUATION.json'),state='prepared_not_launched',utc=utc()))
    return run,record

if __name__=='__main__':prepare_templates()

