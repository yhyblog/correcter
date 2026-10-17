"""Fixed V3 handoff metadata/environment; no hardware or file operations."""
HANDOFF_SPEC = {'environment_variable': 'CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS', 'required_value': '300', 'timeout_seconds': 300, 'default_seconds': 90, 'minimum_seconds': 1, 'maximum_seconds': 300, 'guard_path': '/mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_guard.py', 'guard_expected_sha256': '7910c567a47ddf68294d92fc9698cc780aeb130ddefde0337414bfcd88cb85a4', 'guard_expected_size_bytes': 10704, 'active_guard_required': True, 'formal_lock_path': '/tmp/gpu_occupancy_guard/formal.lock', 'poll_sleep_seconds_max': 1, 'existing_query_timeout_seconds': 15, 'failure_last_observation_rows_max': 64}

def require_handoff_environment(cfg, environment):
    if cfg.get('occupancy_handoff') != HANDOFF_SPEC:
        raise ValueError('V3 requires the exact frozen handoff contract')
    key = HANDOFF_SPEC['environment_variable']
    actual = environment.get(key)
    if actual != HANDOFF_SPEC['required_value']:
        raise ValueError('Missing or mismatched actual V3 handoff timeout; no default90 fallback')
    return dict(environment_variable=key, actual_value=actual,
        timeout_seconds=HANDOFF_SPEC['timeout_seconds'],
        guard_expected_sha256=HANDOFF_SPEC['guard_expected_sha256'],
        guard_SHA_check='parent full INPUT and EXTERNAL manifest verification already returned',
        propagation='frozen sh export -> launcher os.environ -> child_environment copy -> unchanged lifecycle active branch -> fresh guard run process',
        additional_hardware_queries=0)
