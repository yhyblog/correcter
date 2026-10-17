"""CPU-only construction of a new private snapshot; never imports copied code."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import textwrap

ROOT=Path('/mnt/bn/arnold-recommend/yaohaoyang')
BASE=ROOT/'Corrector/sim_command/20260919'
OLD=BASE/'results/A/A10_TORCH_UUID_ABI_CPU_REPAIR_V1'
NEW=BASE/'results/A/A10_PV_OFFLINE_PREFLIGHT_CPU_V1'
WORK=Path(__file__).parent
CODE=NEW/'code'
DER=[]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,s):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:f.write(s)
def dump(p,x):write(p,json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def ref(p):return dict(path=str(p),realpath=str(p.resolve()),sha256=sha(p),size_bytes=p.stat().st_size)
def extract(p,names):
    s=p.read_text();t=ast.parse(s);result=[]
    for name in names:
        nodes=[n for n in ast.walk(t) if isinstance(n,ast.FunctionDef) and n.name==name]
        assert len(nodes)==1,(p,name)
        n=nodes[0];start=min([n.lineno]+[d.lineno for d in n.decorator_list])-1
        result.append(textwrap.dedent('\n'.join(s.splitlines()[start:n.end_lineno])))
        DER.append(dict(source=ref(p),symbol=name,AST_sha256=hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest(),body_unchanged=True))
    return '\n\n'.join(result)+'\n'

def main():
    NEW.mkdir(exist_ok=False)
    for d in ['code','config','proposal','commands','tests']: (NEW/d).mkdir()
    manifest=json.loads((OLD/'code/CODE_MANIFEST.json').read_text())
    copied=0
    for row in manifest['files']:
        name=row['path']
        if name.startswith('vendor_vla/src/lerobot/'):
            p=OLD/'code'/name
            assert sha(p)==row['sha256']
            dest=CODE/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);copied+=1
    for name in ['wave_timing','process_family']:
        p=OLD/f'code/core/{name}.py';write(CODE/f'core/{name}.py',p.read_text());DER.append(dict(source=ref(p),copy=str(CODE/f'core/{name}.py')))
    write(CODE/'core/__init__.py','"""Offline PV private CPU guards and lifecycle."""\n')
    write(CODE/'corrector/__init__.py','"""Frozen numerical primitives; imported only after a compute release."""\n')
    for name in ['critic','guidance','actions']:
        p=ROOT/f'Corrector/src/corrector/{name}.py';write(CODE/f'corrector/{name}.py',p.read_text());DER.append(dict(source=ref(p),copy=str(CODE/f'corrector/{name}.py')))
    p=ROOT/'Corrector/experiments/standalone_ablation_20260918/candidates.py'
    s=p.read_text().replace('from experiments.native10_training_20260916.commands import preserve_raw_anchor','from .raw_commands import preserve_raw_anchor').replace('from corrector.candidates import radii','from .radii import radii')
    write(CODE/'corrector/solo.py',s);DER.append(dict(source=ref(p),copy=str(CODE/'corrector/solo.py'),change='two import paths only; independent project_solo/audit_solo unchanged'))
    write(CODE/'corrector/raw_commands.py',(ROOT/'Corrector/experiments/native10_training_20260916/commands.py').read_text())
    write(CODE/'corrector/radii.py','import numpy as np\n\n'+extract(ROOT/'Corrector/src/corrector/candidates.py',['radii']))
    s='"""Exact extracted feature functions; no D, G0 or environment construction."""\nimport math\nimport numpy as np\nimport torch\nimport einops\nfrom torch import Tensor\nfrom lerobot.utils.constants import OBS_IMAGE, OBS_IMAGES, OBS_ENV_STATE, OBS_STATE, OBS_STR\n\n'
    s+=extract(OLD/'code/vendor_vla/src/lerobot/envs/utils.py',['preprocess_observation'])+'\n'
    s+=extract(ROOT/'ACT-RECAP/src/ac_tmil/future_aware/features.py',['canonical_decode','spatial_tokens'])+'\n'
    s+=extract(ROOT/'ACT-RECAP/src/ac_tmil/ogg/common.py',['cpu_batch'])+'\n'
    # The original methods use only these attributes. The environment-bearing
    # backend constructor and reset_episode are deliberately absent.
    methods=extract(OLD/'code/vendor_backend/metaworld_pi05.py',['_policy_batch','encode_visual_batch','encode_instruction'])
    s+='from typing import Any, Mapping, Sequence\n\nclass OfflineFeatures:\n'+textwrap.indent(methods,'    ')
    write(CODE/'feature_path.py',s)
    identity='import re\nimport subprocess\n\nclass ContractError(ValueError): pass\n\n'
    identity+=extract(OLD/'code/core/native_egl.py',['check_policy_uuid'])
    identity+=extract(OLD/'code/core/release.py',['normalize_pci','verify_device'])
    write(CODE/'core/identity.py',identity)
    old=json.loads((OLD/'proposal/PROPOSAL.json').read_text())
    selected=ROOT/'Corrector/outputs/native10_training_20260916/models/final/final_fit_v1/selected'
    diag=BASE/'results/A/P10_diagnostic_runs/ba0faa37ed325af8c2c61221310c8bb23f47fd10a109ff5a3d4847866d4f1f2a'
    meta=json.loads((WORK/'SMALL_ARTIFACT_METADATA.json').read_text())
    raw_inputs=[]
    for x in old['required_inputs']:
        p=Path(x['path'])
        if str(p).startswith(old['checkpoint']+'/') or '/models--google--paligemma-3b-pt-224/' in str(p) or p.name.startswith('gpu_occupancy'):
            row=dict(x);row.update(size_bytes=p.stat().st_size,realpath=str(p.resolve()))
            if p.name=='model.safetensors':row['verification_now']='inherited V3 accepted SHA; no large weight bytes read in CPU task'
            else:
                assert sha(p)==row['sha256'];row['verification_now']='targeted small input SHA verified in CPU preparation'
            raw_inputs.append(row)
    for p in [diag/'observation_step0.npz',diag/'raw_plans.npy',diag/'checks.json',diag/'transition.json',diag/'COMPLETE.json',
              selected/'config.json',selected/'ranking.json',selected/'complete.json',
              ROOT/'ACT-RECAP/outputs/act_recap_future_aware_20260914/projection.npy',
              ROOT/'Corrector/docs/NATIVE10_CORRECTOR_ALGORITHM_ZH.md']:
        raw_inputs.append(ref(p))
    raw_inputs += [m['identity'] for m in meta['Q'].values()]
    source=dict(old['source']);source.pop('proposed_only',None)
    source.update(step=0,cut_is_legal_alarm=False,instruction='Pick and place a puck onto a shelf',
        observation_path=str(diag/'observation_step0.npz'),raw_plans_path=str(diag/'raw_plans.npy'),raw_index=0,
        raw50_sha256=meta['raw']['first_raw50_sha256'],noise_sha256='b3126bc00d8e44f80cf1ae879db97042477bcfb1408262dd25ce2d9bad22d052',
        noise_shape=[1,50,32],noise_dtype='float32',noise_generator='torch.normal(mean=0,std=1,size=(1,50,32),device=cuda:0,dtype=float32); default CUDA generator reseeded 2026091901 immediately before call',
        history_length=1,history_mask=[False,False,False,False,True],past_executed_actions=0,future_step1_permitted=False)
    config=dict(schema='PV_offline_config_v1',source=source,checkpoint=old['checkpoint'],Q_assets=str(selected),
        projection=str(ROOT/'ACT-RECAP/outputs/act_recap_future_aware_20260914/projection.npy'),
        tokenizer_name=old['tokenizer_name'],tokenizer_revision=old['tokenizer_revision'],
        device=old['device'],physical_inventory=old['physical_inventory'],cuda_environment=old['cuda_environment'],
        python=old['python'],hf_home=old['hf_home'],occupancy_lifecycle=old['occupancy_lifecycle'],
        runtime_packages={k:v for k,v in old['runtime_packages'].items() if k not in ['mujoco','metaworld','gymnasium','jsonschema']},
        guidance=dict(alpha=10.,times=[.3,.2,.1],mode='velocity'),matching=dict(xyz_rms=.05,gripper_rms=.1,xyz_linf=.15,gripper_linf=.4,boundary_clearance=.05,tolerance=1e-6,zero_threshold=1e-10),
        deployment_sampling_calls=dict(Post=1,Velocity=2),cached_diagnostic_sampling_calls=dict(Post=0,Velocity=1),
        Q_scope='historical five-task A4000 compatibility only, not MT50-trained',
        timeout_seconds=1800,kill_grace_seconds=30,restoration_observation_timeout_seconds=120)
    dump(NEW/'config/CONFIG.json',config)
    dump(NEW/'INPUT_MANIFEST.json',dict(schema='PV_saved_input_manifest_v1',files=raw_inputs,source=source,
        future_excluded=['observation_step1.npz','next observation','reward','success','labels','other-source features'],
        large_model_SHA_basis=str(BASE/'manifests/A_NATIVE_PREFLIGHT_V3_FINAL_ACCEPTANCE.json')))
    # Inherited complete accepted package identities are retained without a
    # new environment scan or loading any library. Future launch checks them.
    shutil.copyfile(OLD/'EXTERNAL_SOURCE_MANIFEST.json',NEW/'EXTERNAL_SOURCE_MANIFEST.json')
    dump(NEW/'DERIVATION.json',dict(source_package=ref(OLD/'code/CODE_MANIFEST.json'),vendor_code_files_copied=copied,
        derivatives=DER,feature_chain='same PI05 image/token embedding; canonical decode; singleton spatial projection; fp16 then fp32; cpu_batch; member PCA',
        excluded_constructors=['MetaWorldPi05Backend.__init__','Engine','FrozenFeatures','DeferredRenderRuntime'],
        D_G0_legacy_pooled_feature_models_required=False))
    print(json.dumps(dict(package=str(NEW),copied_vendor_files=copied,new_model_bytes_read=0,driver_calls=0)))

if __name__=='__main__':main()
