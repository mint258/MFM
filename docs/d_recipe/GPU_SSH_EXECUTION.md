# D 原生 GPU 接续与同任务接管

按现行11-26调度规则，仅在20/22使用此混合路径；21禁用。普通sbatch用于有足够可分配CPU的合规目标，实际状态以CURRENT_BEST为准。20/22 CPU不足时按已授权GPU共享规则记录实际5核活动与自有核锁，不额外套用CPU-only任务的95% idle门；RAM、显存/UUID锁、磁盘/UID和安全退出保护继续。本文不授权额外训练臂、种子、预算或删文件。

入口为`tools.d_recipe.gpu_native`及`gpu_takeover`；[节点20计划](../../configs/d_recipe/continuations/L1_GPU20_native_20261126_plan.json)与[节点22计划](../../configs/d_recipe/continuations/L1_GPU22_native_20261126_plan.json)包含现有P提供器/生命周期/接管函数的指纹与冻结启动器。真实运行配置尚未生成，实际GPU运行和standby均未启动。7项定向测试使用CPU上的真实自有进程及合成控制状态，不运行模型；另一次CPU元数据任务核对原提供器、启动器嵌入和接口，记录及成本见[执行记录](../../results/d_recipe/safe_L1_handoff_and_L2_SSH_segments_20261126.json)。

启动时先核实目标State/Reason、UUID/显存与自有锁，并通过独立d-recipe登记的64GiB RAM、节点盘、共享盘及新鲜UID准入。只有准入后才建立已登记的本地根和控制目录，按实际5核亲和性补全唯一原生配置。保持原L1/seed0/3M、3读者、2,090,752完整检查点、优化器/采样/全部RNG与原p99，原科学绑定必须相同。原生入口由现有P GPU SSH提供器监督，使用setsid/nohup/taskset及TERM-only timeout，最长8小时，预留900秒；不伪造Slurm ID。请求原协议的历史job_id字段保存明确的真实SSH句柄。

确认实际原生监督者、科学worker、ready记录及UUID锁后，才提交并登记同一配置的standby；保存其真实job ID后释放hold。接管复用原P的进程等待协议，只在完整更新处保存；原receipt75、匹配ack、reaped/无子进程以及原监督者、启动者和科学worker实际退出均需成立。然后使用原managed_entry及新Slurm job快照恢复同一输出/检查点。已经完成全部训练及读出的源不重跑。完整训练已结束但原生剩余窗口不足整个读出单元时，只延后原读出；不重训、不改R1/R3。下一阶段重新准入。

若原生源75退出而匹配standby仍PENDING/0秒，先核实并退役该精确自有旧句柄再登记下一次接续；不能把旧ID重绑给新源。原生与standby重叠时间属于同一GPU任务，成本不重复归为两份GPU计算。关闭全部写入后释放本线未用future；不删除现存文件、不改其他线预算。所有工程故障保留原输出/成本，从最近完整状态续接；不据此标科学UNRESOLVED。

原提供器或接管函数指纹变化会拒绝新执行，先检查兼容性；不热改已运行源码。这里仍待真实GPU准入后验证实际运行，完整回归和仓库检查仍只在开PR前做一次。
