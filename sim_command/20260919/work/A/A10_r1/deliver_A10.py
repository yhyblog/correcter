import json
import platform
import subprocess
from pathlib import Path
from campaign_io import BASE, RESULTS, atomic, now, sha

message = f'''A10 r1 CPU准备完成，A00原回执未改；实际sim/VLA采样/optimizer/实验GPU秒全部0，未启动训练、推理或仿真。
回执：{BASE}/receipts/A/A10_RESULT.json
短报告（55行）：{BASE}/receipts/A/A10_REPORT.md
总入口：{RESULTS}/CPU_READY_r1.json；437文件manifest同目录ARTIFACT_MANIFEST_r1.json。
1. 当前代码/预检/命令使用code_snapshot_v3、preflight_v3、commands_v3；公共interface_v1保持原SHA。A7+B23样例兼容，E3原生多次事件不被core一次干预摘要限制。
2. 两环境各42项CPU检查、381源码AST和shell通过；当前P00启动真实命令被明确拒绝。成功/部分失败/缺末事件三种成本样例已发布。
3. H/C分离、C10后丢弃尾部恢复nativeH、末cut285/290；核心仍16单元（R仅H10），独立自身半径和raw位模式保留。
4. data_access_v1索引700父源+600固定a0/repeat0后缀=1300真实轨迹，全部核验SHA，359段有首次成功；范围限定train/dev、不含held、不伪造图像/next。
5. 最小可执行预检报价：1诊断初态/1reset/1sim attempt、5完整native采样/50flow、1真实env step、0完整rollout/反向/monitor/更新，0重试，timeout1800+30秒。PROPOSAL.json与实际sh文件在v3目录；尚未执行。
6. 上述仅原生底座加载、五H队列与一条真实transition检查；不冒充P/V真实数值、MT50 D/G0/Q或完整评测验收。预估40GiB VRAM/64GiB RAM/2GiB新磁盘，尚未实测。
7. 命令绑定新release/host/实际GPU UUID及driver/全部输入SHA，不用旧READY或493余额；只允许A-only wave、拒绝联合wave。P10/A11需另冻结两端compute-exited屏障。
8. B的prefix1/逐步观测、policy-state/embedding要求已纳入交接；完整公共池/MT50适配/正式训练评测仍待对应task。E1数据复用train600，B13实际训练预算待发布。
9. receipts/A/STORAGE_CANDIDATES.json：4 keep+9 Smol历史中间checkpoint defer（14,494,556,639逻辑bytes），未排除封存/B恢复依赖，删除0。8张H100 holder正常、guard27508，RAM/VRAM/共享磁盘quota分别列出。
请审核A10+B10并决定有限P10 release；当前CONTROL仍prepare/零GPU额度。queue投递不代表验收或计算放行。'''

folder = BASE/'receipts/A'
attempt = len(list(folder.glob('A10_QUEUE_ATTEMPT_*.json'))) + 1
started = now()
result = subprocess.run(['codex','queue','--thread','01a0b91f-355f-7cd1-ae36-412500534ffb',
                         '--message',message],capture_output=True,text=True,timeout=45)
receipt = {'campaign_id':'corrector-sim-20260919','task_id':'A10','revision':1,'role':'A',
    'hostname':platform.node(),'attempt':attempt,'target_session':'01a0b91f-355f-7cd1-ae36-412500534ffb',
    'started_at_utc':started,'finished_at_utc':now(),'result_path':str(folder/'A10_RESULT.json'),
    'result_sha256':sha(folder/'A10_RESULT.json'),'returncode':result.returncode,
    'stdout':result.stdout,'stderr':result.stderr,'message':message,
    'status':'delivered' if result.returncode==0 else 'delivery_failed',
    'analysis_acceptance':'not_implied_by_queue_delivery'}
atomic(folder/f'A10_QUEUE_ATTEMPT_{attempt}.json',receipt)
if result.returncode==0:
    if (folder/'A10_QUEUE_DELIVERY.json').exists():raise RuntimeError('Already delivered')
    atomic(folder/'A10_QUEUE_DELIVERY.json',receipt)
print(json.dumps({k:receipt[k] for k in ['status','returncode','stdout','stderr','result_path','result_sha256']},ensure_ascii=False))
raise SystemExit(result.returncode)
