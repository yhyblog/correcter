"""Targeted fakes only. No GPU/foreign library import, symbols, model or env."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace, ModuleType
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parents[2]
WORK = BASE/'work/A/A10_NATIVE_EGL_INTEGRATION_CPU_V1_r1'
OUT = WORK/('fake_checks_' + uuid.uuid4().hex)
OUT.mkdir(parents=True, exist_ok=False)  # Retain all synthetic evidence; never delete.
AUDIT = []

def audit(event, args):
    if event.startswith('ctypes.dlopen') or event.startswith('ctypes.dlsym'):
        AUDIT.append(event); raise AssertionError('CPU task forbids foreign library access: ' + event)
    if event == 'import' and args[0].split('.')[0] in {'torch','mujoco','gymnasium','metaworld','OpenGL','numpy'}:
        if args[0] not in sys.modules:
            AUDIT.append(event + ':' + args[0]); raise AssertionError('Real heavy import forbidden: ' + args[0])
sys.addaudithook(audit)
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT/'code'))
from core.native_egl import NativeEGL, policy_ordinal, check_policy_uuid, check_environment
from core.cuda_mapping import CallRecorder, map_devices, EGL_SUCCESS
from core.graphics_contract import CAPS, Refused, reconcile
from core.observation_accounting import ObservationAccounting
from core.release import authorize, verify_device
from core.process_family import drain_group
from launch_preflight import child_environment, claim_release
CONFIG = json.loads((ROOT/'config/INTEGRATION.json').read_text())
PROPOSAL = json.loads((ROOT/'proposal/PROPOSAL.json').read_text())
RELEASE = json.loads((ROOT/'proposal/RELEASE_TEMPLATE.json').read_text())
CONTROL = json.loads((ROOT/'proposal/CONTROL_REQUIRED.json').read_text())


def folder():
    out=OUT/uuid.uuid4().hex;out.mkdir();return out


def fake_runtime():
    r=NativeEGL(CONFIG,folder(),lambda:None)
    log=[]
    def rec(name,value):
        def f(*args): log.append((name,args));return value
        return f
    r.calls=CallRecorder(r.journal,r.destination/'api.jsonl',lambda:EGL_SUCCESS)
    r.api=SimpleNamespace(get_display=rec('get_display',101),initialize=rec('initialize',1),
        choose_config=rec('choose_config',dict(return_code=1,count=1,config=202)),bind_api=rec('bind_api',1),
        create_context=rec('create_context',303),make_current=rec('make_current',1),
        destroy_context=rec('destroy_context',1),terminate=rec('terminate',1),release_thread=rec('release_thread',1),
        query_string=rec('query_string',b'NVIDIA test'),check_loaded_cuda=lambda:['fake535'])
    def gl_get_string():
        r.calls.egl('probe_explicit_egl_get_proc_address_calls',lambda:123,check=bool)
        return rec('glGetString',b'NVIDIA H100 fake')
    r.api.gl_get_string=gl_get_string
    r.selected_handle=98765
    return r,log


def valid_authority():
    p=copy.deepcopy(PROPOSAL);r=copy.deepcopy(RELEASE);c=copy.deepcopy(CONTROL)
    p['_sha256']=r['proposal_sha256'];r['status']='released';c['campaign_id']='corrector-sim-20260919'
    return c,r,p


class IntegrationTests(unittest.TestCase):
    def test_imports_have_no_driver_or_heavy_side_effects(self):
        self.assertFalse(AUDIT)
        for name in ['torch','mujoco','gymnasium','metaworld','OpenGL','numpy','ctypes']:
            self.assertNotIn(name,sys.modules)

    def test_full_mapping_is_passed_unchanged_not_ordinal(self):
        r,log=fake_runtime()
        inventory=list(reversed(CONFIG['physical_inventory']))
        handles=[8000+i*7 for i in range(8)]
        cuda_handles=[100+i*3 for i in range(8)]
        def attribute(h):return dict(return_code=1,value=cuda_handles[handles.index(h)],output_defined=True)
        def pci(h):
            raw=inventory[cuda_handles.index(h)]['pci_bus_id'].encode()+b'\0'
            return dict(return_code=0,buffer=raw.ljust(32,b'\xa5'))
        api=SimpleNamespace(init=lambda f:0,enumerate=lambda:dict(return_code=1,count=8,handles=handles),
            extensions=lambda h:b'EGL_NV_device_cuda EGL_EXT_device_query',attribute=attribute,pci=pci)
        r.selected_handle,index=map_devices(api,r.calls,CONFIG['device'],CONFIG['physical_inventory'],r.mapping,
            kernel_reader=lambda pci:next({**x,'kernel_sha256':'fake'} for x in inventory if x['pci_bus_id']==pci))
        self.assertEqual(index,7)
        r.policy_index=policy_ordinal(CONFIG,r.mapping)
        self.assertEqual(r.policy_index,0)
        r.open_context(480,480)
        self.assertEqual(log[0],('get_display',(handles[7],)))
        r.close()
        self.assertEqual(r.journal.counts['egl_device_enumerations'],1)
        self.assertEqual(r.journal.counts['cuda_device_pci_queries'],8)

    def test_incomplete_eight_device_mapping_refused_before_policy(self):
        mapping=dict(devices=[dict(decision='target',mapping={k:CONFIG['device'][k] for k in ('gpu_uuid','pci_bus_id')})])
        with self.assertRaises(Refused):policy_ordinal(CONFIG,mapping)

    def test_actual_gymnasium_import_function_uses_private_shim(self):
        r,log=fake_runtime()
        r.install_shim()
        path=Path(PROPOSAL['initialization_source_manifest_path']).parent  # no runtime import
        source=Path('/mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/lib/python3.12/site-packages/gymnasium/envs/mujoco/mujoco_rendering.py')
        fn=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='_import_egl')
        namespace={};exec(compile(ast.Module(body=[fn],type_ignores=[]),str(source),'exec'),namespace)
        try:
            ctx=namespace['_import_egl'](480,480)
            ctx.make_current();ctx.free();ctx.free()
            self.assertEqual(log[0],('get_display',(98765,)))
            self.assertEqual(r.journal.counts['graphics_context_creations'],1)
            self.assertEqual(r.journal.counts['egl_make_current_calls'],2)
            self.assertEqual(r.journal.counts['egl_destroy_context_calls'],1)
        finally:
            sys.modules.pop('mujoco.egl',None)

    def test_actual_gymnasium_classes_two_observations_reuse_one_context(self):
        r,log=fake_runtime();r.install_shim()
        class Array:
            def __getitem__(self,key):return self
            def reshape(self,*shape):return self
        class RenderContext:
            def free(self):log.append(('mjr_free',()))
        mj=SimpleNamespace(MjrRect=lambda x,y,w,h:SimpleNamespace(width=w,height=h),
            MjvScene=lambda *a:SimpleNamespace(flags={},ngeom=0,maxgeom=1000),
            MjvCamera=lambda:SimpleNamespace(type=0,fixedcamid=-1,lookat=[0,0,0],distance=0),
            MjvOption=lambda:SimpleNamespace(flags={}),MjvPerturb=lambda:object(),
            MjrContext=lambda *a:RenderContext(),mjr_setBuffer=lambda *a:None,
            mjv_updateScene=lambda *a:None,mjr_render=lambda *a:None,mjr_readPixels=lambda *a:None,
            mj_name2id=lambda *a:2,mjtObj=SimpleNamespace(mjOBJ_CAMERA=7),
            mjtCamera=SimpleNamespace(mjCAMERA_FREE=0,mjCAMERA_FIXED=2),
            mjtFontScale=SimpleNamespace(mjFONTSCALE_150=150),mjtFramebuffer=SimpleNamespace(mjFB_OFFSCREEN=1),
            mjtCatBit=SimpleNamespace(mjCAT_ALL=7))
        np=SimpleNamespace(median=lambda a:0,zeros=lambda *a,**k:Array(),uint8='uint8',float32='float32',ndarray=Array)
        source=Path('/mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/lib/python3.12/site-packages/gymnasium/envs/mujoco/mujoco_rendering.py')
        tree=ast.parse(source.read_text())
        names={'_import_egl','BaseRender','OffScreenViewer','MujocoRenderer'}
        selected=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
        namespace=dict(mujoco=mj,np=np,os=SimpleNamespace(environ={'MUJOCO_GL':'egl'}),
            _MUJOCO_MARKER_LEGACY_MODE=False,glfw=SimpleNamespace(terminate=lambda:self.fail('No GLFW cleanup permitted')))
        exec(compile(ast.Module(body=selected,type_ignores=[]),str(source),'exec'),namespace)
        namespace['_ALL_RENDERERS']={'egl':namespace['_import_egl']}
        rendering=SimpleNamespace(**namespace)
        try:
            r.install_native_hooks(mj,rendering)
            manager=rendering.MujocoRenderer(SimpleNamespace(stat=SimpleNamespace(extent=1)),
                SimpleNamespace(geom_xpos=Array()),width=480,height=480,camera_name='corner2')
            with r.observation_scope('diagnostic'):manager.render('rgb_array')
            first=manager.viewer
            with r.observation_scope('post_control'):manager.render('rgb_array')
            self.assertIs(first,manager.viewer)
            manager.close();manager.close()
            expected=dict(offscreen_viewer_creations=1,graphics_context_creations=1,mujoco_render_context_creations=1,
                mujoco_set_buffer_calls=1,mujoco_scene_updates=2,render_calls=2,rgb_readback_calls=2,
                mujoco_render_context_frees=1,egl_make_current_calls=2,egl_destroy_context_calls=1,
                egl_terminate_calls=1,egl_release_thread_calls=1)
            for key,value in expected.items():self.assertEqual(r.journal.counts[key],value,key)
            self.assertEqual(first.cam.fixedcamid,2)
            self.assertLess([x[0] for x in log].index('mjr_free'),[x[0] for x in log].index('destroy_context'))
            rows=[json.loads(x) for x in r.journal.path.read_text().splitlines()]
            phases=[x['native_observation_phase'] for x in rows if x['operation']=='rgb_readback_calls' and x['phase']=='entered']
            self.assertEqual(phases,['diagnostic','post_control'])
        finally:
            r.close();sys.modules.pop('mujoco.egl',None)

    def test_visibility_and_preimport_guards(self):
        env=child_environment(PROPOSAL,Path('/tmp/fake-native-cache'),CONFIG['cuda_environment'])
        check_environment(CONFIG,env,{})
        for key,value in [('CUDA_VISIBLE_DEVICES',CONFIG['device']['gpu_uuid']),('MUJOCO_EGL_DEVICE_ID','0'),
                          ('LD_LIBRARY_PATH','/usr/local/cuda/compat'),('PYOPENGL_PLATFORM','osmesa')]:
            bad=dict(env);bad[key]=value
            with self.assertRaises(Refused):check_environment(CONFIG,bad,{})
        for module in ['torch','mujoco.egl','OpenGL.EGL','gymnasium']:
            with self.assertRaises(Refused):check_environment(CONFIG,env,{module:object()})
        bad=dict(CONFIG['cuda_environment']);bad['NVIDIA_VISIBLE_DEVICES']='all'
        with self.assertRaises(Refused):child_environment(PROPOSAL,Path('/tmp/fake'),bad)

    def test_policy_uuid_textual_identity_independent_of_egl_index(self):
        target=CONFIG['device']['gpu_uuid']
        check_policy_uuid(target,target);check_policy_uuid(target[4:],target)
        for raw in [None,b'\x01'*16,'',CONFIG['physical_inventory'][1]['gpu_uuid']]:
            with self.assertRaises(Refused):check_policy_uuid(raw,target)
        r,_=fake_runtime();r.policy_index=4
        props=SimpleNamespace(uuid=target)
        seen=[]
        torch=SimpleNamespace(cuda=SimpleNamespace(set_device=lambda i:seen.append(i),get_device_properties=lambda i:props))
        self.assertEqual(r.bind_policy(torch),'cuda:4');self.assertEqual(seen,[4])

    def test_one_context_no_fallback_and_fixed_size(self):
        r,_=fake_runtime()
        with self.assertRaises(Refused):r.open_context(64,64)
        r.open_context(480,480)
        with self.assertRaises(Refused):r.open_context(480,480)
        r.close()

    def test_context_allocation_preserved_if_error_query_fails(self):
        r,log=fake_runtime()
        errors=iter([EGL_SUCCESS]*4+[0x3001]+[EGL_SUCCESS]*4)
        r.calls.egl_get_error=lambda:next(errors)
        with self.assertRaises(Refused):r.open_context(480,480)
        self.assertEqual(r.context,303)
        r.close()
        self.assertIn(('destroy_context',(101,303)),log)
        self.assertIn(('terminate',(101,)),log)

    def test_cleanup_continues_after_free_failure_without_retry(self):
        r,log=fake_runtime();r.open_context(480,480);r.make_current()
        def bad_free():log.append(('mjr_free',()));raise RuntimeError('synthetic free failure')
        r.render_contexts=[SimpleNamespace(free=bad_free)]
        r.close();r.close()
        self.assertEqual(len(r.cleanup_errors),1)
        self.assertEqual([x[0] for x in log][-5:],['mjr_free','make_current','destroy_context','terminate','release_thread'])
        self.assertEqual(r.journal.counts['mujoco_render_context_frees'],1)
        with self.assertRaises(Refused):r.finish()
        self.assertTrue((r.destination/'graphics_cleanup.json').is_file())

    def test_two_phase_observations_and_reset_separation(self):
        d=folder();o=ObservationAccounting(d/'obs.jsonl')
        reset={'returned_operation_units':{'diagnostic_reset_calls':1}}
        s=o.summary(reset);self.assertEqual(s['diagnostic_native_resets_returned'],1)
        self.assertEqual(s['diagnostic_observations_returned'],0);self.assertEqual(s['usable_observation_artifacts'],0)
        with self.assertRaises(ValueError):o.observation_returned('post_control')
        o.observation_returned('diagnostic')
        for phase in ['diagnostic','post_control']:
            if phase=='post_control':o.observation_returned(phase)
            f=d/(phase+'.fake_npz');f.write_bytes(b'synthetic serialized RGB evidence')
            o.artifact_written(phase,f)
        s=o.summary(reset)
        self.assertEqual(s['diagnostic_observations_returned'],1);self.assertEqual(s['post_control_observations_returned'],1)
        self.assertEqual(s['usable_observation_artifacts'],2);self.assertEqual(s['missing_observation_reasons'],{})
        with self.assertRaises(ValueError):o.observation_returned('diagnostic')
        with self.assertRaises(ValueError):o.artifact_written('post_control',f)

    def test_partial_observation_no_saved_file_is_missing(self):
        d=folder();o=ObservationAccounting(d/'obs.jsonl');o.observation_returned('diagnostic')
        with self.assertRaises(ValueError):o.artifact_written('diagnostic',d/'absent')
        s=o.summary({});self.assertEqual(s['usable_observation_artifacts'],0)
        self.assertIn('no usable NPZ',s['missing_observation_reasons']['diagnostic'])

    def test_new_authority_success_fake_only(self):
        c,r,p=valid_authority()
        self.assertEqual(authorize(c,r,p,hostname=r['owner_host']),p['resource_caps'])

    def test_new_authority_rejects_old_release_and_zero_caps(self):
        c,r,p=valid_authority()
        for change in ['template','old_task','host','device','visibility','graphics_cap','global_budget','per_task_budget']:
            cc,rr,pp=copy.deepcopy(c),copy.deepcopy(r),copy.deepcopy(p)
            if change=='template':rr['status']='TEMPLATE_NOT_AUTHORIZED'
            if change=='old_task':rr['task_id']='A10_PREFLIGHT_NATIVE_V1'
            if change=='host':rr['owner_host']='server-B'
            if change=='device':rr['pci_bus_id']='0000:d8:00.0'
            if change=='visibility':rr['cuda_environment']['CUDA_VISIBLE_DEVICES']=rr['gpu_uuid']
            if change=='graphics_cap':rr['graphics_caps']['rgb_readback_calls']=1
            if change=='global_budget':cc['current_compute_limits']['egl_device_enumerations']=0
            if change=='per_task_budget':cc['per_task_compute_limits'][pp['task_id']]['rgb_readback_calls']=1
            with self.subTest(change=change),self.assertRaises(Refused):authorize(cc,rr,pp,hostname=r['owner_host'])

    def test_exclusive_claim_consumed_even_without_compute(self):
        _,r,_=valid_authority();r['_sha256']='fake-release-sha'
        campaign=folder();path=claim_release(campaign,r)
        self.assertTrue(path.exists())
        with self.assertRaises(FileExistsError):claim_release(campaign,r)

    def test_nvml_parser_uses_fake_text_only(self):
        _,r,p=valid_authority()
        text='\n'.join(f'{i}, {x["gpu_uuid"]}, {r["gpu_model"]}, {r["driver"]}, {x["pci_bus_id"]}' for i,x in enumerate(p['physical_inventory']))
        self.assertEqual(len(verify_device(r,p,query=text)),8)
        with self.assertRaises(Refused):verify_device(r,p,query=text.replace('0000:0f:00.0','0000:2d:00.0'))

    def test_group_cleanup_retains_ownership_and_does_not_touch_others(self):
        now=[0.0];alive=[dict(pid=201,start_ticks=55)];calls=[]
        def pause(dt):now[0]+=dt
        def send(pid,sig):
            calls.append((pid,int(sig)))
            if int(sig)==9:alive.clear()
        result=drain_group(200,200,reader=lambda g,o:list(alive),send=send,clock=lambda:now[0],pause=pause)
        self.assertEqual(calls,[(201,15),(201,9)])
        self.assertEqual(result['status'],'all_formal_group_members_exited')
        with self.assertRaises(RuntimeError):drain_group(199,200,reader=lambda g,o:[],send=send)

    def test_source_preserves_native_queue_and_interface_semantics(self):
        s=(ROOT/'code/preflight_pi05.py').read_text()
        for token in ["proposal['horizons']",'devices=[graphics.policy_index]',"generated_length=50, executed_prefix_length=1",'raw_actions=probe_plans[0][:1].tolist()',"observation_scope('diagnostic')","observation_scope('post_control')"]:
            self.assertIn(token,s)
        self.assertNotIn('torch.manual_seed(',s)
        self.assertNotIn("device='cuda:0'",s)
        self.assertNotIn("run_proposed_graphics_probe",s)


if __name__=='__main__':
    suite = unittest.TestSuite(IntegrationTests(name) for name in sys.argv[1:]) if len(sys.argv)>1 else unittest.defaultTestLoader.loadTestsFromTestCase(IntegrationTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    record=dict(status='passed' if result.wasSuccessful() else 'failed',tests_run=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),forbidden_runtime_events=AUDIT,
        synthetic_evidence_directory=str(OUT),real_GPU_CUDA_EGL_NVML_dlopen_model_environment_calls=0)
    (OUT/'TEST_RESULT.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record))
    sys.exit(0 if result.wasSuccessful() else 1)
