"""Frozen static MT50 table; runtime closure qualification remains per parent."""
from core.contracts import ContractError,PACKAGE,read
from source_plan import select_next_slots
TABLE=read(PACKAGE/'config/MT50_TASK_TABLE.json')
PROFILES={row['task']:row for row in TABLE['rows']}
CUTS = (5, 55)
FIXED_SLOTS=()  # source selection belongs to frozen SOURCES_V2, not old eight slots

def profile(task, cut):
    if type(task) is not str or task not in PROFILES:
        raise ContractError('task outside frozen MT50 catalog')
    if type(cut) is not int or cut not in CUTS:
        raise ContractError('cut must be strict integer 5 or 55')
    row=PROFILES[task]
    if row['static_cap_status']!='known' or row.get('initialization_caps') is None:
        raise ContractError('unknown task initialization cap; retain source identity and block: '+task)
    return row

def validate_engine(engine):
    row = profile(engine.task, engine.cut)
    if type(engine.H) is not int or engine.H != 10 or type(engine.target) is not int or engine.target != 300:
        raise ContractError('unfrozen H10/absolute s300')
    if engine.cut % 10 != 5:
        raise ContractError('cut must retain five old queue controls')
    return row

def validate_config(cfg):
    s = cfg['source']; c = cfg['control']; row = profile(s['task'], s['cut'])
    if s['instruction'] != row['instruction'] or s['split'] not in ('train','development') or s['prefix_mode'] != 'cold_policy_replay':
        raise ContractError('task language/split/replay mismatch')
    if c['cut'] != s['cut'] or c['H'] != 10 or c['episode_max_steps'] != 300 or s['absolute_target'] != 300:
        raise ContractError('source/control temporal mismatch')
    if c['normal_reuse'] is not False or c['cold_replay'] is not True or c['maximum_attempts'] != 15:
        raise ContractError('cold branch supervision changed')
    return row

def initialization_caps(task, cut=5):
    row = profile(task, cut)
    return dict(row['initialization_caps'])
