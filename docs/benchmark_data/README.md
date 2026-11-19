# B0 数据线入口

权威为 `docs/benchmark/USER_DIRECTIVE_20261118.md`（提交07be7a0f）及其中引用的Benchmark Plan。本线承担数据获取、适用域、共享几何与原P/D标签；模型拟合和基线环境由基准线消费交付。

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

共享P′入口为 `labels/Pprime/shared_v1/queue.sqlite`，配套lane SQLite存一次原始解析字段及失败/审计输出；`workflows.benchmark_data.pprime_reader.PprimeReader`按共享MID和实际构象ID读取。325,080个实际S′构象已排队；4536491在记录边界C0，保留1,877齐备及1部分结果、INTENT0，4536581已在compute-0-12/8CPU续算；活动期仅同节点消费，跨节点等作业封存后开放。`PPRIME_READY`、部分任务失败、PENDING和UNKNOWN分别保留。尚未完成全量P′，不得将D或UFF能量替代P。原十二任务、900秒、MOPAC23.0.3/xTB6.7.1和原解析函数保持；历史PM7优化二进制仍未证实，S/P待定。

参考组最新D20入口为 `labels/reference_D20/job_4536512/manifest.json`，共45,907条：C7 6,023、NMR¹³C 26,345、¹H 11,974、PPE 1,565。旧闭合D20复用，91条原等待共享生产已补齐。参考D3作业4536501和4536560均C0：C7 5,406/6,023、NMR¹³C 25,683/26,345、¹H 11,263/11,974、PPE 1,542/1,565条齐备，合计43,894；其余2,013条映射未解决、D3显式缺失，源记录保留，不重建参考坐标或额外重试。

C7目标为 `targets/C7H10O2/job_4536471/manifest.json`。NMR域为 `domain/NMRShiftDB2/job_4536470/manifest.json`，原子级标签始终使用原参考索引；恢复图和模型图完整匹配仅用于计算时排列并逆映射，不声称恢复了未公开的作者原始索引处理链。PPE最新入口为 `domain/PPE1694/job_4536507/manifest.json`：作者INDEX/电荷/多重度对应，1,565条域内、126条已知域外、3条图未解析；1,694个原SI目标均绑定，原标签未改动。`reference_bindings.parquet`保存1,542条明确原子映射；域内剩余23条映射未决，不擅自删样或改几何。pKa任务形式和NMR划分仍待用户决定，数据侧工作继续。

统一入口为 `configs/benchmark_data/B0.DELIVERY.json`，指向 `delivery/job_4536591/manifest.json` 和同目录 `domain_counts.csv`。该manifest整合11组来源、12行数量（NMR分核）、原始记录/参考坐标、D20/D3、目标、P′共享读取器及待定事项。公开摘要见 `B0_DOMAIN_COUNTS.md`。数量表聚合生产manifest，不重新筛选或扫描数值；PPE未知图与已知域外分开，非互斥原因不能直接相加。

P′后续4536588→4536590依次afterok续接同一队列，已关闭结果不重算，全量封存后入口直接退出且不新增Native。仅新量化暂态文件在12的/dev/shm（8×8GiB峰值、32GiB系统/并发余量、额外15%整机RAM余量），输入库/解析字段/失败审计均仍为共享NFS单份。每次调用及父循环重新检查真实字节/inode/RAM/UID配额，根盘保留max(10GiB,10%)。72小时quota发布器1197837仅发布真实观测，未改变quota配置。

参考构型使用作者XYZ和原D；历史S配置缺证时P继续待定，P′仅定义在UFF上，没有新增参考几何量化标签类型。最终交付生成器按终态producer manifest区分 `production_closed` 与 `all_ready`：有明确失败时可生产关闭，仍不得把失败记录当成齐备标签。

验证：本线65项全量通过（4536597 C0），完整源码检查PASS。仓库全量回归4536594实际执行，1877通过/95失败/161错误/5跳过；本线4项测试导入/环境问题随后修复，其他旧目录问题未解决，未证明全仓通过。所有报告保留；不为此重跑量化或改变科学规则。
