"""Release-only process runner. CPU tests do not invoke this runner."""
import os,resource,signal,subprocess
from pathlib import Path
from budget import STORAGE
def limits():
    # Virtual address cap also bounds resident host RAM. CUDA virtual-address
    # compatibility is not measured; failure is terminal, never auto-relaxed.
    for key,n in [(resource.RLIMIT_AS,STORAGE['process_address_space_hard_bytes']),
                  (resource.RLIMIT_FSIZE,STORAGE['attempt_record_bytes']),
                  (resource.RLIMIT_CORE,0)]:resource.setrlimit(key,(n,n))
def run(command,*,cwd,stdout,stderr,env=None,pass_fds=(),new_session=False):
    with Path(stdout).open('xb') as so,Path(stderr).open('xb') as se:
        child=subprocess.Popen(command,cwd=cwd,env=env,pass_fds=pass_fds,start_new_session=new_session,
            stdout=so,stderr=se,preexec_fn=limits)
        def forward(sig,_):
            if child.poll() is None:
                try:os.killpg(child.pid,sig) if new_session else child.send_signal(sig)
                except ProcessLookupError:pass
        old={s:signal.signal(s,forward) for s in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP)}
        try:return child.wait()
        finally:
            if child.poll() is None:
                # Preserve guard ownership until its own drain barrier returns.
                try:os.killpg(child.pid,signal.SIGTERM) if new_session else child.send_signal(signal.SIGTERM)
                except ProcessLookupError:pass
                child.wait()
            for s,f in old.items():signal.signal(s,f)
