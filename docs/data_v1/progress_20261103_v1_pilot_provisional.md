# 2026-11-03 数据线每日汇总 — v1-pilot-provisional

D-2、D-4及D-5已交付；D-3已按用户最新六条简化为一个导出作业，实际4525596在compute-0-13运行，16CPU、无SBATCH内存申请。窄索引已完成，16个源投影进程工作；尚未宣称D-3载荷或模型验收完成。

| 项目 | 实际状态 |
| --- | --- |
| D-1 | v3.0已双方冻结，既有精确绑定及Model ACK保持。 |
| D-2 | [正式注册表](../../configs/data_v1/v1-pilot-provisional/D2_registry.json)已发布，146字段、76项TRAIN尺寸相关性（69标量＋7物理范数）闭合。 |
| D-3 | 作业4525596，固定50,000 TRAIN＋5,000 ROUTINE VAL；复用D4 F64几何，仅建窄索引，内部payload/locator及F64旁车无损压缩，训练MFM3和一次F32转换保持。完整审计来源放F64权威副本，训练记录引用该副本。 |
| D-4 | [暂定归一化](../../configs/data_v1/v1-pilot-provisional/D4_normalization.json)已发布。首遍全部888系列统计含MAD完成；最终进程1443031 exit0、Source6为6/0/0。仅50k TRAIN拟合；未执行完整第二遍，independent_numeric_replay_equal=null。 |
| D-5 | [诊断载荷](../../configs/data_v1/v1-pilot-provisional/D5_diagnostic_payload.json)已发布。4525593实际COMPLETED/0:0，1607秒；试点已见893分子、12,502几何、43,757标签记录、53子库。一次随机1000条原Parquet逐字段比较通过。F64旁车3,671,924,736B，LMDB 1,688,424,448B；全局嵌套及20k诊断母清单已交付。 |

D-3末尾只做一次计数、1000条原Parquet逐字段比较、总清单SHA；同一父作业一次rsync --checksum分发至GPU节点，随后一次180秒/4CPU本地随机读取测试，无复制后额外哈希。Model loader及逐预测头过拟合测试作为交付后的实际验收。旧Source3生产前套件、10k、独立16-reader及F64全量二扫不再作本轮门。HPC skill1.0.135及live AGENTS已同步。

本日格式/资源修复汇总一行：修正SQLite并发读写与原生注释分类、合法只读dataset路径白名单，spawn继承ru_maxrss导致的假停止及并发SQLite journal inode复用误报硬链接；当前按实际进程VmHWM守卫后直接续跑。旧4525587重复索引准备已自然收尾，未终止其他用户或模型作业；所有历史FAILED及实际费用保留，不另写逐失败报告。完成D-5的32GiB未来输出预留已结清一次，不退还其真实磁盘占用；D-3保持160GB输出预算、账户扣除当前全部未来预算后100GB余量。

r73保留完整有序F64权威及一次F32转换；r674维持LOSS_DISABLED，无新增QM或质心换算。本轮不宣称最终Common、D-6/D-7或模型实际加载ACK。

后台沿既有核验下限：P′至少1,060,508/2,119,502构象结束，其中1,060,287全12项成功，尚未整理成全量训练库；其独立STOP2修复仍挂起。MoleculeNet/COCONUT保留9/11 READY，Alpha PubChem保留TIMEOUT部分数据、NO_RELEASE；这些不阻塞D系列。此处不是本日新增计数。原48小时期限已错过，不重新设置或冒称按时完成。