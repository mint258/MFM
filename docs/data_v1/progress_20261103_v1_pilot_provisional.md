# 2026-11-03 数据线每日汇总 — v1-pilot-provisional

D-2、D-4、D-5已交付；D-3尚未交付。141/171个实际闭合源组已保留，固定50k TRAIN＋5k ROUTINE VAL及原科学编码器不变。Lustre接续已实际提交，但4525664、4525665分别在启动模块引用、冻结源组索引引用检查处FAILED/1（0秒、5秒；均为compute-0-14/16CPU），未开始新的数据处理。按用户连续失败2次规则，该接续修复现记未解决并停止，无第三次重提；已询问是否批准仅补齐已定位的闭合索引引用后重提一次。此前compute-0-21因Slurm Kill task failed处于DRAIN，原未启动4525663已取消；旧4525651的141闭合源、原Parquet和正式几何全部保留，仅回收49,728,065,536B未完成可重建缓存。Main实际核验恢复64GiB后仍余155.56GB，后台Common已CONT，其后4525659实际FAILED/1，不自动重跑。任务配置保留16CPU、无时间/内存参数、无程序总时限/RSS/MemAvailable退出，100GB真实账户余量和一次末尾校验/复制/180秒读取测试保持。

| 项目 | 实际状态 |
| --- | --- |
| D-1 | v3.0已双方冻结，既有精确绑定及Model ACK保持。 |
| D-2 | [正式注册表](../../configs/data_v1/v1-pilot-provisional/D2_registry.json)已发布，146字段、76项TRAIN尺寸相关性（69标量＋7物理范数）闭合。 |
| D-3 | 固定50k TRAIN＋5k ROUTINE VAL；141/171源组闭合并保留。CPU接续4525664/4525665均在数据处理前FAILED；遵照STOP2暂停修复，待一次限定授权。尚无D3正式LMDB交付。 |
| D-4 | [暂定归一化](../../configs/data_v1/v1-pilot-provisional/D4_normalization.json)已发布。首遍全部888系列统计含MAD完成；最终进程1443031 exit0、Source6为6/0/0。仅50k TRAIN拟合；未执行完整第二遍，independent_numeric_replay_equal=null。 |
| D-5 | [诊断载荷](../../configs/data_v1/v1-pilot-provisional/D5_diagnostic_payload.json)已发布。4525593实际COMPLETED/0:0，1607秒；试点已见893分子、12,502几何、43,757标签记录、53子库。一次随机1000条原Parquet逐字段比较通过。F64旁车3,671,924,736B，LMDB 1,688,424,448B；全局嵌套及20k诊断母清单已交付。 |

D-3末尾只做一次计数、1000条原Parquet逐字段比较、总清单SHA；同一父作业一次rsync --checksum分发至GPU节点，随后一次180秒/4CPU本地随机读取测试，无复制后额外哈希。Model loader及逐预测头过拟合测试作为交付后的实际验收。旧Source3生产前套件、10k、独立16-reader及F64全量二扫不再作本轮门。HPC skill1.0.138及live AGENTS已同步本次D3节点与无时间/内存停止门授权。

本日格式/资源修复汇总一行：修正SQLite、原生注释、只读路径、spawn RSS与inode误报，保留90闭组及正式F64/LMDB；回收89,603,661,824B可重建缓存。取消旧160GB输出硬停，300GB仅为未来写入预测，100GB真实账户余量保留；D3启动连接改为已核实的Main公网地址并复用已认证SSH连接；区分Lustre数据与Main元数据预算，避免跨文件系统重复预留。首次启动失败后已修复重提，不另写失败报告。主SSH连接已恢复，X盘仍不可用，全部编辑经SSH落在原服务器目录；未改OneDrive副本。Slurm早期UID为空按观测未知处理，已修复并重启唯一完成接续器1941100；导出未重启、没有追加数据验证。未修改或终止其他任务。

r73保留完整有序F64权威及一次F32转换；r674维持LOSS_DISABLED，无新增QM或质心换算。本轮不宣称最终Common、D-6/D-7或模型实际加载ACK。

后台沿既有核验下限：P′至少1,060,508/2,119,502构象结束，其中1,060,287全12项成功，尚未整理成全量训练库；其独立STOP2修复仍挂起。去污染新注册表为10/11就绪（MoleculeNet已实际4524733 C0/35秒并获Root接纳，仅供V2保守消费者；21原图UNKNOWN保留；尚缺COCONUT），Alpha PubChem保留TIMEOUT部分数据、NO_RELEASE；这些不阻塞D系列。此处不是本日新增计数。原48小时期限已错过，不重新设置或冒称按时完成。
P′已发布结果的[候选文件索引](../../../artifacts/pprime_completed_catalog_20261103_v1/manifest.json)已生成：82个实际父作业、80份可读回执、8,301份发布清单、91,311个去重family文件引用（声明56,519,557,650B）；23项UNKNOWN保留。仅JSON/文件元数据收拢，未读Parquet正文、未重算科学成功率或SHA、无新增QM，不是全量训练库。

扩充数据口径（本日核对）：新增且正式可训练分子尚未交付。PubChem原500源片覆盖124,857,440条原始记录，110,046,364条通过初筛；这不是去重后新增分子数，指纹/新颖性/去污染/最终入库未闭合。去污染来源10/11就绪，MoleculeNet仅V2保守消费者可用，缺COCONUT。已有4,407分子批次返回4,400个第二几何补充（4项生成/输入失败、3项无第二几何），物理QA及ID注册仍待，不算新增分子。P′既有计算完成下限与候选文件索引属于已有分子补全，也不计作扩充新增分子。


连接：Main现有SSH可用；Alpha现已从Windows恢复密钥登录（UID1264），Main直连仍在KEX阶段被重置。15:27现场Alpha本人队列为空，CPU分区sonmi1余16核；compute-0-1已由其他作业占满，未修改它们。

后台状态复查：权威采用既有 `decontamination_sources_partial_ready10_molnet_conservative_V2_v1.json` 及其实际4524733 C0与Root接纳，不重复计算MoleculeNet；原9/11是沿用旧状态。4份MoleculeNet正式排除输入当前存在且大小吻合，仅核对元数据，未重扫科学数据、未改科学规则或在跑任务输入。Main PubChem原始500片恢复作业4525652实际RUNNING/32CPU，载荷输出在独立Lustre；不冒称已过滤/新颖/可训练。

15:28连接复查：Alpha 1884790、1885088、1885095、1885119已C0，1885120保持TIMEOUT部分数据且未放行；735诊断完整不等于COCONUT身份接纳，735项UNKNOWN保持。未重启已挂起的P′跨集群修复或PubChem旧物化工具，不与Main在跑4525652重复计算。D3实际4525651及完成接续器1941100均存活；共享盘其他Common写入作业运行时按已确认100GB账户余量等待，条件恢复后继续，无人工时间/RSS退出。

D3优先安排（15:44）：按用户D2–D5优先级，仅暂时STOP本账户后台Common4525659的19个实际用户进程，未终止任务或删除结果；已暂停实际核实后，其64GiB未来写入暂延、真实占用保留。独立元数据控制器1957034在D3实际终态后自动恢复原预算并CONT（暂停期间仍占32核Slurm分配，不冲销其已分配核时），控制目录 `control/D3_priority_common_pause_20261103_v1`；手工恢复可创建该目录下 `request_resume_common`。D3已恢复READY并继续写入，4525652后续已观察为CANCELLED，未把部分结果标成完成；不修改任何科学规则。暂停期间Common的sacct可暂显示RUNNING、squeue显示STOPPED，不能据此或T状态重复提交。

18时接续修复一行：大SQLite和LMDB改放实际剩余约1.94TB的Lustre，750GB为预测非硬上限；CPU21 DRAIN时改用此前授权的CPU路由；启动脚本旧模块已定位修正，但第二次被遗漏的闭合索引引用拦截，现记未解决STOP2；科学编码器四文件字节相同，无新增QM/UFF或额外数据复核。
