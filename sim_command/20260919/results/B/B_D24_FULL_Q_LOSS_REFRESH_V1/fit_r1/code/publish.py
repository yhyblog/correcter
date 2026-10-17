"""Publish actual candidate fits; no model selection on Smol test."""
import json
import shutil
from pathlib import Path
import paths
from paths import ROOT,CONFIG,CAMPAIGN
from qio import read,new_json,atomic_json,ref,sha,utc

def publish():
    pipeline=Path(CONFIG['root_pipeline']);fits=[]
    for loss in CONFIG['losses']:
        for member in CONFIG['member_seeds']:
            p=ROOT/'fits'/(loss+'_fit9101_member'+str(member))/'RESULT.json'
            if p.exists():fits.append(read(p))
    ready=len(fits)==16 and all(r['status']=='complete' and r['updates']==4000 and r['parameters']==7058 for r in fits)
    updates=sum(r['updates'] for r in fits);assert updates<=64000
    models={}
    if ready:
        for loss in CONFIG['losses']:
            asset=pipeline/'models'/loss;hashes={}
            for i,member in enumerate(CONFIG['member_seeds']):
                src=ROOT/'fits'/(loss+'_fit9101_member'+str(member))/'final.pt'
                dst=asset/'models/refit'/('member_'+str(i))/'selected.pt';dst.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(src,dst);hashes[str(i)]=sha(dst)
            new_json(asset/'ranking.json',dict(horizon=10,model_hashes=hashes,loss=loss,fit_seed=9101,member_seeds=CONFIG['member_seeds'],selection='fixed final checkpoint; loss chosen later by A development'))
            new_json(asset/'config.json',dict(loss=loss,fit_seed=9101,raw_horizon=50,horizon=10,base='SmolVLA050000',normalization_train_only=True))
            models[loss]=dict(asset_root=str(asset),ranking=ref(asset/'ranking.json'))
    report=dict(status='complete' if ready else 'partial',at_utc=utc(),task_id=CONFIG['task_id'],run_id=CONFIG['run_id'],
        attempts=0,current_run_attempts=0,cumulative_B_attempts=CONFIG['planned_prior_attempts'],new_optimizer_updates=updates,
        fit_count=len(fits),expected_fits=16,fit_seed=9101,fit_results=fits,new_collection_attempts=0,D_G0_base_updates=0,
        chosen_loss=None,candidate_assets=models,all_owned_descendants_exited_before_publication=True,A_waits_for_B=False)
    atomic_json(ROOT/'FINAL_SUMMARY.json',report)
    atomic_json(CAMPAIGN/CONFIG['result_receipt'],dict(report,result_root=str(ROOT)))
    if ready:
        new_json(pipeline/'CANDIDATES_READY.json',dict(report,status='CANDIDATES_READY',preparation=ref(pipeline/'prepared/PREPARATION.json'),
            selection_dependency=CONFIG['selection_path'],test_started=False,no_native_test_loss_selection=True))
    print(json.dumps(dict(status=report['status'],fits=len(fits),updates=updates)))

if __name__=='__main__':publish()
