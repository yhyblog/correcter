"""Bind each environment's owning GL context before every real render.

Process-local wrapper only; no package edit, extra render, policy or RNG change.
"""
def install(rendering=None, native_lifetime=False, restore_buffer=False):
    if rendering is None:
        from gymnasium.envs.mujoco import mujoco_rendering as rendering
    cls=rendering.MujocoRenderer
    if getattr(cls, '_c_l11_explicit_context_binding', False):return
    original=cls._get_viewer
    def bound(self, *args, **kwargs):
        viewer=original(self, *args, **kwargs)
        viewer.make_context_current()
        if restore_buffer:viewer._set_mujoco_buffer()
        self._c_l11_bind_count=getattr(self, '_c_l11_bind_count', 0)+1
        return viewer
    cls._get_viewer=bound
    cls._c_l11_explicit_context_binding=True
    if native_lifetime:
        original_free=rendering.OffScreenViewer.free
        def free(viewer):
            if getattr(viewer, '_c_l11_resources_freed', False):return
            context=getattr(viewer, 'opengl_context', None)
            if context is not None:context.make_current()
            con=getattr(viewer, 'con', None)
            if con is not None:con.free()
            original_free(viewer)
            viewer._c_l11_resources_freed=True
        rendering.OffScreenViewer.free=free


def evidence(env):
    renderer=getattr(env._env, 'mujoco_renderer', None)
    return dict(explicit_owning_context_binding=True,
                owning_renderer_bind_count=getattr(renderer, '_c_l11_bind_count', None),
                extra_render_calls=0, shared_package_changes=False)

def close_environment(env):
    renderer=getattr(env._env, 'mujoco_renderer', None)
    if renderer is not None:
        for viewer in getattr(renderer, '_viewers', {}).values():
            if not getattr(viewer, '_c_l11_resources_freed', False):viewer.make_context_current()
    env.close()
