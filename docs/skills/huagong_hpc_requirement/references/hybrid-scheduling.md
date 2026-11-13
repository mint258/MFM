# compute-0-20/21/22：SSH与sbatch接管

配置由正在工作的仓库维护。P研究入口为X:/MFM_p_recipe/configs/p_recipe/scheduling.json及tools/p_recipe/launch_plan.py；详细协议见X:/MFM_p_recipe/docs/p_recipe/HYBRID_SCHEDULING.md。

先读取实际节点的scontrol show node（CPUTot、CPUAlloc、State）及目标UUID的nvidia-smi。剩余可分配CPU足够本任务则普通sbatch；不足且GPU占用≤30%、显存足够则SSH立即启动，同时提交同一任务的sbatch接管作业。只申请实际需要的CPU，禁止exclusive。不要按其他用户占用显存很少就推断其计算占用很低。

接管作业获得分配后，向原训练发唯一SAVE_AND_EXIT请求；训练在下一次完整优化器更新后保存模型、优化器、计数、采样位置、相关全部RNG及统计窗口。临时文件关闭同步后原子发布最终检查点，再发布回执并主动退出。接管器确认回执对应本job、原生身份与退出、GPU上下文及自有锁释放后恢复。未保存完整前不向原训练发送终止信号。原SSH任务已训练和评价完成则接管作业结束，无需再跑。

台账保存原生PID/UID/start_ticks/PGID、真实Slurm job ID、续训位置、来源/退出和GPU成本；SSH与Slurm等待重叠时间不重复计为GPU训练。作业取消/失败后从已有回执和真实句柄恢复，不盲目重交。其他用户进程不操作，GPU GRES未配置时不声称普通sbatch锁卡。已有旧程序只有完整已保存检查点时才可迁移，并如实报告可能回退量。

本规则主要适用于上述三个开发节点，不扩大其他服务器/科学任务授权。节点实际磁盘字节/inode、根盘max(10GiB,10%)预留、配额与并发峰值保护继续；其他工作流使用其自身断点协议，不能对不支持恢复的程序强行杀停。