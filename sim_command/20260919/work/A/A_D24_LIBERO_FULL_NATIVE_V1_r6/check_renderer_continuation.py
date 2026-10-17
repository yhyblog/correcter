"""CPU-only regression of the observed parser failure and the native selector."""
import ast
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import d24_common as d
import mesa_context_adapter

site=d.ROOT/'embodied-ai-workspace/environments/libero-sim-openpi/lib/python3.8/site-packages'
calls=[]
egl=SimpleNamespace(EGL_NO_DISPLAY=0,EGL_SUCCESS=0,EGL_TRUE=1,EGL_PLATFORM_DEVICE_EXT=0x313f,
    eglQueryDevicesEXT=lambda:[11,22],eglGetError=lambda:0,
    eglGetPlatformDisplayEXT=lambda platform,device,attrs:device,
    eglInitialize=lambda display,a,b:(calls.append(display) or int(display==22)))

def extracted(path):
    tree=ast.parse(path.read_text())
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='create_initialized_egl_device_display')
    namespace=dict(EGL=egl,os=os,error=SimpleNamespace(GLError=RuntimeError))
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(path),'exec'),namespace)
    return namespace[fn.name]

native=SimpleNamespace(create_initialized_egl_device_display=extracted(site/'mujoco/egl/__init__.py'))
robo=SimpleNamespace(create_initialized_egl_device_display=extracted(site/'robosuite/renderers/context/egl_context.py'))
with patch.dict(os.environ,dict(VLA_RENDERER='mesa',LIBGL_ALWAYS_SOFTWARE='1',CUDA_VISIBLE_DEVICES=''),clear=True):
    rejected=False
    try:robo.create_initialized_egl_device_display(-1)
    except ValueError as e:rejected="invalid literal for int()" in str(e)
    assert rejected
    with patch.object(mesa_context_adapter.importlib,'import_module',lambda n:native if n=='mujoco.egl' else robo):
        installed=mesa_context_adapter.install()
        assert robo.create_initialized_egl_device_display(-1)==22
    assert calls==[11,22]
batch=d.load(d.W/'BATCH.json');prior=d.load(d.W.parent/'A_D24_LIBERO_FULL_NATIVE_V1_r5/BATCH.json')
original={s['source_id']:s for j in prior['jobs'] for s in d.load(j['config'])['development']}
pending={s['source_id']:s for j in batch['jobs'] for s in d.load(j['config'])['development']}
entered=set(batch['prior_entered_development_ids'])
assert len(pending)==30 and len(entered)==10 and not (pending.keys() & entered)
assert pending.keys()|entered==original.keys()
assert all(source==original[sid] for sid,source in pending.items())
for p in d.W.glob('*.py'):ast.parse(p.read_text())
value=dict(utc=d.utc(),synthetic=True,status='PASS',observed_original_empty_CUDA_failure_reproduced=True,
           real_installed_selector_with_fake_EGL=True,fake_device_fallback=calls,
           adapter=installed,remaining_original_attempts=30,prior_entered_excluded=10,
           unique_total=40,seed_or_source_changes=0,real_environment=0,real_EGL=0,
           hardware_or_model_calls=0,no_actual_claim_created=True)
d.atomic(d.R/'RENDERER_CONTINUATION_CPU_CHECK.json',value)
print(json.dumps(value,indent=2))
