"""Synthetic reference instrumentation and exact archived-source proof only."""
import ast
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pytest
from . import reference_generation as ref
from .test_engine import Stub


def test_exact_archived_ast_proof_is_not_reimplemented_math():
    proof,node=ref.reference_source_proof()
    assert proof['arithmetic_rewritten'] is False and node.name=='make_bank'
    assert hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()==ref.LEGACY_FUNCTION_AST_SHA256
    assert proof['ast_runtime']['python_minor']==[3,12]
    assert proof['ast_runtime']['executable']==sys.executable
    assert proof['ast_runtime']['serializer']=='ast.dump(include_attributes=False)'
    assert node.type_params==[]


def test_actual_archived_path_and_target_runtime_ast_are_both_bound():
    proof,node=ref.reference_source_proof()
    actual=Path(__file__).resolve().parents[1]/'native10_training_20260916/engine.py'
    assert Path(proof['path'])==actual
    assert hashlib.sha256(actual.read_bytes()).hexdigest()==proof['file_sha256']==ref.LEGACY_ENGINE_SHA256
    assert proof['function_ast_sha256']=='d5f80efca25d652610d1157d44631b75734e47356a4600e3241fa3bd1691b110'
    assert proof['ast_runtime']['runtime_specific'] is True


def test_unregistered_ast_runtime_is_rejected(monkeypatch):
    monkeypatch.setattr(ref,'LEGACY_AST_PYTHON_MINOR',(3,11))
    with pytest.raises(ValueError,match='registered Python 3.12'):ref.reference_source_proof()


def test_changed_archived_source_refused_before_compilation(tmp_path,monkeypatch):
    copy=tmp_path/'changed.py';copy.write_bytes(ref.LEGACY_ENGINE.read_bytes()+b'\n# changed\n')
    monkeypatch.setattr(ref,'LEGACY_ENGINE',copy)
    with pytest.raises(ValueError,match='source SHA'):ref.reference_source_proof()


def test_reference_refuses_formal_stage_before_compiler(monkeypatch):
    from . import protocol
    engine=Stub();engine.stage=protocol.FORMAL
    monkeypatch.setattr(ref,'_compile_reference',lambda _:pytest.fail('Formal stage reached reference compiler'))
    with pytest.raises(ValueError,match='preflight-only'):ref.generate_reference(engine,{}, {},5)
    assert engine.calls==[]


def test_proxy_captures_raw_native_without_extra_sampling_or_method_patch(monkeypatch):
    from . import protocol
    engine=Stub();engine.stage=protocol.PREFLIGHT
    monkeypatch.setattr(protocol,'require_stage_budget',lambda *a,**k:None)
    before_method=engine.propose.__func__
    def archived(self,observed,case,cut):
        raw,base=self.propose(9);a0=np.clip(raw,-1,1)
        for mode in ('velocity','direct'):
            self.hook.settings['mode']=mode
            self.propose(9,object())
        return {'replan':raw},dict(base_generation=base),dict(raw_a0=raw,critic_a0=a0)
    monkeypatch.setattr(ref,'_compile_reference',lambda _: (archived,{'synthetic_only':True}))
    plans,meta,arrays=ref.generate_reference(engine,{}, {},5)
    assert engine.propose.__func__ is before_method
    assert [m for _,m in engine.calls]==[None,'velocity','direct'] and meta['actual_policy_calls']==3
    assert arrays['direct_native_raw'][0,0]==np.float32(.03)
    assert arrays['velocity_native_raw'][0,0]==np.float32(.02)
    assert meta['captured_native_arrays_are_historical'] is False and meta['production_inputs_supplied'] is False
    assert engine.hook.settings['mode']=='velocity'


def _archive(tmp_path):
    from experiments.native10_training_20260916.policy5_cost_diagnostic_v1 import _hash
    bank=tmp_path/'bank';bank.mkdir();raw=np.zeros((50,4),np.float32)
    formal=dict(raw_a0=raw,critic_a0=raw.copy(),mask=np.ones((10,4),bool),
                post_command_gradient=np.ones((10,4),np.float32),post_internal_metric_direction=np.ones((10,4),np.float32))
    np.savez(bank/'formal_directions.npz',**formal)
    (bank/'generation.json').write_text(json.dumps(dict(base_seed=9,base_generation=dict(noise_sha256='n'))))
    files={p.name:_hash(p) for p in bank.iterdir()}
    (bank/'complete.json').write_text(json.dumps(dict(status='complete',files=files)))
    meta=dict(method='solo_post',base_seed=9,noise_sha256='n')
    return bank,formal,meta


def test_archived_comparison_no_fake_historical_native_vd_claim(tmp_path):
    bank,arrays,meta=_archive(tmp_path)
    assert ref.compare_archived_identity(arrays,meta,bank)['native_direction_archive_status']=='bit_exact'
    meta['method']='solo_direct';result=ref.compare_archived_identity(arrays,meta,bank)
    assert result['native_direction_archive_status']=='not_saved_in_archived_bank'
    assert result['native_vd_historical_bit_exact_claim'] is False


@pytest.mark.parametrize('change',['raw','noise','post'])
def test_archived_identity_mismatch_rejected(tmp_path,change):
    bank,arrays,meta=_archive(tmp_path)
    if change=='raw':arrays['raw_a0'][0,0]=1
    elif change=='noise':meta['noise_sha256']='x'
    elif change=='post':arrays['post_command_gradient'][0,0]=2
    with pytest.raises(ValueError):ref.compare_archived_identity(arrays,meta,bank)
