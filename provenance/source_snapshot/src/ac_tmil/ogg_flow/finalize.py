"""Verify the completed study and seal reproducible deliveries without edits."""
import json
import time
from pathlib import Path
from .common import ROOT,REPO,DOC,read,freeze,file_sha256,implementation_hashes

def main():
    cfg=read(ROOT/'config.json');frozen=read(ROOT/'formal_freeze.json')
    result=json.loads((ROOT/'evaluation.json').read_text())
    assert result['status']=='complete' and result['planned_sources']==30
    assert result['audit']['status']=='passed' and result['denominator']==240
    assert not result['independent_validation_success']
    for name,sha in frozen['code_hashes'].items():assert file_sha256(REPO/name)==sha,name
    for name,sha in frozen['supporting_artifact_hashes'].items():assert file_sha256(REPO/name)==sha,name
    previous=read(ROOT/'provenance/previous.json')
    for name,sha in {**previous['old_files'],**previous['dependencies']}.items():assert file_sha256(Path(name))==sha,name
    ledger=[json.loads(s) for s in (ROOT/'budget/attempts.jsonl').read_text().splitlines()]
    assert len(ledger)==result['audit']['budget']['attempts']<=cfg['budget']['hard_maximum']
    gpu=json.loads(Path('/tmp/gpu_occupancy_guard/status.json').read_text())
    assert time.time()-gpu['updated']<30
    assert len(gpu['gpus'])==8 and all(x['state']=='holder' for x in gpu['gpus'].values())
    freeze(ROOT/'audits/gpu_restore.json',dict(unix=time.time(),status='passed',guard=gpu))
    paths=[REPO/'ACT_RECAP_FLOW_GUIDANCE_PROTOCOL_20260916.md',REPO/'ACT_RECAP_FLOW_GUIDANCE_RESULTS_20260916.md',
        ROOT/'config.json',ROOT/'formal_freeze.json',ROOT/'evaluation.json',ROOT/'audits/preflight.json',
        ROOT/'audits/development.json',ROOT/'audits/cpu_checks.json',ROOT/'audits/gpu_restore.json',ROOT/'budget/attempts.jsonl',
        *sorted(DOC.glob('*')),*sorted((ROOT/'implementation_amendments').rglob('*')),
        REPO/'analysis/ogg_flow_20260916_legacy.py',REPO/'analysis/ogg_flow_checkpoint_check.py',REPO/'analysis/ogg_flow_progress.py']
    files={str(p.relative_to(REPO)):file_sha256(p) for p in paths if p.is_file()}
    files.update(implementation_hashes())
    freeze(ROOT/'audits/delivery.json',dict(status='complete',unix=time.time(),files=files,
        previous_files_unchanged=len(previous['old_files']),dependency_files_unchanged=len(previous['dependencies']),
        simulator_attempts=len(ledger),budget_maximum=3000,development_sources=30,
        primary_result=result['methods']['direct_matched'],development_only=True,independent_validation_success=False))
    print(json.dumps(dict(status='complete',simulator_attempts=len(ledger),sealed_files=len(files))),flush=True)

if __name__=='__main__':main()
