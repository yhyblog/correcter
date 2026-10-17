"""CPU-only EVAL20 manifest extension; no simulator, model, or outcome access."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
from collections import Counter
from .protocol import TASKS,episode_key,validate_manifest
from .storage import ROOT,PACKAGE,dump,sha256


def build_manifest(original):
    validate_manifest(original)
    if Counter(row['split'] for row in original)!=dict(p0=20,train=600,development=100,calibration=50,heldout=50):
        raise ValueError('Expected unchanged original820 registration')
    primary=copy.deepcopy(original)
    for split,start in [('calibration',2026111800),('heldout',2026111850)]:
        for index in range(50):
            task=TASKS[index%5];seed=start+index;identity=episode_key(task,seed)
            primary.append(dict(episode_id=identity,case_id=identity,task=task,env_seed=seed,split=split,
                round=None,source_horizon=10,cut_rule={'kind':'first_alarm'}))
    reserve=[];replacements={}
    main=[x for x in primary if x['split']!='p0']
    for slot,row in enumerate(main):
        ordered=[]
        for ordinal in range(2):
            candidate=copy.deepcopy(row);seed=2026120000+2*slot+ordinal
            candidate.update(env_seed=seed,episode_id=episode_key(row['task'],seed),
                case_id=episode_key(row['task'],seed),replacement_of=row['episode_id'],replacement_ordinal=ordinal+1)
            reserve.append(candidate);ordered.append(candidate['episode_id'])
        replacements[row['episode_id']]=ordered
    validate_manifest(primary+reserve)
    if primary[:820]!=original:raise ValueError('Original identities changed')
    return primary,reserve,replacements


def main():
    original_path=ROOT/'preparation/episode_manifest.json'
    original=json.loads(original_path.read_text());primary,reserve,replacements=build_manifest(original)
    roots=[PACKAGE.parent/'ACT-RECAP/outputs',PACKAGE/'outputs/metaworld_small_20260916',PACKAGE/'results']
    scan=subprocess.run([shutil.which('rg'),'--pcre2','-l','--glob','*.json','--glob','*.jsonl',
        r'(?<![0-9])(?:2026111[89][0-9]{2}|202612[01][0-9]{3})(?![0-9])',*map(str,roots)],capture_output=True,text=True)
    if scan.returncode not in (0,1):raise RuntimeError(scan.stderr)
    if scan.stdout.strip():raise ValueError('Proposed main/reserve seeds collide with old records: '+scan.stdout)
    dest=ROOT/'preparation/main_registration_v2'
    dump(dest/'primary_manifest.json',primary)
    dump(dest/'reserve_manifest.json',reserve)
    dump(dest/'replacement_candidates.json',replacements)
    dump(dest/'combined_manifest.json',primary+reserve)
    dump(dest/'registration.json',dict(status='registered_not_collected',original_manifest_sha256=sha256(original_path),
        original820_unchanged=True,p0=20,main_primary=900,reserve_candidates=1800,
        counts=dict(Counter(x['split'] for x in primary)),
        reserve_order='two explicit seeds per primary slot; use only after pre-action duplicate/initialization failure',
        replacement_reason_allowlist=['duplicate_initial_scene','initialization_failed'],
        replacement_sampling_budget='technical_reserve; label branches stay in main stage',
        outcome_filter=False,heldout_initialization_before_final_freeze=False,
        analysis_amendment_sha256=sha256(PACKAGE/'coordination/NATIVE10_EVAL20_AMENDMENT.md'),
        seed_collision_audit={'command':scan.args,'old_matches':[],'passed':True},
        primary_manifest_sha256=sha256(dest/'primary_manifest.json'),
        reserve_manifest_sha256=sha256(dest/'reserve_manifest.json'),
        combined_manifest_sha256=sha256(dest/'combined_manifest.json')))
    print(dest)


if __name__=='__main__':main()
