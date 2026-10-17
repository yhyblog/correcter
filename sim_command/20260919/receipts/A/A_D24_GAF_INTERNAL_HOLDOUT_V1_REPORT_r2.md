# GAF：拟合完成，八卡正式评测运行

真实数据为训练15parent/27830窗口、内部holdout2parent/8494窗口；状态/动作/语言均从既有真实字段物化。三成员均完成10000步，共30000更新；按holdout MSE选择step9000/2000/10000（MSE0.04086844/0.06142881/0.06168959），没有测试选模型。

八个resident worker已记录MODEL_READY，同一预约自动接续原500源H10评测；本时点保存终局201、成功133、技术失败0。仅是进展快照，未宣称500完成。全部holder继续停算，终局发布及整组退出后恢复。

后台PID1849638，终局事件原会话回调已登记，正常接续不等聊天ACK。运行口径/限制见 /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_GAF_INTERNAL_HOLDOUT_V1/NUMERICAL_LINEAGE.md；完成结果将写 /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_GAF_INTERNAL_HOLDOUT_V1/FINAL_SUMMARY.json 和 chain/CHAIN_RESULT.json。
