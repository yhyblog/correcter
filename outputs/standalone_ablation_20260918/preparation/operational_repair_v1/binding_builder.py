from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,tarfile,difflib,shutil
root=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector');workspace=root.parent;out=root/'outputs/standalone_ablation_20260918/preparation/operational_repair_v1';old=root/'outputs/native10_training_20260916/heldout_protocols/heldout_v1';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();ref=lambda p:dict(path=str(p),sha256=sha(p))
f=json.loads((old/'freeze.json').read_text());audit=json.loads((out/'inherited_dependency_audit.json').read_text());assert {Path(r['path']).name for r in audit['drift']}=={'gpu_occupancy_lifecycle.sh','gpu_occupancy_guard.py'}
archive=old/'code_snapshot.tar.gz';assert sha(archive)=='517013a5e653420b3eb8a3c314702f310eb729775f92390d813a230e46973c11'
changes=[]
with tarfile.open(archive) as tf:
 for name in ('gpu_occupancy_lifecycle.sh','gpu_occupancy_guard.py'):
  original=workspace/name;members=[m for m in tf.getmembers() if m.isfile() and Path(m.name).name==name];assert len(members)==1
  data=tf.extractfile(members[0]).read();assert hashlib.sha256(data).hexdigest()==f['files'][str(original)]
  dest=out/'historical'/name;dest.parent.mkdir(exist_ok=True);dest.write_bytes(data)
  current=out/'current'/name;current.parent.mkdir(exist_ok=True);current.write_bytes(original.read_bytes())
  diff=''.join(difflib.unified_diff(data.decode().splitlines(True),original.read_text().splitlines(True),fromfile='historical/'+name,tofile='current/'+name))
  (out/(name+'.diff')).write_text(diff)
  changes.append(dict(historical_location=str(original),historical_snapshot=ref(dest),archive_member=members[0].name,current=ref(original),current_snapshot=ref(current)))
names=['gpu_occupancy_lifecycle.sh','gpu_occupancy_guard.py','gpu_hold.py','ACT-RECAP/scripts/run_recap_gpu_wave.py'];runtime=[ref(workspace/n) for n in names]+[ref(Path('/usr/bin/true'))]
for row in runtime:
 source=Path(row['path']);dest=out/'current'/source.name
 if not dest.exists():shutil.copyfile(source,dest)
record=dict(schema='standalone_operations_binding_v1',created_utc=datetime.now(timezone.utc).isoformat(),decision=ref(root/'coordination/STANDALONE_ABLATION_OPERATIONAL_REPAIR_DECISION_20260918.md'),old_freeze=ref(old/'freeze.json'),old_code_archive=ref(archive),dependency_audit=ref(out/'inherited_dependency_audit.json'),rebindings=changes,runtime_files=runtime,review=dict(scope='read-only current/historical operations source diff',changed_behavior='holder duty cycle target-util .50 and period .20 only',reservation_release_logic_unchanged=True,restoration='asynchronous guard polling after full-wave command exits; verify actual holders separately',original_gpu_hold_historical_identity_available=False,global_files_modified=False,scientific_files_and_large_weight_unchanged=True,checked_inherited_files=1702,checked_large_assets=1),execution=dict(preflight_real_workers=5,preflight_device_slots=8,preflight_empty_device_slots=3,empty_command=['/usr/bin/true'],empty_slots_model_calls=0,empty_slots_environment_calls=0,empty_slots_attempts=0,formal_workers=32,preflight_attempts=50,formal_attempts=1274),model_calls=0,simulator_attempts=0,optimizer_updates=0)
(out/'binding.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');shutil.copyfile(__file__,out/'binding_builder.py');shutil.copyfile('/tmp/audit_standalone_inherited_dependencies.py',out/'inherited_dependency_audit_builder.py')
files={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()};(out/'complete.json').write_text(json.dumps(dict(status='complete',role='standalone_operational_provenance',files=files),indent=2)+'\n');print(json.dumps(dict(path=str(out),seal_sha256=sha(out/'complete.json'),binding_sha256=sha(out/'binding.json')),indent=2))
