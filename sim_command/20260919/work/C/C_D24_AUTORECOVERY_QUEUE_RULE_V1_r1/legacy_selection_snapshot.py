from fractions import Fraction
LOSSES=["L00","L10","L01","L11"]
def validate_selection(row):
    if row.get('task_id')!='A_D24_FULL_Q_LOSS_SELECTION_V1' or row.get('status')!='selected_locked':raise ValueError('A selection identity/status')
    if row.get('test_used') is not False or row.get('no_test_based_change') is not True or row.get('fixed_fit_seed')!=9101:
        raise ValueError('selection must be dev-only with fixed fit9101')
    if row.get('development_valid')!=2400 or row.get('development_technical_missing')!=0:raise ValueError('incomplete development denominators')
    scores=row['scores'];keys={(r['loss'],r['fit_seed'],r['method'],r['task']) for r in scores}
    tasks=sorted({r['task'] for r in scores})
    expected={(l,s,b,t) for l in LOSSES for s in [9101,9102,9103] for b in ['Post','Velocity'] for t in tasks}
    if len(tasks)!=5 or len(keys)!=120 or len(scores)!=120 or keys!=expected:raise ValueError('development cell identity/duplicates')
    totals={l:Fraction(0) for l in LOSSES}
    for r in scores:
        if r['valid']!=20 or type(r['successes']) is not int or not 0<=r['successes']<=20:raise ValueError('development cell denominator')
        totals[r['loss']]+=Fraction(r['successes'],600)
    for loss in LOSSES:
        r=row['loss_scores'][loss]
        if r['valid']!=600 or Fraction(r['score_numerator'],r['score_denominator'])!=totals[loss]:raise ValueError('development score mismatch')
    chosen=min(LOSSES,key=lambda l:(-totals[l],{'L00':0,'L10':1,'L01':1,'L11':2}[l],LOSSES.index(l)))
    if row['chosen_loss']!=chosen:raise ValueError('chosen loss violates locked rule')
    return chosen
