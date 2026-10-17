"""Reuse frozen Smol training tensors; pair every loss at initialization and sampling."""
from pathlib import Path
import numpy as np
import torch
import paths
from paths import ROOT, ARTIFACTS, CONFIG
from qio import read, new_json, ref, utc
from corrector.critic import TenStepCritic, STATE_KEYS
from experiments.native10_training_20260916.protocol import seed_for

torch.set_num_threads(4)
assert read(ARTIFACTS/'DATA_SUMMARY.json')['Q_ready']
train = torch.load(ARTIFACTS/'dataset/train_parents.pt', map_location='cpu', weights_only=True)
dev = torch.load(ARTIFACTS/'dataset/development_parents.pt', map_location='cpu', weights_only=True)
pre = torch.load(ARTIFACTS/'dataset/Q_PREPROCESSING.pt', map_location='cpu', weights_only=True)
assert len(train['parent_ids']) == len(set(train['parent_ids']))
test = read(read(ROOT/'SOURCE_INDEX.json')['full_sources']['path'])['sources']
assert not set(train['parent_ids']) & set(dev['parent_ids'])
assert not (set(train['parent_ids']) | set(dev['parent_ids'])) & {x['source_id'] for x in test}
assert all('train' in s for s in train['parent_ids'])
assert set(pre) == {'norm_mean','norm_std','residual_scale','visual_center','visual_basis','visual_scale','language_center','language_basis','language_scale'}
eligible = torch.where(train['candidate_weights'][:,0] > 0)[0].numpy()
assert len(eligible) == 188 and tuple(train['actions'].shape[1:]) == (3,10,4)
assert torch.isfinite(train['actions']).all() and train['actions'].abs().max() <= 1
assert torch.isfinite(train['labels']).all() and train['labels'].min() >= 0 and train['labels'].max() <= 1
out = ROOT/'prepared'
initial = []
for member in CONFIG['member_seeds']:
    initial_seed = seed_for('full_Q_initialization', 9101, member, namespace='corrector_full_Q_loss_v1')
    stream_seed = seed_for('full_Q_training_stream', 9101, member, namespace='corrector_full_Q_loss_v1')
    torch.manual_seed(initial_seed)
    model = TenStepCritic(pre)
    assert sum(p.numel() for p in model.parameters()) == 7058
    assert all(p.requires_grad for p in model.parameters())
    checkpoint = out/('initial_'+str(member)+'.pt')
    torch.save(model.state_dict(), checkpoint)
    rng = np.random.default_rng(stream_seed)
    bootstrap = []
    for task in sorted(set(train['tasks'])):
        ids = [int(i) for i in eligible if train['tasks'][i] == task]
        if ids:
            bootstrap.extend(rng.choice(ids, len(ids), replace=True).tolist())
    # Store only the 4000 paired minibatches, not an event-by-event ledger.
    batches = rng.choice(bootstrap, size=(4000,32), replace=True)
    np.save(out/('batches_'+str(member)+'.npy'), batches)
    initial.append(dict(member=member, fit_seed=9101, initialization_seed=initial_seed,
        training_stream_seed=stream_seed, bootstrap_parent_indices=bootstrap,
        initialization=str(checkpoint), minibatches=str(out/('batches_'+str(member)+'.npy'))))
with torch.no_grad():
    features = model.features({k:train[k] for k in STATE_KEYS})
assert features.shape == (188,61) and torch.isfinite(features).all()
pack = {k:train[k] for k in ['actions','labels','candidate_weights','gain_weights','pair_weight']}
pack['features'] = features
torch.save(pack, out/'TRAIN_TENSORS.pt')
new_json(out/'PREPARATION.json',dict(status='ready',at_utc=utc(),train_parents=188,
    development_parents=len(dev['parent_ids']),test_sources=500,ordinary_source_intersections_empty=True,
    preprocessing_source=ref(ARTIFACTS/'dataset/Q_PREPROCESSING.pt'),
    training_source=str(ARTIFACTS/'dataset/train_parents.pt'),source_weighting='uniform parent, task-stratified source bootstrap; frozen candidate/gain/pair alias masks',
    initializations=initial,loss_independent_initialization_and_minibatches=True,trainable_parameters=7058,
    fits=16,total_updates=64000,batch_size=32,old_network_parameters_loaded=False,
    base_updates=0,D_updates=0,G0_updates=0,new_collection=0,CUDA_calls=0))
print('PREPARED_16_FULL_Q_FITS_64000_UPDATES')
