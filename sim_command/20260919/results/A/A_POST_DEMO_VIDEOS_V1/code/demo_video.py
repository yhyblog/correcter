"""Bounded actual RGB encoding and CPU-only initial-state checks."""
import hashlib,json,os,subprocess,time
from pathlib import Path
from qio import new_json,read,utc,process_identity

def initial_record(unit,native,obs,path):
    import numpy as np
    from PIL import Image
    frame=np.asarray(obs['pixels']);Image.fromarray(frame).save(path/'initial.png')
    state={k:np.asarray(getattr(native.data,k)).tolist() for k in ('qpos','qvel','mocap_pos','mocap_quat')}
    for k in ('_last_rand_vec','_target_pos','obj_init_pos'):
        v=getattr(native,k,None);state[k]=None if v is None else np.asarray(v).tolist()
    row=dict(utc=utc(),task=unit['task'],source_id=unit['source_id'],env_seed=unit['env_seed'],policy_seed=unit['policy_seed'],H=unit['H'],camera='corner2',shape=list(frame.shape),rgb_sha256=hashlib.sha256(frame.tobytes()).hexdigest(),proprio=np.asarray(obs['agent_pos']).tolist(),native_time=float(native.data.time),state=state,full_hidden_state_equivalence_claimed=False,method='fresh reset under identical frozen seeds; observed physical fields and actual initial policy RGB')
    new_json(path/'INITIAL.json',row);return row

def compare_initial(a,b):
    keys=('task','source_id','env_seed','policy_seed','H','camera','shape','rgb_sha256','proprio','native_time','state')
    checks={k:a[k]==b[k] for k in keys}
    return dict(utc=utc(),passed=all(checks.values()),checks=checks,full_hidden_state_equivalence_claimed=False,comparison='exact saved initial physical fields and policy RGB; not whole-state/MJB audit',verified_before_first_policy_call=True)

class RGBWriter:
    def __init__(self,path):
        self.path=Path(path);self.frames=0;self.last_step=-1;self.log=self.path.with_suffix('.ffmpeg.log').open('xb')
        argv=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-threads','1','-f','rawvideo','-pixel_format','rgb24','-video_size','480x480','-framerate','30','-i','pipe:0','-an','-c:v','libx264','-preset','ultrafast','-crf','18','-pix_fmt','yuv420p','-threads','1','-movflags','+faststart',str(self.path)]
        self.proc=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=self.log,start_new_session=False)
        new_json(self.path.with_suffix('.encoder.json'),dict(argv=argv,process=process_identity(self.proc.pid),utc=utc(),fps=30,extra_render_calls=0,source='actual policy RGB observations'))
    def write(self,step,frame):
        import numpy as np
        if step!=self.last_step+1:raise ValueError('nonsequential saved control observation')
        f=np.asarray(frame)
        if f.shape!=(480,480,3) or f.dtype!=np.uint8:raise ValueError('RGB shape/type')
        self.proc.stdin.write(np.ascontiguousarray(f).tobytes());self.last_step=step;self.frames+=1
    def finish(self):
        self.proc.stdin.close()
        try:rc=self.proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            try:self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait()
            raise
        finally:self.log.close()
        if rc:raise RuntimeError('actual video encoder failed: '+str(rc))
        info=probe(self.path)
        if info['frames']!=self.frames:raise ValueError('encoded frame count mismatch')
        return dict(path=str(self.path),frames=self.frames,fps=30,steps=self.last_step,probe=info,encoder_exit=rc,initial_frame_included=True)

def probe(path):
    x=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name,pix_fmt,width,height,nb_frames,avg_frame_rate,duration','-of','json',str(path)],capture_output=True,text=True,timeout=30,check=True)
    s=json.loads(x.stdout)['streams'][0];rate=s['avg_frame_rate'].split('/');fps=float(rate[0])/float(rate[1])
    if s['codec_name']!='h264' or s['pix_fmt']!='yuv420p' or fps!=30:raise ValueError('video codec/fps not frozen')
    return dict(codec=s['codec_name'],pix_fmt=s['pix_fmt'],width=s['width'],height=s['height'],frames=int(s['nb_frames']),fps=fps,duration=float(s['duration']))

def finite_values(value):
    import math
    reasons={}
    def visit(x,p):
        if isinstance(x,float) and not math.isfinite(x):reasons[p]='nonfinite descriptive statistic';return None
        if isinstance(x,dict):return {k:visit(v,p+'.'+str(k)) for k,v in x.items()}
        if isinstance(x,(list,tuple)):return [visit(v,p+'[%d]'%i) for i,v in enumerate(x)]
        return x
    row=visit(value,'$')
    if reasons and isinstance(row,dict):row['null_reasons']=reasons
    return row
