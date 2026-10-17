# 本轮共同协议与manifest

分析端在盘点完成后冻结：
1. 方法矩阵与任务覆盖；
2. 公共训练/开发/测试parent episode、source与seed；
3. 数据视图和完整字段；
4. 代码、checkpoint、环境身份；
5. A/B互斥分片与公共日志schema；
6. 明确样本数、资源上限与失败处理。

未知量先记录缺口，不用随意数字填成已冻结协议。manifest发布后按revision保留历史，执行端只读。
