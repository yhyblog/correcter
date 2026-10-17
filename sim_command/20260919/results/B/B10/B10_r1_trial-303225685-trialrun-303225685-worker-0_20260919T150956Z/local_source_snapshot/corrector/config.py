"""Frozen method ordering and numerical settings from the 2026-09-16 study."""

METHODS = [
    'replan', 'velocity_matched', 'direct_matched', 'post_matched',
    'reverse_matched', 'random_matched', 'velocity_native', 'direct_native',
]
MATCHED = METHODS[1:6]
COMPARISON_METHODS = METHODS[:4]

DEFAULT_GUIDANCE = dict(alpha=10., times=[.3, .2, .1])
DEFAULT_MATCHING = dict(
    xyz_rms=.05, gripper_rms=.10, xyz_linf=.15, gripper_linf=.4,
    boundary_clearance=.05, tolerance=1e-6, zero_threshold=1e-10,
)
