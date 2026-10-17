"""Bounded CPU video encoding and faithful one-control-step-per-frame comparison."""
import json, subprocess
from pathlib import Path
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
class Writer:
 def __init__(self,path,width=480,height=480):
  self.path=Path(path);self.size=(width,height);self.frames=0
  self.log=self.path.with_suffix('.ffmpeg.log').open('xb')
  self.p=subprocess.Popen(['/usr/bin/ffmpeg','-nostdin','-hide_banner','-loglevel','error','-threads','2','-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height}','-r','30','-i','pipe:0','-an','-c:v','libx264','-preset','veryfast','-crf','18','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart','-n',str(self.path)],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=self.log)
 def write(self,frame):
  import numpy as np
  a=np.asarray(frame)
  if a.dtype!=np.uint8 or a.shape!=(self.size[1],self.size[0],3):raise ValueError('RGB shape/dtype')
  self.p.stdin.write(a.tobytes());self.frames+=1
 def close(self):
  if not self.p.stdin.closed:self.p.stdin.close()
  try:code=self.p.wait(timeout=45)
  except subprocess.TimeoutExpired:self.p.kill();self.p.wait();raise
  finally:self.log.close()
  if code:raise RuntimeError('ffmpeg failed: '+str(self.path))
class Reader:
 def __init__(self,path):
  self.p=subprocess.Popen(['/usr/bin/ffmpeg','-nostdin','-v','error','-threads','1','-i',str(path),'-f','rawvideo','-pix_fmt','rgb24','-threads','1','pipe:1'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 def frame(self):
  import numpy as np
  b=self.p.stdout.read(480*480*3)
  if len(b)!=480*480*3:raise RuntimeError('video ended before advertised frame count')
  return np.frombuffer(b,dtype=np.uint8).reshape(480,480,3).copy()
 def close(self):
  self.p.stdout.close()
  try:code=self.p.wait(timeout=15)
  except subprocess.TimeoutExpired:self.p.kill();self.p.wait();raise
  error=self.p.stderr.read().decode(errors='replace');self.p.stderr.close()
  if code:raise RuntimeError('decode failed: '+error[-1000:])
def probe(path,frames,width=480,height=480):
 p=subprocess.run(['/usr/bin/ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=codec_name,width,height,pix_fmt,r_frame_rate,nb_read_frames,duration','-of','json',str(path)],capture_output=True,text=True,timeout=90,check=True)
 x=json.loads(p.stdout)['streams'][0]
 assert x['codec_name']=='h264' and x['pix_fmt']=='yuv420p' and (x['width'],x['height'])==(width,height),x
 assert int(x['nb_read_frames'])==frames and x['r_frame_rate']=='30/1',x
 assert abs(float(x['duration'])-frames/30)<.04,x
 return dict(x,validated_decodable_frame_count=True)
def compose(destination,unit,arms,cuts,boundary=lambda:None):
 from PIL import Image,ImageDraw,ImageFont
 destination=Path(destination);font=ImageFont.truetype(FONT,17);small=ImageFont.truetype(FONT,13)
 ns=[arms[k]['frame_count'] for k in ['N','Post']];total=max(ns);readers=[Reader(destination/n) for n in ['baseline.mp4','post.mp4']]
 writer=Writer(destination/'comparison.mp4',480,1120);current=[None,None]
 try:
  for i in range(total):
   boundary();canvas=Image.new('RGB',(480,1120),'#111820');draw=ImageDraw.Draw(canvas)
   for j,(reader,arm) in enumerate(zip(readers,['N','Post'])):
    if i<ns[j]:current[j]=reader.frame()
    y=j*560;canvas.paste(Image.fromarray(current[j]),(0,y+80))
    result=arms[arm];end='SUCCESS' if result['success'] else 'FAILURE';held=i>=ns[j]
    title='π0.5 — Baseline' if j==0 else 'π0.5 + Post — Ours'
    draw.text((10,y+3),title+'  |  '+end,font=font,fill='#ff998f' if j==0 else '#79e5b1')
    draw.text((10,y+26),f"{unit['task']}  H{unit['H']}  source{unit['ordinal']:02}",font=small,fill='white')
    draw.text((10,y+44),f'common step {i} / t={i/30:.2f}s  |  arm step {min(i,ns[j]-1)}',font=small,fill='white')
    note='Episode ended — frame held' if held else ('Saved Post actions replay' if j else 'Frozen policy rerun')
    if j and not held and i in cuts:note+=' | recorded Post cut'
    draw.text((10,y+61),note,font=small,fill='#ffdb72' if held else '#c9d3df')
   writer.write(canvas)
 finally:
  try:writer.close()
  finally:
   for reader in readers:reader.close()
 checks={name:probe(destination/name,n) for name,n in zip(['baseline.mp4','post.mp4'],ns)}
 checks['comparison.mp4']=probe(destination/'comparison.mp4',total,480,1120)
 middle=next((c for c in cuts if 0<c<total),total//2)
 indices=[0,middle,total-1];thumbs=[]
 for i in indices:
  p=subprocess.run(['/usr/bin/ffmpeg','-nostdin','-v','error','-threads','1','-i',str(destination/'comparison.mp4'),'-vf',f'select=eq(n\\,{i})','-frames:v','1','-threads','1','-f','image2pipe','-vcodec','png','pipe:1'],capture_output=True,timeout=30,check=True)
  import io
  thumbs.append(Image.open(io.BytesIO(p.stdout)).convert('RGB'))
 sheet=Image.new('RGB',(1440,1152),'#111820');draw=ImageDraw.Draw(sheet)
 for j,(thumb,i) in enumerate(zip(thumbs,indices)):
  sheet.paste(thumb,(j*480,32));draw.text((j*480+10,5),f'Actual video frame {i} | {i/30:.2f}s',font=font,fill='white')
 sheet.save(destination/'preview.jpg',quality=92)
 return dict(videos=checks,comparison_frames=total,preview_indices=indices,top='N',bottom='Post',speed=1,shorter_arm_hold_explicit=True,frame_semantics='frame 0 = reset; frame i = observation after control step i; terminal frame included once before editorial hold')
