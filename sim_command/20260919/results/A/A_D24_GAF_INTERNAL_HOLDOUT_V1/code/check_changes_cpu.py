"""Only new action binding, parent/source metadata and real GAF hook with fake critics."""
import ast
from pathlib import Path
import paths
from paths import ROOT
from qio import read,new_json,utc


def main():
    import numpy as np
    import torch
    from materialize import inverse_commands
    from gaf_runtime import Ledger,make_adapter,pi05_denoiser_hook
    for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text(),filename=str(p))
    binding=read(ROOT/'data/ACTION_BINDING.json');q01=np.asarray(binding['q01'],np.float32);q99=np.asarray(binding['q99'],np.float32)
    cmds=np.array([[-1,-.2,.2,1],[.1,.5,-.8,0]],np.float32)
    internal=inverse_commands(cmds,q01,q99,binding['eps']);back=(internal+1)*(q99-q01)/2+q01
    assert np.allclose(back,cmds,rtol=0,atol=4e-7)
    decision=read(ROOT/'config/HOLDOUT.json');data=read(ROOT/'data/MATERIALIZATION_RESULT.json');sources=read(ROOT/'config/EVAL_SOURCES_V1.json')['rows']
    assert data['summaries']['train']['actual_windows']==27830 and data['summaries']['development']['actual_windows']==8494
    assert set(data['summaries']['train']['parent_ids'])==set(decision['training_parents'])
    assert set(data['summaries']['development']['parent_ids'])==set(decision['holdout_parents'])
    tasks=sorted({s['task'] for s in sources});assert len(sources)==500 and len(tasks)==50 and len({s['source_id'] for s in sources})==500
    shards=[[s['source_id'] for s in sources if tasks.index(s['task'])%8==slot] for slot in range(8)]
    assert len([s for rows in shards for s in rows])==len(set(s for rows in shards for s in rows))==500
    class FakeCritic:
        def __call__(self,obs_features,action_chunk,**kw):return action_chunk.sum((1,2))
    class FakeFlow:
        def denoise_step(self,*,x_t,timestep):return torch.ones_like(x_t)
    ledger=Ledger();adapter=make_adapter([FakeCritic() for _ in range(3)],np.zeros(4,np.float32),np.zeros(2048,np.float32),'cpu',ledger)
    model=FakeFlow();original=model.denoise_step
    with torch.inference_mode(),pi05_denoiser_hook(model,adapter):
        x=torch.zeros(1,50,32);v=model.denoise_step(x_t=x,timestep=torch.tensor([.5]))
    assert torch.equal(v[:,10:,:],torch.ones_like(v[:,10:,:])) and torch.equal(v[:,:10,4:],torch.ones_like(v[:,:10,4:]))
    assert torch.all(v[:,:10,:4]<1) and model.denoise_step==original
    assert ledger.entered==ledger.returned and ledger.entered['critic_forward']==3 and ledger.entered['critic_backward']==1 and ledger.entered['flow_forward']==1
    try:
        with pi05_denoiser_hook(model,adapter):raise RuntimeError('synthetic sampling failure')
    except RuntimeError:pass
    assert model.denoise_step==original and not hasattr(model,'_b10_guidance_active')
    new_json(ROOT/'CPU_CHANGED_PATH_CHECK.json',dict(status='PASS',utc=utc(),synthetic=True,scientific_compute=0,
        scope=['frozen quantile command roundtrip','fixed15/2 parent tensors','500 source partition without duplicates',
               'real GAF hook/fake critics under inference_mode','unchanged raw tail/unused coordinates','hook restored after exception','changed Python AST'],
        actual_model_initializations=0,explicit_hardware_queries=0,explicit_CUDA_API_calls=0,torch_internal_availability_queries="not intercepted",environment_calls=0,shard_sizes=list(map(len,shards))))
    print('PASS changed-path CPU checks')

if __name__=='__main__':main()
