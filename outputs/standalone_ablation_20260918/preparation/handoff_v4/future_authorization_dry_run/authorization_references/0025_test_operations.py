"""Read-only operations provenance and negative metadata tests; zero runtime."""
from copy import deepcopy
from pathlib import Path

import pytest

from . import operations, prepare, storage

BINDING = storage.ROOT/'preparation/operational_repair_v1'


@pytest.fixture
def original():
    return storage.read(prepare.OLD_CONFIG.with_name('freeze.json'))


def test_actual_all_inherited_dependencies_only_two_operations_rebound(original):
    result = operations.inherited_files(prepare.ref(BINDING, directory=True), original)
    changed = {name for name,digest in original['files'].items() if result[name] != digest}
    assert changed == {str(operations.WORKSPACE/name) for name in operations.REBOUND_NAMES}
    assert all(result[name] == digest for name,digest in original['files'].items() if name not in changed)
    assert result['/usr/bin/true'] == storage.sha256('/usr/bin/true')
    assert result[str(operations.WORKSPACE/'gpu_hold.py')] == storage.sha256(operations.WORKSPACE/'gpu_hold.py')
    row = storage.read(BINDING/'binding.json')
    assert row['review']['original_gpu_hold_historical_identity_available'] is False
    for change in row['rebindings']:
        assert storage.sha256(change['historical_snapshot']['path']) == original['files'][change['historical_location']]


@pytest.mark.parametrize('fault,match',[
    ('scientific_rebind','Only two'),('wrong_historical_identity','relabelled'),
    ('missing_inventory','inventory'),('large_weight_changed','large scientific'),
    ('runtime_closure_missing','closure'),('current_digest_changed','relabelled')])
def test_invalid_provenance_rejected_before_any_runtime(original,monkeypatch,fault,match):
    real_read = storage.read
    record = deepcopy(real_read(BINDING/'binding.json'))
    audit = deepcopy(real_read(record['dependency_audit']['path']))
    if fault == 'scientific_rebind':record['rebindings'].append(deepcopy(record['rebindings'][0]))
    elif fault == 'wrong_historical_identity':record['rebindings'][0]['historical_snapshot']['sha256'] = '0'*64
    elif fault == 'missing_inventory':audit['files'].pop()
    elif fault == 'large_weight_changed':audit['large_assets'][0]['actual_sha256'] = '0'*64
    elif fault == 'runtime_closure_missing':record['runtime_files'].pop()
    elif fault == 'current_digest_changed':record['rebindings'][0]['current']['sha256'] = '0'*64
    def read(path):
        path = Path(path)
        if path == BINDING/'binding.json':return record
        if path == Path(record['dependency_audit']['path']):return audit
        return real_read(path)
    monkeypatch.setattr(storage,'read',read)
    with pytest.raises(ValueError,match=match):
        operations.inherited_files(prepare.ref(BINDING,directory=True),original)


def test_new_pending_preserves_entire_original_science_and_sources(tmp_path,monkeypatch):
    source = storage.ROOT/'pending/task_document_v1'
    original = storage.read(source/'config.json')
    monkeypatch.setattr(storage,'ROOT',tmp_path)
    output = tmp_path/'pending_ops'
    prepare.pending_operational(source,BINDING,output)
    updated = storage.read(output/'config.json')
    binding = updated.pop('operational_runtime')
    assert updated == original
    assert binding == prepare.ref(BINDING,directory=True)
    contract = storage.read(output/'ready_contract.json')
    assert contract.pop('operational_runtime') == binding
    assert contract == prepare.ready_contract(original)
    with pytest.raises(FileExistsError):prepare.pending_operational(source,BINDING,output)
