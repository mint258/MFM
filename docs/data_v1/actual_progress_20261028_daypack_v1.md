# 2026-10-28 单日打包实际进度

目的：按用户要求把生产工作合并为约一天的作业，复用已完成结果。

观测时间：2026-10-28T06:59:10.565718+08:00。本报告由 workflows/data_v1_final/execution/daypack_progress_v1.py 从真实 Slurm 和小元数据生成。

- S′ 单一作业 4524556，现场状态 4524556|RUNNING|64|3:17:38|1-00:00:00|compute-0-13。64CPU、24小时上限、无SBATCH内存申请。9项作业内预检已通过。
- 候选剩余32749分子；已派发23479、已启动23479、已存结果包23415、执行器错误文件0。这些是文件元数据计数，不代表最终科学成功率。
- 原结果清点：{"CONSUMED_UNKNOWN_NO_RETRY": 2, "ELIGIBLE_UNCLAIMED_AFTER_ORDINARY_SOURCE_CENSUS": 32749, "EXCLUDED_ORIGINAL_UFF_UNSUPPORTED": 9282, "OLD_DURABLE_RESULT": 57318}。500分子仅作内部检查点，不产生子Slurm作业。
- Drugs全75099名称/558002构象的保守身份并集已通过严格消费读回，实际4524566 C0/82秒/16CPU/1312分配核秒，原126构象差异与31名称差异全部保留。Kraken此前已READY；全11来源仍须汇总验收。
- 标签全量数值缓存正在单一作业4524575中运行：4524575|RUNNING|64|58:52|1-00:00:00|compute-0-14。64CPU、24小时、无内存申请，原3项加新6项预检及整仓检查均通过。处理全2208来源的缓存与覆盖；最终Common TRAIN及D5诊断未闭合前，不冒称最终D4。
- P′只读核验4524581实际C0/121秒/16CPU/1936核秒：500项已定义向量比较、100项张量旋转比较和100项力/梯度关系检查通过原阈值。首次定位清单错误4524577的544核秒与输出保留。没有新增QM/UFF/初始化/once写入；单位、符号、原点和实际参考系仍待综合审阅，2000构象试点及全量尚未放行。

输入证据及哈希：本次观测 /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/daypack_progress_20261028T065910565718_0800.json，1160B，SHA256 0dae5eff725636e7e202fea262c528752ce971f21882c8fd4537bbe45cd89252。其余实际来源见 control/active_checkpoint_v43.json、P′实际核验报告、Drugs READY candidate 和真实会计对象。

已知限制：整轮D1–D7、共同人群最终阈值、P′正式生成及扩充第一批尚未全部完成。原始结果、失败与UNKNOWN、配方及全部质量阈值保持。技能1.0.123已同步本机和X盘。
