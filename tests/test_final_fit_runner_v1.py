"""Synthetic execution/ledger tests; no pipeline model operations are called."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.native10_training_20260916 import final_fit_runner_v1 as runner


def row(number,resource='training_updates',stage='training_final',amount=1,protocol='p'):
    return dict(number=number,resource=resource,stage=stage,amount=amount,
        kind='critic_optimizer_update',protocol_sha256=protocol,identity=str(number))


def snapshot(rows):
    raw=b''.join((json.dumps(r)+'\n').encode() for r in rows)
    totals={};stages={}
    for r in rows:
        totals[r['resource']]=totals.get(r['resource'],0)+r['amount']
        part=stages.setdefault(r['stage'],{});part[r['resource']]=part.get(r['resource'],0)+r['amount']
    return dict(raw=raw,rows=rows,totals=totals,stages=stages)


def test_zero_resource_preflight_never_needs_positive_budget_request():
    value=snapshot([row(1,stage='training_round1')])
    report=runner.resource_delta(value,value,'preflight','p')
    assert report['optimizer_updates']==report['simulator_attempts']==0
    assert report['attempt_numbers']==[]


@pytest.mark.parametrize('change', ['simulator','wrong_stage','wrong_protocol','dummy_update','rewrite','remove'])
def test_preflight_budget_change_rejected(change):
    before=snapshot([row(1,stage='training_round1')]);rows=list(before['rows'])
    if change=='rewrite':rows[0]=row(1,stage='training_round1',amount=2)
    elif change=='remove':rows=[]
    else:
        new=row(2)
        if change=='simulator':new['resource']='simulator_attempts'
        if change=='wrong_stage':new['stage']='round2_labels'
        if change=='wrong_protocol':new['protocol_sha256']='other'
        rows.append(new)
    with pytest.raises(ValueError):runner.resource_delta(before,snapshot(rows),'preflight','p')


def test_fit_only_accepts_own_bound_optimizer_stage():
    before=snapshot([row(1,stage='training_round1')])
    assert runner.resource_delta(before,snapshot(before['rows']+[row(2)]),'fit','p')['optimizer_updates']==1
    for changed in [row(2,resource='simulator_attempts'),row(2,stage='training_round1'),row(2,protocol='other'),row(2,amount=2)]:
        with pytest.raises(ValueError):runner.resource_delta(before,snapshot(before['rows']+[changed]),'fit','p')


def test_existing_final_stage_counts_toward_phase_cap():
    before=snapshot([row(1,amount=32000)])
    with pytest.raises(ValueError,match='budget'):
        runner.resource_delta(before,snapshot(before['rows']+[row(2)]),'fit','p')


def environment(tmp_path,monkeypatch):
    monkeypatch.setattr(runner.storage,'ROOT',tmp_path)
    monkeypatch.setattr(runner.storage,'LOCK_PATH',tmp_path/'lock')
    folder=tmp_path/'budget';folder.mkdir()
    (folder/'attempts.jsonl').write_bytes(snapshot([row(1,stage='training_round1')])['raw'])
    config=tmp_path/'config.json';freeze=tmp_path/'freeze.json';config.write_text('{}');freeze.write_text('{}')
    monkeypatch.setattr(runner,'_verify',lambda *args:dict(analysis_approval=dict(protocol_sha256='p')))
    return dict(config_path=config,freeze_path=freeze,version='synthetic')


def test_missing_scope_rejected_before_ledger_model_import_or_output(tmp_path,monkeypatch):
    monkeypatch.setattr(runner.storage,'ROOT',tmp_path)
    def rejected(*args):raise ValueError('not released')
    monkeypatch.setattr(runner,'_verify',rejected)
    monkeypatch.setattr(runner,'_pipeline',lambda:pytest.fail('model pipeline imported'))
    monkeypatch.setattr(runner,'ledger_snapshot',lambda:pytest.fail('ledger reached'))
    with pytest.raises(ValueError,match='not released'):
        runner.execute('preflight',config_path=tmp_path/'missing',freeze_path=tmp_path/'missing2',version='cpu')
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('status', ['passed','pending_numerical_review'])
def test_preflight_receipt_preserves_scientific_status_and_zero_resources(tmp_path,monkeypatch,status):
    args=environment(tmp_path,monkeypatch);calls=[]
    def execute(config,*,version):calls.append(version);return dict(status=status,optimizer_updates=0)
    monkeypatch.setattr(runner,'_pipeline',lambda:SimpleNamespace(preflight=execute))
    result=runner.execute('preflight',**args)
    assert calls==['synthetic']
    assert result['status']==status
    assert result['resources']['preflight_ledger_unchanged'] is True
    assert result['next_stage_authorized'] is False
    directory=Path(result['path']);seal=json.loads((directory/'complete.json').read_text())
    assert seal['scientific_status']==status
    assert (directory/'budget_before.jsonl').read_bytes()==(directory/'budget_after.jsonl').read_bytes()
    with pytest.raises(FileExistsError):runner.execute('preflight',**args)
    assert calls==['synthetic']


def test_pipeline_error_preserves_logs_and_attempts_without_retry(tmp_path,monkeypatch):
    args=environment(tmp_path,monkeypatch);calls=[]
    def error(config,*,version):calls.append(version);raise RuntimeError('synthetic numerical error')
    monkeypatch.setattr(runner,'_pipeline',lambda:SimpleNamespace(preflight=error))
    before=(tmp_path/'budget/attempts.jsonl').read_bytes()
    with pytest.raises(RuntimeError):runner.execute('preflight',**args)
    path=tmp_path/'final_fit_execution/preflight/synthetic'
    report=json.loads((path/'failure.json').read_text())
    assert report['counted_attempts_preserved'] is True and report['automatic_retry'] is False
    assert report['next_stage_automatically_started'] is False
    assert (tmp_path/'budget/attempts.jsonl').read_bytes()==before
    assert calls==['synthetic']


def test_runner_detects_unexpected_preflight_optimizer_write(tmp_path,monkeypatch):
    args=environment(tmp_path,monkeypatch)
    def invalid(config,*,version):
        with (tmp_path/'budget/attempts.jsonl').open('a') as stream:stream.write(json.dumps(row(2))+'\n')
        return dict(status='passed')
    monkeypatch.setattr(runner,'_pipeline',lambda:SimpleNamespace(preflight=invalid))
    with pytest.raises(ValueError,match='changed'):
        runner.execute('preflight',**args)
    assert len((tmp_path/'budget/attempts.jsonl').read_text().splitlines())==2
    assert (tmp_path/'final_fit_execution/preflight/synthetic/failure.json').exists()


def test_fit_receipt_compares_declared_updates_to_charged_ledger(tmp_path,monkeypatch):
    args=environment(tmp_path,monkeypatch)
    def fitted(config,ledger,*,version):
        with (tmp_path/'budget/attempts.jsonl').open('a') as stream:stream.write(json.dumps(row(2))+'\n')
        return dict(status='complete',optimizer_updates=1)
    monkeypatch.setattr(runner,'_pipeline',lambda:SimpleNamespace(run=fitted))
    result=runner.execute('fit',**args)
    assert result['resources']['optimizer_updates']==1
    assert result['resources']['simulator_attempts']==0
