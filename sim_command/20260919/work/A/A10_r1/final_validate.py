from pathlib import Path
from copy import deepcopy
import ast
import json
import os
import subprocess
import sys
from campaign_io import BASE, WORK, RESULTS, atomic, heartbeat, sha, now

SNAPSHOT = RESULTS / 'code_snapshot_v3'
sys.path.insert(0, str(SNAPSHOT))
from core.validation import validate
from core.accounting import EventJournal, summarize


def main():
    heartbeat('checking final snapshot v3, B23 examples, and durable three-case cost examples on CPU')
    checks = []
    env = dict(os.environ)
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', CUDA_VISIBLE_DEVICES='')
    runtime = '/mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/environments/lerobot/bin/python'
    for label, cmd, expected in [
        ('system_cpu_suite', ['/usr/bin/python3','-B','-m','pytest','-q','-p','no:cacheprovider',str(SNAPSHOT/'test_cpu_contract.py'),'--basetemp='+str(WORK/'test_artifacts_v3_system')], 0),
        ('runtime_cpu_suite', [runtime,'-B','-m','pytest','-q','-p','no:cacheprovider',str(SNAPSHOT/'test_cpu_contract.py'),'--basetemp='+str(WORK/'test_artifacts_v3_runtime')], 0),
        ('shell_syntax', ['bash','-n',str(RESULTS/'commands_v3/run_proposed_native_preflight.sh'),str(RESULTS/'commands_v3/cpu_checks.sh')], 0),
        ('P00_release_denial', ['bash',str(RESULTS/'commands_v3/run_proposed_native_preflight.sh'),str(BASE/'releases/P00_PREP_V1.json')], 1),
        ('full_runtime_AST', [runtime, '-B', '-c',
            'import pathlib,ast; p=pathlib.Path.cwd(); f=list(p.rglob("*.py")); [ast.parse(x.read_text(),filename=str(x)) for x in f]; print("AST passed",len(f),"files")'], 0)]:
        result = subprocess.run(cmd, cwd=SNAPSHOT, env=env, text=True, capture_output=True, timeout=60)
        good = result.returncode == expected and (label != 'P00_release_denial' or 'Formal compute is not released by current CONTROL' in result.stderr)
        checks.append({'name': label, 'command': cmd, 'returncode': result.returncode,
                       'expected_returncode': expected, 'status': 'passed' if good else 'failed',
                       'stdout': result.stdout, 'stderr': result.stderr})
        print(label, result.returncode, good, result.stdout.strip()[-120:])
        if not good:
            atomic(WORK / 'FINAL_CPU_VALIDATION.json', {'status':'failed','checks':checks})
            raise RuntimeError('Final CPU check failed')
    schema = json.loads((RESULTS/'interface_v1/interface.schema.json').read_text())
    b_result = json.loads((BASE/'receipts/B/B10_RESULT.json').read_text())
    b_manifest = Path(next(x['path'] for x in b_result['artifacts'] if x['path'].endswith('ARTIFACT_MANIFEST.json')))
    b_examples = b_manifest.parent / 'evidence/B_PUBLIC_EXAMPLES.synthetic.jsonl'
    examples = [json.loads(line) for line in b_examples.read_text().splitlines()]
    for row in examples: validate(row, schema)
    checks.append({'name':'B_published_examples_semantic_validation','status':'passed','records':len(examples),
                   'input':str(b_examples),'sha256':sha(b_examples)})
    target = RESULTS / 'accounting_examples_v1'
    target.mkdir(exist_ok=False)
    template = next(json.loads(line) for line in (RESULTS/'interface_v1/examples.jsonl').read_text().splitlines()
                    if json.loads(line)['record_type']=='event')
    summaries = []
    for name in ['successful_return','partial_failure','missing_terminal']:
        local = deepcopy(template); local['episode_id'] = 'synthetic-' + name
        journal = EventJournal(target / (name + '.jsonl'), local)
        call = journal.enter('anchor_sample', methods=['Post'], units={'vla_sampling_calls':1})
        flow = journal.enter('flow_forward', methods=['Post'], units={'flow_forward_calls':1}, parent=call)
        if name != 'missing_terminal':
            journal.finish(flow, error='injected CPU fixture error' if name=='partial_failure' else None)
            journal.finish(call, error='injected CPU fixture error' if name=='partial_failure' else None)
        rows = [json.loads(line) for line in journal.path.read_text().splitlines()]
        for row in rows: validate(row,schema)
        summary = summarize(rows)
        assert summary['counts']['vla_sampling_calls'] == summary['counts']['flow_forward_calls'] == 1
        summaries.append({'case':name,'path':str(journal.path),'sha256':sha(journal.path),'summary':summary})
    atomic(target/'SUMMARY.json', {'synthetic':True,'examples':summaries,
        'charge_rule':'resource_units are identical metadata, entered counted once; terminal absence retains counts/incomplete status',
        'real_resource_counts':{'simulator_attempts':0,'vla_sampling_calls':0,'optimizer_updates':0,'gpu_seconds':0}})
    manifest = json.loads((SNAPSHOT/'CODE_MANIFEST.json').read_text())
    for row in manifest['files']:
        assert sha(SNAPSHOT/row['path']) == row['sha256']
    ready = json.loads((RESULTS/'interface_v1/INTERFACE_READY.json').read_text())
    checks.append({'name':'immutable_code_manifest','status':'passed','files':len(manifest['files']),
                   'path':str(SNAPSHOT/'CODE_MANIFEST.json'),'sha256':sha(SNAPSHOT/'CODE_MANIFEST.json')})
    checks.append({'name':'three_durable_cost_lifecycle_examples','status':'passed','path':str(target/'SUMMARY.json')})
    atomic(WORK/'FINAL_CPU_VALIDATION.json', {'status':'passed','checked_at_utc':now(),'checks':checks,
        'runtime_AST_python':'3.12.13 (vendored lerobot contains PEP695 syntax; system Python3.11 is only the CPU gate/test runner)',
        'synthetic_examples_are_not_real_model_calls':True,
        'real_resource_counts':{'simulator_attempts':0,'vla_sampling_calls':0,'optimizer_updates':0,'gpu_seconds':0}})
    print('all final checks passed; B records:',len(examples))


if __name__ == '__main__': main()
