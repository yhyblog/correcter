"""Static hashes, tensor headers, CPU weight read, and dataset schemas only."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import zipfile
import numpy as np
import pyarrow.parquet as pq
import torch
from inventory import ROOT, BASE, WORK, WS, atomic, beat, command, record, now

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8*1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

def main():
    torch.set_num_threads(2)
    beat('verifying small-file hashes, CPU checkpoint structure, and data headers')
    results = {'observed_at_utc': now(), 'torch_version':torch.__version__, 'cuda_initialized':torch.cuda.is_initialized()}
    summaries=[]
    manifest_paths=[
        WS/'manifests/vla-baselines-20260911/legacy-pi05-mt50.files.json',
        WS/'manifests/vla-baselines-20260911/metaworld-raw-and-local-stats.files.json',
        WS/'manifests/vla-baselines-20260911/libero-evaluation-assets.files.json',
        WS/'manifests/vla-baselines-20260911/xvla-initialization.files.json',
        WS/'manifests/vla-baselines-20260911/smolvla-initialization.files.json',
        WS/'artifacts/storage-cleanup/20260914-act-vla/libero-retention/immediate/retained-inference-files.json',
    ]
    for path in manifest_paths:
        manifest=json.loads(path.read_text())
        entries=manifest if isinstance(manifest,list) else manifest['files']
        root=ROOT if isinstance(manifest,list) else Path(manifest['root'])
        summary={'manifest':record(path),'declared_files':len(entries),'size_checked':0,'small_sha_checked':0,'large_sha_not_rechecked':0,'missing':[],'mismatches':[],'bytes':0}
        for entry in entries:
            p=root/entry['path']
            if not p.is_file():
                summary['missing'].append(str(p)); continue
            size=p.stat().st_size; summary['size_checked']+=1; summary['bytes']+=size
            if size != entry['bytes']:summary['mismatches'].append({'path':str(p),'field':'size','actual':size,'expected':entry['bytes']})
            if size <= 2*1024*1024:
                sha=digest(p);summary['small_sha_checked']+=1
                if sha!=entry['sha256']:summary['mismatches'].append({'path':str(p),'field':'sha256','actual':sha,'expected':entry['sha256']})
            else:summary['large_sha_not_rechecked']+=1
        summaries.append(summary)
        beat('manifest checked: '+path.name)
    results['manifest_checks']=summaries
    checkpoints=[WS/'models/vla-sft-030000/model.safetensors',WS/'models/initializations/xvla-mt50-s42/model.safetensors',WS/'artifacts/vla-baselines/runs/metaworld/smolvla/mt50-smolvla-s42-mb-20260912-v1/checkpoints/050000/pretrained_model/model.safetensors']
    results['safetensors_headers']=[]
    for path in checkpoints:
        with path.open('rb') as stream:
            header_len=struct.unpack('<Q',stream.read(8))[0];header=json.loads(stream.read(header_len))
        tensors={k:v for k,v in header.items() if k!='__metadata__'}
        results['safetensors_headers'].append({'file':record(path),'header_sha256':hashlib.sha256(json.dumps(header,sort_keys=True).encode()).hexdigest(),'tensor_count':len(tensors),'elements':sum(int(np.prod(v['shape'])) for v in tensors.values()),'dtype_counts':dict(Counter(v['dtype'] for v in tensors.values())),'file_extent_matches':max(v['data_offsets'][1] for v in tensors.values())+header_len+8==path.stat().st_size})
    corrector=WS/'models/vla-corrector-h1-k10/best_cosine_model.pt'
    state=torch.load(corrector,map_location='cpu',weights_only=True)
    if 'state_dict' in state:state=state['state_dict']
    elif 'model_state_dict' in state:state=state['model_state_dict']
    results['corrector_cpu_weight_check']={'path':str(corrector),'sha256':digest(corrector),'tensor_count':len(state),'elements':sum(t.numel() for t in state.values()),'all_finite':all(bool(torch.isfinite(t).all()) for t in state.values()),'device_types':sorted({t.device.type for t in state.values()}),'config':json.loads((corrector.parent/'config.json').read_text()),'inference_performed':False}
    results['dataset_schemas']=[]
    for dataset in [WS/'datasets/metaworld-mt50', WS/'datasets/libero/physical-intelligence-v2/a4336d589d589045d1c56423ffdf3b88a0e19b1f']:
        info=json.loads((dataset/'meta/info.json').read_text())
        files=sorted((dataset/'data').rglob('*.parquet'));first=files[0];parquet=pq.ParquetFile(first)
        results['dataset_schemas'].append({'path':str(dataset),'info_file':record(dataset/'meta/info.json'),'totals':{k:v for k,v in info.items() if k.startswith('total_')},'features':info.get('features'),'parquet_count':len(files),'sample_path':str(first),'sample_schema':str(parquet.schema_arrow),'sample_rows':parquet.metadata.num_rows})
    bundle=ROOT/'Corrector/outputs/native10_training_20260916/input_bundles/final_train600_input_v1/train'
    with zipfile.ZipFile(bundle/'arrays.npz') as archive:
        fields={}
        for name in archive.namelist():
            with archive.open(name) as stream:
                version=np.lib.format.read_magic(stream)
                shape,order,dtype=np.lib.format._read_array_header(stream,version)
            fields[name]={'shape':list(shape),'dtype':str(dtype)}
    rows=json.loads((bundle/'rows.json').read_text())
    results['train600_bank']={'path':str(bundle),'fields':fields,'source_count':len(rows),'task_counts':dict(Counter(row['task'] for row in rows)),'row_example':rows[0],'limitation':'Array/schema audit only; no full historical trajectory reconstruction.'}
    results['code']=[]
    code_paths=[ROOT/'vla-corrector/src/siglip_dynamics/inference/safety_module.py', ROOT/'vla-corrector/src/siglip_dynamics/inference/circuit_breaker.py', ROOT/'vla-corrector/src/lerobot/safety/siglip_dynamics_mlp.py',ROOT/'Corrector/src/corrector/guidance.py',WS/'projects/vla-baselines/launchers/eval_metaworld.py',WS/'projects/vla-baselines/launchers/serve_pi05.py',WS/'projects/vla-baselines/launchers/eval_libero.py']
    for p in code_paths:
        item=record(p);ast.parse(p.read_text());item['ast_parse']='pass';results['code'].append(item)
    results['git_heads']={str(repo):command(['git','-C',str(repo),'rev-parse','HEAD']) for repo in [ROOT/'vla-corrector',WS/'projects/upstream/lerobot-smolvla-8fff0fd',WS/'projects/upstream/lerobot-xvla-8fff0fd',WS/'projects/upstream/openpi-215abfb']}
    results['cuda_initialized_after']=torch.cuda.is_initialized()
    atomic(WORK/'asset_verification.json',results)
    print(json.dumps({'artifact':str(WORK/'asset_verification.json'),'manifest_checks':[{k:v for k,v in x.items() if k!='manifest'} for x in summaries],'corrector_cpu_weight_check':results['corrector_cpu_weight_check'],'train600_bank':results['train600_bank'],'dataset_schemas':[{k:v for k,v in x.items() if k not in ['features','sample_schema']} for x in results['dataset_schemas']],'cuda_initialized':results['cuda_initialized_after']},ensure_ascii=False,indent=2))
    beat('static asset verification finished')

if __name__ == '__main__':
    main()
