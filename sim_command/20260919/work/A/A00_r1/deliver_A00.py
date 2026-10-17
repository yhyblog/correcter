from audit_support import *
import subprocess

message = '''A00 r1完成（仅只读/CPU，sim/VLA采样/optimizer/实验GPU秒全部0）。回执：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/receipts/A/A00_RESULT.json；短报告同目录A00_REPORT.md（87行），资产表A00_ASSETS.json（43项），节点nodes/A/identity.json。
1. A为8×H100，驱动535.161.08，8holder/guard27508，未见正式GPU任务；共享guard日志不按host分名，勿当跨机状态。
2. 持久π0.5-MT50 030000推理包全7件在、尺寸一致、6小文件SHA匹配；旧/tmp缓存缺失；大权重未重复hash，既有SHA已列。
3. MT50示范497文件在，2500episode/204806frame/50环境（49语言index）；底座MT50已训练及2500episode旧评测完成。
4. D/G0/Q与train600为既有五任务资产；Q4+G0两小权重SHA匹配，A4000不是已完成全MT50适配。
5. train600有动作/reward/success/done/physics轨迹和31,200候选标签+2400normal；缺逐步RGB/next观测及独立terminated/truncated，不能直接充当完整共同池。
6. 外部vla-corrector9d23a0b、epoch30 best_cosine在；旧split是frame-pair随机90/10；101GiB token latent与旧fp32 base链接缺失，完整SFT仍可用。
7. Smol仅保存至50k/计划100k，旧队列signal15中断；X有初始化/环境，标准runs未见正式checkpoint。
8. LIBERO pi05 30k和四套件2000评测完成，最终18推理保留件在；optimizer大文件已清理，不能按旧archive-manifest恢复训练。
CONTROL v3/P00_PREP_V1已观察到；A00不消耗新工程权限，交付后核对A10任务/release。queue投递不代表分析验收。'''
folder = BASE / 'receipts/A'
prior = sorted(folder.glob('A00_QUEUE_ATTEMPT_*.json'))
attempt = len(prior) + 1
started = now()
run = subprocess.run(['codex', 'queue', '--thread', '01a0b91f-355f-7cd1-ae36-412500534ffb',
                      '--message', message], capture_output=True, text=True, timeout=45)
receipt = {'campaign_id': 'corrector-sim-20260919', 'task_id': 'A00', 'revision': 1,
           'role': 'A', 'hostname': platform.node(), 'attempt': attempt,
           'target_session': '01a0b91f-355f-7cd1-ae36-412500534ffb',
           'started_at_utc': started, 'finished_at_utc': now(),
           'result_path': str(folder / 'A00_RESULT.json'),
           'returncode': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr,
           'status': 'delivered' if run.returncode == 0 else 'delivery_failed',
           'message': message, 'analysis_acceptance': 'not_implied_by_queue_delivery'}
atomic(folder / f'A00_QUEUE_ATTEMPT_{attempt}.json', receipt)
if run.returncode == 0:
    assert not (folder / 'A00_QUEUE_DELIVERY.json').exists()
    atomic(folder / 'A00_QUEUE_DELIVERY.json', receipt)
print(json.dumps(receipt, ensure_ascii=False))
raise SystemExit(run.returncode)
