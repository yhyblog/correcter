"""CPU-only lossless encoding and byte checks of already saved arrays."""
from pathlib import Path
import ast,hashlib,json,math,struct,zipfile,zlib
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919');T='A10_CAUSAL_C10_PREFLIGHT_V2'
W=B/'work/A'/(T+'_r1');O=B/'results/A'/T;R=B/'results/A/P10_CAUSAL_C10_V2_launcher_runs'/(T+'_r1_A_wave10')
assert (W/'COMMAND_RESULT.json').exists()
def npy(blob):
 assert blob[:6]==b'\x93NUMPY';version=tuple(blob[6:8]);fmt='<H' if version[0]==1 else '<I';width=struct.calcsize(fmt)
 length=struct.unpack(fmt,blob[8:8+width])[0];offset=8+width+length
 header=ast.literal_eval(blob[8+width:offset].decode('latin1'));assert header['fortran_order'] is False
 return header,blob[offset:]
def png(raw,width,height):
 def chunk(name,data):return struct.pack('>I',len(data))+name+data+struct.pack('>I',zlib.crc32(name+data)&0xffffffff)
 filtered=b''.join(b'\0'+raw[y*width*3:(y+1)*width*3] for y in range(height))
 return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(filtered,6))+chunk(b'IEND',b'')
def png_decode(blob):
 assert blob[:8]==b'\x89PNG\r\n\x1a\n';at=8;data=[]
 while at<len(blob):
  n=struct.unpack('>I',blob[at:at+4])[0];key=blob[at+4:at+8];body=blob[at+8:at+8+n];crc=struct.unpack('>I',blob[at+8+n:at+12+n])[0]
  assert zlib.crc32(key+body)&0xffffffff==crc
  if key==b'IHDR':width,height,depth,color,*other=struct.unpack('>IIBBBBB',body);assert depth==8 and color==2 and other==[0,0,0]
  elif key==b'IDAT':data.append(body)
  at+=n+12
 raw=zlib.decompress(b''.join(data));row_bytes=width*3+1;assert len(raw)==height*row_bytes
 assert all(raw[y*row_bytes]==0 for y in range(height))
 return b''.join(raw[y*row_bytes+1:(y+1)*row_bytes] for y in range(height))
images=[];arrays=[]
for branch in ['Post','Velocity']:
 d=R/branch
 for path in sorted(d.glob('observation_step*.npz'),key=lambda p:int(p.stem.replace('observation_step',''))):
  with zipfile.ZipFile(path) as z:header,pixels=npy(z.read('pixels.npy'))
  assert header['descr']=='|u1' and header['shape']==(480,480,3) and len(pixels)==480*480*3
  output=O/(branch+'_'+path.stem+'.png');blob=png(pixels,480,480)
  with output.open('xb') as f:f.write(blob)
  assert png_decode(blob)==pixels
  images.append(dict(branch=branch,step=int(path.stem.replace('observation_step','')),source=str(path),PNG=str(output),
    pixels_sha256=hashlib.sha256(pixels).hexdigest(),PNG_sha256=hashlib.sha256(blob).hexdigest(),exact_lossless_roundtrip=True,
    min_pixel=min(pixels),max_pixel=max(pixels),byte_constant=len(set(pixels))==1))
 for path in sorted(d.glob('*raw50.npy')):
  header,raw=npy(path.read_bytes());assert header['shape']==(50,4) and header['descr']=='<f4'
  values=[x[0] for x in struct.iter_unpack('<f',raw)];assert len(values)==200 and all(math.isfinite(x) for x in values)
  arrays.append(dict(branch=branch,path=str(path),shape=[50,4],finite=True,raw_payload_sha256=hashlib.sha256(raw).hexdigest()))
 anchor=d/'cut_anchor_raw50.npy';proposed=d/(branch+'_proposed_raw50.npy')
 if anchor.exists() and proposed.exists():
  _,a=npy(anchor.read_bytes());_,b=npy(proposed.read_bytes());assert a[160:]==b[160:]
  arrays.append(dict(branch=branch,check='raw40_tail_bit_exact',passed=True))
 if (d/'guided_noise.npy').exists():
  ha,na=npy((d/'cut_anchor_noise.npy').read_bytes());hb,nb=npy((d/'guided_noise.npy').read_bytes());assert ha==hb and na==nb
  arrays.append(dict(branch=branch,check='anchor_guided_noise_bit_exact',passed=True,sha256=hashlib.sha256(na).hexdigest()))
result=dict(status='CPU_SAVED_ARRAY_CHECKS_PASS' if images or arrays else 'NOT_ENTERED_NO_SAVED_ARRAYS',images=images,array_checks=arrays,
    fresh_render_calls=0,model_calls=0,environment_calls=0,inputs_only_already_saved_files=True,visual_content_acceptance='requires image inspection; nonconstant bytes alone insufficient')
with (O/'SAVED_RGB_ARRAY_AUDIT.json').open('x') as f:json.dump(result,f,indent=2,ensure_ascii=False);f.write('\n')
print(json.dumps(dict(status=result['status'],images=len(images),array_checks=len(arrays))))
