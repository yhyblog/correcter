"""Narrow engineering correction: durable exclusive commit, bounded IO retries."""
import errno, os, time, uuid
from pathlib import Path

def exclusive_commit(path,value,canonical,sync_dir,limit=32*1024**2):
    path=Path(path);raw=canonical(value)
    if len(raw)>limit:raise ValueError('control record byte limit')
    path.parent.mkdir(parents=True,exist_ok=True)
    end=time.monotonic()+30;temp=path.with_name(path.name+'.commit.'+uuid.uuid4().hex)
    while True:
        linked=False
        try:
            if path.exists():
                if temp.exists() and os.stat(temp).st_ino==os.stat(path).st_ino and path.read_bytes()==raw:
                    temp.unlink();return path
                raise FileExistsError(errno.EEXIST,'exclusive outcome already exists',str(path))
            with temp.open('wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
            try:os.link(temp,path);linked=True
            except FileExistsError:
                # Never accept somebody else's existing outcome as our commit.
                if os.stat(temp).st_ino!=os.stat(path).st_ino:raise
                linked=True
            sync_dir(path.parent);temp.unlink();return path
        except OSError as exc:
            if exc.errno not in {errno.EIO,errno.ESTALE,errno.ENOTCONN,errno.EINTR,errno.EAGAIN} or time.monotonic()>=end:raise
            if linked:
                # The original immutable file has already committed. Do not
                # perform the scientific action again to repair an fsync error.
                if path.read_bytes()==raw:
                    try:temp.unlink()
                    except OSError:pass
                    return path
            time.sleep(.25)
