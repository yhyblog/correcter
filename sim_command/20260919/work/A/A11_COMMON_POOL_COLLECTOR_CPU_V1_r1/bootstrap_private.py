from pathlib import Path
import ast,json,hashlib
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
O=B/'results/A/A10_CAUSAL_EVENT_CPU_REPAIR_V1'
P=B/'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1'
C=P/'code';C.mkdir()
for d in ('core','native'): (C/d).mkdir()
for d in ('config','proposal','commands','tests'): (P/d).mkdir()
manifest=json.loads((O/'code/CODE_MANIFEST.json').read_text())
rows=manifest['files'];lineage=[]
for x in rows:
    name=x['path'];q=Path(name)
    if q.is_absolute():name=str(q.relative_to(O/'code'))
    selected=name.startswith('vendor_vla/') or name.startswith('native/') or name in [
        'core/__init__.py','core/event_recorder.py','core/identity.py','core/process_family.py',
        'core/failure_evidence.py','core/handoff.py','core/wave_timing.py','feature_path.py']
    if not selected:continue
    src=O/'code'/name;raw=src.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==x['sha256'],name
    dst=C/name;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(raw)
    lineage.append(dict(path=name,origin=str(src),origin_sha256=x['sha256']))
# Keep exact loader block, omit all Q/D/G0 construction and guidance imports.
source=(O/'code/numeric_setup.py').read_text()
source=source[:source.index('    original_load=torch.load')]
source=source.replace('pc.n_action_steps=20','pc.n_action_steps=10')
a=source.index('    from corrector.critic import')
z=source.index('    ckpt=Path',a)
source=source[:a]+source[z:]
source+="    projection=meter.call('load_spatial_projection',lambda:torch.from_numpy(np.load(cfg['projection'],allow_pickle=False)).to(device),{'projection_loads':1})\n    versions=[(p,p._version) for p in list(policy.parameters())+list(policy.buffers())]\n    return locals()\n"
(C/'numeric_setup.py').write_text(source)
lineage.append(dict(path='numeric_setup.py',origin=str(O/'code/numeric_setup.py'),
    change='H10 and policy/feature-only setup; remove all Q/guidance/normalizer-transform load; strict loader preserved'))
# New per-attempt caps: same fixed initialization and 300 control steps.
p=C/'native/initialization.py';s=p.read_text().replace("'policy_do_simulation_calls': 16","'policy_do_simulation_calls': 300").replace("'policy_physics_substeps': 213","'policy_physics_substeps': 4000").replace("'native_mj_forward_calls': 226","'native_mj_forward_calls': 510").replace("'policy_mj_forward_calls': 16","'policy_mj_forward_calls': 300");p.write_text(s)
p=C/'native/graphics_contract.py';s=p.read_text()
for k in ('mujoco_scene_updates','render_calls','rgb_readback_calls'):s=s.replace("'"+k+"': 17","'"+k+"': 301")
p.write_text(s)
# Production recorder keeps the real serializer/identity rejection, adds bounded sink.
p=C/'core/event_recorder.py';s=p.read_text()
s=s.replace("synthetic=False):","synthetic=False,writer=None):").replace("        self.path=Path(path)","        self.writer=writer\n        self.path=Path(path)")
s=s.replace("        with self.path.open('a') as stream:\n            stream.write(line);stream.flush();os.fsync(stream.fileno())",
"""        if self.writer is not None:
            self.writer.append(self.path,line.encode())
        else:
            with self.path.open('a') as stream:
                stream.write(line);stream.flush();os.fsync(stream.fileno())""")
p.write_text(s)
# All native JSON writes and ledger appends pass the same future child byte guard.
for name in ('native/native_egl.py','native/initialization.py','native/graphics_contract.py'):
    p=C/name;s=p.read_text();tree=ast.parse(s)
    candidates=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.FunctionDef) and (node.name=='write_new' or node.name=='append'):
            candidates.append(node)
    lines=s.splitlines(True)
    for node in sorted(candidates,key=lambda n:n.lineno,reverse=True):
        if node.name=='write_new':
            replacement="def write_new(path, value):\n    from core.contracts import write_new as bounded_write\n    bounded_write(path,value)\n"
        else:
            indent='    '
            extra="        row={**row,'native_observation_phase':getattr(self,'observation_phase',None)}\n" if name.endswith('graphics_contract.py') else ''
            replacement="    def append(self,row):\n        from core.contracts import append_json\n"+extra+"        append_json(self.path,row)\n"
        lines[node.lineno-1:node.end_lineno]=[replacement]
    p.write_text(''.join(lines))
# Reuse audited meter/reconciler without old task authorization constants.
old=(O/'code/core/contracts.py').read_text()
meter=old[old.index('class Meter:'):]
meter=meter.replace("        with self.path.open('a') as f:\n            f.write(json.dumps(row,allow_nan=False)+'\\n');f.flush();os.fsync(f.fileno())","        append_json(self.path,row)")
head="""import hashlib,json,os,time
from pathlib import Path
PACKAGE=Path(__file__).resolve().parents[2]
CAMPAIGN=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
class ContractError(ValueError):pass
STORE=None
def configure_store(store):
    global STORE
    STORE=store
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()
def read(path):return json.loads(Path(path).read_text())
def write_new(path,value):
    raw=(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\\n').encode()
    if STORE is not None:return STORE.write(path,raw)
    with Path(path).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
def append_json(path,value):
    raw=(json.dumps(value,allow_nan=False)+'\\n').encode()
    if STORE is not None:return STORE.append(path,raw)
    with Path(path).open('ab') as f:f.write(raw);f.flush();os.fsync(f.fileno())
"""
(C/'core/contracts.py').write_text(head+meter)
(P/'INHERITED_CODE.json').write_text(json.dumps(dict(source=str(O),files=lineage,
    old_package_modified=False,large_weights_read_or_hashed=False),indent=2)+'\n')
print(json.dumps(dict(private_files_copied=len(lineage),status='private snapshot created')))
