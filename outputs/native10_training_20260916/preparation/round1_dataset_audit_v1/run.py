"""Publish complete round1 train/dev inputs; no simulation/PCA/optimizer."""
from pathlib import Path
import hashlib
import json
import time
import traceback
from datetime import datetime, timezone

from experiments.native10_training_20260916 import storage
from experiments.native10_training_20260916.artifact_loader import load_artifact_dataset, save_audited_dataset

HERE = Path(__file__).resolve().parent
BASE = storage.ROOT / 'main_protocols/round1_v1'

def event(name, **values):
    print(json.dumps(dict(event=name, utc=datetime.now(timezone.utc).isoformat(), **values)), flush=True)

started = time.monotonic()
try:
    config = json.loads((BASE/'config.json').read_text())
    frozen = json.loads((BASE/'freeze.json').read_text())
    for name, expected in frozen['files'].items():
        if storage.sha256(name) != expected:
            raise ValueError('Collection frozen file changed: '+name)
    for name, expected in frozen.get('large_files_verified_once_then_stat', {}).items():
        stat = Path(name).stat()
        observed = dict(bytes=stat.st_size, mtime_ns=stat.st_mtime_ns, inode=stat.st_ino, device=stat.st_dev)
        if any(observed[k] != expected[k] for k in observed):
            raise ValueError('Verified large dependency identity changed: '+name)
    latest = json.loads((storage.ROOT/'progress/watcher/round1_v1_01/latest.json').read_text())
    if latest['completed_primary_slots'] != 400 or latest['worker_failures'] or latest['metadata_errors']:
        raise ValueError('Full 400-slot wave has not closed without technical error')
    registration = dict(config_sha256=storage.sha256(BASE/'config.json'),
        freeze_sha256=storage.sha256(BASE/'freeze.json'),
        loader_sha256=storage.sha256(storage.PACKAGE/'experiments/native10_training_20260916/artifact_loader.py'),
        runner_sha256=storage.sha256(__file__), full_static_inputs=True,
        smoke_seal_reused=False, new_simulator_attempts=0, optimizer_updates=0)
    storage.dump(HERE/'registration.json', registration)
    bundles = {}
    for purpose, rounds, count in [('train', [1], 300), ('development', None, 100)]:
        event('audit_started', purpose=purpose, planned_slots=count)
        tick = time.monotonic()
        bundle = load_artifact_dataset(config, ['round1_labels_v1'], purpose=purpose,
                                       rounds=rounds, completed_collections_only=False)
        audit = bundle['input_audit']
        if audit['status'] != 'passed' or len(audit['episode_ids']) != count:
            storage.dump(HERE/(purpose+'_incomplete_audit.json'), audit)
            raise ValueError('Static full input audit did not pass: '+purpose)
        if audit['missing_artifacts'] or not all(audit['checks'].values()):
            raise ValueError('Missing or invalid full input evidence: '+purpose)
        bundles[purpose] = bundle
        event('audit_passed', purpose=purpose, seconds=time.monotonic()-tick,
              planned_slots=len(audit['episode_ids']), artifacts=len(audit['artifacts']),
              referenced_attempts=len(audit['referenced_attempts']),
              actual_array_sources=len(bundle['packed']['rows']))
    train_ids = set(bundles['train']['input_audit']['episode_ids'])
    dev_ids = set(bundles['development']['input_audit']['episode_ids'])
    assert not train_ids & dev_ids
    assert bundles['train']['budget_snapshot'] == bundles['development']['budget_snapshot']
    assert bundles['train']['scene_registry_snapshot'] == bundles['development']['scene_registry_snapshot']
    phase_attempts = {row['number'] for row in map(json.loads, bundles['train']['budget_snapshot'].splitlines())
                      if row['stage'] == 'round1_labels'}
    referenced = [number for b in bundles.values() for number in b['input_audit']['referenced_attempts']]
    assert len(referenced) == len(set(referenced)) and set(referenced) == phase_attempts
    bindings = {}
    for purpose, bundle in bundles.items():
        version = 'round1_'+purpose+'_full_v1'
        bindings[purpose] = save_audited_dataset(version, bundle)
        storage.dump(HERE/(purpose+'_binding.json'), bindings[purpose])
        event('dataset_published', purpose=purpose, binding=bindings[purpose])
    result = dict(**registration, status='passed', bindings=bindings,
        purpose_ids={purpose:bundle['input_audit']['episode_ids'] for purpose,bundle in bundles.items()},
        purpose_id_intersection=[],
        array_ids={purpose:[r['episode_id'] for r in bundle['packed']['rows']] for purpose,bundle in bundles.items()},
        coverage={purpose:bundle['packed']['metadata'] for purpose,bundle in bundles.items()},
        checks={purpose:bundle['input_audit']['checks'] for purpose,bundle in bundles.items()},
        referenced_attempts=len(referenced), all_stage_attempts_accounted_for=True,
        seconds=time.monotonic()-started,
        ledger_snapshot_sha256=hashlib.sha256(bundles['train']['budget_snapshot']).hexdigest())
    storage.dump(HERE/'result.json', result)
    event('complete', seconds=result['seconds'], referenced_attempts=len(referenced))
except Exception as error:
    storage.dump(HERE/'failure.json', dict(status='failed',error=repr(error),traceback=traceback.format_exc(),
        seconds=time.monotonic()-started,new_simulator_attempts=0,optimizer_updates=0))
    raise
