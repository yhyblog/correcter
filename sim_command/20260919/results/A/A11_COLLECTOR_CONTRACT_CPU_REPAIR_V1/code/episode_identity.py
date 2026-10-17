"""Source identifies the seed proposal; parent groups repeats; episode is an arm."""
from core.contracts import ContractError
def episode_id(parent_source_id,branch):
    if any(type(x) is not str or not x or '/' in x or '\\' in x or len(x)>256 for x in (parent_source_id,branch)):
        raise ContractError('invalid episode identity component')
    # Names are frozen ARMS; reject delimiter ambiguity for the branch.
    if '__' in branch:raise ContractError('ambiguous episode branch')
    return parent_source_id+'__'+branch
def source_fields(source,branch,repeat):
    episode_id(source['parent_source_id'],branch)
    return dict(parent_episode_id=source['parent_source_id'],source_id=source['source_id'],
                initial_state_id=source['parent_source_id']+':s0',branch_id=branch,suffix_id=str(repeat))
