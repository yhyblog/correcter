"""Local process primitives used by deployment and the detached CPU self-check."""
import fcntl
import subprocess
from pathlib import Path

def acquire_singleton(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);handle=path.open('a')
    try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:handle.close();return None
    return handle

def detached(argv,*,cwd,log,env):
    with Path(log).open('ab') as stream:
        return subprocess.Popen(argv,cwd=cwd,env=env,stdin=subprocess.DEVNULL,
            stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
