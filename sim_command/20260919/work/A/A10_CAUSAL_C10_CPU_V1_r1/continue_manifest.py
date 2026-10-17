from pathlib import Path
import json,hashlib
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919');P=B/'results/A/A10_CAUSAL_C10_CPU_V1';O=B/'results/A/A10_PV_HANDOFF_CPU_REPAIR_V1';N=B/'results/A/A10_TORCH_UUID_ABI_CPU_REPAIR_V1'
ext={};superseded=[]
for source in [O/'EXTERNAL_SOURCE_MANIFEST.json',N/'EXTERNAL_SOURCE_MANIFEST.json']:
 for x in json.loads(source.read_text())['files']:
  if x['path'] in ext and ext[x['path']]['sha256']!=x['sha256']:
   assert x['path']==str(B.parents[2]/'gpu_occupancy_guard.py')
   assert ext[x['path']]['sha256']=='7910c567a47ddf68294d92fc9698cc780aeb130ddefde0337414bfcd88cb85a4'
   superseded.append(dict(path=x['path'],old_sha256=x['sha256'],new_sha256=ext[x['path']]['sha256'],reason='Accepted A10_GUARD_HANDOFF_INSTALL_V1 exact installation supersedes native lineage guard'))
   continue
  ext[x['path']]=dict(x,verification_now='inherited accepted lineage SHA; no fresh large weight or driver/library scan')
x=B/'results/A/A10_PREFLIGHT_REVISION_R2/preflight_v4/external_source_manifest.json'
ext[str(x)]=dict(path=str(x),sha256=hashlib.sha256(x.read_bytes()).hexdigest(),size_bytes=x.stat().st_size)
with (P/'EXTERNAL_SOURCE_MANIFEST.json').open('x') as f:json.dump(dict(schema='causal_C10_external_v1',files=list(ext.values()),inherited_from=[str(O/'EXTERNAL_SOURCE_MANIFEST.json'),str(N/'EXTERNAL_SOURCE_MANIFEST.json')],explicit_supersession=superseded,full_environment_binary_fingerprint=False),f,indent=2);f.write('\n')
print('External manifest:',len(ext),'inherited refs; explicit guard supersession',superseded)
