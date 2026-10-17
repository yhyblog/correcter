"""Attempt accounting tests on temporary CPU-only fixtures, not the live ledger."""
from concurrent.futures import ThreadPoolExecutor
import json
import pytest
from . import storage, protocol


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(storage,'ROOT',tmp_path/'outputs')
    monkeypatch.setattr(storage,'LOCK_PATH',tmp_path/'lock')
    monkeypatch.setattr(storage,'CACHE_PATH',tmp_path/'cache')
    document=tmp_path/'unit-test-only.txt'
    document.write_text('No simulator permission; isolated arithmetic fixture')
    def check(config,stage,*,used=0,total_used=0,requested=1,resource='simulator_attempts'):
        if stage!='p0' or used+requested>5 or total_used+requested>5:
            raise ValueError('budget reached')
    monkeypatch.setattr(protocol,'require_stage_budget',check)
    return storage.AttemptLedger({'analysis_approval':{'document_path':str(document),
        'document_sha256':storage.sha256(document),'protocol_sha256':'unit-stub'}})


def test_failures_keep_attempts_and_cache_loss_rebuilds(ledger):
    first=ledger.reserve('p0','failed_capture','unit')
    assert first['number']==1
    storage.CACHE_PATH.unlink()
    second=ledger.reserve('p0','retry','unit')
    assert second['number']==2
    rows=[json.loads(x) for x in (storage.ROOT/'budget/attempts.jsonl').read_text().splitlines()]
    assert len(rows)==2 and rows[0]['kind']=='failed_capture'


def test_concurrent_claims_never_exceed_hard_limit(ledger):
    def reserve(i):
        try:return ledger.reserve('p0','cpu-fixture',str(i))['number']
        except ValueError:return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        result=list(pool.map(reserve,range(12)))
    assert sorted(x for x in result if x is not None)==[1,2,3,4,5]
    assert len((storage.ROOT/'budget/attempts.jsonl').read_text().splitlines())==5


def test_existing_artifact_cannot_be_overwritten_or_escape_new_root(ledger,tmp_path):
    path=storage.ROOT/'record.json'
    storage.dump(path,{'kept':True})
    with pytest.raises(FileExistsError):storage.dump(path,{'changed':True})
    with pytest.raises(ValueError):storage.dump(tmp_path/'outside.json',{})
    assert json.loads(path.read_text())=={'kept':True}
