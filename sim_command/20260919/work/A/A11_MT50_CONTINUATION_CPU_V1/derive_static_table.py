"""Narrow source/JSON/XML analysis only. Never import any environment package."""
from pathlib import Path
import ast, hashlib, json, xml.etree.ElementTree as ET
ROOT=Path('/mnt/bn/arnold-recommend/yaohaoyang')
B=ROOT/'Corrector/sim_command/20260919'
P=B/'results/A/A11_MT50_CONTINUATION_CPU_V1'
OLD=B/'results/A/A11_BATCH_SCALING_CPU_V1'
SITE=ROOT/'.miniforge3/envs/lerobot/lib/python3.12/site-packages'
MW=SITE/'metaworld'
WRAP=B/'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code/vendor_vla/src/lerobot/envs/metaworld.py'
def read(p):return json.loads(Path(p).read_text())
def ref(p):
    p=Path(p).resolve();raw=p.read_bytes()
    return dict(path=str(p),realpath=str(p),sha256=hashlib.sha256(raw).hexdigest(),size_bytes=len(raw))
def write(p,v):Path(p).write_text(json.dumps(v,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def methods(path,classname):
    text=Path(path).read_text();tree=ast.parse(text)
    cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name==classname)
    return text,cls,{x.name:x for x in cls.body if isinstance(x,ast.FunctionDef)}
def excerpt(path,text,node):return dict(path=str(path),lines=[node.lineno,node.end_lineno],source=ast.get_source_segment(text,node))
tree=ast.parse((MW/'env_dict.py').read_text())
mapping=next(x.value for x in tree.body if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ENV_CLS_MAP' for t in x.targets))
pairs=[(ast.literal_eval(k),v.attr) for k,v in zip(mapping.keys,mapping.values)]
assert len(pairs)==50 and len(set(k for k,v in pairs))==50
modules={a.name:n.module for n in ast.parse((MW/'envs/__init__.py').read_text()).body if isinstance(n,ast.ImportFrom) for a in n.names}
wrapper_config=read(WRAP.with_name('metaworld_config.json'))
catalog_path=B/'results/A/A11_COMMON_POOL_DESIGN_CPU_V1/POOL_COVERAGE_AND_GAPS.json'
catalog={x['environment_task']:x for x in read(catalog_path)['rows']}
old_evidence=read(OLD/'TASK_SOURCE_EVIDENCE.json');old_rows={x['task']:x for x in old_evidence['tasks']}
base_text,base_cls,base_methods=methods(MW/'sawyer_xyz_env.py','SawyerXYZEnv')
shared=[MW/'__init__.py',MW/'env_dict.py',MW/'envs/__init__.py',MW/'sawyer_xyz_env.py',SITE/'gymnasium/envs/mujoco/mujoco_env.py',WRAP,WRAP.with_name('metaworld_config.json')]
external=set(shared);evidence=[];rows=[]
FIELDS=('forward','do_simulation','physics','direct_steps')
def zero():return dict.fromkeys(FIELDS,0)
def add(*vs):return {k:sum(v[k] for v in vs) for k in FIELDS}
def scale(v,n):return {k:x*n for k,x in v.items()}
class Unquoted(ValueError):pass
class Effects:
    """Finite native effects on the inspected task functions; reject effectful unknown loops."""
    def __init__(self,ms):self.ms=ms;self.visited=set();self.stack=[]
    def method(self,name):
        if name=='_reset_hand':
            self.visited.add(name)
            if name in self.ms:
                node=self.ms[name]
                calls=[x for x in ast.walk(node) if isinstance(x,ast.Call)]
                if len(calls)!=2 or not any(ast.unparse(x)=='super()._reset_hand(steps=steps)' for x in calls):raise Unquoted('unrecognized _reset_hand override')
            return dict(forward=0,do_simulation=50,physics=250,direct_steps=0)
        if name=='set_state':return dict(forward=1,do_simulation=0,physics=0,direct_steps=0)
        if name in self.stack:raise Unquoted('recursive task path '+name)
        node=self.ms.get(name,base_methods.get(name))
        if node is None:return zero() # Read-only common helpers are checked by native-site audit below.
        self.visited.add(name);self.stack.append(name)
        try:return self.seq(node.body)
        finally:self.stack.pop()
    def seq(self,ns):return add(zero(),*[self.node(n) for n in ns])
    def node(self,n):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)):return zero()
        if isinstance(n,ast.Call):
            inner=self.seq(list(n.args)+[k.value for k in n.keywords]);f=ast.unparse(n.func)
            if f=='mujoco.mj_forward':return add(inner,dict(forward=1,do_simulation=0,physics=0,direct_steps=0))
            if f=='mujoco.mj_step':
                if len(n.args)!=2 or n.keywords:raise Unquoted('unquoted direct mj_step ABI')
                return add(inner,dict(forward=0,do_simulation=0,physics=1,direct_steps=1))
            if f.startswith('mujoco.') and f not in ('mujoco.mj_name2id',):raise Unquoted('other native call '+f)
            if f.startswith('self.') and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name):
                name=n.func.attr
                if name=='_reset_hand' and (n.args or n.keywords):raise Unquoted('nondefault reset hand')
                if name=='do_simulation':raise Unquoted('unclassified direct do_simulation')
                if name in ('reset','step','reset_model') and self.stack:raise Unquoted('extra reset/control from task')
                return add(inner,self.method(name))
            if f.startswith('super().'):
                # Constructor is checked independently; getters are read-only in the shared base.
                return inner
            return add(inner,self.node(n.func))
        if isinstance(n,ast.For):
            body=self.seq(n.body);tail=self.seq(n.orelse)
            if not any(body.values()):return add(self.node(n.iter),tail)
            if ast.unparse(n.iter)=='range(self.frame_skip)':count=5
            elif isinstance(n.iter,ast.Call) and ast.unparse(n.iter.func)=='range' and len(n.iter.args)==1 and isinstance(n.iter.args[0],ast.Constant):count=n.iter.args[0].value
            else:raise Unquoted('effectful unbounded for')
            return add(scale(body,count),tail)
        if isinstance(n,ast.While):
            values=add(self.node(n.test),self.seq(n.body),self.seq(n.orelse))
            if any(values.values()):raise Unquoted('effectful rejection loop')
            return zero()
        if isinstance(n,ast.If):
            a,b=self.seq(n.body),self.seq(n.orelse)
            if a!=b:raise Unquoted('conditional native count')
            return add(self.node(n.test),a)
        return self.seq(list(ast.iter_child_nodes(n)))

for ordinal,(task,classname) in enumerate(pairs):
    cat=catalog[task];language=cat['language_task_indices'];assert len(language)==1
    assert cat['instruction']==wrapper_config['TASK_DESCRIPTIONS'][task]
    assert cat['environment_id']==wrapper_config['TASK_NAME_TO_ID'][task]
    source=SITE/Path(*modules[classname].split('.')).with_suffix('.py')
    row=dict(task=task,task_dictionary_index=ordinal,wrapper_environment_id=cat['environment_id'],
        demonstration_language_index=language[0],instruction=cat['instruction'],module=modules[classname],cls=classname,
        ASCII_index=sorted(k for k,v in pairs).index(task),prior_parent_captured_closure_evidence=task in old_rows,
        physical_equality_proven=None,qualification_scope='captured fields/MJB closure only; per new parent verification still required')
    failure=None
    if task in old_rows:
        old=old_rows[task];row.update(reset_model_forwards=old['profile']['reset_model_forwards'],reset_model_direct_steps=0,
            reset_model_hand_calls=50,reset_model_physics=250,source_ref=old['source_ref'],evidence_reused=True)
        er=dict(task=task,reused_source_evidence=ref(OLD/'TASK_SOURCE_EVIDENCE.json'),reused_initialization=ref(OLD/'config'/('INITIALIZATION_'+task+'.json')),
            real_acceptance=ref(B/'manifests/A11_COMMON_POOL_BATCH1_V1_ACCEPTANCE.json'),new_runtime_proof=False)
    else:
        text,cls,ms=methods(source,classname);external.add(source);fx=Effects(ms)
        er=dict(task=task,source_ref=ref(source),narrow_paths=[],native_sites=[])
        try:
            if [ast.unparse(x) for x in cls.bases]!=['SawyerXYZEnv']:raise Unquoted('unexpected base class')
            if any(k in ms for k in ('reset','step','_get_obs','set_state','do_simulation')):raise Unquoted('unquoted shared-path override')
            constructors=[n for n in ast.walk(ms['__init__']) if isinstance(n,ast.Call) and ast.unparse(n.func)=='super().__init__']
            if len(constructors)!=1 or any(k.arg=='frame_skip' for k in constructors[0].keywords):raise Unquoted('constructor/frame_skip drift')
            init_extra=fx.seq(ms['__init__'].body)
            if any(init_extra.values()):raise Unquoted('extra constructor native work')
            effect=fx.method('reset_model')
            # Count and retain all native effect sites, including getters/reward paths.
            for name,node in ms.items():
                for call in ast.walk(node):
                    if isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute) and call.func.attr in ('mj_step','mj_forward','do_simulation','set_state','reset','reset_model'):
                        er['native_sites'].append(dict(method=name,line=call.lineno,call=ast.unparse(call)))
                        if name not in fx.visited and name not in ('__init__','_set_obj_xyz'):
                            raise Unquoted('native effect in untraced method '+name)
            xml_name=next(x.value for x in ast.walk(ms['model_name']) if isinstance(x,ast.Constant) and isinstance(x.value,str) and x.value.endswith('.xml'))
            pending=[MW/'assets'/xml_name];xml_seen=set();timesteps=[]
            while pending:
                q=pending.pop().resolve()
                if q in xml_seen:continue
                xml_seen.add(q);xt=ET.parse(q);external.add(q)
                timesteps += [n.attrib['timestep'] for n in xt.iter('option') if 'timestep' in n.attrib]
                pending += [(q.parent/n.attrib['file']).resolve() for n in xt.iter('include')]
            if timesteps!=['0.0025']:raise Unquoted('timestep not uniquely frozen 0.0025: '+str(timesteps))
            er['XML_refs']=[ref(q) for q in sorted(xml_seen)];er['timestep']=timesteps[0]
            row.update(reset_model_forwards=effect['forward'],reset_model_direct_steps=effect['direct_steps'],
                reset_model_hand_calls=effect['do_simulation'],reset_model_physics=effect['physics'])
        except (Unquoted,StopIteration,KeyError,ET.ParseError) as exc:failure=type(exc).__name__+': '+str(exc)
        er['narrow_paths']=[excerpt(source,text,ms[n]) for n in sorted(fx.visited|{'__init__','model_name'}) if n in ms]
        er['shared_base_paths_used']=[n for n in sorted(fx.visited) if n not in ms]
        row.update(source_ref=ref(source),evidence_reused=False)
    row['static_cap_status']='known' if failure is None else 'unknown';row['unknown_reason']=failure
    row['runtime_entry_allowed_by_static_support']=failure is None
    if failure is None:
        f=row['reset_model_forwards'];h=row['reset_model_hand_calls'];phys=row['reset_model_physics'];direct=row['reset_model_direct_steps']
        stages={}
        for name,n,constructors in [('taskset',50,1),('wrapper',1,1),('diagnostic_reset',1,0)]:
            stages[name]=dict(environment_instances=constructors,native_resets=n,reset_model_calls=2*n,
                do_simulation_calls=2*n*h,physics_substeps=2*n*phys,direct_mj_step_calls=2*n*direct,
                explicit_mj_forward_calls=constructors+2*n*f,native_state_get_obs_calls=2*n)
        stages['control']=dict(controls_upper=300,do_simulation_calls_upper=300,physics_substeps_upper=4000,
            native_state_get_obs_calls_upper=300,explicit_mj_forward_calls_upper=300,RGB_observations_upper=301,
            step_substeps_formula='floor((i+1)*400/30)-floor(i*400/30)',early_terminal='stop; no fill to300')
        row['stage_caps']=stages
        row['initialization_caps']=dict(model_initializations=0,environment_instances=2,wrapper_instances=1,
            taskset_constructions=1,taskset_reset_calls=50,wrapper_initialization_reset_calls=1,
            initialization_reset_calls=51,diagnostic_reset_calls=1,environment_reset_calls=52,
            reset_model_calls=104,initialization_do_simulation_calls=104*h,
            initialization_physics_substeps=104*phys,initialization_mj_forward_calls=2+104*f,
            policy_do_simulation_calls=300,policy_physics_substeps=4000,policy_mj_forward_calls=300,
            native_mj_forward_calls=302+104*f)
        if task in old_rows:assert row['initialization_caps']==old_rows[task]['per_attempt_initialization_caps']
    else:row['stage_caps']=None;row['initialization_caps']=None
    row['RNG_rejection_iterations_hard_bound']=None
    row['RNG_rejection_reason']='source rejection loops contain no charged physics/forward; inherited branch wall timeout only'
    er['derivation_status']=row['static_cap_status'];er['unknown_reason']=failure
    evidence.append(er);rows.append(row)

shared_evidence=[]
for path,classnames,names in [
    (MW/'sawyer_xyz_env.py',['SawyerXYZEnv','SawyerMocapBase'],['__init__','reset','_reset_hand','_set_obj_xyz','_get_obs','_get_curr_obs_combined_no_goal','step','_set_pos_site','reset_mocap_welds']),
    (SITE/'gymnasium/envs/mujoco/mujoco_env.py',['MujocoEnv'],['__init__','reset','set_state','do_simulation','_step_mujoco_simulation']),
    (WRAP,['MetaworldEnv'],['_make_envs_task','reset','step','_format_raw_obs','_get_obs'])]:
    text=path.read_text();tree=ast.parse(text)
    for cls in tree.body:
        if isinstance(cls,ast.ClassDef) and cls.name in classnames:
            shared_evidence += [dict(class_name=cls.name,**excerpt(path,text,x)) for x in cls.body if isinstance(x,ast.FunctionDef) and x.name in names]
inittext=(MW/'__init__.py').read_text();inittree=ast.parse(inittext)
shared_evidence += [excerpt(MW/'__init__.py',inittext,n) for n in inittree.body if isinstance(n,ast.FunctionDef) and n.name=='_make_tasks']
for cls in inittree.body:
    if isinstance(cls,ast.ClassDef) and cls.name=='MT1':shared_evidence += [excerpt(MW/'__init__.py',inittext,n) for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='__init__']
assert len({r['demonstration_language_index'] for r in rows})==49
known=sum(r['static_cap_status']=='known' for r in rows)
write(P/'config/MT50_TASK_TABLE.json',dict(schema='mt50_static_init_table_v1',status='CPU_STATIC_ONLY',rows=rows,
    known_task_count=known,unknown_task_count=50-known,already_measured_task_count=5,
    module_imports=0,new_real_qualification=False,unknown_task_policy='reject before model/hardware; do not substitute source',
    language_identity_note='dictionary index, wrapper environment id and demonstration language index are distinct; push/back both language40'))
write(P/'TASK_SOURCE_EVIDENCE.json',dict(schema='mt50_narrow_static_source_v1',new_task_rows=45,reused_task_rows=5,
    task_evidence=evidence,common_refs=[ref(q) for q in shared],shared_paths=shared_evidence,
    mapping_basis=ref(catalog_path),runtime_unknowns='actual full-state/MJB fields and equality remain per-parent gates',
    direct_physics_accounting='box-close/door-lock each5 direct mj_step per reset_model,104*5=520 added substeps; separate from do_simulation children'))
write(P/'evidence/NEW_STATIC_EXTERNAL_FILES.json',dict(files=[ref(q) for q in sorted(external)],scope='small source/XML only; no meshes, models or historical trajectory payloads'))
print(json.dumps(dict(known=known,unknown=[(r['task'],r['unknown_reason']) for r in rows if r['static_cap_status']=='unknown'],
    first8=[dict(task=r['task'],forward=r.get('reset_model_forwards'),direct=r.get('reset_model_direct_steps')) for r in sorted(rows,key=lambda r:r['task'])[:8]])))
