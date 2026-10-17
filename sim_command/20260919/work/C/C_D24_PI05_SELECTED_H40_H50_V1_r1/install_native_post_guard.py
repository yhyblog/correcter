"""Guard only the not-yet-started native evaluation entry; preserve live waiter."""
import hashlib,json,os,sys
from pathlib import Path
C=Path(__file__).resolve().parents[3]
X=C/'results/C/C_D24_FULL_Q_LOSS_REFRESH_V1'
N=C/'results/C/C_D24_PI05_SELECTED_H40_H50_V1'
sys.path.insert(0,str(N/'code'))
from qio import read,new_json,ref,utc,same_process

owner=read(X/'PROCESS.json');heartbeat=read(X/'HEARTBEAT.json')
if not same_process(dict(owner,host=owner['hostname'])) or heartbeat['status']!='selection_dependency':raise RuntimeError('Native waiter no longer in safe dependency state')
if (X/'chains/evaluate').exists() or (X/'ATTEMPT_COUNTER.json').exists() or (X/'SELECTION_CONSUMED.json').exists():raise RuntimeError('Do not hot patch an entered native evaluation')
p=X/'code/manager.py';old=p.read_text();needle="    selected=consumed_selection()\n"
if old.count(needle)!=1:raise RuntimeError('Unexpected existing manager interface')
guard=str(N/'code/validate_post_choice.py')
replacement=needle+f"    # Mandatory Post-only rule applies before any native evaluation worker/model.\n    proof=subprocess.run(['/usr/bin/python','-B',{guard!r},selected['chosen_loss']],check=True,capture_output=True,text=True,timeout=30)\n    new_json(ROOT/'POST_SELECTION_GATE.json',dict(utc=utc(),proof=__import__('json').loads(proof.stdout),no_native_GPU_entry_before_gate=True))\n"
backup=Path(__file__).parent/'native_manager_before_post_guard.py';backup.write_text(old)
p.write_text(old.replace(needle,replacement))
new_json(N/'NATIVE_FUTURE_ENTRY_GUARD.json',dict(utc=utc(),status='installed_before_native_evaluation_exists',old=ref(backup),new=ref(p),validator=ref(guard),existing_waiter=owner,existing_waiter_restarted=False,existing_claim_changed=False,training_repeated=False,evaluation_attempts=0,scope='only future subprocess manager entry; live waiter remains untouched',remaining_compatibility='old live joint-score validator may reject a valid Post-only lock; preserve finite original deadline and expose dependency error, never bypass it'))
print('installed future native Post-only gate; original waiter unchanged')
