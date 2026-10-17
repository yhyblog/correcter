"""Trusted small artifact inspection; no torch/numpy/imported checkpoint code."""
import ast
import collections
import hashlib
import io
import json
from pathlib import Path
import pickle
import struct
import sys
import zipfile

ROOT = Path('/mnt/bn/arnold-recommend/yaohaoyang')
BASE = ROOT / 'Corrector/sim_command/20260919'
OUT = Path(__file__).parent

def audit(event, args):
    if event == 'ctypes.dlopen' or (event == 'import' and args[0].split('.')[0] in
            {'torch','numpy','ctypes','mujoco','metaworld','OpenGL','pynvml'}):
        raise RuntimeError('CPU metadata scope denied: ' + event)
sys.addaudithook(audit)

def ref(path):
    p=Path(path)
    return dict(path=str(p), realpath=str(p.resolve()), size_bytes=p.stat().st_size,
                sha256=hashlib.sha256(p.read_bytes()).hexdigest())

def npy(blob):
    if blob[:6] != b'\x93NUMPY': raise ValueError('NPY magic')
    n=struct.unpack('<H' if blob[6]==1 else '<I',blob[8:10 if blob[6]==1 else 12])[0]
    start=(10 if blob[6]==1 else 12)+n
    h=ast.literal_eval(blob[10 if blob[6]==1 else 12:start].decode())
    return {**h,'data_sha256':hashlib.sha256(blob[start:]).hexdigest(),'data_bytes':len(blob)-start},blob[start:]

def tensor(storage, offset, shape, stride, *args):
    return dict(storage=storage, storage_offset=offset, shape=list(shape), stride=list(stride))

class Metadata(pickle.Unpickler):
    def find_class(self,module,name):
        if (module,name)==('collections','OrderedDict'): return collections.OrderedDict
        if module=='torch._utils' and name in {'_rebuild_tensor_v2','_rebuild_tensor'}: return tensor
        if module=='torch' and name in {'FloatStorage','LongStorage','DoubleStorage','HalfStorage','BFloat16Storage'}:
            return 'metadata_only_'+name
        raise ValueError('Unknown checkpoint global (not executed): '+module+'.'+name)
    def persistent_load(self,pid):
        if pid[0]!='storage':raise ValueError('Unknown persistent metadata')
        return dict(dtype=pid[1],key=pid[2],location=pid[3],numel=pid[4])

def main():
    report=dict(schema='PV_CPU_metadata_v1',torch_imports=0,model_loads=0,dlopen=0)
    q=ROOT/'Corrector/outputs/native10_training_20260916/models/final/final_fit_v1/selected'
    rank=json.loads((q/'ranking.json').read_text())
    report['Q']={}
    for i in range(4):
        p=q/f'models/refit/member_{i}/selected.pt';identity=ref(p)
        assert identity['sha256']==rank['model_hashes'][str(i)]
        with zipfile.ZipFile(p) as z:
            name=next(n for n in z.namelist() if n.endswith('/data.pkl'))
            state=Metadata(io.BytesIO(z.read(name))).load()
            tensors={k:v for k,v in state.items() if isinstance(v,dict) and 'shape' in v}
            assert len(tensors)==len(state)
            report['Q'][str(i)]={'identity':identity,'tensors':tensors}
            for k,v in tensors.items():
                data=z.read(name.removesuffix('data.pkl')+'data/'+v['storage']['key'])
                v['storage_sha256']=hashlib.sha256(data).hexdigest()
                if k in ['norm_mean','norm_std','visual_center','visual_basis','visual_scale','language_center','language_basis','language_scale','residual_scale']:
                    vals=struct.unpack('<'+'f'*(len(data)//4),data)
                    v['finite']=all(x==x and abs(x)!=float('inf') for x in vals)
                    v['min']=min(vals);v['max']=max(vals)
                assert v['storage']['location']=='cpu'
    d=BASE/'results/A/P10_diagnostic_runs/ba0faa37ed325af8c2c61221310c8bb23f47fd10a109ff5a3d4847866d4f1f2a'
    with zipfile.ZipFile(d/'observation_step0.npz') as z:
        report['step0']={n:npy(z.read(n))[0] for n in z.namelist()}
    rawh,raw=npy((d/'raw_plans.npy').read_bytes())
    assert rawh['shape']==(5,50,4) and rawh['descr']=='<f4'
    report['raw']=dict(header=rawh,all_five_bit_equal=all(raw[:800]==raw[i*800:(i+1)*800] for i in range(5)),
        first_raw50_sha256=hashlib.sha256(raw[:800]).hexdigest(),slice_index=0,
        bounded_anchor='clip(raw_plans[0][:10],-1,1)',future_step1_read=False,
        full_internal_50x32_saved=False,full_internal_anchor_required=False)
    c=ROOT/'vla-corrector/outputs/metaworld_very_hard/sft_pi05_mt50/checkpoints/030000/pretrained_model'
    p=c/'policy_postprocessor_step_0_unnormalizer_processor.safetensors';b=p.read_bytes();n=struct.unpack('<Q',b[:8])[0];header=json.loads(b[8:8+n]);values={}
    for key,v in header.items():
        if key=='__metadata__':continue
        if key.startswith('action'):
            lo,hi=v['data_offsets'];data=b[8+n+lo:8+n+hi]
            values[key]=dict(metadata=v,values=list(struct.unpack('<'+'f'*(len(data)//4),data)))
    report['normalizer']=dict(identity=ref(p),action=values)
    projection=ROOT/'ACT-RECAP/outputs/act_recap_future_aware_20260914/projection.npy'
    report['projection']=dict(identity=ref(projection),header=npy(projection.read_bytes())[0])
    report['Q_support']='five-task A4000 compatibility diagnostic only; not MT50-trained'
    report['forbidden_read']='observation_step1.npz is not opened'
    (OUT/'SMALL_ARTIFACT_METADATA.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'Q_dimensions':{i:{k:v['shape'] for k,v in m['tensors'].items()} for i,m in report['Q'].items()},'normalizer':values,'step0':report['step0'],'raw':report['raw']},indent=2))

if __name__=='__main__':main()
