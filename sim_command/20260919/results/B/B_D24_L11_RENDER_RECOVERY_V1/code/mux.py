"""Serialized model RPC across real independent rollout processes (batch size 1)."""
import time
import traceback
from multiprocessing.connection import Listener, wait
from pathlib import Path
from admission import boundary
from qio import atomic_json, utc

def serve(cfg, handle, ready):
    out=Path(cfg['output']);listener=Listener(cfg['socket_path'],family='AF_UNIX',authkey=bytes.fromhex(cfg['ipc_auth']),backlog=64)
    sock=listener._listener._socket;connections=[];calls=0;last=0.;active={}
    atomic_json(out/'MODEL_READY.json',ready)
    try:
        while not (out/'STOP.json').exists() or connections:
            boundary()
            for obj in wait([sock,*connections],timeout=1):
                if obj is sock:
                    connections.append(listener.accept());continue
                try:
                    req=obj.recv();branch=req.get('branch_id','default');start=time.monotonic()
                    if req['kind']=='close':
                        obj.send(dict(ok=True,closed=True));connections.remove(obj);obj.close();active.pop(branch,None);continue
                    reply=handle(req)
                    calls+=1;active[branch]=dict(kind=req['kind'],at_unix=time.time(),step=req.get('step'),source_id=req.get('source_id'))
                    obj.send(dict(ok=True,seconds=time.monotonic()-start,**reply))
                except (EOFError,BrokenPipeError,ConnectionResetError):
                    if obj in connections:connections.remove(obj)
                    obj.close()
                except Exception as exc:
                    try:obj.send(dict(ok=False,error=repr(exc),traceback=traceback.format_exc()))
                    except (EOFError,BrokenPipeError):pass
                    atomic_json(out/'LAST_REQUEST_ERROR.json',dict(utc=utc(),error=repr(exc),traceback=traceback.format_exc(),request={k:v for k,v in req.items() if k in ('kind','branch_id','source_id','step')}))
            if time.monotonic()-last>5:
                atomic_json(out/'RPC_HEARTBEAT.json',dict(utc=utc(),connections=len(connections),active_branches=active,calls=calls,inference_batch_size=1,shared_mutable_environment=False));last=time.monotonic()
    finally:
        for conn in connections:conn.close()
        listener.close()
