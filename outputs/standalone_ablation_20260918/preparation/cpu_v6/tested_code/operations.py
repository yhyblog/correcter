"""Explicit historical/current GPU operations identity; no scientific rebinding."""
from pathlib import Path

from . import storage

WORKSPACE = storage.PACKAGE.parent
REBOUND_NAMES = ('gpu_occupancy_lifecycle.sh', 'gpu_occupancy_guard.py')
RUNTIME_NAMES = (*REBOUND_NAMES, 'gpu_hold.py', 'ACT-RECAP/scripts/run_recap_gpu_wave.py')
DECISION_SHA = 'edc84ad61378d2173198cf406e6a75a738f4049851c54f369ea9d33e73be69ae'


def inherited_files(binding, oldfreeze):
    """Replace exactly two allowed operations digests, preserving old provenance."""
    folder = Path(binding['path']).resolve()
    storage.sealed(folder, binding['seal_sha256'])
    record = storage.read(folder/'binding.json')
    decision = record['decision']
    if decision['sha256'] != DECISION_SHA:
        raise ValueError('Exact operational repair decision required')
    storage.checked(decision['path'], DECISION_SHA)
    oldref = record['old_freeze']
    if storage.read(storage.checked(oldref['path'], oldref['sha256'])) != oldfreeze:
        raise ValueError('Operations provenance belongs to another old freeze')
    auditref = record['dependency_audit']
    audit = storage.read(storage.checked(auditref['path'], auditref['sha256']))
    if (audit.get('status') != 'complete' or audit['old_freeze_sha256'] != oldref['sha256']
            or any(audit.get(k) != 0 for k in ('model_calls','simulator_attempts','optimizer_updates'))):
        raise ValueError('Complete zero-resource inherited dependency audit required')
    rows = audit['files']
    if (len(rows) != len(oldfreeze['files']) or
            {r['path']:r['expected_sha256'] for r in rows} != oldfreeze['files']):
        raise ValueError('Inherited dependency audit inventory differs')
    allowed = {str(WORKSPACE/name) for name in REBOUND_NAMES}
    changes = record['rebindings']
    if ({r['historical_location'] for r in changes} != allowed or len(changes) != len(allowed)
            or {r['path'] for r in rows if r['status'] != 'matched'} != allowed):
        raise ValueError('Only two explicitly reviewed operations files may drift')
    large = audit['large_assets']; oldlarge = oldfreeze.get('large_files_verified_once_then_stat', {})
    if (len(large) != len(oldlarge) or {r['path'] for r in large} != set(oldlarge)
            or any(r['status'] != 'matched' or r['expected'] != oldlarge[r['path']]
                or r['actual_sha256'] != oldlarge[r['path']]['sha256'] for r in large)):
        raise ValueError('Original large scientific assets must retain their SHA')
    files = dict(oldfreeze['files']); lookup = {r['path']:r for r in rows}
    for item in changes:
        name = item['historical_location']; historical = item['historical_snapshot']; current = item['current']
        if (current['path'] != name or historical['sha256'] != oldfreeze['files'][name]
                or lookup[name]['actual_sha256'] != current['sha256']):
            raise ValueError('Old/current operations identity was relabelled')
        storage.checked(historical['path'], historical['sha256'])
        storage.checked(current['path'], current['sha256'])
        files[name] = current['sha256']
    runtime = record['runtime_files']
    expected = {str(WORKSPACE/name) for name in RUNTIME_NAMES} | {'/usr/bin/true'}
    if len(runtime) != len(expected) or {r['path'] for r in runtime} != expected:
        raise ValueError('Complete current lifecycle/guard/holder/wave/no-op closure required')
    for item in runtime:
        storage.checked(item['path'], item['sha256'])
        name = item['path']
        if name in files and files[name] != item['sha256']:
            raise ValueError('Runtime closure attempts an unregistered dependency rebind')
        files[name] = item['sha256']
    return files
