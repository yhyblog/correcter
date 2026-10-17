"""Publish own X candidates; consume A's complete dev-only locked loss once."""
from fractions import Fraction
from pathlib import Path
from paths import ROOT,SELECTION,TASK
from qio import read,new_json,ref,sha,utc

LOSSES=['L00','L10','L01','L11']

def publish_candidates():
    ensembles={};results=[]
    for loss in LOSSES:
        assets=ROOT/'ensembles'/f'{loss}_s9101';hashes={};members=[]
        for member in [1041,1042,1043,1044]:
            result=read(ROOT/'training'/f'{loss}_s9101_m{member}'/'RESULT.json')
            if result['status']!='complete' or result['updates']!=4000 or result['trainable_parameters']!=7058 or result['old_network_loaded']:
                raise ValueError('incomplete fresh full-Q candidate')
            checkpoint=Path(result['checkpoint']);digest=sha(checkpoint)
            if digest!=result['checkpoint_sha256']:raise ValueError('own Q checkpoint changed')
            target=assets/'models/refit'/f'member_{member}'/'selected.pt';target.parent.mkdir(parents=True,exist_ok=True);target.symlink_to(checkpoint)
            hashes[str(member)]=digest;members.append(dict(member=member,checkpoint=str(checkpoint),sha256=digest));results.append(result)
        new_json(assets/'ranking.json',dict(horizon=10,model_hashes=hashes,loss=loss,fit_seed=9101,selection='fixed4000 final; own X train-only preprocessing',members=members))
        ensembles[loss]=dict(loss=loss,fit_seed=9101,assets=str(assets),members=members,ranking=ref(assets/'ranking.json'))
    row=dict(task_id=TASK,status='CANDIDATES_READY',utc=utc(),fits=16,actual_optimizer_updates=sum(r['updates'] for r in results),
        trainable_per_member=7058,ensembles=ensembles,results=results,all_parameters_from_scratch=True,
        selected_fit_fixed_in_advance=9101,paired_initialization_and_batches=True,selection_dependency=str(SELECTION),
        new_collection=0,D_G0_updates=0,SFT_updates=0,test_used=False)
    assert row['actual_optimizer_updates']==64000
    new_json(ROOT/'CANDIDATES_READY.json',row);return row

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

def try_consume():
    if (ROOT/'SELECTION_CONSUMED.json').exists():return consumed_selection()
    lock_path=SELECTION.parent/'SELECTION_LOCK.json'
    if not SELECTION.exists() or not lock_path.exists():return None
    selected_ref=ref(SELECTION);row=read(SELECTION);lock=read(lock_path)
    if selected_ref['sha256']!=lock['selection']['sha256'] or not lock['immutable']:raise ValueError('A selection lock not valid')
    chosen=validate_selection(row)
    candidates=read(ROOT/'CANDIDATES_READY.json');own=candidates['ensembles'][chosen]
    consumed=dict(task_id=TASK,utc=utc(),chosen_loss=chosen,fixed_fit_seed=9101,A_selection=selected_ref,A_lock=ref(lock_path),
        own_assets=own['assets'],own_members=own['members'],own_ranking=own['ranking'],
        A_pi05_weights_loaded=False,local_test_used=False,selection_immutable=True)
    new_json(ROOT/'SELECTION_CONSUMED.json',consumed);return consumed_selection()

def consumed_selection():
    row=read(ROOT/'SELECTION_CONSUMED.json')
    if sha(row['A_selection']['path'])!=row['A_selection']['sha256']:raise ValueError('locked A selection changed')
    if sha(row['own_ranking']['path'])!=row['own_ranking']['sha256']:raise ValueError('own ensemble ranking changed')
    if not Path(row['own_assets']).is_relative_to(ROOT/'ensembles'):raise ValueError('must use own X Q weights')
    return row
