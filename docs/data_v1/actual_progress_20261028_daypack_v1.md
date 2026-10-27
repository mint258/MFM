# 2026-10-28 单日打包实际进度

目的：按用户要求把生产工作合并为约一天的作业，复用已完成结果。

观测时间：2026-10-28T05:23:58.488123+08:00。本报告由 workflows/data_v1_final/execution/daypack_progress_v1.py 从真实 Slurm 和小元数据生成。

- S′ 单一作业 4524556，现场状态 4524556|RUNNING|64|1:42:26|1-00:00:00|compute-0-13。64CPU、24小时上限、无SBATCH内存申请。9项作业内预检已通过。
- 候选剩余32749分子；已派发20048、已启动20048、已存结果包19984、执行器错误文件0。这些是文件元数据计数，不代表最终科学成功率。
- 原结果清点：{"CONSUMED_UNKNOWN_NO_RETRY": 2, "ELIGIBLE_UNCLAIMED_AFTER_ORDINARY_SOURCE_CENSUS": 32749, "EXCLUDED_ORIGINAL_UFF_UNSUPPORTED": 9282, "OLD_DURABLE_RESULT": 57318}。500分子仅作内部检查点，不产生子Slurm作业。
- Drugs全75099名称/558002构象的保守身份并集已通过严格消费读回，实际4524566 C0/82秒/16CPU/1312分配核秒，原126构象差异与31名称差异全部保留。Kraken此前已READY；全11来源仍须汇总验收。
- 标签全量数值缓存旧batch2实际4524528 C0/1430秒/16CPU/22880分配核秒；16源各自游标139392，累计2230272源物理行。后续按单日父作业继续，不再逐短批提交。
- P′已有1200次限定诊断及独立读回；500项原向量比较通过断言。单位、符号、张量与坐标原点仍须完成完整证据审阅，2000构象试点及全量尚未放行。

输入证据及哈希：本次观测 /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/daypack_progress_20261028T052358488123_0800.json，792B，SHA256 7283ede995b65aee0d7da1497c0bf2f960935214b3d6e3b5c87be00c165f53fd。其余实际来源见 control/active_checkpoint_v41.json、Drugs READY candidate 和标签batch2真实会计与独立Root接受对象。

已知限制：整轮D1–D7、共同人群最终阈值、P′正式生成及扩充第一批尚未全部完成。原始结果、失败与UNKNOWN、配方及全部质量阈值保持。技能1.0.123已同步本机和X盘。
