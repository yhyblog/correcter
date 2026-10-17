"""Append-only mapping of existing work and exact retained inputs to analysis decisions."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import json
import platform

ROOT=Path('/mnt/bn/arnold-recommend/yaohaoyang')
BASE=ROOT/'Corrector/sim_command/20260919'
OUT=BASE/'receipts/A'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':str(p),'sha256':sha(p)}
def publish(path,data):
    with path.open('x') as f:f.write(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def timestamp():return datetime.now(timezone.utc).isoformat()


def main():
    control=json.loads((BASE/'CONTROL.json').read_text())
    assert control['mode']=='prepare' and not control['stop_requested']
    assert all(v==0 for v in control['current_compute_limits'].values())
    assert control['storage_cleanup']['active_deletion_release'] is None
    decision=BASE/'contracts/INVENTORY_DECISIONS_V1.md'
    inventory_path=OUT/'A00_ASSETS.json'
    assets={x['asset_id']:x for x in json.loads(inventory_path.read_text())['assets']}
    previous=json.loads((OUT/'STORAGE_CANDIDATES.json').read_text())
    old_by_path={x['absolute_path']:x for x in previous['candidates']}
    selected=[
        ('pi05_mt50_sft_030000','MT50 frozen policy; complete processor/normalizer inference bundle'),
        ('mt50_demonstrations','Original MT50 demonstrations; common normal-data source'),
        ('vla_corrector_best_cosine','Selected external baseline; proposed B limited probe input'),
        ('spatial_pair_241','Frozen D member241'),('spatial_pair_242','Frozen D member242'),
        ('gate_341','Frozen G0 member341'),('gate_342','Frozen G0 member342'),
        ('Q_selected_bundle','Selected A4000 ensemble and bundled PCA/preprocessing/selection identity'),
        ('final_B_PCA_fit_audit','PCA provenance; distinct from selected A-member preprocessing'),
        ('train600_input_bundle','Immutable existing600 source supervision; no recollection'),
        ('round1_train_full_v1','Existing round1 training arrays'),('round2_train_full_v1','Existing round2 training arrays'),
        ('round1_development_full_v1','Existing development arrays'),
        ('native10_sources','Original source trajectories/state and source seals'),
        ('native10_banks','Original candidate banks and label provenance'),
        ('native10_rollouts','Original real suffix trajectories/outcomes'),
        ('native10_episode_split','Frozen parent/source/split assignments'),
        ('smolvla_partial_50000','E8 candidate at50000, including its actual recovery state; no resume100k'),
        ('smolvla_initialization','Retained initialization and inherited training lineage'),
        ('xvla_initialization','Initialization only; trained MT50 model still absent'),
        ('pi05_libero_final','Final29999/30k retained inference files and own normalization'),
        ('libero_demonstrations','Original LIBERO demonstrations for planned applicability work')]
    protected=[]
    for asset_id,purpose in selected:
        a=assets[asset_id];p=Path(a['path']);real=p.resolve(strict=True)
        if not real.is_relative_to(ROOT):raise ValueError('Input outside allowed workspace')
        files=a.get('files') or a.get('retained_files') or []
        known=old_by_path.get(str(p))
        if known:
            size=known['logical_bytes'];size_basis='prior published STORAGE_CANDIDATES inventory'
        elif real.is_file():
            size=real.stat().st_size;size_basis='single-file current stat'
        elif isinstance(files,list) and files and all(isinstance(x,dict) and isinstance(x.get('bytes'),int) for x in files):
            size=sum(x['bytes'] for x in files);size_basis='sum of previously inventoried manifest-listed files; not whole-directory rescan'
        else:
            size=None;size_basis='not re-enumerated; A00 identity retained; directory inode size is not payload size'
        protected.append({'asset_id':asset_id,'absolute_path':str(p),'realpath':str(real),
            'project': 'vla-corrector' if real.is_relative_to(ROOT/'vla-corrector') else 'Corrector' if real.is_relative_to(ROOT/'Corrector') else 'ACT-RECAP' if real.is_relative_to(ROOT/'ACT-RECAP') else 'embodied-ai-workspace / named VLA experiment asset',
            'type':'file' if real.is_file() else 'directory','logical_bytes':size,'size_evidence':size_basis,
            'purpose':purpose,'analysis_decision':'keep','decision_source':ref(decision),
            'unused_evidence':'required by the explicit analysis retention decision',
            'dependency_check':{'prior_inventory':ref(inventory_path),'asset_id':asset_id,'referenced_dependencies_must_also_be_retained':True},
            'replacement_retained_asset':None,'cross_node_note':'common A/B input; deletion is not permitted by this preparation release'})
    # Explicit support files and complete sealed result roots. No recursive historical re-inventory.
    extras=[
        (ROOT/'vla-corrector/outputs/metaworld_very_hard/corrector_pi05_mt50/h1_k10/config.json','vla-corrector','Selected baseline model configuration'),
        (ROOT/'Corrector/outputs/standalone_ablation_20260918','Corrector','Completed standalone results, seals and transitive references'),
        (ROOT/'Corrector/outputs/native10_training_20260916','Corrector','Completed native10 audit evidence and required dependency closure'),
        (ROOT/'ACT-RECAP/outputs/act_recap_future_aware_20260914/models/spatial_pair_241','ACT-RECAP','D241 configuration/normalization support for retained checkpoint'),
        (ROOT/'ACT-RECAP/outputs/act_recap_future_aware_20260914/models/spatial_pair_242','ACT-RECAP','D242 configuration/normalization support for retained checkpoint'),
        (ROOT/'ACT-RECAP/outputs/act_recap_future_aware_20260914/critics/gate_341','ACT-RECAP','G0341 configuration/normalization support'),
        (ROOT/'ACT-RECAP/outputs/act_recap_future_aware_20260914/critics/gate_342','ACT-RECAP','G0342 configuration/normalization support')]
    xbase=ROOT/'embodied-ai-workspace/models/base/xvla-cdb7964'
    extras += [(xbase/name,'embodied-ai-workspace / X-VLA base','Required base inference/processor file; distinct from download fragments')
               for name in ['model.safetensors','config.json','policy_preprocessor.json','policy_postprocessor.json']]
    for p,project,purpose in extras:
        real=p.resolve(strict=True)
        assert real.is_relative_to(ROOT)
        protected.append({'absolute_path':str(p),'realpath':str(real),'project':project,
            'type':'file' if real.is_file() else 'directory','logical_bytes':real.stat().st_size if real.is_file() else None,
            'size_evidence':'single-file metadata; large protected directory not rescanned',
            'purpose':purpose,'analysis_decision':'keep','decision_source':ref(decision),
            'unused_evidence':'required input/support or completed sealed evidence',
            'dependency_check':'keep complete configuration/normalization and referenced seals; future exact cleanup exceptions require analysis decision',
            'replacement_retained_asset':None,'cross_node_note':'shared input/evidence; do not delete under P00'})
    temp=[]
    own=BASE/'work/A/A10_r1'
    paths=sorted([p for p in own.iterdir() if p.is_dir() and p.name.startswith('test_artifacts')])
    paths+=sorted((BASE/'work/A').glob('A10_cpu_checks_*'))
    paths+=[BASE/f'results/A/A10/{kind}_v{version}' for version in (1,2) for kind in ['code_snapshot','preflight','commands']]
    for p in paths:
        real=p.resolve(strict=True);assert real.is_relative_to(BASE/'work/A') or real.is_relative_to(BASE/'results/A')
        files=[f for f in real.rglob('*') if f.is_file() and not f.is_symlink()]
        published=p.is_relative_to(BASE/'results/A')
        temp.append({'absolute_path':str(p),'realpath':str(real),'project':'Corrector current campaign / owner A',
            'type':'directory','logical_bytes':sum(f.stat().st_size for f in files),'file_count':len(files),
            'purpose':'superseded published preparation artifact' if published else 'completed CPU synthetic test payload',
            'completion_evidence':ref(OUT/'A10_RESULT.json'),
            'unused_evidence':'not established; published audit/provenance references still exist',
            'dependency_check': 'A10 ARTIFACT_MANIFEST explicitly retains these revisions' if published else 'CPU validation command records name test directories; unique audit payload requirements not cleared',
            'cross_node_check':'B consumed interface_v1 and an earlier accounting snapshot; original inputs remain read-only; no cross-node deletion assumed',
            'replacement_retained_asset':str(BASE/'results/A/A10/code_snapshot_v3') if published else str(BASE/'results/A/A10/evidence_v1/FINAL_CPU_VALIDATION.json'),
            'analysis_decision':None,'decision_status':'pending_analysis','executor_recommendation':'keep_audit_reference' if published else 'defer',
            'risk':'Deleting referenced evidence without a reviewed retention decision can break reproducibility'})
    peer=json.loads((BASE/'receipts/B/STORAGE_CANDIDATES.json').read_text())
    revision={'campaign_id':'corrector-sim-20260919','revision':2,'role':'A','hostname':platform.node(),
        'checked_at_utc':timestamp(),'scope':'existing required VLA inputs plus exact A preparation artifacts; no historical inventory rerun',
        'supersedes_by_append_only_reference':ref(OUT/'STORAGE_CANDIDATES.json'),
        'analysis_decision_source':ref(decision),'required_input_keep_entries':protected,
        'earlier_nonprotected_candidates':[x for x in previous['candidates'] if x['recommendation']!='keep'],
        'peer_candidates':peer['candidates'],'peer_reference_check':ref(OUT/'STORAGE_REFERENCE_CHECK_r1.json'),
        'own_preparation_candidates':temp,'active_deletion_release':None,'deleted_bytes':0,'deleted_paths':[],
        'decision_authority':'analysis alone decides delete/keep/defer; executor recommendations are not decisions',
        'historical_refs':'Any protected root above includes its sealed referenced dependencies; overlapping keep rows must not be summed as unique disk usage',
        'non_vla_scanned':False,'outside_workspace_targets':False,
        'runtime_environment_and_shared_cache_policy':'retained; not cleanup candidates; no broad environment/cache scan'}
    inventory=OUT/'STORAGE_CANDIDATES_r2.json';publish(inventory,revision)
    bresult=json.loads((BASE/'receipts/B/B10_RESULT.json').read_text())
    broot=Path(next(x['path'] for x in bresult['artifacts'] if x['path'].endswith('ARTIFACT_MANIFEST.json'))).parent
    methods=broot/'configs/METHODS.json';quote=broot/'configs/RESOURCE_QUOTE.json'
    report=OUT/'INVENTORY_DECISIONS_ALIGNMENT_r1.md'
    with report.open('x') as f:
        f.write(f'''# 分析决定落实与保留清单

- CONTROL v{control['revision']}、P00合约及A10任务SHA已核对；A00/A10已完成，不因元数据更新重跑。公共 `results/A/A10/interface_v1/INTERFACE_READY.json` 已发布并由B消费。
- E3锁定GAF-v1 adapted。B冻结的MSE/discounted success-to-go及每次采样原生引导见 `configs/METHODS.json`；A接口允许完整多次事件，不强接G0一次门。
- E6准备同D241/242的因果5步误差vs既定G0，均接R/H10/一次上限；动作/分支/reset对齐，缺预测不报警，覆盖率单列。异常开发阈值仍null，不能套用G0的0.05或测试追平。
- Smol使用50000候选，不续100k旧队列。X完整MT50训练底座仍缺；B已独立列原30k更新方案，但未声称它是已证实最小训练量，耗时/显存报价待有限预检；当前不启动。
- A的既有索引为700 train/development父源＋600固定a0/repeat0后缀，共1300条真实轨迹；action/reward/success可用，RGB/next等缺失仍显式保留。B仅bank缺字段的观察不冲突；旧train600未重采。
- 新增 `receipts/A/STORAGE_CANDIDATES_r2.json`：{len(protected)}条精确输入/封存保留项，覆盖SFT及处理器、MT50示范、选定权重、D/G0/Q/PCA、train600/原始树、Smol50k及恢复状态、X初始化/底座、LIBERO最终推理及原数据。复用A00证据，不重扫大数据目录；重叠保留项不可相加算磁盘量。
- 其他候选保留此前9个Smol中间checkpoint（14,494,556,639 bytes）及B2个X下载残片（3,519,073,692 bytes）的待定证据；新增{len(temp)}个本轮测试/过渡发布目录清单，合计{sum(x['logical_bytes'] for x in temp)}逻辑bytes。它们含审计引用，执行端不自行判无用或删除。
- 原 `STORAGE_CANDIDATES.json` 与A10封存回执不覆盖。所有新候选的delete/keep/defer由分析端决定；当前active_deletion_release=null，删除0，训练/模型GPU推理/仿真0。

B的版本化方法/报价：`{methods}`、`{quote}`。完整A10报告/有限预检命令与预算已交，尚未运行；后续只按具体新release推进。
''')
    result=OUT/'INVENTORY_DECISIONS_ALIGNMENT_r1.json'
    publish(result,{'status':'complete_preparation_alignment','created_at_utc':timestamp(),'control_revision':control['revision'],
        'analysis_decision':ref(decision),'report':ref(report),'storage_inventory_r2':ref(inventory),
        'existing_A10_result':ref(OUT/'A10_RESULT.json'),'interface_ready':ref(BASE/'results/A/A10/interface_v1/INTERFACE_READY.json'),
        'data_access':ref(BASE/'results/A/A10/data_access_v1/DATA_ACCESS_READY.json'),'B_methods':ref(methods),'B_resource_quote':ref(quote),
        'resource_counts':{'simulator_attempts':0,'vla_sampling_calls':0,'optimizer_updates':0,'gpu_seconds':0},'deleted_bytes':0})
    print(json.dumps({'report':str(report),'result':str(result),'storage_revision':str(inventory),
        'protected_entries':len(protected),'own_preparation_candidates':len(temp),'own_preparation_bytes':sum(x['logical_bytes'] for x in temp)},ensure_ascii=False))


if __name__=='__main__':main()
