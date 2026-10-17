"""Dev-only locked A pi05 ensemble; no local X model or test-based choice."""
import copy
from fractions import Fraction
from pathlib import Path
from paths import ROOT,ORIGINAL,SELECTION,TASK
from qio import read,new_json,ref,sha,utc,verify
LOSSES=['L00','L10','L01','L11']
POST_RULE_SHA='fa907477112320e7f8356282c5ba64742452172dee998e9efc20a82b92b9c4b1'

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

def try_consume():
    target=ROOT/'SELECTION_CONSUMED.json'
    if target.exists():return consumed_selection()
    lock_path=ORIGINAL/'SELECTION_LOCK.json'
    if not SELECTION.is_file() or not lock_path.is_file():return None
    row=read(SELECTION);selection_ref=ref(SELECTION);lock=read(lock_path)
    if lock.get('immutable') is not True or lock['selection']['sha256']!=selection_ref['sha256'] or Path(lock['selection']['path'])!=SELECTION:raise ValueError('A selection lock mismatch')
    chosen=validate_selection(row);e=row['ensemble'];expected=ORIGINAL/'ensembles'/f'{chosen}_s9101'
    if Path(e['assets'])!=expected or e['key']!=expected.name or e['loss']!=chosen or e['fit_seed']!=9101:raise ValueError('A pi05 ensemble identity')
    if {str(m) for m in [1041,1042,1043,1044]}!=set(e['member_hashes']):raise ValueError('four fixed members required')
    if len(e['members'])!=4 or {m['member'] for m in e['members']}!={1041,1042,1043,1044}:raise ValueError('member identity')
    if Path(e['ranking']['path'])!=expected/'ranking.json':raise ValueError('ranking ownership')
    verify(e['ranking']);ranking=read(expected/'ranking.json')
    if ranking['model_hashes']!=e['member_hashes']:raise ValueError('ranking ensemble mismatch')
    for m in e['members']:
        path=expected/'models/refit'/f"member_{m['member']}"/'selected.pt'
        if path.resolve()!=Path(m['checkpoint']).resolve() or not path.resolve().is_relative_to(ORIGINAL/'training') or sha(path)!=e['member_hashes'][str(m['member'])] or m['sha256']!=e['member_hashes'][str(m['member'])]:raise ValueError('small selected Q checkpoint mismatch')
    new_json(target,dict(task_id=TASK,utc=utc(),chosen_loss=chosen,fixed_fit_seed=9101,A_selection=selection_ref,A_lock=ref(lock_path),ensemble=e,local_test_used=False,local_X_weights_used=False,immutable=True))
    return consumed_selection()

def consumed_selection():
    row=read(ROOT/'SELECTION_CONSUMED.json');verify(row['A_selection']);verify(row['A_lock']);verify(row['ensemble']['ranking'])
    return row

def locked_selection():
    row=consumed_selection();return read(row['A_selection']['path'])

def engine_config(job):
    if job['stage']!='MAIN' or job['H'] not in [40,50] or job['mode']!='G0-multi' or job['method'] not in ['Post','Velocity'] or job['loss']!='SELECTED' or job['fit_seed']!=9101:raise ValueError('C selected pi05 scope')
    e=consumed_selection()['ensemble'];cfg=copy.deepcopy(read(ROOT/'config/CONFIG.json'))
    cfg.update(critic_assets=e['assets'],selected_model=dict(member_hashes=e['member_hashes'],ensemble=e),loss=e['loss'],fit_seed=e['fit_seed'])
    return cfg
