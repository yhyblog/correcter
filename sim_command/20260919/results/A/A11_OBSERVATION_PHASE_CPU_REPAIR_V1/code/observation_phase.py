"""Pure CPU names for the frozen absolute observation clock, s0 through s300."""

ABSOLUTE_TARGET = 300


def observation_phase(t):
    """Reject coercion (including bool); every accepted clock has one spelling."""
    if type(t) is not int:
        raise TypeError('Observation clock must be a strict integer')
    if not 0 <= t <= ABSOLUTE_TARGET:
        raise ValueError('Observation clock must be in [0, 300]')
    return f'step_{t}'


def validate_observation_config(config):
    """Metadata-only gate used before any real model or hardware operation."""
    target = config['source']['absolute_target']
    if type(target) is not int or target != ABSOLUTE_TARGET:
        raise ValueError('Frozen observation target must be the integer 300')
    phases = config['native']['observation_phases']
    expected = [observation_phase(t) for t in range(target + 1)]
    if (type(phases) is not list or any(type(x) is not str for x in phases)
            or phases != expected):
        raise ValueError('Frozen observation phases must exactly equal step_0 through step_300')
    return dict(status='PASS', absolute_target=target, observation_phases=len(phases),
                first=phases[0], last=phases[-1], metadata_only=True)
