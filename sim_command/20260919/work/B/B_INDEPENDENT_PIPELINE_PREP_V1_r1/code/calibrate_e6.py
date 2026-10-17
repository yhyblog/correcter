"""Prepared metadata-only E6 development threshold calibration entry."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import b10_adapters


def calibrate(manifest,output):
    m=json.loads(Path(manifest).read_text())
    if m.get('synthetic') is not False or m.get('split')!='development':
        raise ValueError('real development-only trace manifest required')
    trace=Path(m['episodes']['path']);raw=trace.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=m['episodes']['sha256']:raise ValueError('trace SHA changed')
    episodes=json.loads(raw)
    required={'parent_episode_id','split','eligible_scores','g0_intervened','causal_D5_action_alignment_verified'}
    if not all(required<=e.keys() and e['causal_D5_action_alignment_verified'] is True for e in episodes):
        raise ValueError('causal D5/action/reset alignment not verified')
    if not m.get('frozen_D_identity') or m.get('downstream')!='R' or m.get('horizon')!=5:
        raise ValueError('same D/five-step/downstream R binding missing')
    result=b10_adapters.select_development_threshold(episodes)
    result.update(trace_manifest_sha256=hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
                  D_identity=m['frozen_D_identity'],downstream='R',horizon=5,
                  model_calls=0,synthetic=False)
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    with Path(output).open('x') as f:json.dump(result,f,indent=2)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    print(json.dumps(calibrate(a.manifest,a.output),indent=2))
