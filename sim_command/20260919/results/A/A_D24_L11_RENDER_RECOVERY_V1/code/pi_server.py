import argparse
import copy
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
import paths
from paths import ROOT,CONFIG
from qio import read,new_json,atomic_json,utc,process_identity
from admission import boundary
from counts import Counts

def main(path):
    cfg=read(path);out=Path(cfg['output']);boundary(True)
    base=copy.deepcopy(read(ROOT/'config/BASE.json'));base['device']=base['device_list'][cfg['slot']];base['native']['device']=base['device']
    from resident_egl import ResidentEGL
    egl=ResidentEGL(base['native'],out,lambda:None);egl.prepare()
    import torch
    torch.set_num_threads(2);device=egl.bind_policy(torch);counts=Counts();started=time.monotonic()
    from numeric_setup import initialize
    from numeric_engine import Engine
    state=initialize(base,out,counts,device)
    engine=Engine(state,CONFIG,out)
    from rpc_state import EngineSessions
    from admission import frozen_units
    from qio import append
    sessions=EngineSessions(engine,counts,frozen_units(),ROOT,lambda row:append(out/'OBSERVATION_RPC_OWNERSHIP.jsonl',dict(utc=utc(),server=process_identity(),**row),8*1024**2))
    def handle(req):
        reply=sessions.handle(req)
        if req['kind']=='snapshot':reply['peak_allocated_bytes']=int(torch.cuda.max_memory_allocated(device))
        return reply
    from mux import serve
    try:serve(cfg,handle,dict(status='ready',utc=utc(),process=process_identity(),slot=cfg['slot'],model='pi05',loss='L11',fit_seed=9101,model_replicas_per_GPU=1,logical_branch_capacity=24,inference_batch_size=1,load_seconds=time.monotonic()-started,GPU_allocated_bytes=int(torch.cuda.memory_allocated(device))))
    finally:
        engine.hook.close();egl.finish_resident();atomic_json(out/'SERVER_RESULT.json',dict(utc=utc(),numeric=counts.snapshot(),peak_allocated_bytes=int(torch.cuda.max_memory_allocated(device))))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);main(p.parse_args().config)
