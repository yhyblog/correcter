from collections import Counter
import time
class Counts:

    def __init__(self):
        self.entered = Counter()
        self.returned = Counter()
        self.seconds = Counter()
        self.failed = []

    def call(self, name, fn, units=None, detail=None):
        units = units or {}
        self.entered.update(units)
        t = time.monotonic()
        try:
            value = fn()
            self.returned.update(units)
            return value
        except BaseException as e:
            self.failed.append(dict(name=name, type=type(e).__name__, message=str(e)))
            raise
        finally:
            self.seconds[name] += time.monotonic() - t

    def snapshot(self):
        return dict(entered=dict(self.entered), returned=dict(self.returned), seconds=dict(self.seconds), failed=list(self.failed))

class Runtime:

    def __init__(self, env, observation):
        self.env = env
        self.observation = observation
        self.steps = 0
        self.seconds = 0.0

    def frame(self):
        return self.observation['pixels']

    def proprio(self):
        import numpy as np
        return np.asarray(self.observation['agent_pos'], np.float32)

    def step(self, action, step):
        import numpy as np
        if step != self.steps:
            raise ValueError('physical step clock')
        native = self.env._env
        native.frame_skip = (step + 1) * 400 // 30 - step * 400 // 30
        begin = time.monotonic()
        before = float(native.data.time)
        obs, reward, done, truncated, info = native.step(np.asarray(action, np.float32))
        if abs(float(native.data.time) - before - native.frame_skip / 400) > 1e-09:
            raise ValueError('physics cadence')
        if native._did_see_sim_exception:
            raise RuntimeError('native simulator exception')
        self.observation = self.env._format_raw_obs(obs)
        self.steps += 1
        self.seconds += time.monotonic() - begin
        return dict(reward=float(reward), done=bool(done or truncated), success=bool(info.get('success', False)))
