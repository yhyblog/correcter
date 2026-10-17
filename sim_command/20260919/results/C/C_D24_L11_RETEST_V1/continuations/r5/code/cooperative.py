"""Per-context global RNG state and physical-step cooperative scheduling.

No vector objective averaging; every numerical call retains batch size one.
"""
import random,time
from collections import Counter
import numpy as np
import torch
def capture_rng():
    return (random.getstate(),np.random.get_state(),torch.get_rng_state(),torch.cuda.get_rng_state())
def restore_rng(state):
    if state is not None:
        random.setstate(state[0]);np.random.set_state(state[1]);torch.set_rng_state(state[2]);torch.cuda.set_rng_state(state[3])
class ContextMeter:
    def __init__(self):self.bank={};self.activate('resident_load')
    def activate(self,key):
        row=self.bank.setdefault(key,dict(entered=Counter(),returned=Counter(),seconds=Counter(),failed=[]))
        self.entered,self.returned,self.seconds,self.failed=(row[x] for x in ['entered','returned','seconds','failed'])
    def call(self,name,fn,units=None,detail=None):
        units=units or {};self.entered.update(units);start=time.monotonic()
        try:
            value=fn();self.returned.update(units);return value
        except BaseException as exc:self.failed.append(dict(name=name,error=repr(exc)));raise
        finally:self.seconds[name]+=time.monotonic()-start
    def snapshot(self):return dict(entered=dict(self.entered),returned=dict(self.returned),seconds=dict(self.seconds),failed=self.failed)
    def all(self):return {k:{c:dict(v) if isinstance(v,Counter) else v for c,v in r.items()} for k,r in self.bank.items()}
