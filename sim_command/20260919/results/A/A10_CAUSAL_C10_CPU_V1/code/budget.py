"""Exact upper bounds from this integration's concrete source call sites.
Units named *_alias are never separate operations. Native journal scopes
remain separate and combined amounts charge each physical entry once.
"""
from native.graphics_contract import CAPS as GRAPHICS
from native.initialization import EXPECTED_CAPS as INITIALIZATION

def numeric_caps(branch):
    sampling=3 if branch=='Post' else 4
    gradients=1 if branch=='Post' else 3
    objectives=3 if branch=='Post' else 8
    zeros=['training_updates','completed_rollouts','optimizer_updates','vla_backward_calls','vla_parameter_backward_calls',
           'critic_parameter_updates','baseline_rollouts','environment_state_restores','retries','deletions','static_scene_constructions']
    return dict({k:0 for k in zeros},simulator_attempts=1,native_nvml_identity_queries=1,model_initializations=9,
        policy_model_loads=1,policy_state_file_loads=1,policy_state_dict_loads=1,critic_model_loads=4,
        D_model_initializations=2,G0_model_initializations=2,D_model_loads=2,G0_model_loads=2,
        tokenizer_loads=1,preprocessor_loads=1,postprocessor_loads=1,normalizer_transform_loads=1,projection_loads=1,
        context_builds=6,preprocessor_calls=6+sampling,tokenizer_calls=7+sampling,image_preprocessing_calls=6+sampling,
        visual_encoder_forwards=6+3*sampling,language_embedding_forwards=1+sampling,encoder_forward_calls=7+4*sampling,
        spatial_projection_calls=6,prefix_transformer_forwards=sampling,action_expert_forwards=10*sampling,
        flow_forward_calls=10*sampling,noise_draws=sampling,vla_sampling_calls=sampling,model_gpu_inference_calls=sampling,
        critic_feature_transforms=4,critic_forward_calls=4*objectives,objective_forward_calls=objectives,
        action_gradient_calls=gradients,critic_backward_calls=gradients,post_action_gradient_calls=1 if branch=='Post' else 0,
        velocity_action_gradient_calls=3 if branch=='Velocity' else 0,own_projection_calls=2,raw_constraint_audits=1,
        postprocessor_calls=sampling,reset_observation_calls=1,observation_calls=17,control_observation_calls=16,
        env_steps=16,monitor_calls=1,D_forward_calls=4,G0_forward_calls=2)

def sum_units(*scopes):
    keys=set().union(*(s.keys() for s in scopes))
    return {k:sum(s.get(k,0) for s in scopes) for k in sorted(keys)}

def branch_caps(branch):return sum_units(numeric_caps(branch),INITIALIZATION,GRAPHICS)
LAUNCHER={'native_nvml_identity_queries':1}
BRANCHES={branch:branch_caps(branch) for branch in ('Post','Velocity')}
TOTAL=sum_units(LAUNCHER,*BRANCHES.values())

def validate_dynamic_counts(used,branch,controls,complete):
    # Maximum successful C10 path must match the complete quote. Early natural
    # termination has smaller actual entered/returned counts, not fake zeros.
    caps=BRANCHES[branch]
    if set(used)!=set(caps) or any(type(v)is not int or v<0 or v>caps[k] for k,v in used.items()):raise ValueError('Invalid aggregate branch counters')
    if complete and used!=caps:raise ValueError('Completed maximal path differs from exact source quote')
    if used['env_steps']!=controls or used['control_observation_calls']!=controls or used['observation_calls']!=1+controls:
        raise ValueError('Native controls and full observation returns differ')
    expected_physics=(controls*400)//30
    if used['policy_do_simulation_calls']!=controls or used['policy_physics_substeps']!=expected_physics:raise ValueError('Control substep mismatch')
    if used['policy_mj_forward_calls']!=controls or used['native_mj_forward_calls']!=210+controls:raise ValueError('Native mj_forward accounting mismatch')
    if used['render_calls']!=1+controls or used['rgb_readback_calls']!=1+controls or used['mujoco_scene_updates']!=1+controls:
        raise ValueError('Observation render accounting mismatch')
    return True
