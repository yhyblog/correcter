import runpy,sys
forbidden={'torch','mujoco','gymnasium','metaworld','pynvml','OpenGL','numpy'}
def guard(event,args):
    if event=='import' and args[0].split('.')[0] in forbidden:raise AssertionError('forbidden import '+args[0])
    if event in ('ctypes.dlopen','ctypes.dlsym','subprocess.Popen','os.system','os.kill','os.killpg'):raise AssertionError('forbidden runtime '+event)
    if event=='open' and isinstance(args[0],str) and (args[0].startswith(('/proc/','/sys/','/dev/')) or args[0].endswith(('.safetensors','.pt','.pth'))):raise AssertionError('forbidden file '+args[0])
sys.addaudithook(guard)
entry=sys.argv.pop(1);sys.path.insert(0,str(__import__('pathlib').Path(entry).parent));sys.argv[0]=entry
runpy.run_path(entry,run_name='__main__')
