# 独立纠偏补充实验：GPU 运维依赖漂移审查

日期：2026-09-18 UTC。结论：**可在新协议中显式绑定当前两项 GPU 运维依赖，并补入其直接调用的 `gpu_hold.py`。未发现需改变科学方法的漂移。** 保留旧冻结、旧快照及失败 freeze 原件，不修改全局脚本。本审查仅只读比较及文件哈希核验，未执行脚本、模型、仿真或新增测试。

## 完整继承清单核验

- 原 `outputs/native10_training_20260916/heldout_protocols/heldout_v1/freeze.json` SHA：`a2db97fd0c76650e730b58836b0cd6059d25c76f42e5da4e2ce06611784d11b8`。
- 对其 `files` 全部 **1702 项逐项重算 SHA：1700 一致、2 项改变、0 缺失**，全部漂移均在下表。新失败 freeze 原样继承全部 1702 项，没有遗漏或改写旧期望值。
- 另列的大 VLA 权重遵照原 `large_files_verified_once_then_stat` 口径：bytes、mtime_ns、inode、device 均未变；本次未重新读取并哈希该约 9.35 GB 权重。
- 当前失败 freeze SHA：`0222d4614d0a1b41f9a0b807557eb1691cad99b2e91dc2d3509120f129b30e0b`。失败发生于运行前，封存的 blocker 记录新增 model/simulator/optimizer 均为 0；本审查不触发重试。

三脚本均位于 `/mnt/bn/arnold-recommend/yaohaoyang/`：

| 脚本 | 原冻结 SHA256 | 当前 SHA256 |
|---|---|---|
| `gpu_occupancy_lifecycle.sh` | `bdeffdb30d887ac8ee5c66fe7fe5adec30c931df8c4aaccde6702b9bd9127d68` | `3248ae959f5e43bca50c361818f620cff21eb87d10b1ee6b2d8c8756df623248` |
| `gpu_occupancy_guard.py` | `3107c2c64c95b10296d0a95b3152c16501d0e488c510833c092d06982bebdd15` | `d499982dff72c3b74ddab0e13e359edccb5f282900c534030b3816b58495fcaf` |
| `gpu_hold.py` | 不在原 `files`，不可虚构旧绑定 | `3f75a84145092f2c6beb342f8ea9ae445905c6e0549693c5aa78f525c0436a2e` |

## 旧快照与差异含义

原 `heldout_protocols/heldout_v1/code_snapshot.tar.gz` SHA 为 `517013a5e653420b3eb8a3c314702f310eb729775f92390d813a230e46973c11`。包内 `gpu_occupancy_lifecycle.sh`、`gpu_occupancy_guard.py` 的字节 SHA 分别与上表旧值一致；本次在内存中读取指定成员比较，没有解包覆盖文件。

两个脚本的唯一源码差异都是给 holder 传入 `--target-util 0.50`、`--period-seconds 0.20`；lifecycle 另增加相应环境变量默认值。当前 `gpu_hold.py` 明确支持这两个参数。差异影响非正式计算期间的占用负载，不改变纠偏动作、采样噪声、模型、环境或评分。

静态核对确认原有控制逻辑保持：

- guard 用全局 `formal.lock` 预留全部可见 GPU，启动正式命令前等待全部 GPU compute context 释放；预留覆盖加载及整波，单卡作业早结束不会恢复该卡 holder。
- 整条正式命令结束或异常退出后释放预留，guard 下一轮轮询恢复空闲卡 holder；无 guard 的 lifecycle 路径也保留退出恢复与信号转发。
- guard 只停止其自身创建的 holder 进程组；发现外部计算时让出 GPU，正式命令等待或拒绝启动，不杀无关进程。
- 正式波次仍须符合用户 AGENTS 的全 8 卡生命周期约束；5 个预检 worker 不等于仅预留 5 卡。本次依赖重绑不取消已有调度接口修复要求。

## 重绑边界

仅在新的授权/冻结中记录上述两项旧→新 SHA，并新增当前 holder 的直接依赖；其余 1700 项旧绑定保持。旧 seal 不原地改写，不绕过 SHA 校验，不将新环境追溯称为旧运行环境。

纠偏实现、flow/归一化/raw 语义、模型与 critic、源状态/cut/噪声键以及统计代码若发生漂移，均不能按此运维例外放行。本次对原 `files` 的全量检查没有发现这些漂移。这里确认的是源码与依赖身份，实际释放/恢复状态仍由既定生命周期回执记录。
