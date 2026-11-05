当前闭合摘要：D‑1 v3.0冻结，D‑2至D‑5试点已交付；D3实际4525880 C0，55k全量与唯一末尾验收/复制/读测完成。P′冻结ready范围2,221,502构象计算/覆盖闭合，原审计4525885 C0，全12项成功99.80081%；不等于最终Common或D6已放行。普通构象排序/统计正在准备实际资源接续。下文为当日各时间点日志。

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

P′后台闭合更新：原生4525748 C0/47864秒，最终只读审计4525885 C0/962秒/16CPU/compute-0-18；最终交付入口为 artifacts/pprime_complete_remaining_20261104_v1/final_delivery。原冻结ready范围共1,110,751分子/2,221,502构象，26,658,024任务行，缺失0、意外0；全12项成功2,217,077构象（99.80081%），4,425非全成功原样保留，另有103,467 N1不可用排除。此为P′计算与覆盖闭合，不等于最终Common、TRAIN归一化/异常值扫描、P与P′分布对照或D-6已放行；不得重算已闭合Native。Alpha实际UID1264密钥连接成功，NN 1885263/1885264及rescue1885267运行，后续rank/UFF/D/报告仍在队列，未修改其他线任务。

交付代码整合：隔离worktree保留其他线远端更新与本地dirty；原check_repository实际4525886 C0/11秒，PASS4807文件/3407 Python/1311服务端源码/0错误。合并提交及正式试点代码/报告已推送GitHub delivery/d3-v1-pilot-20261105分支，不强推data-v1、不覆盖扩充PR。
挂载资源修复：原X SSHFS响应挂起，Main密钥SSH仍UID1278正常；重连原UNC到Z后以本机subst恢复X→Z，同一live服务器项目，未编辑OneDrive、未改源数据。ordinary v4五件已完整安装；发现generic旧200GB门与当前用户100GB政策冲突，采用隔离资源适配保留原冻结包，科学函数不改。P′正式pprime_labels.md已由小metadata摘要脚本更新，原试点记录保留为历史，无新增数据QA或QM。

普通构象后处理已实际启动：4525888/compute-0-18/16CPU，fresh startup proof与canonical_current_node_frame已生成，已进入原数据对齐和数据库准备，未查询活动DB。新独立cpu_account100_queue_v1全包与原v2逐文件相等（仅namespace及200→100资源字面替换），旧包不动；ordinary运行原科学函数。原check_repository实际4525887 C0/10秒，PASS4974文件/3530 Python/1311服务器源码/0错误，无新增数据QA。当前预算64GiB+独立provider/admin各64MiB已全计V2，fresh after-allfuture约102.124GB，100GB门保持。

最终Common/P′范围待办：闭合Common为1,196,122成员，冻结P′ready1,110,751；其85,371差可由80,740个fill成功与4,631个旧N1eligible的已有聚合解释，尚未做MID交集，不能宣称精确逐分子覆盖。N1最新进口4,407回包/4,400第二真实几何；完整registered-extra历史登记尚缺，后续使用原物理QA/ID入口，不能用ordinary身份表或UNKNOWN伪造空集合。此缺口不阻塞已启动的ordinary排序。模型线实际payload ACK仍未观察到，D6依原顺序等待真实loader/逐head验收及最终Common/全TRAIN政策。

当日资源修复一行：4525888实际FAILED/1/392秒，在原UFF源投影阶段因共享mutable工作DB使真余量跌破100GB停止，尚无分子claim/checkpoint或新QM/UFF；原始数据和失败历史保留，仅删除已终态纯派生3,185,324,032B工作DB，fresh quota确实恢复；v6将DB/spill改为node18新/dev/shm工作目录（实测free201.85GB、MemAvailable389.94GB），全部正式输出仍共享，原64GiB预测与100GB真门不变，不把本地占用记为Main free credit。原Git整合源码检查4525889实际C0/609秒（一次SSH正常10分钟重试），PASS4830文件/3427 Python/1311服务器源码/0错误；计算未被该Git等待阻塞。

v6接续实际4525890已RUNNING/16CPU/compute-0-18，原startup proof、local_workspace_observation与canonical frame均已生成，原closed-source接入census已完成。工作DB已实核位于/dev/shm且UID1278（观察约987MB），共享输出目录无workingDB；原科学函数、输入、64GiB forecast和100GB account门不变。仍处原UFF输入投影/准备阶段，尚无可报告的完整分子百分比。原源码检查4525891已排队，成品LMDB和P′闭合结果不重算。

收尾核实：v6原源码检查4525891实际C0/10秒，PASS4974文件/3530 Python/1311服务器源码/0错误；本地修复源码ae68ac8与整合后的96912028已推送delivery/d3-v1-pilot-20261105，不触其他线dirty或扩充PR。4525890仍原生RUNNING/16CPU/compute-0-18，已越过原392秒停止点，共享配额保持稳定；尚无完整descriptor checkpoint，不编造分子进度百分比。Alpha 1885263/1885264/1885267继续实际R，共112CPU，后续rank/UFF/D/报告已排队。

N1登记输入进展：只读canonical发布清点4525892实际C0/62秒/16CPU8，读取6531份canonical元数据，相关extra发布父与索引均0；5个无关argv-list的schema分类已按闭合原字节单次修正，不重扫DATA。canonical子域闭合不等于portable非canonical全历史为空（AccountingStoreFlags=null），保留UNKNOWN。D1静态合同审阅确认要求是带release/registry版本的导出域内稳定唯一ID，不要求所有历史私有sidecar跨版本永久不变；正在独立候选接口中按当前v1注册域处理未冻结extras，保留ordinary、历史attempted及既登记ID，沿用原ID算法与全部source/once历史，不修改4525890 pinned源、科学标签或筛选，也不新增UFF/QM。最终Common与D6仍未放行，Model实际payload ACK尚未观察到。

N1当前版本物理登记完成：4525894原生COMPLETED/0:0、237秒、16CPU/compute-0-18，Alpha回包中4400个真实第二几何全部通过原物理QA；4个生成/输入失败和3个无第二真实几何原状态保留。当前release registry已追加accepted index，保留旧snapshot、ordinary/attempted/已登记ID及全部producer/native别名，历史noncanonical覆盖仍UNKNOWN。正式组件入口为 configs/data_v1/N1_current_canonical_physical_20261105_v1.json；未新增QM/UFF，未放行最终Common/D6。普通排序4525890仍实际R，两个生产descriptor关闭合计10000分子，第二个5000批次用时1216秒；正并行准备批量元数据查找的等价加速候选及全量导出接线，不修改活动pinned源或追加QA。
N1早期224已正式接回：新父4525895原生COMPLETED/0:0、149秒、16CPU18；四旧Main父4521418/4521476/4521479/4521481的全部224源包都有真实第二几何，224/224通过原物理QA。实际C0后追加当前registry，保留5894的4400，合计4624；Alpha原7个失败/无第二几何状态不重试。正式组件入口 configs/data_v1/N1_current_canonical_physical_components_20261105_v2.json 绑定不可变registry snapshot，mutable current仅作控制指针；此4631源任务范围不冒称全部Common N1。原Source/once/ID、ordinary N/D5不变，无新增QM/UFF。合法旧同path registry引用的去重误拦已修复后继续，仅在此记一行。

后续实际状态：普通排序4525890仍R/16CPU18，已关闭4个原descriptor、20000/1220466全源分子（1.64%，不是试点LMDB进度）。已安装批量lookup+旧闭结果/orphan复用的新namespace并通过原源码检查；因原指南禁止强行终止运行任务，结束旧作业的单次切换授权尚待用户，未对旧作业发信号。D6物理源索引builder与whole-MID lookup已完成源码，读取全WP5/Pprime身份定位列而非数值载荷；正在接实际Main/Lustre配额guard后提交。Lustre实查为2TiB用户硬配额，使用1797841420KiB、剩约333GiB，不能把卷空闲38T当账户可用；full容量尚未准入。fill成功分子的Pprime固定随机首两几何可独立准备，不等待能量/多样性D7，输入接缝正并行实现。独立交付草稿PR已建立 https://github.com/mint258/MFM/pull/2 ，N1首4400组件合并b64fb14已推送；PR1扩充未改。

后续推进（08:06）：D6物理源索引4525896、4525897连续两次启动检查失败，均未进入数据处理，按用户STOP2规则记“未解决”并停止此问题，不提交第三次。P′补齐范围整理作为独立阶段已启动4525898，原生RUNNING/16CPU18；Main控制64MiB、Lustre输出8GiB分别计入真实账户未来预算。仅冻结原fill成功分子中未进原ready的MID及固定随机首两几何，不作新QM/UFF，不充当最终Common/D6或P′生成。原排序4525890仍R，6个关闭检查点合计30,000/1,220,466分子；批量lookup切换仍待用户回答，未停止旧作业。试点LMDB保持已交付，不重复打包/校验/复制。

P′补齐范围已闭合：4525898原生COMPLETED/0:0、852秒、16CPU18，80728个实际分子/161456个固定随机首两构象、两个组件；这是实际原ready反连接及common/N规则所得，不以80740聚合计数代替。accepted_closed_scope.json绑定真实父会计及scope清单；未执行NoInvoke/input hashes或新QM/UFF。下一输入准备已按真实两域配额准入Main64MiB/Lustre16GiB，复用新provider2537593；scope已终态未用future归零，真实占用仍由quota扣除。原排序4525890仍R，7个关闭检查点35000/1220466分子。全量覆盖候选在提交前发现旧V.execute会重复解码全部471GB及157m行比特，未执行该重复回放；改用已关闭producer窗口证据汇总质量/守恒与所需base首读，明确不冒称独立数值重放。所需原1.5全人群异常扫描、最终TRAIN拟合、D6最终source抽样仍保留。
后续实际接续：coverage首次4525899 FAILED/58秒为field_map相同bytes/SHA的路径别名误拦，独立r2只兼容该等价别名，4525901已R/16CPU18并构建本地catalog；原471GB标签比特未重复扫描。P′输入准备4525900 FAILED/64秒（裸common模块污染），独立r2隔离原导入后4525902 FAILED/61秒（旧Main/Alpha locator拒绝合法Lustre tasks），两次原Source3各3项通过仍不代表全准备成功；按用户STOP2记“未解决”并停止该输入问题，不作第三次提交，不新增QM。scope4525898的80728分子/161456构象及原ready全量P′产物保持。已终态输入future在Main/Lustre归零，真实占用仍quota扣除，未删除原件。Alpha直连已核UID1264、1885263/1885266/1885267实际R合计112CPU；已有Alpha证据只覆盖UFF及旧QM结果只读诊断，尚无可即用的原12任务生产入口，不冒称QM兼容。交付代码5bb4225已推送PR2分支，后续新coverage/input源码待本批整合。
全量覆盖目录已闭合：4525901原生COMPLETED/0:0、1844秒、16CPU18；原source域1220466分子/11231854 base记录、157245956 task记录、146字段，producer-basis目录与19079344128B持久catalog已生成。只读取原base构建所需Z/owner索引，复用原已关闭window的label bit验证，没有再次打开label typed值、没有471GB重投影/复制或新QM/UFF；不是最终mask/全TRAIN拟合/D6。结束后的Main64MiB和Lustre32GiB未用future退休，真实19GB占用仍quota计入。全量归一化单遍/新coverage显式适配源码已备，仍待真实最终Common/D5；正在核1.2的独立Common闭合，避免不必要地等1.3全部D7排序。已仅读2915份closed store小JSON按15家族汇总体积，存储review不把文件字节当可回收率，不更改冻结格式或删除权威数据。原required check一次误用刚结束的5901 allocation，Slurm返回expired，未执行数据复核；改回仍活的5890 allocation运行原仓库检查。
用户已明确批准旧排序切换：4525890经核UID/脚本后实际CANCELLED by1278、14634秒、16CPU18；11个闭catalog/55,000分子及有效orphan全部保留。新批量lookup首次4525914 FAILED/31秒为旧source_mapping仍指前provider，已在新v8仅重绑真实provider/probe元数据；4525919现原生R/16CPU18，canonical_current_node_frame已生成，进入原数据准备/闭结果恢复，尚不冒称55k已全部重放完成或D7闭合。原数学与科学规则、100GB Main账户floor不变；新job复用同工作原已花forecast827113472B且不把旧输入记新产物信用，新provider2546137。旧纯临时缓存保留（进程FD权限检查未解决，不继续该清理）；本地tmpfs启动余量改4GiB，与Main账户100GB严格分开，原local64GiB软件cap保持，无shared/source删除。P′输入STOP2保持，不因这次排序授权重开P′。
## D-3 体积诊断（2026-11-05，只诊断）

**结论：主因是重复 JSON/数组描述头、逐记录分页放大及 F64 原生单元的 JSON-hex 审计副本；不是稀疏空洞或 map 预分配。** 全部大小用十进制 GB/TB；带“约”的结构字节是抽样加权估计。

**1．占用。** 训练与 F64 混放，按正式清单分别求和。指定的 `du -sb` 与 `du -sb --apparent-size` 差均为 **0 B**（`-b` 本身表示表观大小）；实际分配补用 `du -s -B1`。原 rsync **未用 `--sparse`**，但无明显空洞可省。

| 范围 | 两条指定 du 各自结果 B | 实际分配 B | 实际−表观 B |
|---|---:|---:|---:|
| 共享训练 | 575167068007 | 575184314368 | 17246361 |
| 共享 F64 | 398342180864 | 398346493952 | 4313088 |
| GPU21 训练副本 | 575161994136 | 575171993600 | 9999464 |

**2．全库页统计。** 已对 **2915/2915** 库执行 `mdb_stat -e -a -f`。全部 map=8 GiB、页=4096 B；已用高水位 13171–302834 页/库，总 140417897 页，Σ(last pgno+1)×4096=**575151706112 B**。map 合计25.040 TB只是虚拟上限。前五类如下，平均值按逻辑记录计：

| 家族/层级 | LMDB GB | F64 GB | 记录数 | LMDB B/记录 |
|---|---:|---:|---:|---:|
| size（分子） | 89.585 | 21.665 | 5083010 | 17624 |
| bonding（原子/对混合） | 72.811 | 39.956 | 1016602 | 71622 |
| energy（分子/原子/对混合） | 68.384 | 192.809 | 2541505 | 26907 |
| geometry（几何） | 60.417 | 31.424 | 7116214 | 8490 |
| charge（原子） | 53.390 | 39.683 | 3049806 | 17506 |

层级合计 GB：纯分子292.282、纯原子106.889、纯原子对8.544、几何60.417；混合库107.018（分子+原子8.544、原子+对64.267、三者34.207），混合库单列避免重复归账。

**3．表示问题逐项。** 结构抽取覆盖全部库，每个数据/掩码表首末各4条，共44880个封套；仅解析头和字节长度，不解码数值、重算 SHA 或比较内容。

| 检查 | 是/否及字节证据 |
|---|---|
| 原子对是 N×N 稠密矩阵？ | **否**。普通显式 pair 索引约15.174 GB；r73有序传输数组约47.191 GB，含轨道/方向/同原子项及重复，**也不能裁成仅成键对**。 |
| 坐标跨标签家族重复？ | **否**。标签库坐标0 B；独立几何库坐标约4.613 GB（不同实际输入视图保留）。 |
| 键/元数据/JSON 占明显比例？ | **是，主要是头**：约316.400 GB（55.0%，内含元数据249.317 GB）；数据/掩码键约4.637 GB。标签 data/mask 各存一份元数据。 |
| 值未压缩？ | 训练 **是**：数组体约94.600 GB；F64 **否**，已zlib1。能量F64共192.809 GB；一个结构样本元数据1.66 MB→288 KB，数组仅约19 KB。 |
| F64 有 WP5 永久 parquet 没有的内容？ | **是**：原生LMDB单元、图/几何和导出政策/追溯信息。因此398.342 GB **不能整批认作 WP5 重复数据删除**；其中 JSON-hex 是可外提的派生表示。 |

**4．只压实三个新副本。** 下表是原Lustre→compute-0-20本地XFS的实际分配；均 `mdb_copy -c` 返回0，无内容读回。

| 子库 | 压实前 B | 压实后 B |
|---|---:|---:|
| 最大 bonding | 1240412160 | 1239838720 |
| 典型分子 frontier/IP-EA | 167698432 | 167108608 |
| 典型原子 charge | 167829504 | 167243776 |

副本保留于 `compute-0-20:/tmp/D3_size_diagnostic_20261105_v1/`。全库可压实量应按 freelist+其树页计，为**1.705 GB（0.30%）**，不是主树页小计之差2.570 GB；收紧 map 不额外节省实占。

**5．外推与建议。** 计容沿已有 Common 组件：1196122分子，PM7/UFF各11044968构象；试点55000分子、各508301构象。分子倍率21.748、构象倍率21.729；下表沿 D-3 同覆盖，**不含尚未导出的 P′/D′增量，不是最终D6容量准入**。

| 情形 | 试点训练 GB | 全量训练 TB | 全量 F64 TB（暂保留） |
|---|---:|---:|---:|
| 现状 | 575.152 | 12.498 | 8.656 |
| mdb_copy -c + 收紧 map | 573.447 | 12.461 | 8.656 |
| 再修正表示并块级无损压缩 | 70–120 | **1.52–2.61** | 8.656 |

推荐后续新版本：共享字典外提长名/政策/来源，合并 data/mask 元数据，块级无损压缩；数值、掩码、原因及r73有序F64语义保持。末行是规划估计：同三个库各32条/表的内存zlib1数组比例为0.160/0.881/0.488，另计短头、索引及20–30%余量，**非整库新格式实测**。预计训练格式较现状省 **9.89–10.98 TB（79–88%）**。F64后续可将原生JSON-hex改为永久原始源引用，但须保留WP5之外的原生/几何来源与r73权威，本次不虚报其回收量；保留全部F64时总量仍大，不能据此直接开始D6。

本次未覆盖/删除既有D-3或GPU数据，未重导出D-3、未启动D6、未重算SHA/追加内容校验/读回比对/吞吐测试，实际释放 **0 B**。完整[逐库CSV与原始命令输出](../../../control/D3_size_diagnostic_20261105_v1/all_2915_stores.csv)及同目录计容模型为证据。


用户新增测试样本：已从正式D3按原字节复制10个TRAIN分子的全部记录至 `runs/data_v1_20261025/samples/D3_10molecules_20261105_v1/`，53分库、1400几何/视图、4900标签，附对应F64及README/相对路径清单；文件合计184423845B，ZIP 72866687B（不含运行时lock.mdb，解压后可由本机LMDB创建）。新库只更新内部计数，原schema/来源字段保留；未重算SHA、未做内容读回比对或吞吐，原D3/GPU不动。该样本是可修改测试件，不是正式发布。

10:20 接续汇总：批量排序4525919原生FAILED/1、720秒，完成55,318个旧闭结果恢复（含318份有效orphan），未重算其PM7/RMSD；原principal_00209558包的正引用检查仍为UNKNOWN HOLD，按连续失败两次规则记“未解决”，未提交第三次。共享数据全部保留；仅将已终态的普通排序未用future归零，实际占用仍由quota扣除，Common仍使用的provider保留。

指南1.2 Common已与D7排序解耦并实际提交：首次4525920因真实会计的parent/parents格式差异FAILED/1、32秒；新独立r2仅兼容两种真实会计schema，不改原membership、min-N、2%/元素20%与Se例外，不新增QM/UFF。接续4525921已原生RUNNING/16CPU/compute-0-18；当前仍等待该节点启动与fresh proof，尚无新Common C0或冻结声明。Main控制64MiB、Lustre输出8GiB分别绑定真实future与原有限provider，未借Lustre空余冒Main额度。原仓库检查在4525919中PASS（3593 Python/1311服务端源码/0错误）；包含r2的后续同一原检查已在4525921 allocation发起，当前尚未完成，不增加数据QA。两个原交付子agent继续并行完成全TRAIN归一化Lustre IO与独立D5元数据接线；正式Common/D5引用待真实终态绑定，P′ input STOP2维持。试点交付与原ready P′结果不重跑。
用户最新暂停：D-3出现问题，D-6及之后暂不推进。已停止相关候选开发及后续提交；D5候选冻结、全量归一化IO适配未实施，未提交D6/全量归一化任务。原Common作业未因本条指令终止。后续优先D3，具体报错/日志路径待用户提供；仅在用户明确恢复后续阶段后再推进D6。

D3问题只读定位：已核对正式D3索引、数据端接口STATUS及已有模型线接口/执行记录，索引仍Model_payload_ACK=false；所查记录尚无本次具体报错，不能据旧C0或旧测试推断本次问题原因。接口STATUS已置顶说明用户报告的问题与D6暂停。等待此前已询问的具体报错/日志路径，未重跑导出、未新增数据验收或D6提交。

D3 v3.1用户修订已落实到独立代码与同一大作业：保留旧55k、旧v30及全部副本，仅重排存储，r73四数值数组已获用户批准。实际代码8865115，已推PR2；正式作业4525960/compute21/16CPU正在运行，不设SBATCH时间/内存参数、不新增QM/UFF。初始214秒已完成2725/55000MID及27183条P、27183条U；本次来源为原D3加对应893个已见D5诊断载荷，heldout照存标记。Main控制8MiB、Lustre估计64GiB分别真实计入未来预算，100GB账户余量保持，估计不是输出停止门。只安排末尾一次原子/拓扑对齐、1000P逐字段NaN/值比较和计数，随后每split一次mdb_copy -c、rsync --sparse到当前GPU节点；不做新hash、额外读回或吞吐。D1仅第6项存储修订，Model确认待，不阻塞导出；D6仍暂停。实际最终du、三类平均字节、线性全量外推和耗时将在完成后追加本汇总，不把运行状态当交付。
D3 v3.1传输修复：4525960已完成两库compact及唯一1000P/计数检查，之后rsync的ssh -n与--protect-args冲突；仅结束其传输重试循环，4525969复用闭合库四路rsync --sparse续传，不重导出、不重做compact或数值校验，旧v30未动。

D3 v3.1正式交付：传输原生4525969在全部10节点rsync成功后因compute本机sacct连接失败而FAILED/1:0；仅管理元数据已在Main补齐，未重跑科学检查或复制，16CPU/compute-0-21、633秒；同一TRAIN50000/VAL5000，共P=509194、U=509194。两份默认DB已各一次mdb_copy -c，唯一1000P原v30逐字段/NaN检查与计数通过，拓扑差异0；10个GPU节点rsync --sparse完成。实际共享du=34935087616B（34.935GB），逻辑34936865924B；M/P/U平均键加值字节=576.09/58964.77/677.62B；导出2208.9秒，总流程3415.0秒。按1220466源分子线性外推du约775.22GB（仅体积描述，不是D6容量准入；旧Common候选1196122约759.76GB）。全部字段/方向/通道/重复保留，稠密原子对并集及r73有序数组会随N/J/K增加；超预期只如实报告，未删字段或试其它压缩。原v30及副本/F64保留，D2/D4/D5不变；新格式无F64副本、新SHA、独立复核或吞吐。Model加载/逐头过拟合ACK仍待，D6继续暂停。正式入口configs/data_v1/v1-pilot-provisional-v31/D3_export.json。
