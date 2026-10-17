"""One CPU deserialization of each small checkpoint; no model construction/forward.

The multi-GB base checkpoint is accessed only for its JSON shape header.
No hardware inquiry, hashing of weights, launcher, or training occurs here.
"""
import json
import math
import os
import struct
from datetime import datetime, timezone
from pathlib import Path

os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['OMP_NUM_THREADS'] = '1'
ROOT = Path(__file__).resolve().parent
WORKSPACE = Path('/mnt/bn/arnold-recommend/yaohaoyang')
OUT = ROOT / 'SMALL_MODULE_SHAPES.json'
if OUT.exists():
    raise SystemExit('Shape evidence already exists: no second checkpoint load.')

import torch


def describe(value, prefix=''):
    if isinstance(value, torch.Tensor):
        return [{'key': prefix, 'shape': list(value.shape), 'dtype': str(value.dtype),
                 'elements': value.numel(), 'bytes': value.numel() * value.element_size(),
                 'device': str(value.device)}]
    if isinstance(value, dict):
        return [row for k, v in value.items() for row in describe(v, prefix + ('/' if prefix else '') + str(k))]
    if isinstance(value, (tuple, list)):
        return [row for i, v in enumerate(value) for row in describe(v, prefix + '/' + str(i))]
    return []


members = []
for entry in json.loads((ROOT / 'MODULE_INPUTS.json').read_text()):
    p = Path(entry['path'])
    if p.stat().st_size != entry['bytes'] or p.stat().st_size > 32 * 1024**2:
        raise ValueError('Not the bounded small checkpoint described by MODULE_INPUTS')
    state = torch.load(p, map_location='cpu', weights_only=True)
    tensors = describe(state)
    assert tensors and all(t['device'] == 'cpu' for t in tensors)
    members.append(dict(entry, root_keys=list(state) if isinstance(state, dict) else None,
                        tensors=tensors, tensor_elements=sum(t['elements'] for t in tensors),
                        tensor_bytes=sum(t['bytes'] for t in tensors)))
    print(entry['component'], entry['member'], 'root_keys=', members[-1]['root_keys'],
          'tensor_elements=', members[-1]['tensor_elements'], flush=True)
    del state

base_dir = WORKSPACE / 'vla-corrector/outputs/metaworld_very_hard/sft_pi05_mt50/checkpoints/030000/pretrained_model'
with (base_dir / 'model.safetensors').open('rb') as f:
    header_size = struct.unpack('<Q', f.read(8))[0]
    assert 0 < header_size < 2 * 1024**2
    header = json.loads(f.read(header_size))
base_shapes = {k: v for k, v in header.items() if k != '__metadata__'}
base = dict(checkpoint=str(base_dir), config=json.loads((base_dir / 'config.json').read_text()),
            access='JSON config and safetensors shape header only; tensor payload not read',
            header_bytes=header_size, stored_tensor_count=len(base_shapes),
            serialized_weight_tensor_elements=sum(math.prod(v['shape']) for v in base_shapes.values()),
            all_keys_weight_or_bias=all(k.endswith(('.weight', '.bias')) for k in base_shapes),
            tied_or_unused_head_review={k: v for k, v in base_shapes.items()
                if 'lm_head' in k or 'embed_tokens' in k},
            unique_runtime_parameter_count=None,
            null_reason='Serialized tensors do not establish runtime tying/unused heads; no base model instantiated.')

import numpy as np
projection_path = WORKSPACE / 'ACT-RECAP/outputs/act_recap_future_aware_20260914/projection.npy'
with projection_path.open('rb') as f:
    version = np.lib.format.read_magic(f)
    shape, fortran, dtype = np.lib.format._read_array_header(f, version)
projection = dict(path=str(projection_path), shape=list(shape), dtype=str(dtype),
                  elements=math.prod(shape), data_bytes=math.prod(shape)*dtype.itemsize,
                  file_bytes=projection_path.stat().st_size, trainable=False,
                  access='NPY header only', shared=True)
evidence = dict(utc=datetime.now(timezone.utc).isoformat(), status='CPU_METADATA_ONLY',
                checkpoint_loads=len(members), map_location='cpu', model_instances=0,
                model_forwards=0, hardware_queries=0, weight_hashes=0,
                members=members, base=base, shared_projection=projection)
with OUT.open('x') as f:
    json.dump(evidence, f, indent=2, allow_nan=False); f.write('\n')
print('SAVED', OUT, 'base_serialized_elements=', base['serialized_weight_tensor_elements'], flush=True)
