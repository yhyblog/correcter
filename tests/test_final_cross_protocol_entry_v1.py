"""Real metadata entrypoint composition with synthetic inputs; no model work."""
from types import SimpleNamespace

import pytest

from experiments.native10_training_20260916 import final_fit_protocol_v1 as protocol
from experiments.native10_training_20260916 import final_fit_runner_v1 as runner
from experiments.native10_training_20260916 import final_training_pipeline_v1 as pipeline
from test_final_fit_protocol_v1 import synthetic, prepare


def test_actual_protocol_freezes_all_actual_pipeline_dependencies():
    required = pipeline.pipeline_code_files()
    supplied = protocol.code_files()
    assert required.keys() <= supplied.keys()
    assert all(supplied[path] == digest for path, digest in required.items())
    assert pipeline.NUMERICAL_DECISION_SHA == protocol.NUMERICAL_DECISION_SHA
    assert pipeline._runtime() == protocol.numeric_runtime()


def test_actual_specification_interface_preserves_two_child_protocols(synthetic, monkeypatch):
    frozen = prepare(synthetic)
    config = protocol.verify_frozen(frozen['config'], frozen['freeze'], 'preflight')
    monkeypatch.setattr(pipeline, 'pipeline_code_files', protocol.code_files)
    monkeypatch.setattr(pipeline, 'NUMERICAL_DECISION_SHA', protocol.NUMERICAL_DECISION_SHA)
    spec, design, identity = pipeline._validate_specification(config, 'preflight')
    assert spec['input_bundle'] == synthetic['binding']
    assert identity == synthetic['preview']['identity']
    children = spec['source_bindings']
    assert (children['round1_train']['pipeline_binding']['input_protocol_sha256']
            == children['development']['pipeline_binding']['input_protocol_sha256']
            != children['round2_train']['pipeline_binding']['input_protocol_sha256'])
    assert design['approved_parameters']['training_stages']['final']['max_updates_per_member'] == 4000


def test_runner_uses_real_new_freeze_gate_and_keeps_zero_ledger(synthetic, monkeypatch):
    frozen = prepare(synthetic)
    root = synthetic['root']
    monkeypatch.setattr(runner.storage, 'LOCK_PATH', root/'budget.lock')
    (root/'budget').mkdir()
    (root/'budget/attempts.jsonl').write_bytes(b'')
    calls = []

    def fake_model_work(config, *, version):
        # Only the expensive model stage is stubbed; actual freeze verification
        # and the pipeline's real new specification adapter both run.
        monkeypatch.setattr(pipeline, 'pipeline_code_files', protocol.code_files)
        monkeypatch.setattr(pipeline, 'NUMERICAL_DECISION_SHA', protocol.NUMERICAL_DECISION_SHA)
        spec, _, identity = pipeline._validate_specification(config, 'preflight')
        calls.append((version, identity))
        assert len(spec['source_bindings']) == 3
        return dict(status='passed', numeric_contract='canonical_strict_passed_dense_reported',
                    batch_singleton_bit_exact=False, optimizer_updates=0, simulator_calls=0)

    monkeypatch.setattr(runner, '_pipeline', lambda: SimpleNamespace(preflight=fake_model_work))
    result = runner.execute('preflight', config_path=frozen['config'],
                            freeze_path=frozen['freeze'], version='synthetic_entry')
    assert calls == [('synthetic_entry', synthetic['preview']['identity'])]
    assert result['pipeline_result']['batch_singleton_bit_exact'] is False
    assert result['resources']['preflight_ledger_unchanged'] is True
    assert result['next_stage_authorized'] is False
    assert (root/'budget/attempts.jsonl').read_bytes() == b''


def test_real_preflight_config_cannot_route_runner_into_fit(synthetic, monkeypatch):
    frozen = prepare(synthetic)
    monkeypatch.setattr(runner, '_pipeline', lambda: pytest.fail('Model pipeline reached'))
    monkeypatch.setattr(runner, 'ledger_snapshot', lambda: pytest.fail('Resource ledger reached'))
    with pytest.raises(ValueError):
        runner.execute('fit', config_path=frozen['config'], freeze_path=frozen['freeze'],
                       version='forbidden_fit')
    assert not (synthetic['root']/'final_fit_execution').exists()
