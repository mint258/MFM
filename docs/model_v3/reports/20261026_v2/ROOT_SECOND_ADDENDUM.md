# 第二份Root补充：真实运行暴露的工具缺陷与独立修订

旧报告和失败结果保持。以下工作不构成模型/训练配方冻结或正式预训练放行。

C4 layer/head实际4521181（FAILED/65秒）已完成全部48例无hook控制并精确重放原baseline，随后在首例hook后的权重校验失败。原模型在inference mode构造参数，而仪器代码在该上下文退出后调用原torch.isfinite/hash校验，触发PyTorch的autograd/out错误。本次v3仅在两个原权重校验调用处保持torch.inference_mode，原checksum函数、模型forward、权重、输入、原abs1e-5/rtol0、52终端逐位控制及384次forward计划均保持。

v3增加普通/推理参数、环境grad模式恢复及权重改变拒绝的真实源码小测试。实际4521186在CPU13完成27项、0失败/错误/跳过，父C0/6秒。完整新诊断尚待这次v3公开注册之后执行，不能用旧48控制或27 unit代替96矩阵闭合。

CPU监督器v4保留原九项严格身份字段，在清理前落盘旧/新完整身份及changed_keys，禁止用新的capture覆盖旧信号授权。仅对预声明的四个直接pytest子进程，使用精确argv与fsync exec receipt完成两阶段登记；pending仍计入RSS/时间/存储，未知exec或kernel/session/cgroup/job差异仍拒绝。实际4521187在CPU12完成45项、0失败/错误/跳过，父C0/2秒，包含真实/proc fork→exec、Popen回执与严格单进程清理测试。

旧4521159缺比较帧，其唯一差异字段仍未知，不能倒推已证明根因。新Root整合回归另冻结native_s_precision_identity_v4_retry1，全部八片必须新执行，不拼接旧通过部分；旧45秒/60秒预取超时及监督器失败记录保留，未改测试等待时间或断言。新完整回归当前仍PENDING。

A01独立RTX4090计时v1的实际4521173（FAILED/4秒）在模型/GPU计算前，被原监督器的fresh-output/外部record规则拒绝。新布局修订另行准备，旧series intent、原数值20-batch/500-update资格及失败成本均保留，不在原v1自动重试位置1，也未产生独立速度结论。

W&B原生header probe4521164已校验55条来源及原始路由，另2条未通过；header不代表完整EOF/history证书或在线同步。完整native-integrity分类另行准备，只能授予日志同步资格，不能升级成科学source-mirror或数据线最终交付。

截至349个实际父作业的账本快照含全部已登记失败与0秒分辨率：757664分配CPU秒、29551个GPU节点作业分配秒；这是点时快照，后续新作业另行累计，GPU作业秒不是设备利用率。
