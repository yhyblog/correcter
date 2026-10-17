"""CPU-only composition; both valid recording terminals are required."""
import argparse,json,os,shutil,subprocess,time,traceback
from pathlib import Path
import paths
from paths import ROOT,OUTPUT,CONFIG
from qio import read,new_json,utc
from demo_video import probe

def compose(candidate,N,Post):
    dest=OUTPUT/candidate['task']/candidate['candidate_id'];dest.mkdir(parents=True,exist_ok=True)
    if (dest/'metadata.json').exists():return read(dest/'metadata.json')
    if not (N['status']==Post['status']=='complete' and N['terminal'] and Post['terminal'] and N['success'] is False and Post['success'] is True):raise ValueError('not a real N-failure/Post-success recording pair')
    initial=read(ROOT/'pairs'/candidate['candidate_id']/'INITIAL_CHECK.json')
    if not initial['passed']:raise ValueError('different initial states')
    for name,row in [('baseline',N),('post',Post)]:
        source=Path(row['video']['path']);target=dest/(name+'.mp4')
        if not target.exists():shutil.copyfile(source,target)
        p=probe(target)
        if p['frames']!=row['steps']+1 or p['width']!=480 or p['height']!=480:raise ValueError('saved video/control-frame count mismatch')
    frames=max(N['steps'],Post['steps'])+1
    font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    common=f"{candidate['task']} | H{candidate['H']} | source {candidate['ordinal']:02d}"
    filters=[]
    for index,(name,row,title,outcome) in enumerate([('baseline',N,'pi0.5 - Baseline','FAILURE'),('post',Post,'pi0.5 + Post - Ours','SUCCESS')]):
        missing=frames-(row['steps']+1)
        # Header is outside the unchanged480x480 policy camera frame.
        line=f'[{index}:v]setpts=PTS-STARTPTS'
        if missing:line+=f',tpad=stop_mode=clone:stop={missing}'
        line+=",pad=480:564:0:84:black"
        texts=[(title+' | final '+outcome,6,18),(common,30,14)]
        for text,y,size in texts:line+=f",drawtext=fontfile={font}:text='{text}':x=8:y={y}:fontsize={size}:fontcolor=white"
        counter="step %{eif\\:min(n\\,"+str(row['steps'])+")\\:d} | replay %{pts\\:hms} | 1x"
        line+=f",drawtext=fontfile={font}:text='{counter}':x=8:y=49:fontsize=13:fontcolor=white"
        if missing:line+=f",drawtext=fontfile={font}:text='Episode ended - frame held':x=8:y=66:fontsize=13:fontcolor=yellow:enable='gte(n,{row['steps']+1})'"
        line+=f'[v{index}]';filters.append(line)
    filters.append('[v0][v1]vstack=inputs=2[v]')
    script=dest/'composition.fffilter';script.write_text(';\n'.join(filters)+'\n')
    argv=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-threads','1','-i',str(dest/'baseline.mp4'),'-threads','1','-i',str(dest/'post.mp4'),'-filter_complex_threads','1','-filter_complex_script',str(script),'-map','[v]','-frames:v',str(frames),'-an','-c:v','libx264','-threads','2','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(dest/'comparison.mp4')]
    with (dest/'composition.log').open('ab') as log:
        result=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=log,stderr=log,timeout=180)
    if result.returncode:raise RuntimeError('ffmpeg composition failed; recordings retained')
    output=probe(dest/'comparison.mp4')
    if output['frames']!=frames or output['height']!=1128:raise ValueError('comparison duration/layout mismatch')
    # Decode all frames once on CPU; no renderer/model is invoked.
    verified=subprocess.run(['ffmpeg','-nostdin','-v','error','-threads','1','-i',str(dest/'comparison.mp4'),'-f','null','-'],capture_output=True,text=True,timeout=90)
    if verified.returncode:raise ValueError('comparison not fully decodable')
    from PIL import Image,ImageDraw
    import io
    points=[0,min(Post.get('first_cut') or 0,frames-1),Post['steps'],frames-1]
    contact=Image.new('RGB',(4*320,776),'#101827');draw=ImageDraw.Draw(contact)
    for i,step in enumerate(points):
        cmd=['ffmpeg','-nostdin','-v','error','-threads','1','-i',str(dest/'comparison.mp4'),'-vf',f'select=eq(n\\,{step})','-frames:v','1','-threads','1','-f','image2pipe','-vcodec','png','pipe:1']
        frame=subprocess.run(cmd,capture_output=True,timeout=30,check=True)
        img=Image.open(io.BytesIO(frame.stdout)).convert('RGB');img.thumbnail((320,752));contact.paste(img,(i*320,24));draw.text((i*320+6,5),'Saved video step '+str(step),fill='white')
    contact.save(dest/'preview.jpg',quality=92)
    meta=dict(task=candidate['task'],pair_id=candidate['candidate_id'],source_id=candidate['source_id'],env_seed=candidate['env_seed'],policy_seed=candidate['policy_seed'],H=candidate['H'],utc=utc(),qualified=True,recording_mode='frozen_policy_rerun',outcome_selected_qualitative_only=True,scientific_success_rate_update=False,new_initial_states=0,Q_loss='L11',Q_fit_seed=9101,Q_members=[1041,1042,1043,1044],Q_assets=CONFIG['selected_model'],DG0='frozen pi05 five-task D241/242 G0341/342',camera='corner2',render_size=[480,480],fps=30,control_hz=30,physics_hz=400,action_scale=.015,initial_check=initial,full_hidden_state_equivalence_claimed=False,baseline_above_Post=True,playback_speed_both=1,frame_origin='existing actual policy observation at every step, no added render',Post_intervention_steps=Post['intervention_cuts'],N=dict(success=False,terminal_reason=N['terminal_reason'],steps=N['steps'],frames=N['video']['frames'],result=str(ROOT/'episodes'/N['uid_hash']/('attempt_%d'%N['attempt'])/'RESULT.json')),Post=dict(success=True,terminal_reason=Post['terminal_reason'],steps=Post['steps'],frames=Post['video']['frames'],result=str(ROOT/'episodes'/Post['uid_hash']/('attempt_%d'%Post['attempt'])/'RESULT.json')),historical_evidence={'N':candidate['N'],'Post':candidate['Post']},video_checks={'comparison':output,'baseline':probe(dest/'baseline.mp4'),'Post':probe(dest/'post.mp4'),'all_comparison_frames_decoded':True,'layout':'unmodified camera pixels resized by codec only;84px external header per arm;N on top;Post below','held_frames':{'N':frames-N['video']['frames'],'Post':frames-Post['video']['frames']},'ffmpeg_command':argv},metadata_note='Terminal frame held only after actual end, visibly labelled. One initial frame included:frames=control_steps+1. No outcome is inferred from historical label.')
    new_json(dest/'metadata.json',meta);return meta

def main(cfg):
    job=read(cfg);pair=ROOT/'pairs'/job['candidate']['candidate_id'];target=pair/'ENCODE_RESULT.json'
    try:
        m=compose(job['candidate'],read(job['N']),read(job['Post']));row=dict(status='published',utc=utc(),metadata=str(OUTPUT/m['task']/m['pair_id']/'metadata.json'))
    except BaseException as e:row=dict(status='publication_error',utc=utc(),error={'type':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()},recordings_preserved=True,scientific_worker_stop_required=False)
    new_json(target,row);return 0 if row['status']=='published' else 3

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);raise SystemExit(main(p.parse_args().config))
