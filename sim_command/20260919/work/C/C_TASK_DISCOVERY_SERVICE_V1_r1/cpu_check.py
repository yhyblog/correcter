"""Small fake metadata/transport tests. No actual session or GPU call."""
import datetime,hashlib,json,os,tempfile
from pathlib import Path
import d24_common as d
import task_discovery as td
import wakeup

NOW=datetime.datetime(2026,9,22,12,0,tzinfo=datetime.timezone.utc)
def put(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x))
def fixture(root):
 tid='C_FAKE_DISCOVERY_TEST_V1';task='tasks/'+tid+'.md';p=root/task;p.parent.mkdir(parents=True);p.write_text('CPU fake task revision1')
 auth=dict(task_id=tid,revision=1,node='C',status='released',scientific_compute_added=0,new_GPU_claims=0,task=dict(path=task,sha256=td.sha(p)))
 ap='deadline_20260924/FAKE_AUTH.json';put(root/ap,auth);ref=dict(path=ap,sha256=td.sha(root/ap))
 row=dict(task_id=tid,revision=1,node='C',task=task,authorization=ref)
 put(root/td.META[0],row);put(root/td.META[1],row);put(root/td.META[2],dict(tasks=[dict(row,id=tid,owner='C',status='ready')]))
 put(root/td.META[3],dict(stop_requested=False,formal_gpu_runs_enabled=True,stage_authorizations=[ref]))
 put(root/td.META[4],dict(global_stop=False,nodes={'C':{'enabled':True}},stage_authorizations=[ref]))
 for name in ['outbox','delivery','handler_acks','jobs']:(root/'persistent_queue/nodes/C/wakeup'/name).mkdir(parents=True,exist_ok=True)
 (root/'receipts/C').mkdir(parents=True,exist_ok=True)
 return tid

checks=[]
with tempfile.TemporaryDirectory(prefix='C_discovery_CPU_') as temp:
 base=Path(temp)
 def setup(name):
  root=base/name;root.mkdir();tid=fixture(root);return root,tid,td.Discovery(root)
 root,tid,disc=setup('dedup');events=disc.poll(NOW);assert len(events)==1;assert disc.poll(NOW)==[]
 again=td.Discovery(root);assert again.poll(NOW)==[] and len(again.state['entries'])==1;checks+=['one_legal_C_task_once','scan_and_restart_dedup']
 board=td.load(root/td.META[2]);board['tasks'].append(dict(id='B_NEW_TASK',owner='B',revision=9,status='ready'));put(root/td.META[2],board);assert again.poll(NOW)==[];checks+=['B_update_no_wakeup']
 p=root/td.META[0];raw=p.read_bytes();p.unlink();before=json.dumps(again.state,sort_keys=True);assert again.poll(NOW)==[] and not again.fresh;assert json.dumps(again.state,sort_keys=True)==before;p.write_bytes(raw);assert again.poll(NOW)==[];checks+=['temporary_missing_metadata_preserves_state']
 put(root/'receipts/C'/(tid+'_ACK.json'),dict(revision=1,status='accepted'));assert again.poll(NOW)==[] and not again.eligible;checks+=['ACK_suppresses_without_relaunch']
 for name,change in [('closed','completed'),('disabled','disable'),('wrong_authorization','wrong')]:
  root,tid,disc=setup(name)
  if change=='completed':
   x=td.load(root/td.META[2]);x['tasks'][0]['status']='completed';put(root/td.META[2],x)
  elif change=='disable':
   x=td.load(root/td.META[4]);x['nodes']['C']['enabled']=False;put(root/td.META[4],x)
  else:
   ap=root/'deadline_20260924/FAKE_AUTH.json';x=td.load(ap);x['unauthorized_change']=True;put(ap,x)
  assert disc.poll(NOW)==[] and not disc.state['entries'];checks.append(name+'_rejected')
 root,tid,disc=setup('same_revision');assert len(disc.poll(NOW))==1
 ap=root/'deadline_20260924/FAKE_AUTH.json';x=td.load(ap);x['changed_without_revision']=True;put(ap,x);newsha=td.sha(ap)
 for name in td.META:
  x=td.load(root/name)
  if name in td.META[:2]:x['authorization']['sha256']=newsha
  elif name==td.META[2]:x['tasks'][0]['authorization']['sha256']=newsha
  else:x['stage_authorizations'][0]['sha256']=newsha
  put(root/name,x)
 assert disc.poll(NOW)==[] and any(x['reason']=='same_revision_authorization_changed' for x in disc.decisions.values());checks+=['same_revision_changed_authority_no_reexecution']
 root,tid,disc=setup('busy');eid=disc.poll(NOW)[0];event=td.load(disc.wakeup/'outbox'/(eid+'.json'))
 prompt=td.task_message(event,Path('/fake/work'));assert 'task_available' in prompt and '不是科学终局' in prompt and tid in prompt;checks+=['dedicated_dispatch_message']
 wakeup.STATE=disc.wakeup;wakeup.DISCOVERY=disc;wakeup.thread_state=lambda:dict(turn_id='fake_busy',status='inProgress');wakeup.writer_locked=lambda:True;wakeup.profile=lambda:{};put(disc.wakeup/'ORIGINAL_THREAD_PROFILE.json',{})
 class FakeProc:
  pid=os.getpid()
  def poll(self):return 0
  returncode=0
 calls=[];original=wakeup.subprocess.Popen;original_identity=d.identity
 def fake_popen(argv,**kwargs):calls.append(argv);return FakeProc()
 wakeup.subprocess.Popen=fake_popen
 d.identity=lambda pid:dict(hostname='fake',boot_id='fake',pid=pid,start_ticks=1,session_id=pid)
 try:wakeup.dispatch(event);wakeup.dispatch(event)
 finally:wakeup.subprocess.Popen=original;d.identity=original_identity
 assert len(calls)==1 and calls[0][1]=='queue' and '--thread' in calls[0];checks+=['busy_session_queues_once_no_actual_transport']
result=dict(status='passed',utc=d.utc(),checks=checks,synthetic_CPU_tests=True,actual_session_messages=0,scientific_launches=0,GPU_calls=0,holder_mutations=0)
d.atomic(d.C/'results/C/C_TASK_DISCOVERY_SERVICE_V1/CPU_CHECK.json',result);print(json.dumps(result,indent=2))
