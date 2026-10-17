"""Read-only analysis of two authorized saved states; standard library only.

No projection implementation, model, gradients, noise or trajectories executed.
Relations below compare SAVED arrays; no new candidate is generated or scored.
"""
import ast,csv,hashlib,importlib.abc,json,math,struct,sys,zipfile
from pathlib import Path
P=Path(__file__).resolve().parent;B=P.parents[2]
FORBIDDEN={'torch','numpy','ctypes','mujoco','metaworld','gymnasium','pynvml','OpenGL','safetensors','corrector'}
class NoRuntime(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in FORBIDDEN:raise RuntimeError('Forbidden analysis import: '+fullname)
sys.meta_path.insert(0,NoRuntime())
INPUTS={};FIELDS=[];RELATIONS=[];STAGES=[];TAUS=[];OBJECTIVES=[]
def digest(data):return hashlib.sha256(data).hexdigest()
def blob(p):
    p=Path(p);assert p.stat().st_size<3*1024*1024,('not a small authorized input',str(p))
    value=p.read_bytes();INPUTS[str(p)]=dict(path=str(p),sha256=digest(value),size_bytes=len(value));return value
def read(p):return json.loads(blob(p))
def put(name,value):
    with (P/name).open('x') as f:f.write(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def parse_npy(value):
    assert value[:6]==b'\x93NUMPY';width=2 if value[6]==1 else 4
    n=struct.unpack('<H' if width==2 else '<I',value[8:8+width])[0];at=8+width+n
    h=ast.literal_eval(value[8+width:at].decode('latin1'));raw=value[at:]
    assert not h['fortran_order'];formats={'<f4':'f','<f8':'d','|b1':'?','|u1':'B','<i8':'q','<i4':'i','<f2':'e'}
    fmt='<'+formats[h['descr']];vals=[v[0] for v in struct.iter_unpack(fmt,raw)]
    assert len(vals)==math.prod(h['shape'])
    assert all(not isinstance(v,float) or math.isfinite(v) for v in vals)
    return dict(shape=list(h['shape']),dtype=h['descr'],values=vals,raw=raw,sha256=digest(raw))
def arrays(p,state,label):
    blob(p);out={}
    with zipfile.ZipFile(p) as z:
        for name in z.namelist():
            a=parse_npy(z.read(name));key=name.removesuffix('.npy');out[key]=a
            FIELDS.append(dict(state=state,branch=label,container=str(p),field=key,shape=a['shape'],dtype=a['dtype'],payload_sha256=a['sha256']))
    return out
def single(p,state,label):
    a=parse_npy(blob(p));FIELDS.append(dict(state=state,branch=label,container=str(p),field=Path(p).stem,shape=a['shape'],dtype=a['dtype'],payload_sha256=a['sha256']));return a
def vals(a,key,n=None):return a[key]['values'][:n]
def norm(x):return math.sqrt(math.fsum(v*v for v in x))
def dot(x,y):return math.fsum(a*b for a,b in zip(x,y))
def cosine(x,y):return dot(x,y)/(norm(x)*norm(y)) if norm(x)*norm(y)>0 else None
def sub(a,b):assert len(a)==len(b);return [x-y for x,y in zip(a,b)]
def clamp(x):return [min(1.,max(-1.,v)) for v in x]
def f32(x):return struct.unpack('<f',struct.pack('<f',x))[0]
def relation(state,branch,name,left,right,tol=1e-12):
    assert len(left)==len(right)
    error=max((abs(a-b) for a,b in zip(left,right)),default=0.)
    RELATIONS.append(dict(state=state,branch=branch,relation=name,max_abs_error=error,tolerance=tol,passed=error<=tol))
    assert error<=tol,(state,branch,name,error)
def stats(state,branch,stage,vector,g,candidate=None):
    assert len(vector)==len(g)==40
    row=dict(state=state,branch=branch,stage=stage,coordinates='environment command displacement/direction, first10x4',
        anchor_gradient='same-state Post saved dJ/da at common bounded a0; never a different-state gradient',
        dot_g=dot(g,vector),cosine_g=cosine(g,vector),l2=norm(vector),linf=max(map(abs,vector)),
        zero_fraction=sum(v==0 for v in vector)/40)
    for name,indices in [('xyz',[i for i in range(40) if i%4<3]),('gripper',list(range(3,40,4)))]:
        x=[vector[i] for i in indices];gg=[g[i] for i in indices]
        row.update({name+'_dot_g':dot(gg,x),name+'_l2':norm(x),name+'_rms':norm(x)/math.sqrt(len(x)),name+'_cosine_g':cosine(gg,x)})
    row.update(command_clip_fraction=None if candidate is None else sum(abs(v)>1 for v in candidate)/40,
        command_boundary_fraction=None if candidate is None else sum(abs(v)>=1 for v in candidate)/40,
        candidate_linf=None if candidate is None else max(map(abs,candidate)),
        clipping_scope='saved candidate first10x4' if candidate is not None else 'not applicable: direction/displacement has no saved executable candidate')
    STAGES.append(row);return row
def score(state,branch,label,record):
    pairs=record['member_probabilities'];base=[x[0] for x in pairs];cand=[x[1] for x in pairs];gains=sub(cand,base)
    row=dict(state=state,branch=branch,evaluation_object=label,anchor_members=base,candidate_members=cand,member_delta=gains,
        anchor_mean_f64=math.fsum(base)/len(base),candidate_mean_f64=math.fsum(cand)/len(cand),J_recomputed_f64=math.fsum(gains)/len(gains),J_saved_float32=record.get('mean_gain',record.get('value')),
        positive_members=sum(x>0 for x in gains),negative_members=sum(x<0 for x in gains),network_queries=0)
    row['rounding_error']=row['J_recomputed_f64']-row['J_saved_float32'];assert abs(row['rounding_error'])<1e-7
    OBJECTIVES.append(row);return row

S0=B/'results/A/P10_PV_V3_launcher_runs/A10_PV_OFFLINE_PREFLIGHT_V3_r1_A_wave08/diagnostic'
S5=B/'results/A/P10_CAUSAL_C10_V2_launcher_runs/A10_CAUSAL_C10_PREFLIGHT_V2_r1_A_wave10'
C0=B/'results/A/A10_PV_HANDOFF_CPU_REPAIR_V1';C5=B/'results/A/A10_CAUSAL_EVENT_CPU_REPAIR_V1'
# Verify only selected small inputs against already accepted manifests.
registry={}
for path in [S0/'ARTIFACT_MANIFEST.json',S5/'Post/ARTIFACT_MANIFEST.json',S5/'Velocity/ARTIFACT_MANIFEST.json',B/'results/A/A10_CAUSAL_C10_PREFLIGHT_V2/EVIDENCE_MANIFEST.json']:
    for r in read(path)['files']:registry[r['path']]=r
configs={};Q_ids={};source_ids={}
for label,cp in [('step0',C0),('cut5',C5)]:
    proposal=read(cp/'proposal/PROPOSAL.json');cfg=read(cp/'config/CONFIG.json');configs[label]=cfg
    assert INPUTS[str(cp/'config/CONFIG.json')]['sha256']==proposal['config']['sha256']
    manifest=read(cp/'INPUT_MANIFEST.json');assert INPUTS[str(cp/'INPUT_MANIFEST.json')]['sha256']==proposal['input_manifest']['sha256']
    Q_ids[label]=[r for r in manifest['files'] if r['path'].startswith(cfg['Q_assets']+'/')]
    assert Q_ids[label]
    source_ids[label]=cfg['source']
    cm=read(cp/'code/CODE_MANIFEST.json');idx={r['path']:r for r in cm['files']}
    for rel in ['corrector/guidance.py','corrector/actions.py','corrector/solo.py','corrector/raw_commands.py','vendor_vla/src/lerobot/policies/pi05/modeling_pi05.py']:
        path=cp/'code'/rel;data=blob(path);assert digest(data)==idx[rel]['sha256']
for rel in ['corrector/guidance.py','corrector/actions.py','corrector/solo.py','corrector/raw_commands.py','vendor_vla/src/lerobot/policies/pi05/modeling_pi05.py']:
    assert INPUTS[str(C0/'code'/rel)]['sha256']==INPUTS[str(C5/'code'/rel)]['sha256']
blob(C0/'code/diagnostic.py');blob(C5/'code/runtime_engine.py')
IDENTITY=[];RESULTS={}
for state in ['step0','cut5']:
    pp=S0/'Post_arrays.npz' if state=='step0' else S5/'Post/Post_arrays.npz'
    vp=S0/'Velocity_arrays.npz' if state=='step0' else S5/'Velocity/Velocity_arrays.npz'
    ap=arrays(pp,state,'Post');av=arrays(vp,state,'Velocity')
    jp=read(S0/'Post_result.json' if state=='step0' else S5/'Post/Post_numeric.json')
    jv=read(S0/'Velocity_result.json' if state=='step0' else S5/'Velocity/Velocity_numeric.json')
    common=arrays(S0/'Q_observed_context.npz',state,'shared_context') if state=='step0' else arrays(S5/'Post/context_step5.npz',state,'Post_context')
    other=common if state=='step0' else arrays(S5/'Velocity/context_step5.npz',state,'Velocity_context')
    assert set(common)==set(other) and all(common[k]['raw']==other[k]['raw'] and common[k]['shape']==other[k]['shape'] and common[k]['dtype']==other[k]['dtype'] for k in common)
    assert ap['raw_a0']['raw']==av['raw_a0']['raw'] and ap['critic_a0']['raw']==av['critic_a0']['raw']
    assert jp['score']['member_probabilities'] and [p[0] for p in jp['score']['member_probabilities']]==[p[0] for p in jv['score']['member_probabilities']]
    extra=read(S0/'numeric_checks.json') if state=='step0' else {b:read(S5/b/'model_identity.json') for b in ['Post','Velocity']}
    if state=='cut5':assert extra['Post']['Q_assets']==extra['Velocity']['Q_assets']==configs[state]['Q_assets'] and jp['models_frozen'] and jv['models_frozen']
    else:assert extra['frozen_models']
    IDENTITY.append(dict(state=state,raw_anchor_identical=True,raw_anchor_payload_sha256=ap['raw_a0']['sha256'],bounded_anchor_identical=True,
        context_arrays_identical=True,context_fields={k:dict(shape=a['shape'],dtype=a['dtype'],payload_sha256=a['sha256']) for k,a in common.items()},
        Q_assets_identity=Q_ids[state],Q_identity_basis='accepted frozen input manifest and saved frozen-model flags; no weight opened or rehashed',
        same_objective_instance=state=='step0',same_anchor_member_probabilities=True,source=source_ids[state],same_state_geometry_allowed=True,
        hidden_environment_state_equivalence_claim=False,controlled_performance_pair_claim=False))
    g=vals(ap,'command_gradient' if state=='step0' else 'action_gradient_0')
    poststats=jp['gradient'] if state=='step0' else jp['updates'];scales=poststats['transform_slopes']
    raw=vals(ap,'raw_a0',40);base=vals(ap,'critic_a0',40)
    guided=vals(av,'own_native_raw',40) if state=='step0' else single(S5/'Velocity/guided_raw50.npy',state,'Velocity')['values'][:40]
    slope_sq=[f32(s*s) for s in scales]
    relation(state,'Post','saved raw_direction equals float32 S² * saved anchor command gradient',vals(ap,'raw_direction'),[f32(v*slope_sq[i%4]) for i,v in enumerate(g)],tol=1e-7)
    relation(state,'Velocity','saved raw_direction equals clamp(saved guided raw) minus saved bounded anchor',vals(av,'raw_direction'),sub(clamp(guided),base))
    stats(state,'Velocity','guided_native_raw_delta',sub(guided,raw),g,guided)
    stats(state,'Velocity','guided_clamped_delta',vals(av,'raw_direction'),g,clamp(guided))
    for branch,a,j in [('Post',ap,jp),('Velocity',av,jv)]:
        direction=vals(a,'raw_direction');mask=vals(a,'mask');masked=vals(a,'masked_direction');unit=vals(a,'unit_direction');requested=vals(a,'requested_delta');actual=vals(a,'actual_delta')
        relation(state,branch,'saved critic_a0 == clamp(saved raw_a0)',vals(a,'critic_a0'),clamp(vals(a,'raw_a0')))
        relation(state,branch,'saved mask uses anchor clearance .05',mask,[1-abs(v)>=.05 for v in base])
        relation(state,branch,'saved masked == saved direction * saved mask',masked,[v*m for v,m in zip(direction,mask)])
        relation(state,branch,'saved actual_delta == saved raw_plan - saved raw_a0',actual,sub(vals(a,'raw_plan',40),raw))
        relation(state,branch,'saved critic commands == clamp(saved raw_plan prefix)',vals(a,'critic_commands'),clamp(vals(a,'raw_plan',40)))
        relation(state,branch,'raw delta equals bounded execution delta',actual,sub(vals(a,'critic_commands'),base),tol=1e-6)
        for group,indices in [('xyz',[i for i in range(40) if i%4<3]),('gripper',list(range(3,40,4)))]:
            meta=j['matching']['groups'][group];n=meta['raw_masked_rms'];radius=meta['achieved_target']
            relation(state,branch,group+' saved masked RMS', [n],[norm([masked[i] for i in indices])/math.sqrt(len(indices))])
            relation(state,branch,group+' saved unit * saved normalization denominator == masked',[unit[i]*max(n,1e-10) for i in indices],[masked[i] for i in indices])
            relation(state,branch,group+' saved requested_delta == saved radius * saved unit',[requested[i] for i in indices],[radius*unit[i] for i in indices])
            relation(state,branch,group+' recorded radius/min/cap/margin scalar relation',[radius],[max(0.,min(meta['requested'],meta['feasible_radius'])*.999999) if n>1e-10 else 0.])
        for label,key in [('raw_direction','raw_direction'),('masked_direction','masked_direction'),('unit_direction','unit_direction'),('requested_delta','requested_delta'),('actual_delta','actual_delta')]:stats(state,branch,label,vals(a,key),g)
        stats(state,branch,'final_raw_proposal_delta',sub(vals(a,'raw_plan',40),raw),g,vals(a,'raw_plan',40))
        stats(state,branch,'final_clamped_proposal_delta',sub(vals(a,'critic_commands'),base),g,vals(a,'critic_commands'))
        anchor=extra['anchor_score'] if state=='step0' else j['anchor']
        score(state,branch,'same-state bounded a0',anchor)
        score(state,branch,'clamp(final projected raw proposal)[:10]',j['score'])
    RESULTS[state]=dict(anchor_gradient_norm=norm(g),anchor_gradient_payload_sha256=ap['command_gradient' if state=='step0' else 'action_gradient_0']['sha256'],scales=scales,
        own_radius_metadata={b:j['matching']['groups'] for b,j in [('Post',jp),('Velocity',jv)]},
        guided_raw_Q=None,guided_clamped_Q=None,guided_Q_missing_reason='No independent final guided-before-projection Q query is saved; last tau local-after is not substituted.',
        no_cross_state_gradient_reuse=True)
    logs=jv['updates'] if state=='step0' else jv['updates']['updates']
    anchor_mean=math.fsum(x[0] for x in jv['score']['member_probabilities'])/4
    for k,row in enumerate(logs):
        key='action_gradient_tau_'+str(k) if state=='step0' else 'action_gradient_'+str(k)
        d=vals(av,key);tau=row['tau'];alpha=row['alpha'];d_norm=norm(d)
        active=[d[t*32+j] for t in range(10) for j in range(4)]
        outside=[v for i,v in enumerate(d) if not (i//32<10 and i%32<4)]
        assert all(v==0 for v in outside)
        clean_grad=[-v/tau for v in active]
        relation(state,'Velocity',f'tau{k}: saved velocity derivative L2 vs log',[d_norm],[row['injection_gradient_norm']],tol=1e-6)
        relation(state,'Velocity',f'tau{k}: -d/tau clean gradient norm vs log',[norm(clean_grad)],[row['gradient_norm']],tol=2e-6)
        relation(state,'Velocity',f'tau{k}: alpha times derivative norm vs logged finite velocity delta norm',[alpha*d_norm],[row['velocity_delta_norm']],tol=3e-6)
        first_order=alpha*dot(d,d);observed=row['objective_after']-row['objective_before']
        before_mean=anchor_mean+row['objective_before'];headroom=1-before_mean
        TAUS.append(dict(state=state,branch='Velocity',tau_index=k,tau=tau,dt_static=-.1,alpha=alpha,
            saved_derivative_field=key,derivative_coordinates='dJ/dv in internal velocity coordinates, not anchor command gradient',
            derivative_l2_f64=d_norm,derived_clean_gradient_l2=norm(clean_grad),outside_C10x4_max=max(map(abs,outside)),
            local_J_before=row['objective_before'],local_J_after=row['objective_after'],local_J_change=observed,
            local_member_probabilities=None,local_probabilities_reason='Only local J scalar is saved; cannot independently recompute local J from missing member probabilities.',
            derived_local_candidate_mean_before=before_mean,derived_local_candidate_mean_after=anchor_mean+row['objective_after'],
            first_order_local_J_change=first_order,first_order_formula='alpha * ||saved dJ/dv||², before finite update and new active-set changes',
            predicted_clean_displacement_L2=alpha*tau*d_norm,recorded_velocity_delta_L2=row['velocity_delta_norm'],
            Euler_injection_clean_gradient_dot_at_same_point=first_order*.1/tau,
            Euler_dot_scope='algebra in same clean coordinates only; not a next-tau Q prediction',
            upward_probability_headroom=headroom,first_order_over_headroom=first_order/headroom,
            realized_to_first_order_ratio=observed/first_order if first_order else None,
            logged_clipping_fraction=row['clipping_fraction'],logged_boundary_fraction=row['boundary_fraction'],
            logged_clip_fraction_per_dimension=row['clipping_fraction_per_dimension'],
            logged_clean_unclipped_linf=row['clean_unclipped_linf'],logged_command_delta_linf=row['command_delta_linf'],
            logged_command_delta_per_dimension=row['command_delta_per_dimension'],
            accepted=row['accepted'],accepted_meaning='fixed update executed; no Q acceptance condition',halvings=row['halvings'],
            full_x_t=None,full_native_velocity=None,full_updated_velocity_precast=None,full_returned_velocity_postcast=None,
            full_clean_before=None,full_clean_after=None,intermediate_command_vectors=None,
            within_tau_actual_command_delta_dot_g=None,within_tau_actual_command_delta_cosine_g=None,
            missing_reason='Full per-tau state/velocity/clean/command vectors were not saved. Scalar norms cannot identify these vectors or finite-update direction.',
            final_guided_Q_independently_observed=False,actual_new_gradient_calls=0))

assert RESULTS['step0']['anchor_gradient_payload_sha256']!=RESULTS['cut5']['anchor_gradient_payload_sha256']
selected_verified=[]
for path,row in list(INPUTS.items()):
    if path in registry:
        assert row['sha256']==registry[path]['sha256'] and row['size_bytes']==registry[path]['size_bytes']
        selected_verified.append(path)
for field in FIELDS:
    name=field['field']
    if name in ['raw_a0','raw_plan','own_native_raw','cut_anchor_raw50','guided_raw50']:
        unit='raw environment-command coordinate, may exceed [-1,1]; not internal normalized clean'
    elif name in ['critic_a0','critic_commands']:
        unit='bounded environment-command coordinate in [-1,1]; J evaluates first10x4'
    elif name=='mask':unit='boolean boundary-clearance mask at bounded anchor'
    elif name in ['command_gradient','action_gradient_0'] and field['branch']=='Post':unit='dJ/da at bounded anchor; probability per environment-command coordinate'
    elif name.startswith('action_gradient'):unit='dJ/dv at this tau; internal normalized velocity coordinates, 1x50x32'
    elif name=='own_internal_guided':unit='saved final Euler x; normalized internal model coordinates, NOT saved per-tau clean-after'
    elif name=='unit_direction':unit='group-RMS-normalized direction (RMS includes masked zeros)'
    elif name in ['raw_direction','masked_direction','requested_delta','actual_delta']:unit='environment-command direction/displacement; inspect mapping/formulas for metric scaling'
    else:unit='saved observed-context feature; no new encoding or context construction'
    field['unit']=unit
put('INPUT_MANIFEST.json',dict(task_id='A10_PV_DIRECTION_CPU_ANALYSIS_V1',files=list(INPUTS.values()),
    selected_runtime_inputs_verified_against_accepted_manifest=selected_verified,
    Q_weight_identity_references_only=Q_ids,large_weight_files_opened=0,scope='two authorized saved states and narrow source/config/manifest files only'))
put('IDENTITY_PROOF.json',dict(states=IDENTITY,across_states_gradient_reuse=False,
    states_are_not_controlled_ablation=True,selected_formula_sources_byte_identical=True,new_weight_hashes=0))
put('ARRAY_FIELDS_AND_UNITS.json',dict(fields=FIELDS,S=RESULTS['step0']['scales'],
    physical_units='Commands are normalized actuator controls; no interpretation as metres or physical velocity.',
    g_clean_vs_g_command='clean gradient includes ActionTransform S and true clamp Jacobian; Velocity log gradient_norm is clean-coordinate gradient.'))
put('RELATION_CHECKS.json',dict(status='PASS',checks=RELATIONS,projection_implementation_called=False,
    new_projection_or_candidate_generated=False,arithmetic_scope='Compare saved-array identities and saved radius scalars; no optimization or projection replay.'))
put('DIRECTION_STAGES.json',dict(states=RESULTS,rows=STAGES,gradient_scope='same-state anchor only'))
put('OBJECTIVE_RECOMPUTATION.json',dict(rows=OBJECTIVES,arithmetic='binary64 sum of saved member probabilities; original float32 reductions retained separately',new_Q_queries=0))
put('TAU_LOCAL_ANALYSIS.json',dict(rows=TAUS,independent_final_guided_Q=None,new_Q_queries=0,
    interpretation='First-order algebra is local, not a finite-step guarantee or diagnosis of alpha as root cause.'))
for name,rows in [('DIRECTION_STAGES.csv',STAGES),('TAU_LOCAL_ANALYSIS.csv',TAUS),('OBJECTIVE_RECOMPUTATION.csv',OBJECTIVES)]:
    with (P/name).open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
assert not any(k.split('.')[0] in FORBIDDEN for k in sys.modules)
put('CPU_ARITHMETIC_RESULT.json',dict(status='PASS',states=2,direction_stage_rows=len(STAGES),local_tau_rows=len(TAUS),
    saved_array_relation_checks=len(RELATIONS),forbidden_imports=[],model_or_gradient_calls=0,projection_calls=0,
    launcher_calls=0,holder_operations=0,new_arrays_scored=0))
print(json.dumps(dict(status='PASS',states=RESULTS,stage_summary=[{k:x[k] for k in ['state','branch','stage','dot_g','cosine_g','l2']} for x in STAGES if x['stage'] in ['guided_native_raw_delta','guided_clamped_delta','masked_direction','actual_delta']],
    taus=[{k:x[k] for k in ['state','tau','first_order_local_J_change','local_J_change','first_order_over_headroom']} for x in TAUS],checks=len(RELATIONS)),ensure_ascii=False))
