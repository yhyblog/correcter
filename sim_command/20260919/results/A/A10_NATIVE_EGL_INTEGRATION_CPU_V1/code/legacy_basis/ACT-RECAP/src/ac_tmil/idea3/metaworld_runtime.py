"""Real frozen PI0.5 adapter for the tested local intervention engine."""
from __future__ import annotations

import time

import numpy as np
import torch

from ac_tmil.collection.metaworld_pi05 import MetaWorldPi05Backend
from ac_tmil.evaluation.metaworld_adaptive_execution import physics_state
from ac_tmil.evaluation.metaworld_conformal_interruption import CommandCapture
from ac_tmil.evaluation.metaworld_fm_value_pilot import reset_world, world_fingerprint


class MetaWorldRuntime:
    def __init__(self, vla_root, checkpoint, device="cuda:0"):
        self.backend = MetaWorldPi05Backend(vla_root=vla_root, checkpoint=checkpoint,
                                            device=device, control_hz=30, native_action_scale=.015)
        self.capture = CommandCapture(self.backend)
        self.observation = None
        self.instruction = None
        self.versions = [(parameter, parameter._version) for parameter in self.backend.policy.parameters()]

    def clear_policy(self, horizon):
        if not 1 <= horizon <= 50:
            raise ValueError(horizon)
        backend = self.backend
        backend.policy.config.n_action_steps = horizon
        backend.policy_config.n_action_steps = horizon
        backend.policy.reset()
        if backend.policy._action_queue.maxlen != horizon or backend.policy._queues["action"].maxlen != horizon:
            raise ValueError("actual queue capacity differs from configured horizon")

    def reset(self, case, horizon):
        self.clear_policy(horizon)
        self.observation = reset_world(self.backend, case["task"], case["env_seed"])
        self.instruction = self.backend.task_instruction(case["task"])
        if self.backend.policy._action_queue.maxlen != horizon:
            raise ValueError("environment reset changed the policy horizon")

    def physics_state(self):
        return physics_state(self.backend)

    def fingerprint(self):
        return world_fingerprint(self.backend)

    def frame(self):
        return np.asarray(self.observation["pixels"], dtype=np.uint8)

    def proprio(self):
        return self.backend.state_from_observation(self.observation)

    def native_action(self, seed):
        backend = self.backend
        fresh = not backend.policy._action_queue
        if fresh:
            torch.cuda.synchronize(backend.device)
            start = time.perf_counter()
            with torch.random.fork_rng(devices=[backend.device.index or 0]):
                torch.manual_seed(seed)
                torch.cuda.manual_seed(seed)
                action = backend.select_action(self.observation, self.instruction)
            torch.cuda.synchronize(backend.device)
            return action, self.capture.last.copy(), time.perf_counter() - start
        return backend.select_action(self.observation, self.instruction), None, 0.

    def step(self, action):
        result = self.backend.step(action)
        self.observation = result.observation
        return dict(reward=result.reward, success=result.success, done=result.done)

    def verify_frozen(self):
        if any(parameter.requires_grad or parameter.grad is not None or parameter._version != version
               for parameter, version in self.versions):
            raise ValueError("frozen policy parameters were modified")

    def close(self):
        self.capture.close()
        self.backend.close()
