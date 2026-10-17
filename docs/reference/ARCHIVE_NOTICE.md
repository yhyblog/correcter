# 历史实验归档说明

本目录保存 2026-09-16 flow guidance 实验的原始文档副本，保留原始字节以支持 SHA256 核验。配套的完整实验文件位于 `../../results/reference_flow_20260916/`，原关键实现位于 `../../provenance/source_snapshot/`。

## 当前执行范围

用户已要求暂缓更广泛验证，当前只开展现有 MetaWorld 设置下的 15 个新 source 小批量采样比较。归档中的 `ogg_flow_20260916/next_validation_plan.md`、`next_validation_plan.json` 及 identity 文件描述的是此前提出的 100-source 计划，仅为历史记录；该计划当前不执行。

历史主实验包含普通重规划、三种受控修正、反向与随机对照及两种未匹配原生注入，共 8 个执行分支。三种待比较修正为 velocity 注入、direct 注入，以及采样完成后的 post 修正；其中 post 不在 flow 积分过程中注入。

## 完整性与可复现范围

- 所有归档文件均实际复制，未使用软链接。
- `../../provenance/reference_archive_manifest.json` 记录原路径、当前相对路径、文件大小、SHA256 和拷贝时间。
- `../../provenance/assets_manifest.json` 记录四个 frozen critic 权重与动作归一化资产的相同信息。
- `../../provenance/source_snapshot/` 是用于追溯和数值一致性测试的原代码快照；其原始绝对路径和导入没有改写。
- 最新实验输出完整归档。原 9.35 GB VLA 主权重和 MetaWorld/Python 环境属于外部运行依赖，不包括在此历史实验归档中。
- 历史结果的 240 个配对 suffix 来自 30 个独立 source；按 source 进行统计推断。历史排序和置信区间仍属于探索性结果，不能把新的小批量结果误写为大规模确认。

归档后可运行：

```bash
python Corrector/provenance/archive_reference.py --verify-only
```

此命令仅校验当前副本，无需原 ACT-RECAP 目录或 GPU。
