# 模型线 W&B 记录

每个真实训练CSV的100000累计样本边界保存在 [`points/<Slurm作业>/<样本数>.json`](points/)，包含指标、来源及W&B同步状态。每次只推新边界文件，避免反复提交不断增大的总表。`100k_snapshots.json`保留最初19个边界的汇总历史。B64越过边界时保留实际样本数，不修改训练批量。历史补录标记`imported_history`；一次Slurm执行对应一个SDK run，续跑恢复点及弃置尾部成本保留，不能直接把多个执行的重叠曝光相加作为科学进度。

原始SDK位于 `/lfshome/zixiao/model_v31_20261105/WANDB_20261110/<job>/wandb/`，独立CPU任务读取日志，GPU训练不等待网络。新dispatcher训练自动注册。根协调器监控新的边界快照并推送到`model-v3`分支；数据、权重、SDK流和密钥不进入Git。

系统诊断使用同一project/group下的配对run `m3-<job>-diagnostics`，约30秒记录实际GPU功率、利用率、显存、温度/时钟、主进程CPU/RSS/I/O、节点余量与区间吞吐；连续1000实际更新的总/分项平均损失保留首尾步数、样本数和有效条数。新边界文件附最近观测的独立时间/样本计数。整卡功率不当作模型独占功耗，缺失指标不填零。详见[诊断口径](../../docs/model_v3/WANDB_TRAINING_DIAGNOSTICS.md)。

2026-11-10用户已重新登录；实际SDK仍报AuthenticationError，直接API返回HTTP403且非JSON，当前保持`OFFLINE_UNSYNCED`。离线记录继续，云端可见性仍需核实后才能声明同步成功。训练检查点仍按原科学里程碑与滚动恢复规则保存，本目录的10万样本快照是训练记录。
