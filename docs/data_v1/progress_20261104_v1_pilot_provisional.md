# 2026-11-04 数据线每日汇总 — v1-pilot-provisional

D‑1 v3.0已冻结，D‑2、D‑4、D‑5保持已交付；D‑3尚未交付。D‑3优先；后台P′由另一独立授权接续流程运行，本Root不重复提交或修改其作业。

D‑3当前实际作业4525670在compute-0-8 RUNNING、16CPU。固定50,000 TRAIN＋5,000 ROUTINE VAL；141/171源组复用、171/171源组已全部关闭。10:44（北京时间）实际进程READ锁对应第108组，前107/171组已提交，来源前缀257.128/430.926GB、domain257.732GB；近3812秒增长14.585GB，约3.8MB/s。此整小时包含已撤销677秒辅助预读，不重复。实际read247.717GB/write358.061GB，存储READY，metadata观察器2135737真实身份仍匹配。合并仍进行，未查询活动SQLite；合并体积约60%不是全D3百分比。整体剩余保守暂估14–18小时，窗口上调至11月5日01–05点（很低置信度）；后续LMDB/原定一次QA/复制仍未测，非运行时限。

大文件输出沿Lustre；750GB为预测非硬上限，100GB真实账户余量保持。脚本无任务时间及内存参数，程序无总墙钟、RSS、MemAvailable停止门。原始Parquet、D4几何和141个闭合成果全部保留。

本日格式/资源修复一行： 可选活库预读step4525670.2实为1CPU/677秒，因同组推进放缓已在核对UID/完整argv/Slurm step cgroup后只停该辅助步骤（CANCELLED0:15）；D3父任务保持RUNNING，停止后短观察恢复约7MB/s文件增长。未修改源/SQLite、未做数值比较或SHA，不重复预读。原sacct -P表头适配及新SSH暂拒绝已沿原会话完成必要原生会计采集，D3未中断；补齐闭合索引及所属计划冻结引用；4525668在回连SSH临时拒绝后仅同job重排，随后暴露漏写资源字段；4525669在源组复用前被旧single_job目录分类拦截。已按事先授权修正资源字段、目录分类及早期Slurm UID未知观察；四个提取/投影/坐标/读取源码与旧parallel_store登记字节完全相同，不放松其完整字节一致性检查，无新增QM/UFF。旧失败和原回执保留；没有独立数据复核作业。

导出末尾只做一次计数、随机1,000条原Parquet逐字段比较与总清单SHA；一次rsync --checksum复制、一次180秒随机读取测试。模型加载器及逐预测头过拟合为交付后的验收，当前不代填模型ACK。

[D‑2注册表](../../configs/data_v1/v1-pilot-provisional/D2_registry.json)、[D‑4归一化](../../configs/data_v1/v1-pilot-provisional/D4_normalization.json)、[D‑5诊断载荷](../../configs/data_v1/v1-pilot-provisional/D5_diagnostic_payload.json)保持原交付。r73完整有序F64与单次F32、r674 LOSS_DISABLED保持。本轮不宣称最终Common、D‑6/D‑7或模型实际加载ACK完成。
一次性能处理：OS进程观察显示磁盘等待，36.7GB冻结几何库原仅2.4GB缓存；在现有作业4525670内以低优先级只读预热，step4525670.0实际C0/206秒，之后OS观察缓存驻留36.7GB。没有新增sbatch、数据比较、SHA或质量测试；缓存可由系统回收，源文件与活跃代码未改。

05:44（北京时间）更新：171/171源组已全部完成。当前父作业运行约4小时43分，合并库约132.5GB；相对约430.9GB源组中间库，体积约31%，仅为合并阶段的近似进度，不是整个D3完成率。合并开始后平均约18–19MB/s，低于初始短样本34MB/s，早先仅合并3–4小时的估算偏乐观。当前粗估合并还需4–5小时；LMDB写入、原定一次校验及复制缺实测，暂预留2–5小时，整体剩余粗估6–10小时。无新增数据校验或计算作业；存储READY。

同日工具修复补充：只读源码审阅发现未来额度退休异常可阻断已C0导出的metadata发布，已启用独立completion_r2。配额UNKNOWN时保守保留future并单独重试，原publisher仍要求真实C0/UID/16CPU/原manifest；同父PUBLIC存在时不重复发布。活动producer、冻结文件、DATA/QA/复制均未改动或重跑，未另起计算任务。

阶段推进：4525670运行约2小时44分时，171个源组全部关闭；同作业内开始合并。通过文件元数据观察，合并库从12.0GB增长至18.3GB，约3分钟实测速率34MB/s；仅合并暂估还需3–4小时，文件大小不是精确行进度，后续LMDB写入/校验/复制仍未实测。存储READY，未查询活动SQLite、未新增DATA复核。

06:06进度补充：实际父进程1148417（UID1278、原module argv）唯一活动POSIX READ锁对应第89/171个源组；结合逐组commit后才ATTACH下一组的既有实现，前88组已提交。按组数约51.5%；前缀来源库体积147.945/430.926GB约34.3%，各组大小不等，均不得当作整个D3的百分比。只读取/proc与闭合顺序日志，没有查询活动SQLite。

06:19后台核对：Alpha实际UID1264；1885187全11来源排除索引和1885196精确NN参考均RUNNING、各16CPU，1885190更新后100万基线统计实际C0（该更新结果尚未由本线重新验收）。扩充工作树的1885176完整结构参考及1885195完整Common回归已分别验收，1196122个MID/角色/原生记录摘要一致；这仅支持后续结构参考复用。原Common manifest仍保留Main父失败/pending历史、geometry_map_frozen_by_this_manifest=false、orders_frozen=false和PENDING_N1_POLICY，未据此放行D6、改试点55k或把Alpha C0当作Main C0。D3实际4525670继续RUNNING；P′仍挂起。不修改或重复提交另一扩充任务。

06:28性能处理：OS READ锁定位当前合并第91组，前90组已提交；其后第92–95组共23997906944B经fincore实测缓存均为0，节点MemAvailable约349GiB。在原4525670分配内以1CPU、nice19/ionice2:7只读预读这四个既有关闭来源库，实际step4525670.1正常exit0，23.998GB/45.2秒；父数据任务仍RUNNING。没有修改活动producer、源库、科学规则或增加数据QA，没有新增sbatch；是否改善合并吞吐仍待观察。

配额观测修复一行：新P′作业4525671（另一独立完成范围的既有提交，本Root未提交/修改）缺少与PPRIME_REMAINING_COMPLETION_20261104_V1既有80GiB Main预算的job_id关联，被Lustre观察误列UNKNOWN。已通过真实Slurm命令、submission_day001及资源范围核对，在Linux flock下仅为原预算条目补job_id及来源；各条future和总额128849018880B未变，无重复/删减预算。原D3 snapshot已恢复，Lustre总预测750000000000B、实测free约1638.479GB；未改科学规则、活跃源码、其他作业或重新排队。修复执行器位于control/D3_lustre_cpu_export_20261104_v6/bind_existing_main_budget_4525671_v1.py。

07:02重新估时：实际父进程1148417唯一活动READ锁对应第94组，前93/171组已commit；对应闭合来源前缀175.068GB（40.63%体积；按组54.39%，均非全D3百分比），当前组6.613GB。较06:06的147.945GB增加27.123GB/3376秒，期间约6分钟quota等待；近段有效速度约8–9MB/s，低于初始短样本。剩余合并暂估7–8小时，未测LMDB/原定一次QA/复制预留2–5小时，整体剩余上调为10–13小时（约今日17–20点，低置信度，非运行时限）。此前6–10小时范围偏乐观。实际domain约177.283GB，进程read_bytes170.470GB/write_bytes240.223GB持续增加，squeue RUNNING/16CPU、存储READY；无活动SQLite查询。

07:38后台实际状态更新：Alpha UID1264、compute-0-1上1885201（corrected_fixed1M_exact_before_v1）实际RUNNING/64CPU；先前1885187全来源索引及1885196精确NN参考打包均已sacct COMPLETED0:0（分别16CPU、2:44:15及2:06:22）。此处只记录实际运行/终态，R/N队列及完整去污染放行仍按扩充工作树正式验收清单；本Root未修改、重复提交这些作业。Main D3仍为原4525670 RUNNING/16CPU，domain约195.15GB、存储READY。

08:02整点观察：实际1148417的唯一活动READ锁对应第99组，前98/171组已提交；闭合来源前缀206.831/430.926GB（约48.0%来源体积，仅属合并阶段）。较07:02增加31.763GB/3627秒，约8.8MB/s，与最近估计一致。剩余合并按该速率约7.1小时，后续LMDB/一次QA/复制仍未实测，整体当前粗估还需9–12小时，暂维持今日17–20点低置信度窗口。domain约207.859GB，实际read193.075GB/write284.429GB，作业RUNNING/16CPU、存储READY；metadata观察器实际PID/start_ticks/UID仍匹配。没有查询活动SQLite。

09:07实际观察：前102/171组已提交，唯一活动来源READ锁对应第103组（7.101GB）。已提交来源前缀228.161/430.926GB；domain235.430GB，相对08:02增加27.571GB/3905秒，约7.1MB/s。当前大组仍在事务内，按已提交前缀单独测速会受组边界偏差影响。实际read222.818GB/write324.556GB继续增加，原作业RUNNING/16CPU、存储READY、metadata观察器实际身份仍匹配。剩余合并按近段文件增长率粗估7.7小时，后续LMDB/原定一次QA/复制未测预留2–5小时；整体剩余暂估10–13小时，窗口更新为今日19–22点（很低置信度，不是运行时限）。未查询活动SQLite，未修改源或增加数据测试。

SB‑2后台接续：Root已实际读取Main4525659的完整Common组件manifest（32份物理map、16份ordinary uff_identity，TRAIN1188592/VAL7530），并新鲜SSH确认其父FAILED1:0；failure明确在common.build完成后的graph quota阶段。复用该关闭组件准备N1物理权威，不重跑全Common，不把父改称C0；历史extra-ID登记完整性仍待绑定，N1 QA及Common/D6正式release尚未发生。无新增QM/UFF或后台计算提交。 接续候选索引为control/n1_physical_binding_prepare_20261104_v1/input_locators.json，已补Root实采719B会计及154B原生sacct。唯一剩余为registered-extra完整登记权威，保持null/UNKNOWN；未执行N1 QA、未分配ID、不增加冻结/复核框架。

ordinary后台续接：最薄ordinary_postprocess_resume_v1已安装为未执行代码，直接调用原PM7/D7/三序及Collector；复用5659关闭Common与5100关闭缓存，两个真实FAILED标准会计均已实采/归一。CSV已修为StringIO，资源credit改为已闭正引用一次st_blocks采样与后续quota起点确认，不全树反复盘存，不双扣；9条旧QUOTA200GB UNKNOWN保留，只重做原输入的只读缓存，Native_once/N1不改。原allocation内4525670.3完成0:0，只AST解析4py加D6库共5件，不导入/执行模块或DATA。未提交新计算或预留预算，须等D3真实retirement及现配额核算。D6分块IO库仅在control待用，缺真实FULL driver/精确源窗口、最终Common/orders/full统计和D3 loader ACK，不可用pilot冒full，D6原10000条末尾抽样不缩为1000。

额外只读观察：Lustre2.15.2，活库单OST1/4MiB条带；lfs原生配额used730136188KiB、limit2147483648KiB。全部Lustre未来现已约1.283TB，扣100GB后额外余量约68GB，不能容纳约270GB布局迁移副本，因此未执行迁移、不改任何活库布局。另条已授权P′线实际squeue为17任务/272CPU；Alpha1885201仍64CPU。这里只作全局状态观察，本Root未提交或修改另一目标。


12:40实际更新：4525670仍RUNNING/16CPU，前120/171组合并提交、当前121，prefix275.943/430.926GB、domain276.607GB，进程read269.545GB/write388.064GB，storage READY及watcher真实身份匹配。全量payload合并是当前单库writer的实现开销，并非接口科学要求；直接分片候选正在准备，保留当前job。仅96KB闭合log元数据证实171组/7,128,716来源行/65,570,829片段/430,926,245,888B源库，最大源10,018,541,568B；geometry_index3,523,170,304B。compute8 /tmp与/var/tmp均为75,125,227,520B root xfs，空闲59,086,950,400B，不能做430GB全量本地merge；改为小型位置索引加原分片只读查找，不复制BLOB。未新增sbatch、QM/UFF、DATA复核或终止原父；旧01–05点窗口已不作当前完成承诺。


存储清理：仅删除旧Main4525651(CANCELLED0:0) day03及旧Lustre4525669(FAILED3:0) day05的两份geometry_index.sqlite，当前v6 plan/proof与D2/D4/D5均无精确引用，旧父原生sacct终态、原节点与当前node8 fuser无持有者。按实际st_blocks释放7,046,373,376B（Main3,523,194,880B、Lustre3,523,178,496B）；逐个unlink精确文件，保留目录、元数据及全部171个闭合来源。compute21 SSH曾报主机键变化，未改known_hosts/认证配置；只读命令返回后结束该连接。当前v6活domain/index不动。直接分片新namespace已安装为未执行源码，原四科学文件逐字节一致，尚未提交或切换。


直接分片接续已完成源码和原queue/preparer/watcher接线并安装为独立未运行namespace；原allocation内step4525670.5实际COMPLETED0:0/1CPU/0秒，30源码仅AST通过、四科学文件逐字节一致，无模块导入/DATA执行。compute8→Main新key SSH只读返回UID1278。原scope_entry_key实为D3_LUSTRE_CPU_EXPORT_20261104_V6，须旧父终态及旧watcher真实retire0并自然退出后转移同一750GB，不叠加预测；大geometry index只在实际分配CPU用原1MiB流式pin一次，Main只收小ref。13:05实际4525670仍RUNNING，前129/171组合并commit、当前130，domain280.166GB、storage READY、watcher身份匹配。原指南明确禁止强停运行中任务，已仅为结束旧导出并清理约280GB副本、保全171源后立即提交新16CPU导出发一次确认；回答前原任务继续，未发送任何信号、未清活库、未新提交。


源码固定：new direct namespace已在data-v1以05c6103b62f1afaa9254d4cef6798cbdced09880提交；先本地提交后核到原指南必须仓库检查，已补原tools/check_repository.py并在PASS后amend未推送提交。实际4759文件/3334Python/53,203,706B、errors0；node8缺git的一次失败仅用短时shim获取Main原生git ls-files列表，原检查在allocation执行，shim已删，未改检查逻辑或加载科学模块。未停止旧任务或启动接续，切换确认仍待答复。


已获用户明确批准切换：原4525670实际CANCELLED0:0/16CPU/45330秒，Root仅先发该精确PID的SIGINT、未退出后仅scancel该job；保全171闭合source和原geometry index，删除旧domain及journal实际释放287,730,905,088B，含此前两旧index累计294,777,278,464B。接续4525744在SQLite URI ATTACH处FAILED3:0/62秒，4525745在公网Main SSH拒绝连接处FAILED1:0/4秒；一行记录修为writable uri=True及已实核同Main UID/boot的内网sonmi10.1.1.1，只有明确连接前拒绝才600秒重试。现4525746实际RUNNING/16CPU/compute8/pid1157599，URI及启动通过，171源句柄键扫描中，route从90KB增至49.4MB，未复制payload；SourceGroup PK串行随机I/O仍慢，正在准备16路rowid纯键扫描再本地归并的源码候选，当前任务继续。新路径尚无实测LMDB写入速度，先前2–5小时仅预留，不再当作完成预测；将用正式首5000MID分片估计，无新增benchmark、QM/UFF或科学规则改动。


4525746通过Python清理路径SIGINT退出，实际FAILED3:0/1244秒，仅串行准备键索引、无标签写入；并行纯键准备代码以ac075c97提交，Guide repo check4759文件/3334Python/53,210,710B PASS/errors0，实际4525747.0 C0/1CPU/10秒。当前4525747在compute8/16CPU运行，16线程逐源NOT INDEXED纯键扫描后本地归并，已有闭合纯键分片日志可监测。运行时配额SSH连接拒绝触发软等待，已仅为该SLURM_JOB_ID启用用户SSH客户端ControlMaster复用、保留原配置0600备份及私有socket目录；元数据master为原job内overlap1CPU持久步骤，未改认证/主机键/服务器daemon，真实查询已恢复READY、扣future后余量419,054,105,755B，原计算保留且继续。结束后清理该job专属Match块。范围实核：关闭的实际geometry index含pm7和uff_sprime，故本批有S′几何；129物理目标/146启用字段的D/P标签均pm7，不含UFF上的D′/P′；未查询活动route DB、未新增QM/UFF或数值测试。


实际阶段推进：171/171来源、65,570,829条纯键全部扫描闭合，本地路由表12,073,861,120B，纯键中间分片在全部reader关闭后已回收。当前已出现8组LMDB及F64 authority写入，未做额外数值读回；首5000MID尚未整体闭合，暂不外推全库时间。另仅删除已终态4525744/4525746的节点本地重复geometry index及部分route缓存，实际释放7,280,824,320B；未动当前4525747文件、原171source或正式交付物。

继续打包观察：4525747仍RUNNING，第一5000MID包含53个store任务，已闭合29个；其余writer继续，storage READY、无failure。仅只读核对原自动publisher接口兼容及watcher2286338的真实start_ticks，compute8→21元数据连接返回UID1278、/tmp空余924,083,154,944B；未提前复制、重做QA或bench，也未改变活跃源码。

首批实际闭合：checkpoint index0明确molecules=1000，非此前假定5000；已纠正当前进度为1000/55000（1.82%），原1710.58秒为首1000分子的写入，线性剩余54批约25.66h，仅写入估计。53闭合stores共139,202几何和487,207标签记录，LMDB11,171,192,832B、F64 7,290,720,256B；后续批次已自动继续，最新58stores/66authority、RUNNING、storage READY。单OST1已实核，无可用多OST条带提速，未改布局；只读评估局部node-local store staging以避免共享盘细碎sync，当前生产保持运行。

本地暂存正式接续：原4525747仅精确亲进程SIGINT停止新派发，所有在跑worker自然结束，实际FAILED3:0/7472秒，原171source、闭合LMDB/F64、eligibility、未merge的已闭metadata和12.07GB本地路由全部保留。新4525785实际RUNNING/compute8/16CPU；同一作业先执行原Guide源码检查PASS4790文件/3363Python/1311server sources/0errors，再进行DATA；没有独立QA作业或数值二次读回。临时git转发参数与控制命令身份载荷问题已直接修复，未影响数据。当前3000/55000完整闭合（5.45%）、8个本地cache阶段真实存在，storage READY；旧job专属SSH Match块及失效socket已移除，新job使用自己私有复用连接。新预测1.03TB不作输出硬停，接续时真实旧已用块只计一次、100GB账户余量保持；去掉静默512 FD计数上限，使用实际进程额度。GPU20/21本地盘均约954GB；单次checksum只复制训练LMDB及清单，完整F64权威仍永久位于原Lustre路径、bytes/SHA不变，交接已明确禁止把未复制的旁车引用改成本地路径。最终1000原Parquet/计数/总清单SHA、一次180秒读取及Model真实验收规则不变。当前生产仅剩两项重store时有明显尾部空闲，5秒实际进程遥测1.58CPU/16；已非阻塞准备重任务优先/最多15writer的源候选，活跃v1不改，尚未采用。

15writer调度接续已实际落实：原4525785经自身亲进程SIGINT后所有worker自然结束，真实FAILED3:0并由原watcher退同一scope为0；新4525812在compute8/16CPU实际RUNNING，原Guide检查PASS4821/3392Python/1311server sources/0errors。Native /proc确认parent1165005下15个spawn worker，私有缓存15阶段，/tmp余41,373,028,352B、storage READY，无新failure。保全所有4000完整分子及后续闭合子库；按原profile重store先发、最多15writer加parent共用16CPU，其余科学、schema、F64、一次QA/复制规则不变。调度调整完成，后续保持本不可变job持续至55k和原定交付；不再因空输出或观察超时重启。


原4525812仅自身亲进程SIGINT停止派发、worker自然收尾，实际FAILED3:0/3486s，原watcher退同一scope为0；缓存原native.graph结果的接续4525822已在compute8/16CPU实际RUNNING，Guide源码检查PASS4854/3422Python/1311server sources/0errors，源码提交c90fde01c4e1d9a71fca53ebe75bd3ea3515997a。实际闭合前缀7000/55000（12.73%）已复用；所有源读取及原科学检查保留，不新增QA。自动终态发布watcher2362611身份已实核，storage READY。新缓存速度等正常批次检查点后再估计，不沿用旧速度承诺；本不可变作业持续至原定55k与一次末尾验收。


正常生产显示v3第8批47/53 store已闭时仅约4.13CPU/16、后来只剩一个重store，跨批barrier使其余writer空闲。独立v4仅把最多8个原1000MID分片汇入同一15worker重任务优先窗口；原单store写入/merge/恢复函数及四科学文件字节不动，全pool真实exit0后按index连续写原checkpoint，闭合数据不重编码。原Guide在真实4525822内PASS4886文件/3452Python/1311server sources/0errors后提交源码；未加QA。已仅向精确亲进程1169156发送SIGINT停止派发，全部worker自然收尾；现同一会话自动等原终态、watcher退future为0后仅提交一次v4，尚未冒称新job已启动。


跨批窗口已实际启动：4525822自然收尾为FAILED3:0/1110s，原watcher退同scope future为0并退出后，控制器只提交一次4525824。新作业compute8/16CPU实际RUNNING，原Guide实际PASS4886文件/3452Python/1311server sources/0errors；plan实绑8分片窗口/15writer，parent1171016，自动发布watcher2367289。此前闭合分片与所有source继续复用，未新增QA/QM/UFF或改变科学规则；首个窗口未闭，实际总工期尚待生产数据估计。


运行观察补充：4525824已生成8份原分片partition，Native /proc实核15个spawn writer且已同时写多个原分片，storage READY，无failure。另将4525825已属于现有600GB P′总scope的零增量别名修正为观察器可识别的LUSTRE分类，原310GB剩余预算完整保留、未改任何P′作业，解除UNKNOWN_WRITER假暂停；扣全部future后的真实账户余量约189.54GB。未增加QA或读活动SQLite。


运行资源修复/提速一行：新原预算别名4525830已按native脚本与同600GB中央scope正确分类，原剩余预算保留；临时Main观察流程已对同类明确覆盖的零增量别名自动做同样兼容，真正未知写入不猜零。node8根/tmp仅41.1GB空余导致部分大store回退共享写；/home虽有395GB但无写权限，故独立v5选用实际202GB空余、MemAvailable375711516KiB的私有0700 tmpfs缓存，原/tmp路由与所有Shared正式路径不动。v5原Guide在实际4525824内PASS4918文件/3482Python/1311server sources/0errors后提交；仅向精确自身parent1171016发SIGINT停派发，15worker自然收尾后自动只提交一次接续，无新增QA/QM/UFF、无时间/内存停止门或科学变更。


实际tmpfs接续已启动：4525824自然收尾并由原watcher退同scope为0后，仅一次sbatch提交4525834；其在compute8/16CPU实际RUNNING，Guide PASS4918文件/3482Python/1311server sources/0errors，启动日志实际确认202,231,173,120B缓存空余。原/tmp索引和共享正式路径全部沿用，Source4科学文件与8窗15writer逻辑保持。D2/D4/D5只读交接检查未发现缺失refs；D5当前actual_D3_seen仍正确为null，待D3实际C0/既定QA/复制后完成小元数据绑定，并同步D3引用，避免悬空SHA，不追加数据QA。


正常生产观察：4525834已实际同时使用15个私有tmpfs stage；约122秒内闭合子库540→579，storage READY、扣全部future后账户余量183.47GB、无failure。此为正式生产日志/文件元数据观察，未新增benchmark或QA，完整MID检查点仍等本窗口pool真实退出；保持当前v5持续交付，不因空输出或尾部等待再改版。


正式检查点推进：4525834仍实际RUNNING，checkpoint已闭合15000/55000 MID（27.27%）、795子库，最后index14与window全部worker真实退出标记成立，mtime1793794253；已自动进入15k→23k下一原8k窗口。storage READY、账户扣future后余量174.34GB，无failure。恢复窗包含v4闭合数据复用，不用它伪估全新8k耗时；下一正常窗口提供可比时长，不新增吞吐测试。


最终小元数据接线源码已就绪：final_metadata_bind_v1.py仅在真实D3 C0/既定1000QA与checksum分发完成、同冻结pilot引用后，创建不可变D5 bound索引再原子更新D3引用；原D5不改，无环或旧SHA悬空，不重读科学DATA。原Guide在现有4525834分配内PASS4919文件/3483Python/1311server sources/0errors后已提交该单文件，尚未执行绑定。正式作业保持原v5；3秒/proc遥测约2.52CPU且worker主要等待页读取，核数分配不等于实际CPU占用。


只读缓存优化：现有4525834分配内1CPU预读完成3.52GB index和36.70GB输入几何，未哈希/比较科学值；Native mmap检查定位到两个当前活跃原始LMDB共78.86GB，原resident仅1.32GB，已用同分配单CPU顺序预读至页缓存，正式pack与后台配额兼容观察继续，未改版本/数据文件/科学规则或新增QA。当前869闭合子库，完整检查点15000，storage READY，无failure。


原始LMDB输入页预读实际完成：同4525834内step2 C0/1CPU/1163s，两文件38,323,257,344B与40,540,778,496B均按原大小只读，fincore实际resident分别38,323,257,344B与40,540,774,400B；step1几何预读C0/306s。未哈希/数值复查/新QA或新增sbatch。正式C0后D5小索引绑定等待器2406536已实际启动并核UID/start/argv，只待真实4525834完成并由原publisher交付后调用原绑定器，不提前改Model ACK。

D3运维续接：原4525834持续RUNNING/16CPU，保留全部闭合输出；已将既有中央600GB预算覆盖的零增量别名兼容处理转为Main后台PID2414807（实核UID/start/boot/argv），仅维护已证明条目、不降低中央预算，直至实际D3终态，避免交互观察器到达23k检查点后失去兼容维护。原一次末尾验收、分发和D5小元数据绑定不变。

D3 I/O续接：一次只读/proc syscall观察定位到实际阻塞pread64的闭合源SQLite；在原4525834分配内用1CPU的step .3预读5个实际命中且列于原171闭合清单的文件（22,941,773,824B），实际C0/112秒、原inode/大小/mtime/ctime均未变。未读取活动SQLite表、未新增QA/SHA/副本，原DATA未停止。

D3正式生产检查点：4525834仍RUNNING/16CPU，已闭合23,000/55,000分子（41.82%）、1,219子库，原8k窗口全部worker退出且LMDB/F64关闭。实际15k→23k检查点mtime差6198秒（1.722小时）；按同速剩余32k仅打包约6.887小时，末尾原一次QA与checksum复制另计且尚无实测。资源READY，扣所有future后余156,100,992,912B；自动发布watcher、D5实际绑定和独立账本兼容维护均保留。

D3运维：新出现的PubChem本地FP作业4525875未入共享账本造成配额观察暂等；已按其实际Slurm UID/node/script与生成plan确认60GB输出仅在compute-0-16私有tmpfs，并在Main登记100MiB共享元数据future，Lustre观察器原逻辑据此认定非本卷写入。未改/停任何科学作业，4525834已连续两次恢复READY且15个stage输出继续增长，闭合子库1231；不另做失败报告。

D3第二窗口定向缓存：3秒系统观察实测约4.342核，等待来自真实pread输入；原4525834内1CPU step .4针对3个实际命中的输入做一次只读预读，C0/402秒，原文件frame未变。几何文件native fincore由14,454,468,608/36,698,353,664B升至36,673,134,592/36,698,353,664B；两个标签源达到100%缓存。未新增QA/SHA/副本、未重启DATA，最新闭合1328子库/完整23k检查点、资源READY。

D3实际检查点31k：4525834仍RUNNING/16CPU/compute-0-8，31,000/55,000完整分子（56.36%）和1,643子库已关闭，本窗口worker全部实际退出。23k→31k检查点mtime差4939.0秒（包含其间运维等待），只按生产时序估计剩余24k打包约4.116小时、最近两轮范围4.116–5.165小时；最终一次QA及checksum分发仍另计，未追加吞吐测试。原作业继续，Main快照观察器已改到39k；原终态发布及D5绑定进程保持。
