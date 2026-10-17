"""Shared real-controller event serialization with reserved identity rejection."""
from qio import append

def record(path,owned,kind,event):
    row=dict(owned)
    for key,value in event.items():
        if key in owned and value!=owned[key]:raise ValueError('event identity conflict: '+key)
        row[key]=value
    row['event_kind']=kind
    append(path,row,max_bytes=16*1024**2)
    return row
