"""Reuse the verified physical EGL mapping, retain one GL context per worker.

Individual task renderers own and free their own MjrContext. Shared installed
packages are unchanged. Only the worker epilogue destroys the shared EGL context.
"""
import paths
from native.native_egl import NativeEGL
from qio import new_json


class ResidentEGL(NativeEGL):
    def __init__(self, cfg, destination, gate):
        super().__init__(cfg,destination,gate)
        self.journal.caps.update(egl_make_current_calls=10000,egl_error_queries=20000,
            mujoco_render_context_creations=1000,mujoco_render_context_frees=1000)
        self.journal.caps.update(render_calls=20000, rgb_readback_calls=20000, mujoco_scene_updates=20000, mujoco_set_buffer_calls=20000, offscreen_viewer_creations=1000)
        self.journal.caps.update({k:2000000 for k in self.journal.caps})
        original_call=self.journal.call
        frequent={'egl_make_current_calls','egl_error_queries','mujoco_scene_updates','render_calls','rgb_readback_calls','mujoco_set_buffer_calls','mujoco_render_context_creations','mujoco_render_context_frees','offscreen_viewer_creations'}
        def counted(key,fn,*,check=None,cleanup=False):
            if key not in frequent or self.journal.counts.get(key,0)<2:
                return original_call(key,fn,check=check,cleanup=cleanup)
            self.journal.counts[key]+=1
            value=fn()
            if check is not None and not check(value):raise RuntimeError('graphics call failed: '+key)
            return value
        self.journal.call=counted
        self.renderer_reported = False
        self.viewers = []

    def open_context(self,width,height):
        if self.opened and not self.closed:
            if (width,height)!=(480,480):raise ValueError('resident renderer size mismatch')
            return
        return super().open_context(width,height)

    def make_current(self):
        if not self.renderer_reported:
            super().make_current();self.renderer_reported=True
        else:
            if self.closed:raise RuntimeError('renderer already closed')
            self.calls.egl('egl_make_current_calls',lambda:self.api.make_current(self.display,self.context),check=bool)

    def install_resident_rendering(self,rendering):
        runtime=self
        original=rendering.OffScreenViewer.__init__
        def init(viewer,*a,**kw):
            original(viewer,*a,**kw)
            viewer._d24_freed=False;runtime.viewers.append(viewer)
        def free(viewer):
            if getattr(viewer,'_d24_freed',False):return
            con=getattr(viewer,'con',None)
            if con is not None:
                runtime.journal.call('mujoco_render_context_frees',con.free,cleanup=True)
            viewer._d24_freed=True
        rendering.OffScreenViewer.__init__=init
        rendering.OffScreenViewer.free=free
        rendering.OffScreenViewer.close=free
        self.free_viewer=free

    def finish_resident(self):
        errors=[]
        for viewer in self.viewers:
            try:self.free_viewer(viewer)
            except BaseException as e:errors.append(dict(type=type(e).__name__,message=str(e)))
        new_json(self.destination/'GRAPHICS_AGGREGATE_COUNTS.json',dict(counts=self.journal.counts,per_frame_ledger=False,startup_ledger_only=True))
        super().finish()
        new_json(self.destination/'RESIDENT_GRAPHICS_CLEANUP.json',dict(
            viewer_count=len(self.viewers),errors=errors,one_shared_EGL_context=True,
            shared_library_modifications=False))
        if errors:raise RuntimeError('resident renderer cleanup failed')

