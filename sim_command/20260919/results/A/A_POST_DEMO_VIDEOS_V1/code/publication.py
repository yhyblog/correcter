"""Incremental node-local review index; never updates scientific tables."""
import csv,html,json,os,traceback
from collections import Counter
from pathlib import Path
from paths import ROOT,OUTPUT,TASK
from qio import read,new_json,atomic_json,utc

def publish(terminal=False,force=False):
    try:
        candidates=[json.loads(x) for x in (ROOT/'CANDIDATES.jsonl').read_text().splitlines()]
        counts={x['task']:dict(qualified=0,unqualified=0,technical_missing=0,not_needed=0,pending=0,publication_error=0,candidates=0) for x in candidates};videos=[];dispositions=[]
        for c in candidates:
            t=counts[c['task']];t['candidates']+=1;p=ROOT/'pairs'/c['candidate_id'];m=OUTPUT/c['task']/c['candidate_id']/'metadata.json'
            if m.exists():
                d=read(m);t['qualified']+=1;videos.append(dict(candidate=c,metadata=d));status='qualified'
            elif (p/'PAIR_RESULT.json').exists():
                d=read(p/'PAIR_RESULT.json');status=d['status'];key=status if status in t else 'pending';t[key]+=1
            elif (p/'ENCODE_RESULT.json').exists() and read(p/'ENCODE_RESULT.json')['status']=='publication_error':status='publication_error';t[status]+=1
            else:status='pending';t[status]+=1
            dispositions.append(dict(candidate_id=c['candidate_id'],task=c['task'],source_id=c['source_id'],H=c['H'],status=status))
        body=['<!doctype html><html lang="en"><meta charset="utf-8"><title>pi0.5 / Post paired recordings — A</title><style>body{background:#111827;color:#eef2ff;font:16px system-ui;max-width:1200px;margin:32px auto}video{width:360px;max-height:85vh}article{display:inline-block;vertical-align:top;width:380px;margin:8px}a{color:#9dc7ff}table{border-collapse:collapse}td,th{padding:8px;border:1px solid #405069}</style><h1>pi0.5 / L11 Post: same-initial-state recordings</h1><p>Top: baseline final failure. Bottom: Post final success. Selected qualitative cases, not a success-rate evaluation. Frozen L11/fit9101, G0-multi. Camera corner2; 1× playback.</p><p>Updated '+utc()+'</p><table><tr><th>Task</th><th>Qualified / target3</th><th>Unqualified</th><th>Technical missing</th><th>Pending</th></tr>']
        for task,d in sorted(counts.items()):body.append(f'<tr><td>{html.escape(task)}</td><td>{d["qualified"]}/3</td><td>{d["unqualified"]}</td><td>{d["technical_missing"]}</td><td>{d["pending"]}</td></tr>')
        body.append('</table>')
        tmp=OUTPUT/'REVIEW.csv.tmp'
        with tmp.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['task','source_id','H','pair_id','comparison','baseline','post','metadata','reviewer','review_decision','review_notes']);w.writeheader()
            for v in videos:
                c=v['candidate'];rel=c['task']+'/'+c['candidate_id'];w.writerow(dict(task=c['task'],source_id=c['source_id'],H=c['H'],pair_id=c['candidate_id'],comparison=rel+'/comparison.mp4',baseline=rel+'/baseline.mp4',post=rel+'/post.mp4',metadata=rel+'/metadata.json'))
                body.append(f'<article><h2>{html.escape(c["task"])}</h2><p>H{c["H"]} / source {c["ordinal"]:02d}</p><video controls preload="metadata" poster="{rel}/preview.jpg" src="{rel}/comparison.mp4"></video><p><a href="{rel}/baseline.mp4">Baseline</a> · <a href="{rel}/post.mp4">Post</a> · <a href="{rel}/metadata.json">Evidence</a></p></article>')
        os.replace(tmp,OUTPUT/'REVIEW.csv');body.append('</html>');tmp=OUTPUT/'INDEX.html.tmp';tmp.write_text('\n'.join(body));os.replace(tmp,OUTPUT/'INDEX.html')
        summary=dict(task_id=TASK,utc=utc(),candidate_pairs=79,qualified_pairs=len(videos),per_task=counts,dispositions=dispositions,recording_attempts=read(ROOT/'ATTEMPT_COUNTER.json')['count'] if (ROOT/'ATTEMPT_COUNTER.json').exists() else 0,first_arm_cap=158,attempt_cap=316,new_scientific_evaluation_units=0,training_updates=0,all_candidates_disposed=all(x['status']!='pending' for x in dispositions),review_index=str(OUTPUT/'INDEX.html'),scientific_success_rate_update=False)
        atomic_json(ROOT/'SUMMARY.json',summary)
        if videos and not (ROOT/'FIRST_PREVIEW.json').exists():
            v=videos[0]['candidate'];dest=OUTPUT/v['task']/v['candidate_id'];new_json(ROOT/'FIRST_PREVIEW.json',dict(utc=utc(),task_id=TASK,candidate_id=v['candidate_id'],comparison=str(dest/'comparison.mp4'),preview=str(dest/'preview.jpg'),metadata=str(dest/'metadata.json'),CPU_visual_review_pending=True))
            new_json(ROOT/'outbox/first_preview.json',dict(event_id=TASK+'_first_preview_v1',kind='first_preview',synthetic=False,utc=utc(),result=str(ROOT/'FIRST_PREVIEW.json')))
        if terminal:atomic_json(ROOT/'FINAL_SUMMARY.json',summary)
        row=dict(status='published',utc=utc(),qualified_pairs=len(videos),summary=str(ROOT/'FINAL_SUMMARY.json' if terminal else ROOT/'SUMMARY.json'),attempts=1)
        atomic_json(ROOT/'PUBLICATION_STATE.json',row);return row
    except BaseException as e:
        old=read(ROOT/'PUBLICATION_STATE.json') if (ROOT/'PUBLICATION_STATE.json').exists() else {}
        row=dict(status='publication_error',attempts=old.get('attempts',0)+1,utc=utc(),error={'type':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()},do_not_stop_recording_workers=True)
        atomic_json(ROOT/'PUBLICATION_STATE.json',row);return row
