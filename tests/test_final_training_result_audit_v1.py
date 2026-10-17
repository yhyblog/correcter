import json
from pathlib import Path
import numpy as np
import pytest
import torch
from experiments.native10_training_20260916 import final_training_result_audit_v1 as mod


def test_double_completion_gate_precedes_all_reads(tmp_path,monkeypatch):
    monkeypatch.setattr(mod,'ROOT',tmp_path)
    model=tmp_path/'models/final/test';model.mkdir(parents=True)
    (model/'complete.json').write_text('{}')
    def forbidden(*args,**kwargs):raise AssertionError('Intermediate data read')
    monkeypatch.setattr(mod,'read',forbidden)
    monkeypatch.setattr(mod.Audit,'seal',forbidden)
    with pytest.raises(RuntimeError,match='AND execution'):mod.audit('missing-config','missing-freeze','test','new')
    assert not (tmp_path/'final_training_audits').exists()


def test_unsafe_version_rejected_before_completion_reads():
    with pytest.raises(ValueError,match='Unsafe'):mod.completed_paths('../other')


@pytest.fixture(scope='module')
def ledger():
    rows=[dict(number=1,stage='training_round1',resource='training_updates',amount=19200,kind='history',identity='old',protocol_sha256='old')]
    before=(json.dumps(rows[0])+'\n').encode()
    for path in ('A','B'):
        for member in range(4):
            for step in range(1,4001):
                rows.append(dict(number=len(rows)+1,stage='training_final',resource='training_updates',amount=1,
                                 kind='critic_optimizer_update',identity=f'v:final:{path}:{member}:{step}',protocol_sha256='new'))
    return before,rows


def encode(rows):return ''.join(json.dumps(x)+'\n' for x in rows).encode()


def test_all_32000_path_member_step_identities_exact(ledger):
    before,rows=ledger
    got=mod.verify_ledger_delta(mod.Audit(),before,encode(rows),'v','new')
    assert got['optimizer_updates']==32000 and got['totals']=={'training_updates':51200}
    assert len(set(got['attempt_numbers']))==32000


@pytest.mark.parametrize('field,value',[('identity','v:final:A:0:1'),('resource','simulator_attempts'),('amount',2),('protocol_sha256','other')])
def test_duplicate_update_or_unauthorized_resource_fails(ledger,field,value):
    before,rows=ledger;changed=[dict(x) for x in rows];changed[-1][field]=value
    with pytest.raises(ValueError):mod.verify_ledger_delta(mod.Audit(),before,encode(changed),'v','new')


def test_history_cannot_be_replaced(ledger):
    before,rows=ledger;changed=[dict(x) for x in rows];changed[0]['amount']=19199
    with pytest.raises(ValueError,match='history'):mod.verify_ledger_delta(mod.Audit(),before,encode(changed),'v','new')


def test_actual_minibatches_match_bytes_and_sealed_hash():
    plan=np.arange(4000*32,dtype=np.int64).reshape(4000,32)%600
    sample=dict(minibatch_plan_sha256=mod.digest_bytes(plan.tobytes()),minibatch_plan_shape=[4000,32],minibatch_plan_dtype='int64')
    mod.verify_minibatches(mod.Audit(),plan,plan.copy(),plan.copy(),sample)
    changed=plan.copy();changed[100,3]+=1
    with pytest.raises(ValueError,match='differ'):mod.verify_minibatches(mod.Audit(),plan,changed,plan,sample)
    with pytest.raises(ValueError,match='dtype'):mod.verify_minibatches(mod.Audit(),plan,plan.astype(float),plan,sample)


def test_frozen_state_byte_drift_or_nonfinite_is_rejected():
    initial={'buffer':torch.tensor([.5]),'weight':torch.tensor([1.])}
    trained={'buffer':torch.tensor([.5]),'weight':torch.tensor([2.])}
    assert mod.verify_checkpoint(mod.Audit(),trained,initial,['weight'])==['weight']
    trained['buffer']=torch.nextafter(trained['buffer'],torch.tensor([1.]))
    with pytest.raises(ValueError,match='Frozen'):mod.verify_checkpoint(mod.Audit(),trained,initial,['weight'])
    trained['buffer']=initial['buffer'];trained['weight']=torch.tensor([float('nan')])
    with pytest.raises(ValueError,match='Nonfinite'):mod.verify_checkpoint(mod.Audit(),trained,initial,['weight'])


def test_full_planned_no_cut_denominator_and_exact_tie_rule():
    p=np.full((4,3,13),.5,np.float32);p[:,0,1]=.75;p[:,2]=np.nan
    y=np.zeros((3,13,4),bool);y[0,1,:2]=True;y[2]=True
    weights=np.ones((3,13),np.float32);weights[:,0]=0;weights[2]=0
    got=mod.selection_metrics(p,y,[True,True,False],weights)
    assert got['selected_slots']==[1,0,0] and got['gain']==2/12
    records=[dict(path='A',step=400,metrics=dict(gain=.1,harms=1,gain_mse=.2)),
             dict(path='B',step=400,metrics=dict(gain=.1,harms=1,gain_mse=.2+1e-14))]
    assert max(records,key=mod.selection_key)['path']=='A' # Scalar audit tolerance is never a ranking tie.
    records[1]['metrics']['gain_mse']=.2
    assert max(records,key=mod.selection_key)['path']=='B'
