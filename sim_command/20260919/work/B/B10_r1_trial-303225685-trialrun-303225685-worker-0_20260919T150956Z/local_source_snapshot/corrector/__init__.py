"""Frozen-critic velocity, direct-flow and post-sampling action correction.

The numerical core requires NumPy and PyTorch; simulator and VLA dependencies
belong to the separately configured experiment adapter.
"""

from .actions import ActionTransform, GuidanceError
from .candidates import construct
from .config import COMPARISON_METHODS, DEFAULT_GUIDANCE, DEFAULT_MATCHING, MATCHED, METHODS
from .critic import FrozenSelector, TenStepCritic
from .guidance import FlowHook, FrozenObjective, flow_update, post_direction

__all__ = [
    'ActionTransform', 'GuidanceError', 'construct', 'COMPARISON_METHODS',
    'DEFAULT_GUIDANCE', 'DEFAULT_MATCHING', 'MATCHED', 'METHODS',
    'FrozenSelector', 'TenStepCritic', 'FlowHook', 'FrozenObjective',
    'flow_update', 'post_direction',
]
