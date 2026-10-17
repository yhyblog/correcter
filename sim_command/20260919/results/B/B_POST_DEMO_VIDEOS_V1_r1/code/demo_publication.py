"""Incremental node-owned review artifacts, never scientific result updates."""
import csv,html,io,os
from collections import Counter
from pathlib import Path
from paths import ROOT,CONFIG,CAMPAIGN
from qio import read,atomic_json,new_json,utc

def rows():return [read(p) for p in sorted((ROOT/'pairs').glob('*/PAIR_RESULT.json'))]
def text_atomic(path,text):
 path=Path(path);tmp=path.with_name(path.name+'.tmp');tmp.write_text(text);os.replace(tmp,path)
def publish_incremental(final=False):
 output=Path(CONFIG['output_root']);output.mkdir(parents=True,exist_ok=True);results=rows();qualified=[r for r in results if r['status']=='qualified' and r['qualified']]
 fields=['task','source_id','H','pair_id','comparison','baseline','post','metadata','human_review']
 existing={}
 if (output/'REVIEW.csv').exists():
  with (output/'REVIEW.csv').open() as f:existing={r['pair_id']:r.get('human_review','') for r in csv.DictReader(f)}
 stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
 page=['<!doctype html><meta charset="utf-8"><title>B · π0.5 / Post review</title><style>body{font-family:system-ui;background:#121820;color:#eee;max-width:1200px;margin:auto;padding:24px}a{color:#7cd6ff}article{display:inline-block;vertical-align:top;width:350px;margin:12px}video{width:320px;max-height:750px}img{width:320px}small{display:block}</style><h1>B · π0.5 baseline / Post</h1><p>Outcome-selected qualitative cases. Top: baseline; bottom: Post. Same initial state, 1× speed, 30 fps. N uses frozen policy rerun; Post replays saved actions with outcomes checked again. Shorter arms are explicitly held after their actual terminal step. These recordings do not update scientific success rates.</p>',f'<p>Updated {utc()} | {len(qualified)} qualified pairs | '+('Final' if final else 'Queue running')+'</p><p><a href="REVIEW.csv">Review CSV</a> · <a href="STATUS.json">Status and shortfalls</a></p>']
 for r in qualified:
  rel=Path(r['output']).relative_to(output);link=lambda n:html.escape(str(rel/n),quote=True)
  writer.writerow(dict(task=r['task'],source_id=r['source_id'],H=r['H'],pair_id=r['candidate_id'],comparison=str(rel/'comparison.mp4'),baseline=str(rel/'baseline.mp4'),post=str(rel/'post.mp4'),metadata=str(rel/'metadata.json'),human_review=existing.get(r['candidate_id'],'')))
  page.append(f'<article><h2>{html.escape(r["task"])}</h2><p>H{r["H"]} · {html.escape(r["source_id"])}</p><video controls preload="none" poster="{link("preview.jpg")}" src="{link("comparison.mp4")}"></video><small><a href="{link("baseline.mp4")}">Baseline</a> · <a href="{link("post.mp4")}">Post</a> · <a href="{link("metadata.json")}">Metadata</a> · <a href="{link("preview.jpg")}">Actual keyframes</a></small></article>')
 text_atomic(output/'REVIEW.csv',stream.getvalue());text_atomic(output/'INDEX.html','\n'.join(page))
 tasks=sorted(set(u['task'] for u in read(ROOT/'SOURCE_INDEX.json')['units']));per_task={}
 dispositions=read(ROOT/'DISPOSITIONS.json') if (ROOT/'DISPOSITIONS.json').exists() else {}
 for task in tasks:
  counts=Counter(r['status'] for r in results if r['task']==task);per_task[task]=dict(counts,target=3,remaining_to_target=max(0,3-counts['qualified']),candidate_limit=sum(u['task']==task for u in read(ROOT/'SOURCE_INDEX.json')['units']))
 counter=read(ROOT/'ATTEMPT_COUNTER.json') if (ROOT/'ATTEMPT_COUNTER.json').exists() else {'recording_attempts':0}
 resolved=set(r['candidate_id'] for r in results)|set(dispositions)
 pending=[u['candidate_id'] for u in read(ROOT/'SOURCE_INDEX.json')['units'] if u['candidate_id'] not in resolved]
 status='complete' if final and not pending and all(r['status'] in ('qualified','unqualified') for r in results) else 'partial' if final else 'running'
 summary=dict(task_id=CONFIG['task_id'],run_id=CONFIG['run_id'],status=status,utc=utc(),qualified_pairs=len(qualified),attempted_pairs=len(results),recording_attempts=counter['recording_attempts'],candidate_cap=CONFIG['max_candidate_pairs'],per_task=per_task,dispositions=dispositions,pending=pending,technical_failures=[r['candidate_id'] for r in results if r['status']=='technical_failure'],new_scientific_evaluation_units=0,scientific_success_rate_update=False,output_root=str(output),index=str(output/'INDEX.html'),review=str(output/'REVIEW.csv'),qualified_metadata=[r['metadata'] for r in qualified],sampling='outcome-selected fixed qualitative candidates')
 atomic_json(output/'STATUS.json',summary);atomic_json(ROOT/'INCREMENTAL_SUMMARY.json',summary)
 if qualified and not (ROOT/'FIRST_PREVIEW.json').exists():
  first=qualified[0];record=dict(utc=utc(),task_id=CONFIG['task_id'],pair=first,index=str(output/'INDEX.html'),preview=str(Path(first['output'])/'preview.jpg'))
  new_json(ROOT/'FIRST_PREVIEW.json',record);atomic_json(CAMPAIGN/'receipts/B/B_POST_DEMO_VIDEOS_V1_FIRST_PREVIEW.json',record)
 return summary
