"""CPU-only integration validation and evidence publication. No optimizer or simulator."""
import ast
import contextlib
import copy
import datetime
import io
import json
import os
from pathlib import Path
import subprocess
import unittest
import torch
import numpy as np
from prepare_delivery import W,C,sha,dump,ref
from public_interface import validate_record,public_to_trajectory
from b10_adapters import EventLedger,gaf_view,lvm_pair_indices
from test_public_interface import transitions,events,TEMPLATES
from a_accounting_snapshot.accounting import summarize
import future_jobs

class ReleaseAndMatrixTests(unittest.TestCase):
    def test_current_P00_cannot_start_formal_model_jobs(self):
        self.assertEqual(future_jobs.BASE,C)
        with self.assertRaisesRegex(PermissionError,'P00 permits CPU'):
            future_jobs.authorize(W/'configs/lvm_gpu_probe_2.json',C/'releases/P00_PREP_V1.json')
    def test_e1_matrix_has_three_complete_seeds_equal_loss_budgets(self):
        matrix=json.loads((W/'configs/E1_MATRIX.json').read_text());self.assertEqual(len(matrix['matrix']),12)
        initial={};permutations={}
        for row in matrix['matrix']:
            self.assertEqual(len(row['members']),4)
            for job_id in row['members']:
                job=json.loads((W/'configs'/f'{job_id}.json').read_text());key=job['member']
                initial.setdefault(key,job['inputs']['initial_model']['sha256']);self.assertEqual(initial[key],job['inputs']['initial_model']['sha256'])
                self.assertEqual(job['updates'],4000);self.assertEqual(job['architecture_parameters'],7058);self.assertEqual(job['trainable_modules'],['residual','advantage'])
                key=(job['train_seed'],job['member']);sequence=np.random.default_rng(job['train_seed']*100+job['member']).integers(0,600,100).tolist()
                permutations.setdefault(key,sequence);self.assertEqual(permutations[key],sequence)
        self.assertEqual(len(permutations),12)
        self.assertEqual(len({tuple(v) for v in permutations.values()}),12)
    def test_train600_identity_and_initial_capacity(self):
        job=json.loads((W/'configs/e1_L00_s9101_m1041.json').read_text())
        for entry in job['inputs'].values():self.assertEqual(sha(entry['path']),entry['sha256'])
        rows=json.loads(Path(job['inputs']['train_rows']['path']).read_text());self.assertEqual(len(rows),600)
        self.assertEqual(len({r['episode_id'] for r in rows}),600)
        self.assertEqual(set(r['split'] for r in rows),{'train'})
        state=torch.load(job['inputs']['initial_model']['path'],map_location='cpu',weights_only=True)
        self.assertTrue(all(t.device.type=='cpu' for t in state.values()))
        params=sum(t.numel() for k,t in state.items() if k.endswith('.weight') or k.endswith('.bias'))
        self.assertEqual(params,7058)

def main():
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    stream=io.StringIO();suite=unittest.TestSuite()
    loader=unittest.defaultTestLoader
    suite.addTests(loader.loadTestsFromNames(['test_b10_adapters','test_public_interface']))
    suite.addTests(loader.loadTestsFromTestCase(ReleaseAndMatrixTests))
    with contextlib.redirect_stderr(stream):result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    log=W/'evidence/CPU_TESTS.log';log.write_text(stream.getvalue())
    static=[]
    for p in W.rglob('*.py'):
        if '.git' not in p.parts and '__pycache__' not in p.parts:ast.parse(p.read_text(),filename=str(p));static.append(str(p.relative_to(W)))
    shells=[]
    for p in (W/'commands').glob('*.sh'):
        checked=subprocess.run(['bash','-n',str(p)],text=True,capture_output=True)
        if checked.returncode:raise RuntimeError(checked.stderr)
        shells.append(str(p.relative_to(W)))
    rows,features=transitions();t=public_to_trajectory(rows,state_features_by_sha=features,task_features=[1.,0.],state_feature_sha256='a'*64,language_feature_sha256='b'*64,allow_synthetic=True)
    view=gaf_view([t],split='development')
    dump(W/'evidence/derived_view.synthetic.json',{'synthetic_only':True,'for_training':False,'gaf':{k:(v.tolist() if torch.is_tensor(v) else v) for k,v in view.items()},'lvm_pairs':lvm_pair_indices(t,normal_demo=True)})
    ledger=EventLedger()
    with ledger.operation('guided_sample'):
        with ledger.operation('flow_forward'):pass
    try:
        with ledger.operation('guided_sample'):raise ValueError('explicit CPU synthetic failure')
    except ValueError:pass
    ledger.emit('guided_sample',status='entered');wire=events(ledger,decision_index=3,sampling_index=5)
    shadow=EventLedger()
    with shadow.operation('monitor'):pass
    wire+=events(shadow,methods=[],research_only=True)
    examples=rows+wire
    # Shared schema already carries all seven records; B adds method-specific view manifests.
    for method,target in [('GAF-v1-adapted','success-to-go/MSE'),('VLA-Corrector-adapted','cosine(delta_z)')]:
        row=copy.deepcopy(TEMPLATES['view_manifest']);row['method']['name']=method
        row.update(target=target,transition_count=12,selection_rule='One explicit synthetic development parent; forbidden for real training',actual_execution_length_semantics='12 contiguous per-step records; actual execution length1 per wire record, sliding true10-action windows')
        row['method']['version']='B10-adapter-synthetic-v1'
        if method.startswith('GAF'):
            row['discount']=.99;row['missing_reasons'].pop('discount',None)
        else:row['missing_reasons']['discount']='No discounted target for cosine delta dynamics'
        examples.append(row)
    for row in examples:validate_record(row,allow_synthetic=True)
    (W/'evidence/B_PUBLIC_EXAMPLES.synthetic.jsonl').write_text(''.join(json.dumps(x,allow_nan=False)+'\n' for x in examples))
    dump(W/'evidence/ACCOUNTING_CHECK.json',{'synthetic_only':True,'experiment_actual':summarize(wire),'GAF_deployment':summarize(wire,method='GAF-v1-adapted'),'N_deployment':summarize(wire,method='N'),'A_working_snapshot':ref(W/'a_accounting_snapshot/PROVENANCE.json')})
    info={'status':'pass' if result.wasSuccessful() else 'fail','started_at_utc':started,'finished_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'tests_run':result.testsRun,'failures':[(str(t),e) for t,e in result.failures],'errors':[(str(t),e) for t,e in result.errors],'python_files_ast_parsed':len(static),'shell_files_syntax_checked':shells,'B_public_records_validated':len(examples),'A_public_records_validated':7,'torch_cuda_initialized':torch.cuda.is_initialized(),'resource_counts':{'simulator_attempts':0,'completed_rollouts':0,'vla_sampling_calls':0,'optimizer_updates':0,'model_gpu_inference_calls':0,'gpu_seconds':0},'cpu_only_work':'Synthetic tensor forward/action-gradient operations and one checkpoint CPU tensor format/capacity audit; no optimizer steps','warning':'CPU autograd may probe CUDA device count and emit sandbox OS304 warning; all tensors CPU, torch.cuda.is_initialized is false','test_log':ref(log)}
    dump(W/'evidence/CPU_CHECK_RESULT.json',info);print(json.dumps(info,ensure_ascii=False,indent=2))
    if not result.wasSuccessful() or info['torch_cuda_initialized']:raise SystemExit(1)

if __name__=='__main__':main()
