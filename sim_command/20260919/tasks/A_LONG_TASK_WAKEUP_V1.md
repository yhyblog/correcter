# A_LONG_TASK_WAKEUP_V1（revision1）

读取`persistent_queue/LONG_TASK_EVENT_WAKEUP_V1.md`及同名JSON授权。将完成事件与原执行会话唤醒纳入现有A_QUEUE_BOOTSTRAP_V1 r2；可独立先安装给当前长任务，不等待8路GPU配置或B接入。先窄核本机queue/exec resume实际行为；完成后不能仅交CPU_READY等待，按本授权安装并做至多2次短的原对话回调自检。

目标线程固定`01a0b91f-7443-71b1-915d-6cdb6d6a1a13`。任务稳定且后台trigger已登记后结束对话轮次；完成/失败事件自动触发原对话补审计、检查并续下一项已授权工作。当前Batch3的冻结入口/claim/科学预算不得改，只允许旁路消费已有结果/状态。不要因安装通知机制重跑当前批或启动尚未release的首8路。

公共组件可供B复用，但A本机安装、自检和长任务休眠不等B；共享源码封存后不热改已运行版本。保持八卡正式任务目标、空闲holder最新覆盖及同卡退出握手；通知器不操作正式进程/占卡。

输出`receipts/A/A_LONG_TASK_WAKEUP_V1_ACK.json`、`_REPORT.md`、`_RESULT.json`；node/A下发布独立wake机制READY、注册表和outbox引用（不要伪造采集daemon READY）。RESULT写真实验证支持的范围、未验证的关闭/重启边界。真实synthetic回调只写ACK并结束。身份正确的下一正式终局自动唤醒也是本次授权范围，无逐事件手动许可。
