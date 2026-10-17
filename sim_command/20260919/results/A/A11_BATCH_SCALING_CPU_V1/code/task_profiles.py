"""Five narrowly audited task paths; no native import or compatibility claim."""
from core.contracts import ContractError

PROFILES = {
    'disassemble-v3': dict(module='metaworld.envs.sawyer_disassemble_peg_v3', cls='SawyerNutDisassembleEnvV3', reset_model_forwards=2, instruction='Pick a nut out of a peg'),
    'pick-place-wall-v3': dict(module='metaworld.envs.sawyer_pick_place_wall_v3', cls='SawyerPickPlaceWallEnvV3', reset_model_forwards=1, instruction='Pick a puck, bypass a wall and place the puck'),
    'shelf-place-v3': dict(module='metaworld.envs.sawyer_shelf_place_v3', cls='SawyerShelfPlaceEnvV3', reset_model_forwards=2, instruction='Pick and place a puck onto a shelf'),
    'stick-pull-v3': dict(module='metaworld.envs.sawyer_stick_pull_v3', cls='SawyerStickPullEnvV3', reset_model_forwards=2, instruction='Grasp a stick and pull a box with the stick'),
    'stick-push-v3': dict(module='metaworld.envs.sawyer_stick_push_v3', cls='SawyerStickPushEnvV3', reset_model_forwards=2, instruction='Grasp a stick and push a box using the stick'),
}
CUTS = (5, 55)
FIXED_SLOTS = [('disassemble-v3',0,5), ('pick-place-wall-v3',0,5),
    ('stick-pull-v3',0,5), ('stick-push-v3',0,5), ('disassemble-v3',1,55),
    ('pick-place-wall-v3',1,55), ('shelf-place-v3',1,55), ('stick-pull-v3',1,55)]

def profile(task, cut):
    if type(task) is not str or task not in PROFILES:
        raise ContractError('task outside five-task static allowlist')
    if type(cut) is not int or cut not in CUTS:
        raise ContractError('cut must be strict integer 5 or 55')
    return PROFILES[task]

def validate_engine(engine):
    row = profile(engine.task, engine.cut)
    if type(engine.H) is not int or engine.H != 10 or type(engine.target) is not int or engine.target != 300:
        raise ContractError('unfrozen H10/absolute s300')
    if engine.cut % 10 != 5:
        raise ContractError('cut must retain five old queue controls')
    return row

def validate_config(cfg):
    s = cfg['source']; c = cfg['control']; row = profile(s['task'], s['cut'])
    if s['instruction'] != row['instruction'] or s['split'] != 'train' or s['prefix_mode'] != 'cold_policy_replay':
        raise ContractError('task language/split/replay mismatch')
    if c['cut'] != s['cut'] or c['H'] != 10 or c['episode_max_steps'] != 300 or s['absolute_target'] != 300:
        raise ContractError('source/control temporal mismatch')
    if c['normal_reuse'] is not False or c['cold_replay'] is not True or c['maximum_attempts'] != 15:
        raise ContractError('cold branch supervision changed')
    return row

def initialization_caps(task, cut=5):
    row = profile(task, cut)
    # MT1 _N_GOALS=50; wrapper reset1; diagnostic reset1. Native reset invokes
    # reset_model twice; each of these five reset_model paths calls _reset_hand(50).
    resets = 50 + 1 + 1
    forwards = 2 + resets * 2 * row['reset_model_forwards']
    return dict(model_initializations=0, environment_instances=2, wrapper_instances=1,
        taskset_constructions=1, taskset_reset_calls=50, wrapper_initialization_reset_calls=1,
        initialization_reset_calls=51, diagnostic_reset_calls=1, environment_reset_calls=resets,
        reset_model_calls=2*resets, initialization_do_simulation_calls=resets*2*50,
        initialization_physics_substeps=resets*2*50*5, policy_do_simulation_calls=300,
        policy_physics_substeps=4000, native_mj_forward_calls=forwards+300,
        initialization_mj_forward_calls=forwards, policy_mj_forward_calls=300)
