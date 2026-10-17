"""Collection intervention evidence; no online G0-trigger assertion."""
from core.contracts import ContractError
def initial_evidence():
    return dict(commitment_entered=False,entry_event_id=None,plan_key=None,plan_replaced=False,
        returned_commitment_steps=0,kind='not_entered',online_G0_triggered=False)
def was_intervened(result):
    e=result['intervention_evidence']
    if e['online_G0_triggered'] is not False or type(e['returned_commitment_steps']) is not int or not 0<=e['returned_commitment_steps']<=10:
        raise ContractError('invalid collection intervention evidence')
    happened=e['commitment_entered'] and e['plan_replaced'] and e['returned_commitment_steps']>0
    if happened and (not result['legal_cut_reached'] or result['restore_level']!='full_state_verified' or type(e['entry_event_id']) is not int):
        raise ContractError('intervention lacks actual entry/state evidence')
    return bool(happened)
