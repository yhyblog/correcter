from pathlib import Path
import shutil,json
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919');O=B/'results/A/A10_CAUSAL_C10_CPU_V1';P=B/'results/A/A10_CAUSAL_EVENT_CPU_REPAIR_V1'
# Only new private source/config/manifest bytes; no cached arrays or weights.
shutil.copytree(O/'code',P/'code',ignore=shutil.ignore_patterns('CODE_MANIFEST.json','__pycache__','*.pyc'))
for name in ['config/CONFIG.json','INPUT_MANIFEST.json','EXTERNAL_SOURCE_MANIFEST.json','proposal/RESOURCE_BUDGET.json']:
 p=P/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((O/name).read_bytes())
for rel in ['core/contracts.py','diagnostic.py','launch.py']:
 p=P/'code'/rel;s=p.read_text().replace('A10_CAUSAL_C10_PREFLIGHT_V1','A10_CAUSAL_C10_PREFLIGHT_V2').replace('P10_A_CAUSAL_C10_PREFLIGHT_V1','P10_A_CAUSAL_C10_PREFLIGHT_V2').replace('P10_CAUSAL_C10_V1','P10_CAUSAL_C10_V2');p.write_text(s)
p=P/'code/causal_contract.py';s=p.read_text();old="engine.emit('branch_start',branch=branch,state_restored=False,shared_prefix=False)";assert s.count(old)==1;s=s.replace(old,"engine.emit('branch_start',state_restored=False,shared_prefix=False)");p.write_text(s)
(P/'commands').mkdir();(P/'commands/run_proposed_causal_c10.sh').write_text((O/'commands/run_proposed_causal_c10.sh').read_text().replace(str(O),str(P)))
print('Private snapshot initialized; no compute imports or old writes')
