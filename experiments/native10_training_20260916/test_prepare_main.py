from collections import Counter,defaultdict
import pytest
from . import prepare_main
from .protocol import ProtocolError,require_stage_budget


def test_pending_round1_boundaries_and_budget_are_explicit():
    c=prepare_main.build_round1();assert c['status']=='pending'
    assert sum(v['simulator_attempts'] for v in c['budget']['stages'].values())==50000
    assert sum(v['training_updates'] for v in c['budget']['stages'].values())==51200
    bank=c['main_collection']['banks']['round1_labels_v1']
    lookup={x['episode_id']:x for x in c['episode_manifest']}
    rows=[lookup[x] for x in bank['episode_ids']]
    assert Counter(x['split'] for x in rows)=={'train':300,'development':100}
    assert all(x['round']==1 for x in rows if x['split']=='train')
    assert not any(x.get('replacement_of') for x in rows)
    assert c['split_replicates']==dict(train=4,development=4,calibration=2,heldout=4)
    buckets=defaultdict(Counter)
    for row in rows:
        buckets[(row['task'],row['split'],row['cut_rule']['kind'])][bank['channel_radius_by_episode'][row['episode_id']]]+=1
    assert all(count[.5]==count[1.] for count in buckets.values())
    for stage in ('round1_labels','technical_reserve','training_round1','heldout'):
        with pytest.raises(ProtocolError):require_stage_budget(c,stage)
