# L11 正式重测：三机独立分工

用户已明确授权本轮正式测试；固定L11=BCE+gain+0.5pair、fit9101、四成员。Post为本文，Velocity沿用同配置另文保留。旧L01结果原样保留，不改名为L11。

| 节点 | 独立任务（每格500源，H10 multi扣除已完成50） | 新episode |
|---|---|---:|
| A | π0.5 Post：H10 multi450、H10 once500、H30 multi500；Velocity相同三格 | 2900 |
| B | SmolVLA Post/Velocity各500；π0.5 H20 Post/Velocity各500；π0.5 H50 Post500 | 2500 |
| C | X-VLA Post/Velocity各500；π0.5 H40 Post/Velocity各500；π0.5 H50 Velocity500 | 2500 |

合计7900新单元，另复用π0.5 H10multi L11 fit9101 Post/Velocity各50，合并后8000。实际科学身份、env/policy seed以prepared_by_analysis/NEW_UNITS_<node>.jsonl为准。不同模型source域不得串用。无新初态、重训、采集或GPU预检；不重跑有效终局。Smol/X使用自身专属D/G0及各自已训L11 Q，π0.5使用原冻结D/G0及π0.5 L11 Q，不跨底座挪辅助网络。除Q损失对应checkpoint外，触发阈值、once/multi条件、C10、恢复H、动作单位、候选seed域不变。

各机先Post再Velocity，按cell自动衔接；可按模型加载成本调整同一优先级次序。所有任务独立，无跨机握手前置。每卡24路×8卡规则见CONCURRENCY_192.md，实际容量不足需证据及最大可执行并发，不伪称192已上线。

N/R五H、E6的R对照、R随机once、VLA-Corrector/GAF及完整Q消融复用现成结果；本次E3的L11 Post直接取H10主表，无额外500。LIBERO暂不做，Random-multi取消，475采集关闭，旧standalone/pilot/SFT不重跑。

总表EXPERIMENT_RESULTS_MASTER.md保存全部版本、原始失败、成本缺失、复用来源；EXPERIMENT_FOR_PAPER.md仅选最终L11 Post及适用独立基线。新L11终局成本需重新聚合，不沿用L01调用/耗时/配对统计。已用于选择L11的50源与主500重叠必须披露，不包装成新盲测。
