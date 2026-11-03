# 2026-11-04 数据线每日汇总 — v1-pilot-provisional

D‑1 v3.0已冻结，D‑2、D‑4、D‑5保持已交付；D‑3尚未交付。用户要求P′暂时挂起，先完成D‑3；本日不启动P′修复或新QM。

D‑3沿固定50,000 TRAIN＋5,000 ROUTINE VAL接续，141/171个已关闭源组保留。已补齐冻结清单中旧闭合索引及其所属计划引用，不改路径检查逻辑或科学编码器。实际sbatch作业4525668申请16CPU；脚本无时间及内存参数，程序不设总墙钟、RSS、MemAvailable停止门。大文件输出沿Lustre，750GB为预测而非硬上限，实际100GB账户余量规则保留。

本日格式/资源修复一行：补齐闭合元数据引用后提交一次；第一次因compute-0-8回连Main的临时SSH连接拒绝而在数据处理前FAILED/1，密钥路由实际恢复后仅requeue同一个4525668，无第二个sbatch、无新分子或QM/UFF。当前处于接续启动阶段，实际进度随后更新在本页。

导出末尾仍只做一次计数、随机1,000条原Parquet逐字段比较与总清单SHA；一次rsync --checksum复制、一次180秒随机读取测试。无独立复算或额外读回。模型加载器及逐预测头过拟合为交付后的验收；当前不代填模型ACK。

[D‑2注册表](../../configs/data_v1/v1-pilot-provisional/D2_registry.json)、[D‑4归一化](../../configs/data_v1/v1-pilot-provisional/D4_normalization.json)、[D‑5诊断载荷](../../configs/data_v1/v1-pilot-provisional/D5_diagnostic_payload.json)保持原交付。r73完整有序F64与单次F32、r674 LOSS_DISABLED保持。原始数据、几何及全部闭合成果保留。