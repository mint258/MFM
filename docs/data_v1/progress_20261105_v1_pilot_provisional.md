# 2026-11-05 数据线当日汇总：v1-pilot-provisional

本文件持续更新，不另写逐次失败报告。D-3尚未交付，Model_payload_ACK仍false。

## 00:01 实际状态

Main原生Slurm确认4525834仍RUNNING，compute-0-8、16CPU，15个writer按8个原1000MID分片组成的窗口继续处理。最近完整检查点为31,000/55,000分子（56.36%）、1,643子库；下一窗口正在写出，00:01观察累计1,793子库关闭。完整分子计数只在整个窗口worker实际退出且各库及F64关闭后更新。

存储状态READY，当前扣除全部future后账户余量135,418,619,233B，继续保持100,000,000,000B余量要求。无SBATCH时间/内存请求，不设程序总墙钟、RSS或MemAvailable停止门。昨天的只读输入预读已完成，未生成源数据副本或增加QA。

## 已交付与待交付

D-1 v3.0沿用[联合冻结接口](../interfaces/D1_v3_0_joint_interface_freeze_20261029_v1.md)。[D-2注册表](../../configs/data_v1/v1-pilot-provisional/D2_registry.json)、[D-4暂定归一化](../../configs/data_v1/v1-pilot-provisional/D4_normalization.json)、[D-5诊断载荷](../../configs/data_v1/v1-pilot-provisional/D5_diagnostic_payload.json)沿用已交付组件；D-4仅拟合50k TRAIN，VAL不参与。D-3仍在打包，不以部分文件或RUNNING状态冒充完成。

D-3完成后沿用原脚本一次计数与随机1000条原Parquet逐字段校验、一次总清单SHA、一次rsync --checksum及180秒随机读取；不增加独立复核、F64二次全量读回或额外吞吐测试。原终态发布watcher、D5实际已见绑定进程及预算别名维护进程均已核实在线；实际C0及正式交付成立后才绑定D5的小元数据。

本批包含PM7 S/D/P和已有UFF S′几何，不包含UFF D′/P′标签。r73完整有序F64作为共享Lustre权威，训练只转一次F32；r674继续LOSS_DISABLED，不追加QM。GPU节点仅缓存训练LMDB与清单，F64沿用原共享路径。

下一完整检查点为39k，届时使用正常生产检查点mtime差更新耗时估计。末尾QA与复制尚无本轮实测耗时。MoleculeNet、PubChem、P′由各自后台任务继续，本批D-3不等待共同人群、D-6或D-7。

D3实际检查点39k：4525834仍RUNNING/16CPU/compute-0-8，39,000/55,000完整分子（70.91%）及2,067子库已关闭，全部window worker实际退出。31k→39k原检查点mtime差3601秒；剩余16k按最近窗口仅打包约2.001小时，最近两轮范围2.001–2.744小时，末尾QA与复制另计。下一观察目标47k，原自动发布及D5绑定继续等待实际C0，不追加QA。

D3资源观察修正：一次只读元数据盘点发现69,442,551,808B自有小文件被原64MiB过滤排除，未直接把瞬时数值作为credit。隔离v6只在原FD固定inode lifetime/generation及quota前后min交集下纳入全部regular文件；保留真实quota、1.03TB预测、100GB floor及全部科学规则，四科学文件逐字节相同。原check_repository在实际4525834分配内PASS（4952文件/3513Python/1311服务端源码/0错误），源码已提交058c329。已实核启动Main接续进程2465040及Node边界观察的srun进程2465041；仅在完整47k且全部窗口worker已退出后，对原UID1278/PID1175845/start_ticks2091388489/boot/PGID/SID/argv/cgroup全部匹配的自身父进程发送一次协作SIGINT，不对child发信号；待真实旧终态、watcher退出和原scope退休后才提交一次v6，复用所有已闭合DATA。当前v5继续RUNNING，无DATA重算，实际信号尚未发生。

D3接续：47k/55k（85.45%）及2491库已完整闭合，4525834按预定协作SIGINT自然结束（实际FAILED/3，非质量失败）。首个接续4525878仅启动前因Main硬FD8192不够全文件census而未建DATA plan；已协作中断等待中的Main metadata helper，Native该job FAILED/1、无DATA。v6b将Main准入仅用保守的大文件已用下界（64MiB门，仍不改实际quota/floor），Node DATA继续v6全文件FD因果交集精确计量；已实际提交4525880并RUNNING/16CPU，现源码检查的Git只读转发遇Main预连接拒绝，沿用用户10分钟重试间隔；47k原数据和全部科学规则不变，未新增QM/UFF/QA。

4525880已通过本分配原源码检查（4952文件/0错误），Main SSH重试已恢复，真实startup proof及DATA plan已生成；数据模块仍为原v6，Main准入保守下界与Node全文件计量均生效。实际storage READY，计入855,012,917,248B已占自有输出后，扣全部future余206,662,915,826B；未改真实quota、floor或未知writer预算。47k全部复用，最后8k进入DATA；终态发布watcher及指向4525880的D5绑定进程均在线。

4525880末批读取等待优化：在原16CPU allocation内以1CPU overlap步骤4525880.0只读预取实际阻塞且位于已关闭171来源清单中的4个文件，共48,154,337,280B；native步骤COMPLETED/0:0、336秒，4个原文件inode/size/mtime/ctime均保持，缓存加载完成。不增加数据副本、哈希、QA或新科学计算；原15个writer持续运行，未重启DATA。

D3打包完成：2026-11-05 02:27:29+08:00，原生产shard_checkpoints最终index54，55,000/55,000分子、2,915子库全部关闭，全部window writer实际退出；4525880仍RUNNING，进入原脚本唯一的末尾计数与1000条原Parquet校验。当前正式export_manifest及receipt尚未生成，未提前宣告验收或分发成功。原自动checksum复制、180秒读取、实际C0发布及D5小元数据绑定继续衔接。第二次仅预取当前阻塞闭合来源2个文件16,177,651,712B，原步骤4525880.1实际C0/70秒，文件frame不变；闭合输出缓存只读观察4525880.2 C0/2秒，约8.9GB resident，未执行缓存丢弃提示。没有新增QA、哈希或数据副本。

交付收尾准备：当前源码原check_repository在同一4525880 allocation的步骤4525880.3实际COMPLETED/0:0、10秒，PASS4953文件/3514 Python/1311服务端源码/0错误，包含新增的正式报告生成脚本。该脚本仅在实际D3 C0及D5同父绑定后消费正式JSON生成1.8方法报告，尚未执行。仅核对已有正式证据：D1签署Model ACK SHA匹配；D4真实local exit0及原Source6六项PASS的正式引用匹配；D5原4525593仍由native sacct证实C0。Main P′4525748/4525882运行；Alpha密钥连接UID1264成功，1885263/1885264运行、后续rank/UFF/D/报告作业已排队，均未修改或重复提交。D3数据验收继续，尚未冒充正式交付。

D3末尾验收通过：原唯一export_manifest已关闭，TRAIN50000/VAL5000、2915库计数一致；1000条源记录涉及987个原Parquet分组/2698个target pieces，全部比较完成。导出共32022963条几何/家族记录；训练LMDB 575151706112B，共享永久F64 398342180864B，原清单总payload 973495752551B。实际16个QA子进程已退出，当前原作业进入分发准备，尚无正式receipt或D3发布；不将QAPASS冒充copy/C0或模型ACK。

分发进展：原唯一rsync进程1269930已实际运行，compute-0-21目标目录持续写入（最初164GB为PTY换行误读，已更正为单行字节观察：103,872,868,352B，约104GB/18%；仅文件系统元数据观察，非额外内容复核）。目标节点旧SSH known_hosts警告已通过原生Slurm只读身份任务4525883 C0/UID1278/16CPU/compute-0-21读取公钥，与网络公钥逐字节一致后，仅替换此目标的3条旧key并留原文件备份；StrictHostKeyChecking=yes的密钥连接及UID1278复验通过。未改其他主机条目、源数据、计算或复制参数，原copy持续。

正式交付完成：4525880真实C0/9785秒；单次1000源QA通过，单次checksumcopy返回0、575,161,700,855B到compute-0-21:/tmp/dv1_pilot55k_20261103_9b66baf693，单次4-reader 180.033秒/11.981分子每秒/6994.720记录每秒。D3正式索引已发布，D5原组件保留并生成同5880绑定索引；actual_seen_TRAIN50000、diagnostic893/12502几何/43757标签/53库。方法报告已仅从正式元数据生成；Model payload ACK仍false。D2-D5均为v1-pilot-provisional，后续Common/D6等继续，不以试点代替正式版本。ordinary v4候选移除过期物理删缓存工具前置，改真实D3 C0+原quota/V2全部future100GB；保留缓存全计quota.used、无free credit，待真实准入部署，科学函数和输入不变。

正式交付提交前原check_repository已对包含D3/D5正式索引和报告的当前树PASS4956文件/3514 Python/1311服务端源码/0错误；原生只读代码检查任务4525884完成，未执行新数据QA。GitHub data-v1存在其他线更新，后续采用隔离worktree整合，保留其修改及当前非本任务dirty文件，不强推、不覆盖现有扩充PR。
