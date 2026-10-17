"""Check saved requested-delta -> saved float32 command write, no projection.

Only four NPZ inputs already present in INPUT_MANIFEST are opened. No new
capacity, direction, proposal, Q value or gradient is calculated.
"""
import ast
import hashlib
import json
import math
import struct
import zipfile
from pathlib import Path

P=Path(__file__).resolve().parent
manifest=json.loads((P/'INPUT_MANIFEST.json').read_text())
index={r['path']:r for r in manifest['files']}
fields=json.loads((P/'ARRAY_FIELDS_AND_UNITS.json').read_text())['fields']
containers={(r['state'],r['branch']):r['container'] for r in fields
            if r['field']=='requested_delta'}

def parse(data):
    assert data[:6]==b'\x93NUMPY'
    width=2 if data[6]==1 else 4
    length=struct.unpack('<H' if width==2 else '<I',data[8:8+width])[0]
    at=8+width+length
    head=ast.literal_eval(data[8+width:at].decode('latin1'))
    assert not head['fortran_order']
    fmt={'<f4':'f','<f8':'d','|b1':'?'}[head['descr']]
    return [x[0] for x in struct.iter_unpack('<'+fmt,data[at:])]

def f32(value):
    return struct.unpack('<f',struct.pack('<f',value))[0]

rows=[]
for (state,branch),file in sorted(containers.items()):
    path=Path(file)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==index[file]['sha256']
    with zipfile.ZipFile(path) as archive:
        a={name:parse(archive.read(name+'.npy')) for name in
           ['critic_a0','critic_commands','requested_delta','actual_delta','mask']}
    assert len(a['requested_delta'])==len(a['actual_delta'])==40
    error=max(abs(a['critic_commands'][i]-f32(a['critic_a0'][i]+a['requested_delta'][i])) for i in range(40))
    assert error==0
    rows.append(dict(state=state,branch=branch,input=index[file],passed=True,
        relation='saved critic_commands == float32(saved bounded anchor + saved requested_delta)',
        max_abs_write_relation_error=error,
        actual_minus_requested_linf=max(abs(x-y) for x,y in zip(a['actual_delta'],a['requested_delta'])),
        actual_minus_requested_l2=math.sqrt(math.fsum((x-y)**2 for x,y in zip(a['actual_delta'],a['requested_delta']))),
        mask_removed_fraction=sum(not x for x in a['mask'])/40,
        new_candidate_or_projection_generated=False))
assert len(rows)==4
out=dict(status='PASS',checks=4,rows=rows,source_files_modified=0,
         projection_implementation_calls=0,model_calls=0,
         scope='scalar saved-write rounding relations only; no projection replay or capacity search')
with (P/'WRITEBACK_AND_CLIP_CHECKS.json').open('x') as f:
    json.dump(out,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
print(json.dumps(dict(status='PASS',checks=4,max_rounding_linf=max(r['actual_minus_requested_linf'] for r in rows))))
