"""Capture live exception objects at handlers; never reconstruct old stacks."""
import traceback
from .contracts import write_new

def record_failure(error,*,branch,stage,category,operation=None,synthetic=False):
    return dict(type=type(error).__name__,message=str(error),branch=branch,stage=stage,
        category=category,operation=operation,synthetic=bool(synthetic),
        traceback=''.join(traceback.format_exception(type(error),error,error.__traceback__)),
        traceback_present=error.__traceback__ is not None,
        traceback_origin='exception object at current handler; never reconstructed from saved error text')

def save_failure(path,error,**context):
    evidence=record_failure(error,**context)
    write_new(path,evidence)
    return evidence

def branch_stage(phase,engine):
    recorder=getattr(engine,'recorder',None)
    return dict(phase=phase,last_committed_event=getattr(recorder,'last_event',None),
        pending_event=getattr(recorder,'pending_event',None),returned_control_steps=getattr(engine,'steps',None))
