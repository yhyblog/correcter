from collections import Counter
from .register_main_v2 import build_manifest
from .protocol import TASKS,episode_key


def test_preserve_old_slots_append_states_and_keep_ordered_reserves_separate():
    original=[]
    for split,n in [('p0',20),('train',600),('development',100),('calibration',50),('heldout',50)]:
        for i in range(n):
            seed=1000+len(original);task=TASKS[i%5];key=episode_key(task,seed)
            original.append(dict(episode_id=key,case_id=key,task=task,env_seed=seed,split=split,
                round=1 if split=='train' and i<300 else 2 if split=='train' else None,
                cut_rule={'kind':'first_alarm'}))
    primary,reserve,mapping=build_manifest(original)
    assert primary[:820]==original and len(primary)==920 and len(reserve)==1800
    assert Counter(r['split'] for r in primary)==dict(p0=20,train=600,development=100,calibration=100,heldout=100)
    registry={r['episode_id']:r for r in primary+reserve}
    for key,ordered in mapping.items():
        assert len(ordered)==2 and registry[key]['split']!='p0'
        for i,identity in enumerate(ordered):
            row=registry[identity]
            assert row['replacement_ordinal']==i+1 and row['replacement_of']==key
            assert all(row.get(k)==registry[key].get(k) for k in ('split','task','round','cut_rule'))
