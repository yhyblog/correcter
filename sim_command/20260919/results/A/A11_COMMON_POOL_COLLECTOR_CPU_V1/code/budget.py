from native.graphics_contract import CAPS as GRAPHICS
from native.initialization import EXPECTED_CAPS as INITIALIZATION
from pool_protocol import ARMS
ZERO=['D_forward_calls','G0_forward_calls','critic_forward_calls','action_gradient_calls',
      'training_updates','optimizer_updates','environment_state_restores','retries','deletions']
def numeric_caps(name):
    n=33 if name=='normal' else 30
    return dict({k:0 for k in ZERO},simulator_attempts=1,native_nvml_identity_queries=1,
        model_initializations=1,policy_model_loads=1,policy_state_file_loads=1,policy_state_dict_loads=1,
        tokenizer_loads=1,preprocessor_loads=1,postprocessor_loads=1,projection_loads=1,
        preprocessor_calls=301+n,tokenizer_calls=302+n,image_preprocessing_calls=301+n,
        visual_encoder_forwards=301+3*n,language_embedding_forwards=1+n,encoder_forward_calls=302+4*n,
        spatial_projection_calls=301,prefix_transformer_forwards=n,action_expert_forwards=10*n,
        flow_forward_calls=10*n,noise_draws=n,vla_sampling_calls=n,model_gpu_inference_calls=n,
        torch_generator_creations=n,torch_generator_seed_calls=n,
        postprocessor_calls=n,reset_observation_calls=1,observation_calls=301,control_observation_calls=300,
        env_steps=300,environment_seed_calls=1,completed_rollouts=1,
        python_rng_seed_calls=1,numpy_rng_seed_calls=1,torch_global_seed_calls=2,
        full_state_captures=1,full_state_comparisons=0 if name=='normal' else 1,
        state_document_writes=2 if name=='normal' else 1,state_field_digest_calls=0 if name=='normal' else 4096,
        mj_stateSize_calls=1,mj_getState_calls=1,mj_sizeModel_calls=1,mj_saveModel_calls=1,
        callback_read_calls=8,plugin_field_reads=2,
        python_rng_state_reads=1,numpy_rng_state_reads=17,torch_rng_state_reads=2,
        CPU_local_direction_draws=12 if name=='normal' else 0,
        CPU_own_radius_group_calculations=2 if name=='normal' else 0,
        CPU_candidate_raw50_writes=2 if name=='normal' else 0,
        state_serialization_calls=1,feature_state_serializations=301)
def sum_units(*scopes):
    keys=set().union(*(x.keys() for x in scopes))
    return {k:sum(x.get(k,0) for x in scopes) for k in sorted(keys)}
def attempt_caps(name):return sum_units(numeric_caps(name),INITIALIZATION,GRAPHICS)
PER_ATTEMPT={j[0]:attempt_caps(j[0]) for j in ARMS}
PARENT={'native_nvml_identity_queries':1}
TOTAL=sum_units(PARENT,*PER_ATTEMPT.values())
TIMEOUTS=dict(preparation_seconds=900,lock_wait_seconds=None,handoff_seconds=300,
    child_seconds=1800,child_grace_seconds=30,reserved_wave_seconds=27900,
    reserved_wave_grace_seconds=30,drain_TERM_seconds=30,drain_poll_seconds=0.2,
    restoration_observation_seconds=120,end_to_end_hard_bound_seconds=None,
    GPU_compute_seconds_cap=None)
STORAGE=dict(attempt_bytes=512*1024**2,attempt_record_bytes=32*1024**2,
    attempt_logical_files=2048,attempt_physical_directory_entries=4096,
    attempt_emergency_reserve_bytes=1024**2,parent_bytes=64*1024**2,
    parent_record_bytes=1024**2,parent_files=256,
    wave_new_payload_bytes=15*512*1024**2+64*1024**2,
    additional_private_cache_bytes=0,CUDA_CACHE_DISABLE=True,
    process_address_space_hard_bytes=128*1024**3,host_RAM_planning_bytes=64*1024**3,CPU_serialization_buffer_bytes=64*1024**2,
    project_reserved_bytes=None,project_quota_known=False,
    metadata_filesystem_overhead_reservation_bytes=256*1024**2)
STORAGE.update(child_stdout_bytes=32*1024**2,child_stderr_bytes=32*1024**2,
    parent_stdout_bytes=32*1024**2,parent_stderr_bytes=32*1024**2,
    wave_log_bytes=32*32*1024**2,uncontrolled_library_temporary_bytes=None,
    quota_admission_required=True)
