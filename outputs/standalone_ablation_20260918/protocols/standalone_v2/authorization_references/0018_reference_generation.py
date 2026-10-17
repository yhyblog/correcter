"""Preflight-only execution of the EXACT archived joint-generation function.

The production module never imports this module. A local proxy captures V/D raw
outputs without changing engine methods or archived module globals. Existing
source AST and file SHA are checked before compilation; the original function
body and relative read-only helpers are used without rewriting its arithmetic.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import sys
import time
import numpy as np

from .candidates import array_sha,bit_equal

LEGACY_ENGINE=Path(__file__).resolve().parents[1]/'native10_training_20260916/engine.py'
LEGACY_ENGINE_SHA256='43bfe0799c3815e29b06be26475dfbb6c70df7bf431cedc630d9eb7622dd65ea'
LEGACY_AST_PYTHON_MINOR=(3,12)
# Python 3.12 includes FunctionDef.type_params=[] in its native ast.dump.
# The formal lerobot runtime is 3.12; do not strip fields to match a 3.11 dump.
LEGACY_FUNCTION_AST_SHA256='d5f80efca25d652610d1157d44631b75734e47356a4600e3241fa3bd1691b110'


def reference_source_proof():
    if sys.version_info[:2]!=LEGACY_AST_PYTHON_MINOR:
        raise ValueError('Archived AST proof requires the registered Python 3.12 runtime')
    source=LEGACY_ENGINE.read_bytes()
    if hashlib.sha256(source).hexdigest()!=LEGACY_ENGINE_SHA256:
        raise ValueError('Archived generation source SHA changed')
    tree=ast.parse(source,filename=str(LEGACY_ENGINE))
    nodes=[node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=='make_bank']
    if len(nodes)!=1:raise ValueError('Archived generation function is not unique')
    node=nodes[0];digest=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
    if digest!=LEGACY_FUNCTION_AST_SHA256:raise ValueError('Archived generation AST changed')
    return dict(path=str(LEGACY_ENGINE),file_sha256=LEGACY_ENGINE_SHA256,function='Native10Engine.make_bank',
                function_ast_sha256=digest,arithmetic_rewritten=False,
                ast_runtime=dict(python=sys.version.split()[0],python_minor=list(sys.version_info[:2]),
                    executable=sys.executable,serializer='ast.dump(include_attributes=False)',runtime_specific=True)),node


def _compile_reference(config):
    # Called only after the new preflight scope gate; no old READY is consulted.
    from corrector.guidance import FrozenObjective
    from corrector.candidates import construct
    from experiments.native10_training_20260916.protocol import candidate_seed,seed_for
    proof,node=reference_source_proof()
    namespace=dict(__name__='standalone_joint_reference',__package__='experiments.native10_training_20260916',
        config=config,time=time,np=np,FrozenObjective=FrozenObjective,construct=construct,
        candidate_seed=candidate_seed,seed_for=seed_for)
    tree=ast.Module(body=[node],type_ignores=[])
    exec(compile(tree,str(LEGACY_ENGINE),'exec'),namespace)
    return namespace['make_bank'],proof


class _CaptureProxy:
    def __init__(self,engine):
        self._engine=engine;self.captured={};self.proposal_records=[]

    def __getattr__(self,name):return getattr(self._engine,name)

    def propose(self,seed,loss=None):
        name='replan' if loss is None else self._engine.hook.settings['mode']
        if name not in ('replan','velocity','direct') or name in self.captured:
            raise ValueError('Reference generator changed its original proposal order or multiplicity')
        raw,stats=self._engine.propose(seed,loss)
        self.captured[name]=np.array(raw,copy=True)
        self.proposal_records.append(dict(method=name,seed=seed,stats=stats))
        return raw,stats


def generate_reference(engine,observed,case,cut):
    """Return original joint plans/meta/formal arrays plus captured native V/D.

    This diagnostic has its own restored-state attempt and full cost. Captured
    native V/D arrays are NEW reference evidence, never claimed to have existed
    in the historic bank. Production solo generation cannot receive this output.
    """
    from .protocol import require_stage_budget,PREFLIGHT
    if engine.stage!=PREFLIGHT:raise ValueError('Joint reference generation is preflight-only')
    require_stage_budget(engine.study,engine.stage)
    started=time.perf_counter();function,proof=_compile_reference(engine.study)
    proxy=_CaptureProxy(engine);old_mode=engine.hook.settings['mode']
    try:
        plans,metadata,arrays=function(proxy,observed,case,cut)
        if list(proxy.captured)!=['replan','velocity','direct']:
            raise ValueError('Reference must have exactly the original three sampler entries')
        if any(r['stats'].get('fallback') is not None or r['stats'].get('policy_calls')!=1 for r in proxy.proposal_records):
            raise ValueError('Reference fallback blocks exact technical comparison')
        for mode in ('velocity','direct'):
            arrays[mode+'_native_raw']=proxy.captured[mode]
            arrays[mode+'_native_clipped']=np.clip(proxy.captured[mode],-1,1).astype(np.float32)
            arrays[mode+'_native_direction']=arrays[mode+'_native_clipped'][:10].astype(float)-arrays['critic_a0'][:10].astype(float)
        metadata=dict(metadata,reference_only=True,reference_source=proof,reference_stage=engine.stage,
            reference_full_entry_seconds=time.perf_counter()-started,reference_proposal_records=proxy.proposal_records,
            actual_policy_calls=sum(r['stats']['policy_calls'] for r in proxy.proposal_records),
            captured_native_arrays_are_historical=False,production_inputs_supplied=False,restore_included=False)
        return plans,metadata,arrays
    finally:
        engine.hook.begin(None);engine.hook.settings['mode']=old_mode


def compare_archived_identity(new_arrays,new_meta,old_bank_path,*,expected_seal=None):
    """Read-only bank identity comparison AFTER independent solo generation.

    No old candidate, radius or direction is returned as an input to generation.
    The collector separately binds its source/context/cut and original bank seal.
    """
    from experiments.native10_training_20260916.policy5_cost_diagnostic_v1 import _seal,_read,_hash,_npz
    bank=Path(old_bank_path).resolve()
    if expected_seal is not None and _hash(bank/'complete.json')!=expected_seal:
        raise ValueError('Archived source bank seal differs from its registered binding')
    _seal(bank)
    generation=_read(bank/'generation.json');formal=_npz(bank/'formal_directions.npz')
    for name in ('raw_a0','critic_a0','mask'):
        if not bit_equal(new_arrays[name],formal[name]):raise ValueError('New solo differs from archived '+name)
    if (new_meta['base_seed']!=generation['base_seed']
            or new_meta['noise_sha256']!=generation['base_generation']['noise_sha256']):
        raise ValueError('Solo a0 seed/noise differs from archived source bank')
    method=new_meta['method'];post=method=='solo_post'
    if post:
        for name in ('post_command_gradient','post_internal_metric_direction'):
            if not bit_equal(new_arrays[name],formal[name]):raise ValueError('Independent post native direction differs from archive')
    return dict(status='passed',old_bank_path=str(bank),old_bank_seal_sha256=_hash(bank/'complete.json'),
        archived_generation_sha256=_hash(bank/'generation.json'),archived_formal_sha256=_hash(bank/'formal_directions.npz'),
        raw_a0_sha256=array_sha(new_arrays['raw_a0']),raw_a0_bit_exact=True,critic_a0_bit_exact=True,mask_bit_exact=True,
        base_seed_equal=True,initial_noise_equal=True,native_direction_archive_status='bit_exact' if post else 'not_saved_in_archived_bank',
        native_vd_historical_bit_exact_claim=False,comparison_after_independent_generation=True)


audit_saved_source_identity=compare_archived_identity
