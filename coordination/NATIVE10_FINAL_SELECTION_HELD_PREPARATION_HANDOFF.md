# 最终选择封存与 held 工程准备交接

已完成隔离实现和必要CPU检查，当前仅准备。校准完整交接已完成，未重复波次或旧79项CPU。原720份冻结代码逐SHA未变；新增模型/PCA/环境初始化/仿真/优化均为0，账本仍46025sim/51200opt，8卡holder保留。

选择入口 `final_selection_v1.py` 提供pending、精确READY契约、0资源封存和只读验证。实际scope/stage为 `calibration_selection_seal`，READY须精确绑定下列selection_future_ready_fields内容并显式释放scope；本轮没有调用seal。payload绑定A4000四文件、selected/reload、cal config/freeze、完整matching/guidance/raw、100源200结局/净14、全局post与两份分析独立review。严格保持完整V/D/P/reverse/random共同半径，未改单独post幅度。

- 选择pending：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/final_selection_preparations/final_selection_pending_v1`，seal `c1c052e98228be5c371fbefe5aef264383f2bb5fd376f4cf1fc302d4aa616a2c`。
- payload SHA：`f9e528e6f4ab740a4f7424349649705df791d2a149cbd3b0caba5cd9008e4796`。
- 可直接用于选择阶段READY的精确字段：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/execution_control/final_selection_held_preparation_v1/selection_future_ready_fields.json`，SHA `b40054f8ff54cf75d760a3e6103973876a0b39b8fe17e6b4c6be81d841558b6d`。

held新prepare/guard/runner/shell/统计已接线：原100主槽每task20、200有序backup、五臂×4、2200sim/0opt，原注册/随机流/G0/firstalarm/native10/raw及全部匹配依赖保持。只读注册确认held未初始化；800条旧scene前缀封存，真实物理唯一性留首次动作前核验。当前held配置仅指向pending选择计划，不能运行；实际选择seal生成后必须用真实path/seal/result重新生成独立pending，再由held READY绑定。

- held pending：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/heldout_preparations/heldout_pending_v1`，seal `5daf62537fb378c053b867dead92c9b652d272b02edbe1bca37ffc93f69fd262`；config SHA `f953c0a3dc00403d518b676b3a9f9b8fc25926954e197c97c614d060c6a2a14e`。
- held字段模板：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/execution_control/final_selection_held_preparation_v1/heldout_future_ready_template.json`，SHA `339023c9105f29ca21a143bbec2e60c641517cf1305888fb25af8d8ae844784e`。它不是本轮真实held放行字段。

唯一主比较P−R，其他六项次要；完整100源分母、4后缀先源内平均、任务内source bootstrap10000/seed2026091622/percentile95 linear，实际排序已保存。不在held后选方法；点估计>=5pp与区间支持正收益分开报告，不声称真实收益至少5pp。无报警真实共同结局保留，技术缺失不能填0。

新整合75项通过（5.02秒），另17项统计已通过（0.56秒）并直接归档未重跑。整合受测9文件+统计2文件SHA闭合，共11新文件；旧720代码不变。早期guard开发56pass未记录完整before/after SHA，明确只作历史收据；正式采用当前75+17证据。最终signed-zero修复已被整合测试覆盖。一个已封存cal bank的纯数组依赖检查通过，未读结局或调用模型；不当held效果或新初态证据。

新READY递归引用解析通过，选择精确字段16引用、held模板25引用全部实际可查；live v12同时拒绝真实选择封存与held执行。新held契约显式列selection/result.json路径SHA，确保其与complete一并进入freeze清单。没有裸假SHA、未冻结增长ledger/scene。

CPU：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/preparation/final_selection_heldout_cpu_20260917_v1`，seal `ef8ec8b07f14d145df49ba64733cc08596e591cf7b7e2a70a3f0efb70d793822`；统计CPU：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/preparation/heldout_statistics_cpu_20260917_v1`，seal `687482c2464a89eed63aaad857a6bb6deeb3b631c4d87eb0035f2fcfa0598720`。资源上界46025+2200+1200=49425<50000，共享储备没有新增；这仅是预算核对，不是held授权。

完整代码/参数/注册/证据路径与SHA见交接包summary.json。当前实际selection目录和held运行目录均不存在；准备完成后由分析端先发布0资源选择scope，再基于实际selection seal另行放行held。

交接包 `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/final_selection_held_preparation_handoffs/preparation_v1`，seal `61a720361d295ed9222e769ca19b3e900f1e53420d193bd0cbd1a9ad9bc57f41`。
