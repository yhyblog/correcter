"""Transfer the existing guard's lock FD, never acquire a second formal lock."""
import array
import os
import socket
import struct
import time
from pathlib import Path
from qio import read, process_identity, same_process, new_json, utc


def send_existing_fd(address, fd):
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
        sock.settimeout(30);sock.connect(address)
        fds=array.array('i',[fd]);sock.sendmsg([b'QFD1'],[(socket.SOL_SOCKET,socket.SCM_RIGHTS,fds)])
        if sock.recv(16)!=b'ACK':raise RuntimeError('outer supervisor did not retain reservation FD')


def receive_existing_fd(server, expected_lock, peer_check):
    conn,_=server.accept()
    with conn:
        conn.settimeout(5)
        pid,uid,gid=struct.unpack('3i',conn.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
        row=process_identity(pid)
        if uid!=os.getuid() or not row or row['pid']!=row['pgid'] or not peer_check(row):
            raise RuntimeError('reservation peer identity mismatch')
        data,ancillary,flags,_=conn.recvmsg(16,socket.CMSG_SPACE(array.array('i').itemsize))
        descriptors=[]
        for level,kind,payload in ancillary:
            if level==socket.SOL_SOCKET and kind==socket.SCM_RIGHTS:
                values=array.array('i');values.frombytes(payload[:len(payload)//values.itemsize*values.itemsize]);descriptors.extend(values)
        try:
            if data!=b'QFD1' or len(descriptors)!=1:raise RuntimeError('invalid reservation FD message')
            fd=descriptors[0];os.set_inheritable(fd,False)
            actual=Path('/proc/self/fd',str(fd)).resolve(strict=True)
            if actual!=Path(expected_lock).resolve():raise RuntimeError('wrong reservation descriptor')
            conn.sendall(b'ACK')
            return fd,row
        except BaseException:
            for fd in descriptors:os.close(fd)
            raise


def holder_exit_ack(before, *, status_reader=None, alive=same_process, clock=time.monotonic, pause=time.sleep, seconds=30):
    """Only cached guard status and saved holder process identities. No GPU probe."""
    status_reader=status_reader or (lambda:read('/tmp/gpu_occupancy_guard/status.json'))
    end=clock()+seconds;last=None
    while True:
        last=status_reader();rows=last.get('gpus',{})
        from qoccupancy import session_members
        stopped=all(not alive(p) and not session_members(p) for p in before.get('holder_processes',[]))
        stopped=stopped and all(not alive(p) for p in before.get('holder_descendants',[]))
        reserved=set(rows)==set(map(str,range(8))) and all(r['state']=='reserved' for r in rows.values())
        if last.get('updated',0)>=before['request_unix'] and stopped and reserved:
            return dict(status='all8_holder_processes_exited_before_formal_child',utc=utc(),guard_cached_status=last,
                        old_holder_identities=before.get('holder_processes',[]),old_descendant_identities=before.get('holder_descendants',[]),
                        all_holder_private_sessions_observed_empty=True,extra_GPU_queries=0,
                        successful_guard_poll_count=None,successful_guard_poll_missing_reason='existing client does not persist successful raw polls')
        if clock()>=end:raise RuntimeError('cached all8 holder exit acknowledgement missing; no formal child started')
        pause(min(.2,max(0,end-clock())))
