"""Exclusive, bounded new-output writer. Failed partial files are retained."""
import hashlib,json,os
from pathlib import Path
class StorageDenied(RuntimeError):pass
class Store:
    def __init__(self,root,byte_limit=512*1024**2,record_limit=32*1024**2,
                 file_limit=2048,reserve_bytes=1024**2,write_fn=os.write):
        self.root=Path(root).resolve();self.limit=byte_limit;self.record_limit=record_limit
        self.file_limit=file_limit;self.reserve=reserve_bytes;self.used=0;self.files=set()
        self.write_fn=write_fn;self.serial=0;self.emergency_mode=False
    def path(self,path):
        p=Path(path);p=p if p.is_absolute() else self.root/p
        if not p.resolve().is_relative_to(self.root) or p.is_symlink():raise StorageDenied('output escapes private root')
        return p
    def charge(self,p,n,emergency=False):
        emergency=emergency or self.emergency_mode
        if type(n) is not int or n<0 or n>self.record_limit:raise StorageDenied('record hard byte limit')
        if self.used+n>self.limit-(0 if emergency else self.reserve):raise StorageDenied('output hard byte limit')
        if p not in self.files and len(self.files)>=self.file_limit:raise StorageDenied('file hard count limit')
        # Reservation is consumed even if the following syscall partially fails.
        self.used+=n;self.files.add(p)
    def bytes_to_fd(self,fd,raw):
        view=memoryview(raw)
        while view:
            n=self.write_fn(fd,view)
            if type(n) is not int or n<=0:raise OSError('partial writer made no progress')
            view=view[n:]
        os.fsync(fd)
    def write(self,path,raw,emergency=False):
        p=self.path(path)
        if p.exists():raise FileExistsError(p)
        self.charge(p,len(raw),emergency)
        self.serial+=1;tmp=p.with_name(p.name+'.partial_'+str(self.serial))
        p.parent.mkdir(parents=True,exist_ok=True)
        # Keep the completed temporary inode as a hardlink; no deletion, overwrite
        # or race-prone replacement. Payload bytes are not allocated twice.
        fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        try:self.bytes_to_fd(fd,raw)
        finally:os.close(fd)
        os.link(tmp,p)
        directory=os.open(p.parent,os.O_RDONLY)
        try:os.fsync(directory)
        finally:os.close(directory)
        return dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),size_bytes=len(raw))
    def append(self,path,raw,emergency=False):
        p=self.path(path);self.charge(p,len(raw),emergency)
        p.parent.mkdir(parents=True,exist_ok=True)
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
        try:self.bytes_to_fd(fd,raw)
        finally:os.close(fd)
    def json(self,path,value,emergency=False):
        raw=bytearray()
        for chunk in json.JSONEncoder(allow_nan=False,sort_keys=True).iterencode(value):
            encoded=chunk.encode()
            if len(raw)+len(encoded)+1>self.record_limit:raise StorageDenied('JSON record hard byte limit during serialization')
            raw.extend(encoded)
        raw.extend(b'\n')
        return self.write(path,raw,emergency)
