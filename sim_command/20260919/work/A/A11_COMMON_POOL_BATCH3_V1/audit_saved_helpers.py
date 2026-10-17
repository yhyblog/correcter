"""Stdlib readers for post-exit audit. Never import model/native/launcher modules."""
from pathlib import Path
import hashlib,json

HASH_CACHE={}
def load(path,default=None):
    path=Path(path)
    return json.loads(path.read_text()) if path.exists() else default
def digest(path):
    path=Path(path);s=path.stat();key=(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)
    if key not in HASH_CACHE:
        h=hashlib.sha256()
        with path.open('rb') as f:
            for part in iter(lambda:f.read(4*1024**2),b''):h.update(part)
        HASH_CACHE[key]=h.hexdigest()
    return HASH_CACHE[key]
def ref(path):
    path=Path(path).absolute();s=path.stat()
    return dict(path=str(path),realpath=str(path.resolve()),sha256=digest(path),size_bytes=s.st_size)
def save(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False);f.write('\n')
def add(a,b):
    for k,v in b.items():a[k]=a.get(k,0)+v
    return a
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)

def audit_journal(path,kind,caps):
    path=Path(path);starts={};ends={};bad=[];entered=dict.fromkeys(caps,0);returned=dict.fromkeys(caps,0)
    failed_units=dict.fromkeys(caps,0);incomplete_units=dict.fromkeys(caps,0)
    stage_sources={}
    stage_times={};start_times=[];end_times=[]
    if not path.exists():
        return dict(path=str(path),kind=kind,present=False,entered=entered,returned=returned,
            failed_units=failed_units,incomplete_entered_units=incomplete_units,initialization_by_stage_source=stage_sources,
            entries=0,terminals=0,failed=0,incomplete_ids=[],corrupt=[],counts_complete=False,
            missing_reason='journal absent; no operation count inferred beyond saved lower bounds',timing={})
    unitkey='resource_units' if kind=='graphics' else 'units'
    namekey='operation' if kind=='graphics' else 'source' if kind=='initialization' else 'name'
    def clock(row,terminal=False):
        if kind=='graphics':return row.get('monotonic_ns',0)/1e9
        if kind=='initialization':return row.get('wall_end' if terminal else 'wall_start')
        return row.get('monotonic')
    with path.open() as f:
        for lineno,line in enumerate(f,1):
            try:
                row=json.loads(line);key=row['event_id'];phase=row['phase']
                if phase=='entered':
                    if key in starts:raise ValueError('duplicate entry')
                    units=row[unitkey]
                    if type(units) is not dict or any(k not in caps or type(v) is not int or v<0 for k,v in units.items()):raise ValueError('unfrozen units')
                    starts[key]=row;add(entered,units)
                    t=clock(row)
                    if t is not None:start_times.append(t)
                elif phase in ('returned','failed','raised'):
                    if key not in starts or key in ends:raise ValueError('orphan/duplicate terminal')
                    original=starts[key]
                    if kind!='numeric' and (row.get(unitkey)!=original[unitkey] or row.get(namekey)!=original[namekey]):raise ValueError('terminal identity drift')
                    ends[key]=row
                    if phase=='returned':add(returned,original[unitkey])
                    else:add(failed_units,original[unitkey])
                    t=clock(row,True);t0=clock(original)
                    if t is not None:end_times.append(t)
                    if t is not None and t0 is not None:
                        group=stage_times.setdefault(original[namekey],dict(entered=0,returned=0,failed=0,seconds=0.,max_seconds=0.))
                        group['entered']+=1;group['returned' if phase=='returned' else 'failed']+=1
                        dt=t-t0
                        if dt<0:raise ValueError('negative saved elapsed interval')
                        group['seconds']+=dt;group['max_seconds']=max(group['max_seconds'],dt)
                else:raise ValueError('unknown phase')
            except (ValueError,KeyError,TypeError) as e:bad.append(dict(line=lineno,error=str(e)))
    for key,original in starts.items():
        terminal=ends.get(key)
        if terminal is None:add(incomplete_units,original[unitkey])
        if kind=='initialization':
            label=original.get('stage','unknown')+':'+original[namekey]
            group=stage_sources.setdefault(label,dict(entered={},returned={},failed={},incomplete={}))
            add(group['entered'],original[unitkey])
            category='incomplete' if terminal is None else 'returned' if terminal['phase']=='returned' else 'failed'
            add(group[category],original[unitkey])
    return dict(path=str(path),kind=kind,present=True,reference=ref(path),entered=entered,returned=returned,
        failed_units=failed_units,incomplete_entered_units=incomplete_units,initialization_by_stage_source=stage_sources,
        entries=len(starts),terminals=len(ends),failed=sum(r['phase']!='returned' for r in ends.values()),
        incomplete_ids=sorted(set(starts)-set(ends),key=str),corrupt=bad,
        counts_complete=not bad,within_caps=all(entered[k]<=caps[k] for k in caps),
        first_monotonic=min(start_times) if start_times else None,last_monotonic=max(end_times) if end_times else None,
        timing=stage_times,charge_rule='count each entered unit once; no refund for failed or missing terminal; private scopes kept separate',
        timing_note='saved host monotonic intervals; nested calls overlap and GPU work may be asynchronous')

def fields_comparison(reference,observed):
    if reference is None or observed is None:return dict(available=False,exact_equal=None,physical_equality_proven=None)
    a={x['name']:x for x in reference['fields']};b={x['name']:x for x in observed['fields']}
    duplicates=len(a)!=len(reference['fields']) or len(b)!=len(observed['fields'])
    equal=(reference['schema']==observed['schema'] and reference['byte_order']==observed['byte_order'] and
        not reference['unknown_fields'] and not observed['unknown_fields'] and not duplicates and a==b)
    return dict(available=True,exact_equal=equal,field_count=len(b),groups=sorted({k.split('.')[0] for k in b}),
        missing_fields=sorted(a.keys()-b.keys()),extra_fields=sorted(b.keys()-a.keys()),
        changed_fields=sorted(k for k in a.keys()&b.keys() if a[k]!=b[k]),unknown_fields=observed['unknown_fields'],
        scope='frozen captured-field/MJB closure only',physical_equality_proven=None)

def independent_label(rows,arms,kind):
    rows=[r for r in rows if r['arm'] in arms];by={(r['arm'],r['repeat']):r for r in rows};valid=[]
    crosskeys=('parent','cut','target','source_signature','context_signature')
    cross=(len(by)==len(rows) and all(rows and len({canonical(r.get(k)) for r in rows})==1 and all(r.get(k) is not None for r in rows) for k in crosskeys))
    target='G0_C5' if kind=='G0' else 'Q_C10'
    cross=cross and all(r['target']==target and r['cut'] in (5,55) for r in rows)
    stable=all(len({r.get('raw_group') for r in rows if r['arm']==a})==1 and all(r.get('raw_group') for r in rows if r['arm']==a) for a in arms)
    for repeat in (0,1):
        members=[by.get((a,repeat)) for a in arms]
        if any(r is None or not r['outcome_complete'] or r['success'] not in (0,1) or r['restore_level']!='full_state_verified' for r in members):continue
        keys=(*crosskeys,'suffix_stream')
        if cross and stable and all(len({canonical(r.get(k)) for r in members})==1 and members[0].get(k) is not None for k in keys):valid.append(repeat)
    alias=kind!='G0' and all(by.get((arms[0],r),{}).get('raw_group') is not None and by.get((arms[0],r),{}).get('raw_group')==by.get((arms[1],r),{}).get('raw_group') for r in (0,1))
    distinct=all(by.get((a,0),{}).get('suffix_stream')!=by.get((a,1),{}).get('suffix_stream') for a in arms)
    eligible=valid==[0,1] and not alias and distinct;value=None
    if eligible:
        means={a:sum(by[a,r]['success'] for r in (0,1))/2 for a in arms}
        value=sum(means[a] for a in arms[1:])/3-means[arms[0]] if kind=='G0' else means[arms[0]]-means[arms[1]]
    return dict(valid_pair_repeat_ids=valid,target_mask=eligible,target=value,raw_alias_masked=alias)
