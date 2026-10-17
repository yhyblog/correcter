from fractions import Fraction
from c_recovery_policy import P as ROOT, POST_SHA as POST_RULE_SHA
from ops_io import read
LOSSES=["L00","L10","L01","L11"]
def validate_selection(row):
    if row.get('task_id')!='A_D24_FULL_Q_LOSS_SELECTION_V1' or row.get('status')!='selected_locked':raise ValueError('A selection identity/status')
    if row.get('test_used') is not False or row.get('no_test_based_change') is not True or row.get('fixed_fit_seed')!=9101:raise ValueError('selection must be dev-only fit9101')
    scores=row['scores'];tasks={r['task'] for r in read(ROOT/'SOURCE_INDEX.json')['source_sets']['DEV']}
    scores=[r for r in scores if r['method']=='Post']
    keys={(r['loss'],r['fit_seed'],r['method'],r['task']) for r in scores}
    expected={(l,s,'Post',t) for l in LOSSES for s in [9101,9102,9103] for t in tasks}
    if len(tasks)!=5 or len(scores)!=60 or keys!=expected:raise ValueError('complete Post development cell identity/duplicates')
    # An old joint-score lock is ineligible even when it happens to pick the same loss.
    criterion=str(row.get('selection_criterion',''))+' '+str(row.get('selection_rule',''))
    refs=[v for v in row.values() if isinstance(v,dict) and v.get('sha256')==POST_RULE_SHA]
    if not refs and not ('post' in criterion.lower() and any(k in criterion.lower() for k in ['post-only','post_only','post only'])):raise ValueError('selection must explicitly declare the Post-only override')
    totals={l:Fraction(0) for l in LOSSES}
    for r in scores:
        if r['valid']!=20 or type(r['successes']) is not int or not 0<=r['successes']<=20:raise ValueError('development denominator')
        totals[r['loss']]+=Fraction(r['successes'],300)
    chosen=min(LOSSES,key=lambda l:(-totals[l],{'L00':0,'L10':1,'L01':1,'L11':2}[l],LOSSES.index(l)))
    if row['chosen_loss']!=chosen:raise ValueError('chosen loss violates Post-only rule')
    return chosen
