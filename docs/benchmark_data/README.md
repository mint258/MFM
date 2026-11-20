# B0 数据线入口

权威为 `docs/benchmark/USER_DIRECTIVE_20261118.md`（原科学流程07be7a0f）、`USER_DIRECTIVE_20261119.md`（补充6d056a41）及其中引用的Benchmark Plan。本线承担数据获取、适用域、共享几何与原P/D标签；模型拟合和基线环境由基准线消费交付。

数据在 `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119`，不进Git、不为各节点复制。`acquisition/<group>.json`只证明来源获取；`domain/<group>/job_<id>/manifest.json`只证明适用域计数，均不表示几何和标签已经就绪。当前状态见本目录日报。

`all_rows.parquet`保留原文件、原行号、原始字段、官方划分、源原子映射、适用域原因与盲测备用预测标记。所有盲测行保留。ExpansionRx原始测定表只作来源，不重复计为训练集；Joung保留溶剂上下文，不将溶剂当发色团过滤。Biogen的7份官方benchmark JSON保留各任务划分，不强行合成一个划分。TDC从原ZIP流式读44个train_val/test文件，不解压小文件。

ASAP从原Zarr块通过官方numcodecs解码，无数值变换；HLM/MLM官方排除只作终点评价掩码，原560个分子均保留。pKahub先沿作者exclude规则保留97,614条记录，再做本计划适用域筛选；宏观跃迁不视为原子电离位点，预测microspecies不视为实验微观pKa。

CPU生产入口为 `workflows/benchmark_data/` 下的sbatch，限定compute-0-8至19、按需CPU、非exclusive。容量准入与运行期保护使用实际文件系统、inode和UID1278实时quota；元数据发布器有明确寿命和独立停止文件。新源码测试在CPU节点运行；实际构象/标签只允许生产端一次检查，不另起数值复读任务。

共享 S′/D 数据库为上述数据根下的 `geometry/shared_v1/queue.sqlite`，149,238种有序模型SMILES服务303,547条来源记录，生产4536478已COMPLETED/0:0：113,679个分子S′/D齐备；34,766个缺少明确立体参考、715个无接受构象、62个UFF不支持、16个历史中断未知，均显式保留。消费者使用 `workflows.benchmark_data.shared_reader.SharedB0Reader`，在原共享路径只读打开，保留来源原子映射，不复制到节点：

```python
from workflows.benchmark_data.shared_reader import SharedB0Reader

with SharedB0Reader(shared_queue_path) as reader:
    for record_id in reader.iter_membership("MoleculeACE"):
        item = reader.get("MoleculeACE", record_id)
        if item["result"] is None:
            continue  # 保留该记录的PENDING/INTENT/UNKNOWN状态，不能当成零标签。
        d20 = item["result"].get("D20")
        conformers = item["result"].get("conformers", [])
```

`D20`含原20维名称、F64值、valid_mask和issues。`conformers`含实际构象ID、源候选ID、UFF坐标/能量、D3和问题列表；D3原子SASA沿原顺序。`model_atom_to_source`把模型图原子映回各自输入，新增H通过结果的`model_atom_to_template`标为-1。读取返回后即释放SQL语句；不要另开长事务或对活动库做全表QA。`access.json`控制跨节点读取：活动写入期仅写入节点可读，原生作业C0和终态manifest闭合后才发布immutable、开放跨节点。共享S′/D现已封存，源失败与UNKNOWN不会被当成成功。

共享P′入口为 `labels/Pprime/shared_v1/queue.sqlite`，配套lane SQLite存一次原始解析字段及失败/审计输出；`workflows.benchmark_data.pprime_reader.PprimeReader`按共享MID和实际构象ID读取。325,080个实际S′构象已排队；4536491在记录边界C0，保留1,877齐备及1部分结果、INTENT0，4536581已原生C0，160,048齐备/157部分/164,875待启动/INTENT0；4536588已在compute-0-12/8CPU续算；活动期仅同节点消费，跨节点等作业封存后开放。`PPRIME_READY`、部分任务失败、PENDING和UNKNOWN分别保留。尚未完成全量P′，不得将D或UFF能量替代P。原十二任务、900秒、MOPAC23.0.3/xTB6.7.1和原解析函数保持；用户已禁止重建或试算旧PM7优化；下游统一S′，C1的P组明确使用P′。

参考组最新D20入口为 `labels/reference_D20/job_4536512/manifest.json`，共45,907条：C7 6,023、NMR¹³C 26,345、¹H 11,974、PPE 1,565。旧闭合D20复用，91条原等待共享生产已补齐。参考D3作业4536501和4536560均C0：C7 5,406/6,023、NMR¹³C 25,683/26,345、¹H 11,263/11,974、PPE 1,542/1,565条齐备，合计43,894；其余2,013条映射未解决、D3显式缺失，源记录保留，不重建参考坐标或额外重试。

C7目标为 `targets/C7H10O2/job_4536471/manifest.json`。历史CSTShift-DFT参考域为 `domain/NMRShiftDB2/job_4536470/manifest.json`，原子级标签始终使用原参考索引；恢复图和模型图完整匹配仅用于计算时排列并逆映射，不声称恢复了未公开的作者原始索引处理链。PPE最新入口为 `domain/PPE1694/job_4536507/manifest.json`：作者INDEX/电荷/多重度对应，1,565条域内、126条已知域外、3条图未解析；1,694个原SI目标均绑定，原标签未改动。`reference_bindings.parquet`保存1,542条明确原子映射；域内剩余23条映射未决，不擅自删样或改几何。pKa宏观酸/碱及NMR2018官方划分已按新指示确定；活跃任务使用下文覆盖入口，历史参考域不代替2018任务。

统一入口为 `configs/benchmark_data/B0.DELIVERY.json`，指向 `delivery/directive19_current_counts_4537016/manifest.json`、当前 `active_source_domain_counts.csv` 与历史 `domain_counts.csv`。该manifest整合11组来源、12行数量（NMR分核）、原始记录/参考坐标、D20/D3、目标、P′共享读取器及待定事项。公开摘要见 `B0_DOMAIN_COUNTS.md`。数量表聚合生产manifest，不重新筛选或扫描数值；PPE未知图与已知域外分开，非互斥原因不能直接相加。

P′当前4536588→后续4536590依次afterok续接同一队列，已关闭结果不重算，全量封存后入口直接退出且不新增Native。仅新量化暂态文件在12的/dev/shm（8×8GiB峰值、32GiB系统/并发余量、额外15%整机RAM余量），输入库/解析字段/失败审计均仍为共享NFS单份。每次调用及父循环重新检查真实字节/inode/RAM/UID配额，根盘保留max(10GiB,10%)。有限7天quota发布器3058760（旧1443347退出后顺序更换）仅发布真实观测，延迟2秒公布以避免实测节点时钟差导致负年龄；真实时间戳和0..90秒检查不变，未改变quota配置。

历史参考构型和原D保留作来源；下游3D已统一改用共享UFF。P′仍只定义在UFF上，没有把参考几何量化结果改名为P′。最终交付生成器按终态producer manifest区分 `production_closed` 与 `all_ready`：有明确失败时可生产关闭，仍不得把失败记录当成齐备标签。

验证：本线65项全量通过（4536597 C0），完整源码检查PASS。仓库全量回归4536594实际执行，1877通过/95失败/161错误/5跳过；本线4项测试导入/环境问题随后修复，其他旧目录问题未解决，未证明全仓通过。所有报告保留；不为此重跑量化或改变科学规则。

SAMPL6/7来源关联补充在 `provenance/SAMPL6_7/job_4536607/manifest.json`（4536607 C0），统一入口的`supplemental_sources`可定位。SAMPL6保留31条/24个原挑战分子编号，SAMPL7保留20条/20个编号；51条均按`dataset + rawdataID`关联既有pKahub域内记录。原SM编号跨挑战可复用，必须连同挑战名使用，不能直接当全局molid。每条保留原数值文本、原字段和主表/域记录定位；源编号关联不表示构象或标签齐备。训练/盲测角色现由新宏观目标与完整InChIKey排除清单冻结；旧关联产物仅保留原来源事实。未推断原子位点、未将预测microspecies改成实验微观标签。新增2项来源测试通过，完整源码检查PASS；此前65项本线全量及全仓回归的结果继续保留，不以增量检查冒充重跑全仓。

16核候补使用 `workflows/benchmark_data/standby_pprime.sbatch` / `pprime_standby.py`，当前候选4536991以显式环境 `B0_PREVIOUS_PPRIME_JOB=4536588` 绑定实际8核生产6588，后续为6590。原候选4536722因前驱6581已C0，在核实其自有PENDING/RunTime0且不存在accept文件后取消，0Native；未中断正在运行的6588。当前提交排除0至7、20至22、尚未证明NFS启动恢复的18，以及新增8核P′正在写入的17；后者实际tmpfs总201,841,762,304B，小于同时24workers×8GiB＋32GiB余量=240,518,168,576B。待该tmpfs科学写入实际关闭后，可在候补仍PENDING/0Native时解除对17的临时排除。候补PENDING不表示16核提速已发生。

候补实际获配后，入口先核实native RUNNING、UID、实际节点/CPU、/dev/shm字节/inode、整机RAM、根盘与共享quota，打印 `STANDBY_READY_ZERO_NATIVE` 和完整进程identity；约300秒内无协调指令即0QM退出。协调者重新验证这些证据后，先将6590依赖改为 `afterok:4536588:4536991`，6599/6961尾链保持；同时核实新增范围后续6907仍PENDING/0Native，并让它排除候补实际分配的16核节点，以免将来的8核写入与16核候补重复预算同一tmpfs；确认quota服务寿命覆盖新链，再核实实际6588 Python父进程UID/完整argv/start_ticks/Slurm归属，只对该父进程发原SIGTERM收尾请求，不信号QM子进程。随后向 `control/B0_pprime_standby_4536991_accept.json` 写入候补identity，且只在上述操作真实完成后写 `previous_parent_sigterm_verified=true` 与 `followup_requires_both_jobs=true`。这是本线内部协调，无需用户操作。

候补仍须等旧6588原生COMPLETED/0:0、实际producer身份、writers_closed与INTENT0，再复核资源，才exec原pprime_tmpfs_queue的16worker。原12任务/900秒/二进制/解析/单位及源原子序不变；只传实际Slurm剩余墙钟减60秒，原约3小时记录收尾余量保持。如果旧生产身份在候补获配前已变化，不伪造accept文件、不重试科学记录；仅在核实自有PENDING/0Native边界后重新绑定候选，原8核接续照常。


2026-11-19补充指示的数据覆盖入口：先读统一入口的 `active_target_manifests`，不要从历史参考数量表推定当前任务标签。新可用handoff4537016只聚合生产元数据，没有数值复读。

- `NMRShiftDB2` 指向原作者2018发布数据的目标manifest。其 `records` 保存全部39,719谱行、作者 `official_split`、重复谱、源原子编号、`target_values_ppm`、`target_source_atom_ids`、`target_group_indices` 和有效掩码。原始标签F64且不重分配原子ID。测试谱行5,390/2,554与唯一原分子5,055/2,527分别报告，不能互换；4536946已按Kwon2020原作者datasets.zip核对：测试谱行5,390/2,554、唯一原分子5,055/2,527与Jonas2019原划分全部一致；原文正文没有印出分核唯一分子数，不伪造正文数字。核对只读身份/计数，不比较标签数值。
- `pKahub` 指向宏观目标manifest。读取 `training_targets`、`blind_targets`、`training_exclusions` 与 `blind_identities`。29,972个训练池分子，酸15,879/碱16,997终点；SAMPL6/7的44个完整InChIKey排除79条源记录。每条目标保留测量值/源行，并通过 `geometry_dataset + geometry_record_id` 读取原共享S′/D；原子单位点证据提案已产出，结构定义仍待用户确认。
- `directive19_data_preparation.uniform_Sprime_scope` 指向新范围输入manifest；`geometry_bindings` 提供逐目标记录的几何路由。38,240个新有序图现已终态封存；163条来源记录直接引用原封存几何，包括原失败/UNKNOWN，不复制、不重试。是否可用由对应队列的状态及access声明决定，不把已准备输入冒称几何就绪。

新范围几何读取遵循路由，保留目标自己的原子映射：
```python
with SharedB0Reader(binding["shared_geometry_queue"]) as reader:
    item = reader.get(binding["shared_geometry_dataset"],
                      binding["shared_geometry_record_id"])
target_atom_mapping = binding["model_atom_to_source"]
```
复用路由返回的reader映射属于旧来源，目标映射应使用binding中的这一份。原队列与新scope队列均通过同一SharedB0Reader读取。相应P′队列位于该几何队列所属scope的 `labels/Pprime/shared_v1/queue.sqlite`，用PprimeReader按 `binding["mid"]` 和实际conformer_id读取；跨节点仍须等实际封存，不能复制活动数据库绕过。

新范围链为4536924（compute-0-17/2CPU）UFF几何→4536978失败D3原子对齐修复→4536979封存/准备→4536906→4536907原P′续接。原4536898在node18的资源检查阶段阻塞于NFS，实际FAILED/9:0、消耗17,560分配核秒；目标节点身份及进程树证明尚未进入科学计算。同一38,240图队列改由node17继续，已观测真实生产；旧4536905为零运行准备任务，重接依赖后取消。生产入口 `uniform_pprime_scope` 在父进程和每个spawn worker中安装同一联合存储守卫，科学调用仍是原十二任务、二进制、解析和900秒。后续段若发现全队列已关闭则零Native退出；各段按实际Slurm剩余墙钟保留原记录收尾余量。原325,080构象P′链独立继续，当前并未声明全部生产完成。

pKa原子位点定义提案见 `directive19_data_preparation.pKa_single_site_definition_proposal`（4536942 C0）。37类SMARTS逐项转录自作者SI Table S2（S2–S4，CC BY-NC 4.0，DOI 10.1021/acs.jcim.6c00107.s001）；增加的site_atom_maps是本线对酸失质子/碱受质子原子的显式解释。按原模型图、不改质子化，重叠规则按实际原子合并；多原子和未识别N/杂原子供氢或电荷状态保留多位点/未决。训练池5,588个单一catalog位点、18,838个多位点、5,546个未决，其中5,465条候选原子标签另满足唯一实验跃迁/端点类型/原子映射；外盲9条候选。此为待用户冻结的结构定义，不是实验微观标注，也不是已激活的原子训练标签。宏观目标与盲测排除不变；用户确认后才将候选发布为正式机制入口，无需重新扫描。

双范围最终交付由 `workflows.benchmark_data.final_scope_handoff` 生成，4536961依赖新源码检查4536963、原范围交付4536599及新增P′尾段4536907。它只读两范围的geometry/Pprime access与producer元数据，并分别查询实际原生C0；任一PENDING/INTENT或活跃写入均拒绝最终封存，不扫描SQLite或标签正文。NMR作者计数证据必须匹配。只有几何/P′均封存时，all_scopes_production_closed才为true；若pKa单位点定义/正式原子入口仍待定，all_required_production_complete与all_required_work_complete仍为false，不把候选提案当正式标签。原S/P不重建。最终元数据守卫只在两范围均证明终态后退休其未来科学增长预测，继续保护模型114,569,896,448B、B1环境24GiB、账户100GB及真实磁盘/inode；旧运行守卫不变。当前future manifest尚不存在，统一入口指向可用交付7016，生产未完成。

新增NMR保留作者显式H原子序，而旧D3 wire默认解析SMILES并把H追加到末尾，6970已确认4个原部分失败分子均报旧元素序对齐错误，D20无错误。针对原记录明确报D3_SOURCE_MAPPING_OR_PROPERTY_FAILED且D3为None、原错误属于元素序/键图序的情况，新适配器用含H完整图和手性双射排列输入，调用原D3函数一次，再逆排列SASA_atom；不重算UFF/QM、成功D3或D20。6970读取少量已失败记录的错误元数据（不比较数值），6974/6976分别做合成测试/源码检查；6978必须等这三项及原UFF6924全部C0，且仅在原写入节点17、原源未封存时执行。原失败保存在结果历史和once表，已有失败/中断尝试不重复；6979只在6978实际C0后封存。原6925验证PENDING/0秒后取消，6906已接6979。原UFF6924现已原生COMPLETED/0:0，全部38,240图终态；6974六项合成/once测试通过，6976源码检查通过5,264文件/3,735 Python/0错误。6978已原生COMPLETED/0:0，修复41,243个原对齐失败D3；23,287图S′/D齐备、1图D部分，656无接受构象/14,285立体参照缺失/11个UFF不支持保持显式。6979已C0并将源geometry access置immutable及cross_node_read_allowed；53,896个实际构象已入新增P′队列，6906已CPU17/8CPU实际运行并产出齐备记录，6907依赖续接。原325,080构象P′继续。

当前源数量表由handoff额外生成 active_source_domain_counts.csv，仅用生产manifest计数，将NMR替换为作者2018谱行统计，保留两核及各原因列；历史domain_counts.csv继续保留。pKahub此表仍为作者curated测量行，非宏观终点/唯一分子数，也不表示B1有效任务数。可用交付4537016已实际COMPLETED/0:0（11秒/2CPU），新增3项路由测试通过，源码检查PASS5,265文件/3,736 Python/0错误；两条最终handoff均保留其成功依赖。
