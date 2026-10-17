"""Production private JSONL recorder; standard library only, shared by fixtures."""
from episode_identity import episode_id
import json
import os
from pathlib import Path
from types import MappingProxyType

RESERVED_FIELDS=frozenset({'schema','event_id','event','branch','source_id','parent_source_id','episode_id','split'})
# Synthetic is recorder-owned evidence scope, never supplied by event payload.
PROTECTED_FIELDS=RESERVED_FIELDS | {'synthetic'}

class EventIdentityConflict(ValueError):
    pass

class EventRecorder:
    def __init__(self,path,*,branch,source_id,parent_source_id,split='development',synthetic=False,writer=None):
        self.writer=writer
        self.path=Path(path)
        self.identity=MappingProxyType(dict(schema='private_causal_event_v1',branch=branch,source_id=source_id,
            parent_source_id=parent_source_id,episode_id=episode_id(parent_source_id,branch),split=split,synthetic=bool(synthetic)))
        self.events=0
        self.last_event=None
        self.pending_event=None

    def emit(self,name,**data):
        self.pending_event=name
        conflicts=PROTECTED_FIELDS.intersection(data)
        if conflicts:
            raise EventIdentityConflict('Reserved causal event fields in payload: '+', '.join(sorted(conflicts)))
        next_id=self.events+1
        row=dict(self.identity,event_id=next_id,event=name,**data)
        # Serialize completely before touching the file or committing the ID.
        line=json.dumps(row,allow_nan=False)+'\n'
        if self.writer is not None:
            self.writer.append(self.path,line.encode())
        else:
            with self.path.open('a') as stream:
                stream.write(line);stream.flush();os.fsync(stream.fileno())
        self.events=next_id
        self.last_event=name
        self.pending_event=None
        return row
