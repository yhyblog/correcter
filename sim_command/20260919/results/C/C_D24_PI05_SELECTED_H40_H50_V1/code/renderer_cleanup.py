"""Release MuJoCo resources in their own live GL context before EGL teardown."""


def install():
    from gymnasium.envs.mujoco import mujoco_rendering
    cls = mujoco_rendering.OffScreenViewer
    if getattr(cls, '_b_d24_cleanup_installed', False):
        return
    original_free = cls.free
    original_render = cls.render

    def free(viewer):
        if getattr(viewer, '_b_d24_freed', False):
            return
        context = getattr(viewer, 'opengl_context', None)
        con = getattr(viewer, 'con', None)
        if con is not None:
            if context is not None:
                context.make_current()
            con.free()
            viewer.con = None
        if context is not None:
            original_free(viewer)
        viewer._b_d24_freed = True

    def render(viewer, *args, **kwargs):
        if getattr(viewer, '_b_d24_freed', False):
            raise RuntimeError('Attempt to render a freed MuJoCo context')
        viewer.make_context_current()
        image = original_render(viewer, *args, **kwargs)
        # This task uses RGB; all-zero frames indicate the diagnosed GL failure.
        if getattr(image, 'ndim', 0) == 3 and not image.any():
            raise RuntimeError('Invalid all-zero RGB observation; episode is technical failure')
        return image

    cls.free = free
    cls.render = render
    cls._b_d24_cleanup_installed = True
