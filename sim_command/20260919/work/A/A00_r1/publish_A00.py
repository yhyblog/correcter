"""Publish the completed A00 read-only inventory, with RESULT written last."""
from audit_support import *
import collections

progress('Publishing A00 inventory and short report')
ACK = json.loads((BASE / 'receipts/A/A00_ACK.json').read_text())
CONTROL = json.loads((BASE / 'CONTROL.json').read_text())
WS = ROOT / 'embodied-ai-workspace'
NT = ROOT / 'Corrector/outputs/native10_training_20260916'
FA = ROOT / 'ACT-RECAP/outputs/act_recap_future_aware_20260914'
VL = ROOT / 'vla-corrector/outputs/metaworld_very_hard'


def evidence(name):
    return json.loads((WORK / name).read_text())['data']


assets = []


def asset(asset_id, path, kind, coverage, source=None, expected=None,
          verified=None, missing=None, notes=None, version=None):
    record = info(path, expected, hash_small=Path(path).suffix in ('.json', '.md'))
    record.update(asset_id=asset_id, kind=kind, coverage=coverage,
                  version=version, hash_source=source,
                  verified=verified or {'scope': record['identity_status']},
                  missing=missing or ([] if record['exists'] else [str(path)]),
                  notes=notes or [])
    assets.append(record)
    return record


checks = evidence('manifest_presence_checks.json')
for manifest_name, asset_id, kind, coverage in [
    ('legacy-pi05-mt50.files.json', 'pi05_mt50_sft_030000', 'inference_checkpoint_directory',
     'MT50 50 environments; 2500 demonstration episodes; 30000 optimizer steps; training seed 1000'),
    ('metaworld-raw-and-local-stats.files.json', 'mt50_demonstrations', 'demonstration_dataset',
     '2500 episodes / 204806 frames / 50 environment IDs / 49 language task indices'),
    ('libero-evaluation-assets.files.json', 'libero_evaluation_assets', 'simulator_assets',
     'Pinned LIBERO assets; historical four-suite evaluation available'),
    ('smolvla-initialization.files.json', 'smolvla_initialization', 'untrained_initialization',
     'MT50 seed42 initialization; not the partially trained 50k model'),
    ('xvla-initialization.files.json', 'xvla_initialization', 'untrained_initialization',
     'MT50 seed42 initialization; no formal X-VLA checkpoint found in indexed runs'),
]:
    manifest = WS / 'manifests/vla-baselines-20260911' / manifest_name
    original = json.loads(manifest.read_text())
    summary = checks[manifest_name]['summary']
    record = asset(asset_id, original['root'], kind, coverage,
                   source=str(manifest), verified=summary,
                   notes=['Large-file hashes are historical manifest identities; A00 verifies existence and size, not their full payload SHA.'])
    record['files'] = checks[manifest_name]['files']

asset('old_local_pi05_cache', '/tmp/act_recap_future_aware_20260914/checkpoint_cache/030000/pretrained_model',
      'machine_local_cache', 'Historical standalone runtime reference',
      source=str(ROOT / 'Corrector/outputs/standalone_ablation_20260918/protocols/standalone_v2/freeze.json'),
      notes=['Cache is missing on A; the persistent complete seven-file SFT inference directory exists. Rebind only a new campaign runtime.'])
asset('legacy_pi05_base_fp32', WS / 'models/pi05-base', 'linked_base_checkpoint',
      'Historical b211 PI0.5 base, distinct from complete SFT checkpoint',
      source=str(ROOT / 'vla-corrector/reproduction/metaworld_very_hard/HANDOFF.md'),
      notes=['Broken target under piper-work; the D-017 config/model overlay links are also broken. This does not mean the full SFT model is missing.'])
asset('legacy_siglip_token_latents', WS / 'artifacts/vla-latents-pi05-mt50', 'linked_latent_cache',
      'Historical 204806 x 256 x 2048 int8 SigLIP token cache, approximately 101 GiB',
      source=str(ROOT / 'vla-corrector/reproduction/metaworld_very_hard/HANDOFF.md'),
      notes=['Missing target. Historical metadata/SHA remains in handoff; new extraction would consume model calls and is not run in A00.'])
asset('paligemma_tokenizer_whitelist', WS / 'cache/paligemma-tokenizer-only', 'tokenizer_cache_index',
      'Tokenizer-only linked subtree; no credentials inspected or copied',
      source=str(WS / 'README.md'), notes=['Top-level existence checked; no full cache hash or import/model load.'])

for row in evidence('runtime_metadata.json'):
    metadata = json.loads(row['stdout']) if row.get('returncode') == 0 else None
    asset('runtime_' + Path(row['path']).parent.parent.name,
          Path(row['path']).parent.parent, 'runtime_environment', metadata,
          source=str(WORK / 'runtime_metadata.json'),
          verified={'interpreter_metadata_probe_returncode': row.get('returncode'),
                    'gpu_or_environment_instantiation': False},
          notes=['Package metadata only. Preserve base_prefix and editable source targets; no shared environment was changed.'])
asset('mesa_renderer', WS / 'environments/mesa-render', 'renderer_libraries',
      'Existing Mesa software EGL libraries and vendor JSON',
      source=str(WS / 'config/vla-corrector-mesa.env'),
      notes=['No renderer/environment instantiated in A00.'])

models = evidence('D_G0_Q_identities.json')
for row in models['D_G0']:
    selected = row['selected']
    asset(Path(row['directory']).name, selected['path'], 'frozen_D_or_G0_checkpoint',
          'Existing five-task local experiment; no completed MT50 adaptation claim',
          source=str(Path(row['directory']) / 'complete.json'),
          expected=row['checkpoint_sha256'], version={'selected_step': selected['step']},
          notes=['G0 labels used execute5 and historical H20/H50 sources; calibration to nativeH/C10 is not established.'])
q = NT / 'models/final/final_fit_v1/selected'
for member, expected in models['Q_hashes'].items():
    asset('Q_A4000_member_' + member, q / f'models/refit/member_{member}/selected.pt',
          'success_probability_critic', 'Five tasks; 600 training sources; C10; four-member A4000',
          source=str(q / 'ranking.json'), expected=expected,
          notes=['Selected A retains original per-member PCA/normalization; mixed-candidate training; standalone deployment does not imply independent training.'])
asset('Q_selected_bundle', q, 'sealed_critic_bundle', 'A4000 ensemble; H10/C10 historical protocol',
      source=str(q / 'complete.json'),
      verified={'four_member_small_payload_sha256': 'matched'},
      notes=['Need models/, config.json, ranking.json and complete.json together.'])
asset('final_B_PCA_fit_audit', NT / 'fit_preflight/final/final_preflight_v1/pca_fit_audit.json',
      'PCA_training_provenance', 'Train-only 600 unique sources, visual16/language8 for final B',
      notes=['This B PCA audit must not be mistaken for newly fitted PCA in the selected A4000 model.'])
asset('train600_input_bundle', NT / 'input_bundles/final_train600_input_v1/manifest.json',
      'sealed_input_manifest', '600 train, 100 planned development / 95 effective cut sources',
      source=str(NT / 'input_bundles/final_train600_input_v1/complete.json'))
for name in ('round1_train_full_v1', 'round2_train_full_v1', 'round1_development_full_v1'):
    schema = evidence('train600_schema.json')[name]
    asset(name, NT / 'datasets' / name, 'critic_training_arrays',
          {'rows': schema['rows'], 'task_counts': schema['task_counts'], 'split_counts': schema['split_counts']},
          source=str(NT / 'datasets' / name / 'complete.json'),
          verified={'npz_headers_and_row_metadata': True},
          notes=['Contains cut features, 13 candidate actions, four binary outcomes and separate normal controls. Not a complete generic transition dataset.'])
for name in ('sources', 'banks', 'rollouts'):
    asset('native10_' + name, NT / name, 'historical_raw_and_labels',
          'Five-task historical source/candidate/branch trees including train/development/calibration/heldout',
          source=str(WORK / 'trajectory_field_samples.json'),
          verified={'schema_sampled': True, 'all_payloads_rehashed': False},
          missing=['per-step RGB and next RGB', 'separate terminated/truncated flags'],
          notes=['Sample trajectory stores actions, physics_states, rewards, success_flags, done_flags, generated_plans and sampling seeds; cut context stores observed history/proprio/language. Physics state is for restoration, not a legal model observation.'])
asset('native10_episode_split', NT / 'main_protocols/round2_v1/config.json',
      'frozen_split_registry', '920 primary slots = 20 P0 + 600 train + 100 dev + 100 cal + 100 held; registry has 2720 records including reserves',
      notes=['Manifest record count is not the actual sample count. All same-episode cuts/branches stay together. Held data already revealed; do not reuse as new independent test.'])
asset('standalone_completed_status', ROOT / 'Corrector/coordination/STANDALONE_ABLATION_EXECUTOR_STATUS.json',
      'completed_historical_experiment', 'complete_analysis_accepted; no restart',
      notes=['No historical output/READY/ledger/freeze was changed by A00.'])

asset('vla_corrector_upstream', ROOT / 'vla-corrector', 'source_repository',
      'Historical MT50 dynamics training / Very Hard and Hard evaluation',
      source=str(WORK / 'repository_identities.json'),
      version='9d23a0ba6fad562d3ed1a68fc52c8a12459abb41',
      verified={'git_head': True, 'tracked_worktree_clean': True})
asset('vla_corrector_best_cosine', VL / 'corrector_pi05_mt50/h1_k10/best_cosine_model.pt',
      'external_baseline_checkpoint', 'MLP 20m, h1/k10, action4, epoch30, seed42',
      source=str(ROOT / 'vla-corrector/reproduction/metaworld_very_hard/HANDOFF.md'),
      version={'historical_sha256': '0efadcfdfde814fc4e929d007ed0b95894de33f0d51e3d3cae512605e223d168', 'expected_bytes': 170051647},
      notes=['Size checked; no payload rehash/model load. Original random split is over 179806 within-episode frame pairs (161826/17980), not grouped by episode. New common-data split needs an adapter.'])
asset('vla_corrector_entry', ROOT / 'vla-corrector/reproduction/metaworld_very_hard/04_eval_very_hard.sh',
      'historical_evaluation_entry', 'PI0.5 generated50/native10, h1/k10, 4 actions, budget300, eta1, attraction objective',
      source=str(WORK / 'code_static_checks.json'),
      notes=['Historical wrappers only; new campaign requires a new output/config and source identity.'])
smol = WS / 'artifacts/vla-baselines/runs/metaworld/smolvla/mt50-smolvla-s42-mb-20260912-v1/checkpoints/050000'
asset('smolvla_partial_50000', smol, 'partial_training_checkpoint',
      'Seed42; saved step50000 of planned100000; not a completed formal model selection',
      source=str(smol / 'training_state/training_step.json'),
      verified={'pretrained_model_directory_present': True, 'step_metadata': 50000},
      missing=['completed100000 receipt', 'formal SmolVLA evaluation in indexed evaluations'],
      notes=['Old queue failed on signal15. Do not restart it from A00.'])
asset('xvla_formal_runs', WS / 'artifacts/vla-baselines/runs/metaworld/xvla',
      'formal_training_runs', 'No formal X-VLA result found in this standard indexed location',
      notes=['Initialization/base weights and runtime are present; this is not a claim about every unrelated path on shared storage.'])
libero = WS / 'artifacts/vla-baselines/runs/libero/pi05/pi05_libero/libero-pi05-s42-ma-20260912-v1/29999'
record = asset('pi05_libero_final', libero, 'retained_inference_checkpoint',
      'Optimizer step30000; final four-suite evaluation 2000 episodes, 1933 successes',
      source=str(WS / 'artifacts/storage-cleanup/20260914-act-vla/libero-retention/immediate/retained-inference-files.json'),
      verified={'retained_files_present_and_sizes_match': 18, 'small_hash_mismatches': 0},
      missing=['optimizer/train_state large binary payloads intentionally removed'],
      notes=['Inference params/assets retained. Original archive-manifest predates cleanup and is not current optimizer-resume evidence.'])
record['retained_files'] = checks['libero_retained']['files']
asset('pi05_libero_reference', WS / 'models/reference/pi05-libero-official', 'reference_checkpoint',
      'Official PI0.5-LIBERO reference params and normalization',
      source=str(WS / 'artifacts/vla-baselines/preparation/20260911/pi05_libero_reference.download.json'),
      notes=['Directory inventory only; no new official-reference inference.'])
asset('libero_demonstrations', WS / 'datasets/libero/physical-intelligence-v2/a4336d589d589045d1c56423ffdf3b88a0e19b1f',
      'demonstration_dataset', '1693 episodes / 273465 frames / 40 tasks; four suites',
      source=str(WS / 'artifacts/vla-baselines/preparation/20260911/libero.data-audit.json'),
      verified={'metadata_present': True, 'coverage_from_historical_full_audit': True},
      notes=['No full data rehash in A00.'])
asset('baseline_multi_runtime_entry', WS / 'projects/vla-baselines/launchers/runtime.sh',
      'runtime_dispatch_entry', 'Legacy PI0.5, SmolVLA, X-VLA, openpi JAX and LIBERO simulator isolation',
      source=str(WORK / 'code_static_checks.json'), notes=['Syntax checked; never invoked to run a model or simulator.'])

node = evidence('node_probe.json')
runtime = evidence('runtime_metadata.json')
identity = {
    'role': 'A', 'hostname': platform.node(), 'session_id': ACK['executor_session_id'],
    'workspace_path': str(ROOT), 'checked_at_utc': now(),
    'shared_mount_check': {'local_mount': json.loads(node['commands']['mount']['stdout']),
                           'read_and_atomic_write_A_receipt': True,
                           'cross_host_bytes_identity': 'B must independently verify; A did not run remote commands'},
    'gpu_model': 'NVIDIA H100 80GB HBM3', 'gpu_count': 8, 'driver_version': '535.161.08',
    'gpu_inventory': node['commands']['gpu_inventory'],
    'environment_summary': [json.loads(row['stdout']) for row in runtime if row.get('returncode') == 0],
    'machine_local_checkpoint_gaps': [a['path'] for a in assets if a['asset_id'] == 'old_local_pi05_cache'],
    'persistent_asset_gaps': [a['path'] for a in assets if a['asset_id'] in ('legacy_pi05_base_fp32', 'legacy_siglip_token_latents')],
    'occupancy_status_source': str(WORK / 'node_probe.json'),
    'occupancy_state_source_is_machine_local': '/tmp/gpu_occupancy_guard/status.json',
    'occupancy': node['guard_status'],
    'formal_project_jobs_observed': [p for p in node['project_compute_processes']
                                    if not any('/sim_command/20260919/work/A/' in x for x in p['relevant_arguments'])],
    'gpu_processes_match_guard_driver_pids': True,
    'shared_guard_log_warning': 'Guard appends to common workspace gpu_occupancy_guard.log and gpu_occupancy_guard.holders.log without host-qualified paths. Use node-local status and host-stamped snapshots; plan isolated logging in later engineering.',
}
assert len(node['guard_status']['gpus']) == 8
assert all(g['state'] == 'holder' for g in node['guard_status']['gpus'].values())
gpu_pids = {int(line.split(',')[1].strip()) for line in node['commands']['compute_processes']['stdout'].splitlines()}
guard_pids = {pid for g in node['guard_status']['gpus'].values() for pid in g['driver_pids']}
assert gpu_pids == guard_pids

asset_doc = {'schema_version': 1, 'campaign_id': CONTROL['campaign_id'], 'task_id': 'A00',
             'task_revision': 1, 'role': 'A', 'hostname': platform.node(),
             'checked_at_utc': now(), 'assets': assets,
             'verification_policy': 'Small metadata/checkpoint hashes only; multi-GB weights are stat checked against historical manifest and are not rehashed. Existence, historical hash provenance, current hash verification and runtime readiness are separate.',
             'workspace_index': str(WORK / 'workspace_index.json')}

report = '''# A00 资产盘点回执（A，revision 1）

结论：A00完成；完成前CONTROL v3已发布P00_PREP_V1并放行A10/B10工程准备，正式训练、推理或仿真额度仍为0。A00交付后核对下一任务合同。
已存在的π0.5-MT50完整SFT、五任务D/G0/Q、train600、MT50示范与LIBERO推理权重可作为新任务输入候选；这不等于新比较协议或全MT50 Corrector已就绪。

| 资产/能力 | 当前可用事实 | 缺口与边界 |
|---|---|---|
| A主机/GPU | trial-303224955-trialrun-303224955-worker-0；8×H100 80GB；驱动535.161.08；224逻辑CPU | 未见正式项目计算；GPU进程PID全部匹配本机guard |
| occupancy | guard PID27508；8/8 holder，每卡1013MiB、49–50% | /tmp锁是本机的；guard两个日志为共享根目录固定路径，A/B不可用混合日志判断本机状态 |
| π0.5-MT50 SFT | 持久030000/pretrained_model全7文件，9,354,084,596B；6小文件SHA匹配，9.354GB权重尺寸匹配 | 大权重只引用既有SHA，未重新全量hash；旧/tmp推理缓存缺失 |
| MT50示范 | 497文件全部存在且尺寸匹配；492 Parquet；2500 episodes/204806 frames | 历史全量数据审计证明50环境、每环境50示范；49是语言task index数 |
| 五任务D/G0 | spatial_pair_241/242各选finetune400；gate341/342选1000/1200；文件存在 | G0仍是旧execute5收益目标；不能当作已校准的nativeH/C10收益或全MT50适配 |
| Q与PCA | A4000四成员小权重SHA全部匹配；A沿用原成员PCA；B另有train600 PCA审计 | 部署solo不代表训练独立；Q仍是五任务混合候选训练 |
| train600 | 两轮各300、每轮每任务60；31,200候选二值标签+2,400 normal标签 | 公共池字段不完整；需新合同和采集/视图适配 |
| vla-corrector复现 | commit 9d23a0b，tracked clean；best_cosine epoch30与配置在；Very Hard80/100、Hard71/120为历史结果 | 原按frame-pair随机90/10划分；不能宣称与本轮episode分组及共同数据相同 |
| SmolVLA-MT50 | 独立环境、初始化、005000…050000检查点；最新保存step50000 | 原100k队列signal15中断；未见完成100k或正式Smol评测回执，不能标“训练完成” |
| X-VLA-MT50 | 固定源码、独立环境、base与seed42初始化完整 | 标准正式runs位置未见X-VLA训练/评测完成产物 |
| π0.5-LIBERO | 30k训练完成；29999的params/assets保留18文件均尺寸匹配；四套件2000 episode完成 | train_state大文件已历史清理，不能用旧archive-manifest声称可恢复优化器 |
| 缺失旧资产 | pi05-base链接指向缺失piper-work；旧SigLIP token latent链接断裂 | 不影响完整SFT目录的存在；重训旧baseline需新提取或恢复latent，A00未执行 |
| 环境/入口 | lerobot、Smol、X、openpi、LIBERO五解释器元数据探针全成功；Mesa库在 | 只做CPU元数据/语法检查，没有CUDA、渲染或模型可运行性测试 |

路径约定：R=/mnt/bn/arnold-recommend/yaohaoyang；W=R/embodied-ai-workspace；N=R/Corrector/outputs/native10_training_20260916；V=R/vla-corrector/outputs/metaworld_very_hard。
逐资产完整路径、存在性、历史hash来源和本次核验层级见同目录A00_ASSETS.json；详细CPU证据在../../work/A/A00_r1/。

## 1. 迁机输入与embodied-ai-workspace关系

- W是物理目录和符号链接混合索引，不是可独立拷贝的完整备份。本次顶层55入口，7个断链；其中Corrector相关主要是pi05-base及旧latent，其余为Piper旧资源。
- W/projects/vla-corrector、W/models/vla-sft-030000、W/datasets/metaworld-mt50指向VLA原项目持久路径；Corrector复用其π0.5与环境，并从ACT-RECAP取D/G0与运行适配。
- B若共享同一持久挂载可直接核对W/models/vla-sft-030000；不应把A的/tmp路径或PID当成B的现状。
- 推理迁移必须带全7件：config.json、model.safetensors、train_config.json、policy_preprocessor.json、policy_preprocessor_step_2_normalizer_processor.safetensors、policy_postprocessor.json、policy_postprocessor_step_0_unnormalizer_processor.safetensors。
- 完整SFT权重历史SHA=dff338a91dbe534ca3c4525ba82df9324662e3c87131f42ed6e3d1b7bf0e94d4；证据W/manifests/vla-baselines-20260911/legacy-pi05-mt50.files.json。本次核对7件尺寸和6小件SHA；大权重身份尚非迁机后重hash证明。
- 另需固定VLA代码/复现脚本、tokenizer白名单、处理器和归一化、D/G0模型及normalization、Q完整selected目录、新campaign配置与source manifest。继续SFT还需要optimizer等training_state，不能只拿推理目录。
- 五环境分别为Python3.12/Torch2.7.1/TF5.4.0的legacy；Python3.12/Torch2.7.1/TF4.57.1的Smol与X；Python3.11/JAX0.5.3/Flax0.10.2的openpi；Python3.8/MuJoCo3.2.3/robosuite1.4.1的LIBERO仿真。
- Smol/X虚拟环境依赖.miniforge3/envs/lerobot，openpi依赖.miniforge3/envs/piper-wine，LIBERO依赖W/cache/python的3.8基座。独立迁移不能漏掉这些解释器基座和editable源码。
- ACT-RECAP HEAD=3063947且有既有tracked修改，Corrector本身不是独立Git仓库；新协议应绑实际文件SHA/快照，不能仅写Git HEAD。

## 2. 公共训练池与split事实

- N/input_bundles/final_train600_input_v1/manifest.json是合并输入身份；N/datasets/round1_train_full_v1与round2_train_full_v1各有arrays.npz、rows.json、metadata.json、complete.json。
- arrays含history[5,4096]、proprio[5,4]及mask、past_actions[4,4]、language[2048]、remaining、13×10×4 raw/bounded actions、13×4 outcomes、alias/pair权重、物理attempt IDs、episode/task/split/cut/round；normal的4次结果单独存control_outcomes，不是a0槽。
- a0是新重规划计划；normal保持原队列。bank下plans.npz保留13个50×4计划；generation/metadata保存噪声与生成器身份。
- N/sources、N/banks、N/rollouts保留原始树。已抽查源和a0后缀trajectory.npz：逐步action、reward、success、done、physics_state、完整生成计划和sampling seed确实存在，不是只有终局均值。
- 这些trajectory没有逐步RGB/next RGB/完整模型观测，done合并了终止语义，未分开terminated与truncated；不能把MuJoCo真实state当作合法观测。离线补图/特征如需恢复环境或编码要另计正式成本。
- 外部VLA-Corrector需要(t,t+10)的256×2048 token级latent；Q的4096维cut聚合特征不能直接替代。旧101GiB缓存缺失，底座/示范仍在，新提取或共享轨迹视图由P00/P10定义。
- 原实际主源为train600/dev100/cal100/held100，另P0=20；2720注册记录包含备用，不能当作实际完成源数。dev有效cut95，其他5源保留共同终局。
- 同一episode及其cut/候选/后缀归同一split；held已揭晓，禁止回流新训练或充当新独立测试。原MT50示范元数据只有train集合，新共同池仍需显式episode级划分。
- π0.5 SFT使用完整MT50示范、seed1000、30000更新；已有2500-episode MT50正常策略评测run.json为complete。旧五任务D/G0/Q及local labels不证明其他45任务或H20/30/40/50已适配。

## 3. 外部baseline与E8现状

- 先读了R/vla-corrector/reproduction/metaworld_very_hard/HANDOFF.md与RUN_LOG.md，再针对split/接口读实现。
- 旧VLA-Corrector：MLP 20m、42,509,568参数、h1/k10/action4、cosine loss、30 epoch、batch512、seed42；179806个episode内合法frame-pair按random_split分成161826/17980，非episode分组。
- 可用旧入口04_eval_very_hard.sh：π0.5生成50/正常执行10、预算300、k10、eta1、attract_delta_z_correction、apply_every1、cooldown10；不能用其旧连续seed或旧对照直接完成新E3。
- Smol/X复用W/projects/vla-baselines/launchers/runtime.sh及eval_metaworld.py；Smol生成50、X生成30且环境4维/内部20维。新P/V需要各底座flow/action映射，不能只换checkpoint路径。
- LIBERO复用serve_pi05.py+eval_libero.py的GPU服务/CPU环境分离接口；JAX、7维动作、双相机/任务文本、归一化与MW不同，P/V需要独立适配。
- LIBERO最终1933/2000=96.65%来自已发布summary；只表明旧底座验收完成，不是本方法E8的结果。29999保留清单优先于清理前archive-manifest。
- 旧baseline README仍写“仅准备”已过时：以9月13/14实际queue状态、保留清单及最终summary为准；历史machine-A/B与本轮A/B身份不可混用。

## 4. A10接口工作量（仅建议，未改旧实现）

| 新接口 | 现有位置/事实 | 建议准备单元 |
|---|---|---|
| nativeH与C10分离 | native10/semantics.py的Native10Queue使用固定HORIZON10；snapshot/prefix/合法cut也绑定它 | 新隔离队列+恢复序列；五H正常周期、C10干预及恢复nativeH的CPU边界检查 |
| source/restore/branch | native10/main_collection.py及standalone/collection.py校验/写死source与suffix10 | 新capture/restore schema与source ID；跨H只配初态、同H配cut；不复用冻结collector直接跑新协议 |
| standalone P/V | standalone/engine.py已有独立生成、失败日志和1/2调用事实，但绑定A4000/旧OGG | 提取新接口并显式绑定新模型与协议；数学保持分析端定义 |
| 完整调用和时间 | _JournalRuntime.native_action记录enter/return/error，generate_solo记录组件耗时；旧trace只聚合部分时间 | 统一episode/source/bank/suffix调用账本，分开VLA采样、flow前向、D/G0/Q及CUDA同步事件计时 |
| 原始transition与统计行 | main_collection trajectory与summary已有actions/rewards/seed/配对ID，缺完整观测和终止区分 | 观测/next观测引用、terminated/truncated、success_step、执行prefix、host/shard/H/C、model/data/code SHA、失败和资源逐源行 |

工作量按上述5个准备单元核价，另有跨主机路径/日志与资产绑定1单元；A10做CPU接口验证和成本报价，P00先固定数据字段/分组/方法，P10才冻结正式数量与上限。

## 5. 数量与资源估算口径

- A00实际simulator_attempts/completed_rollouts/vla_sampling_calls/optimizer_updates/gpu_seconds全部0；既有AGENTS占卡不属于本任务实验计算。
- 采集attempt按capture、bank恢复、每个物理分支含恢复、预检、技术失败分别累加；不可用逻辑结果单元数替代物理attempt。
- 若沿旧13候选+normal、每项4后缀，完整cut源示例为1 capture+1 bank恢复+14×4分支=58 attempts；此例不是新协议数量承诺。
- E4有16逻辑单元；50任务、每任务n初态、K后缀时逻辑规模为50nK×16，E3再加50nK×2。跨方法源恢复、无报警复用、早终止和故障另作实际attempt账；n/K未发布。
- 每条未提前结束nativeH轨迹的普通完整采样参考上界为ceil(300/H)=30/15/10/8/6；报警会改变节拍。每个独立干预入口R/P/V采样1/1/2；prefix恢复、后缀和失败进入同一总账，不能只报入口常数。
- 优化按实际完整训练seed×ensemble成员×每成员更新累加；E1四损失×建议3seed不等于四成员ensemble。D/G0/Q及外部模型更新上限、数据规模、存储预算、失败/重试上限仍待P10。
- 旧49507/50000的493余额不转作新预算；历史并发耗时不可作为A/B受控加速比。A的/tmp当前约2.81TiB可用，存储/加载与采集成本需由新受限预检报价。

## 6. 审计范围、失败与下一步

- 17个实际存在的Python/shell入口通过AST或bash -n；初始猜测native10/collection.py不存在，正确实现是main_collection.py，已检查，未执行模型代码。
- G0两件与Q四件small checkpoint SHA匹配；已核查清单的MW497、SFT7、LIBERO970、Smol初始化6、X初始化6均存在且尺寸一致，小文件hash无漂移；LIBERO最终保留18件同样通过尺寸/小文件检查。
- 轨迹字段为源+后缀样本及压缩数组header核查，未重新执行旧全量统计/仿真审计。大型权重没有重复hash，完整新机模型/渲染可运行性未声明通过。
- CONTROL从v1变v2、v2变v3时本地严格revision门分别让node probe及发布器退出1；前者登记B身份，后者发布A10/B10零计算准备。重新读取确认A00正文/SHA及授权未改，改为每批核对A00身份、范围及零预算后继续。另git -C Corrector rev-parse退出128，已确认无独立Git，改用文件SHA。均未触及模型/仿真。
- 只写nodes/A、receipts/A和work/A；未改CONTROL/TASK_BOARD、旧封存/READY/环境/权重。建议新P00/A10采用上述字段、split及路径结论；交付后读取已发布P00_PREP_V1及A10任务书，不自动启动任何正式计算。
'''

assert len(report.splitlines()) <= 150, len(report.splitlines())
report_path = BASE / 'receipts/A/A00_REPORT.md'
asset_path = BASE / 'receipts/A/A00_ASSETS.json'
identity_path = BASE / 'nodes/A/identity.json'
result_path = BASE / 'receipts/A/A00_RESULT.json'
assert not result_path.exists(), 'Published result exists; use a revision receipt instead of overwriting.'
atomic(identity_path, identity)
atomic(asset_path, asset_doc)
temporary = report_path.with_name(report_path.name + '.tmp.' + uuid.uuid4().hex)
temporary.write_text(report)
os.replace(temporary, report_path)

findings = [
    'A has eight H100 80GB GPUs, driver535.161.08, all holder PIDs match local guard27508; no formal project compute observed.',
    'Persistent PI0.5-MT50 030000 inference directory has all seven files and expected sizes; six small hashes match; only historical /tmp cache is missing.',
    'MT50 demos cover50 environment IDs,2500 episodes,204806 frames;497 manifest files present.49 language indices do not mean a missing task.',
    'D/G0 and A4000/train600 are existing five-task assets; Q four and G0 two small weight SHA values match; no completed full-MT50/H adaptation claim.',
    'Train600 contains source/branch actions,rewards,success/done,physics states and candidate labels, but lacks per-step legal observations/next observations and distinct terminated/truncated.',
    'External vla-corrector code9d23a0b and epoch30 best_cosine are retained; historical training split was frame-pair random90/10; token latent cache is missing.',
    'SmolVLA retains step50000 of planned100000 after signal15 queue interruption; X-VLA has initialized assets but no formal checkpoint in indexed runs.',
    'LIBERO pi05 completed30000 training and2000 final episodes;18 retained inference files present; optimizer large binaries intentionally removed.',
    'Five Python environments metadata probes and17 existing entry syntax checks passed; legacy base/latent links broken; shared guard logs are not host-qualified.',
    'A00 experimental simulator,rollout,VLA sampling,optimizer andGPU-second counts are all0; only P00/A10 preparation is proposed, no new compute authorized.',
]
failures = [
    {'command': '/usr/bin/python3 -B ' + str(WORK / 'probe_node.py'), 'exit_code': 1,
     'error_class': 'CONTROL_revision_guard', 'detail': 'CONTROL advanced from1 to2 while A00 revision1 and zero-compute scope remained unchanged.',
     'recovery': 'Read CONTROL/TASK_BOARD/A00; revision2 only fills B host/session; updated own audit helper accepted revisions and retried read-only probe successfully.'},
    {'command': 'git -C ' + str(ROOT / 'Corrector') + ' rev-parse HEAD', 'exit_code': 128,
     'error_class': 'not_a_git_repository', 'recovery': 'Recorded filesystem/source-SHA identities; no git mutation or repository recreation.'},
    {'command': 'python3 -B ' + str(WORK / 'publish_A00.py'), 'exit_code': 1,
     'error_class': 'CONTROL_revision_guard', 'detail': 'CONTROL advanced to3 and released P00/A10/B10 zero-compute preparation; A00 unchanged.',
     'recovery': 'Re-read CONTROL; own helper now validates unchanged A00 task SHA, owner, scope, stop flag and zero compute limits on each batch. Retried publication.'},
]
blockers = [
    {'id': 'new_runtime_paths', 'affects': ['A10', 'future_GPU_runs'], 'detail': 'Old local /tmp checkpoint is absent; persistent SFT remains.', 'resolution': 'New campaign config must bind the persistent directory or a newly audited per-host cache without changing old freeze.'},
    {'id': 'common_data_and_split', 'affects': ['P00', 'A10', 'B10', 'A11', 'B11'], 'detail': 'Five-task Q arrays and frame-pair baseline split are not the agreed full transition pool / episode-grouped split.', 'resolution': 'Freeze fields and source-level splits; add legal observations,next observations,termination semantics and provenance before released collection.'},
    {'id': 'MT50_H_adaptation', 'affects': ['A12', 'E4', 'E3'], 'detail': 'No completed MT50 D/G0/Q or multi-H validation; runtime hardcodes10 and A4000.', 'resolution': 'Prepare separate H/C interfaces then new released training/calibration/evaluation inputs.'},
    {'id': 'external_assets', 'affects': ['B10', 'B12', 'E8'], 'detail': 'Token latent cache and legacy fp32 base links missing; Smol partial; X initialization only; LIBERO optimizer intentionally removed.', 'resolution': 'Reuse persistent inference assets; analysis decides needed new training or feature extraction with explicit budgets.'},
    {'id': 'host_logging', 'affects': ['A10', 'B10'], 'detail': 'Guard uses machine-local PID/locks but global shared log filenames.', 'resolution': 'Use node-local live state and own host-stamped receipts; prepare host-separated logging without changing archived science.'},
]
atomic(WORK / 'failures_and_recoveries.json', failures)
atomic(WORK / 'control_revision_observations.json', {
    'ack_control': next(x for x in ACK['inputs_checked'] if x['path'].endswith('/CONTROL.json')),
    'completed_control': info(BASE / 'CONTROL.json', hash_small=True),
    'review': 'revision2 registers B identity; revision3 releases P00/A10/B10 preparation. A00 task SHA and zero-compute limits remain unchanged; A00 does not consume the new engineering scope.',
})
manifest = [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size}
            for p in sorted(WORK.iterdir()) if p.is_file() and p.name != 'evidence_manifest.json']
atomic(WORK / 'evidence_manifest.json', {'task_id': 'A00', 'revision': 1, 'files': manifest})
result = {
    'campaign_id': CONTROL['campaign_id'], 'task_id': 'A00', 'revision': 1,
    'role': 'A', 'hostname': platform.node(), 'session_id': ACK['executor_session_id'],
    'status': 'complete', 'started_at_utc': ACK['started_at_utc'], 'finished_at_utc': now(),
    'control_revision_at_ack': ACK['control_revision'], 'control_revision_at_completion': CONTROL['revision'],
    'input_identity': {
        'protocol': {'path': None, 'sha256': None, 'reason': 'No formal protocol released; prepare-only A00 task is the authority.', 'task': info(BASE / 'tasks/A00.md', hash_small=True)},
        'config': [info(BASE / 'CONTROL.json', hash_small=True), info(BASE / 'MASTER_PLAN.md', hash_small=True), info(ROOT / 'Corrector/docs/NATIVE10_CORRECTOR_ALGORITHM_ZH.md', hash_small=True)],
        'code': {'path': str(WORK / 'code_static_checks.json'), 'sha256': hashlib.sha256((WORK / 'code_static_checks.json').read_bytes()).hexdigest()},
        'data': [info(NT / 'input_bundles/final_train600_input_v1/manifest.json', hash_small=True), info(WS / 'manifests/vla-baselines-20260911/metaworld-raw-and-local-stats.files.json', hash_small=True)],
        'model': {'path': str(VL / 'sft_pi05_mt50/checkpoints/030000/pretrained_model/model.safetensors'), 'sha256': None,
                  'historical_sha256': 'dff338a91dbe534ca3c4525ba82df9324662e3c87131f42ed6e3d1b7bf0e94d4',
                  'reason': 'Large payload existence and9354050752-byte size verified; no redundant full hash for A00.',
                  'manifest': info(WS / 'manifests/vla-baselines-20260911/legacy-pi05-mt50.files.json', hash_small=True)},
    },
    'artifacts': [info(p, hash_small=True) for p in (report_path, asset_path, identity_path, WORK / 'evidence_manifest.json')],
    'resource_counts': {'simulator_attempts': 0, 'completed_rollouts': 0, 'vla_sampling_calls': 0, 'optimizer_updates': 0, 'gpu_seconds': 0},
    'resource_count_scope': 'A00 new experimental compute only; existing mandatory occupancy holders excluded.',
    'failures_and_retries': failures, 'findings': findings, 'blockers': blockers,
    'next_task_proposal': 'Read released P00_PREP_V1 and A10 contract after A00 queue delivery; incorporate inventory gaps in isolated zero-compute preparation. No formal experiment is released.',
    'delivery_receipt_path': str(BASE / 'receipts/A/A00_QUEUE_DELIVERY.json'),
    'legacy_assets_modified': False,
}
atomic(result_path, result)
heartbeat = json.loads((BASE / 'receipts/A/A00_HEARTBEAT.json').read_text())
heartbeat.update(status='complete', updated_at_utc=now(), progress='A00_RESULT published; queue delivery follows')
atomic(BASE / 'receipts/A/A00_HEARTBEAT.json', heartbeat)
print(json.dumps({'result': str(result_path), 'report_lines': len(report.splitlines()), 'assets': len(assets),
                  'status': result['status'], 'resource_counts': result['resource_counts']}, ensure_ascii=False))
