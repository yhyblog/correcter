"""Bind each environment's owning GL context before every real render.

Process-local wrapper only; no package edit, extra render, policy or RNG change.
"""
def install(rendering=None):
    if rendering is None:
        from gymnasium.envs.mujoco import mujoco_rendering as rendering
    cls=rendering.MujocoRenderer
    if getattr(cls, '_c_l11_explicit_context_binding', False):return
    original=cls._get_viewer
    def bound(self, *args, **kwargs):
        viewer=original(self, *args, **kwargs)
        viewer.make_context_current()
        self._c_l11_bind_count=getattr(self, '_c_l11_bind_count', 0)+1
        return viewer
    cls._get_viewer=bound
    cls._c_l11_explicit_context_binding=True

def evidence(env):
    renderer=getattr(env._env, 'mujoco_renderer', None)
    return dict(explicit_owning_context_binding=True,
                owning_renderer_bind_count=getattr(renderer, '_c_l11_bind_count', None),
                extra_render_calls=0, shared_package_changes=False)

def close_environment(env):
    renderer=getattr(env._env, 'mujoco_renderer', None)
    if renderer is not None:
        for viewer in getattr(renderer, '_viewers', {}).values():
            viewer.make_context_current()
    env.close()
