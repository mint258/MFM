# B0 数据线入口

权威为 `docs/benchmark/USER_DIRECTIVE_20261118.md`（提交07be7a0f）及其中引用的Benchmark Plan。本线承担数据获取、适用域、共享几何与原P/D标签；模型拟合和基线环境由基准线消费交付。

数据在 `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119`，不进Git、不为各节点复制。`acquisition/<group>.json`只证明来源获取；`domain/<group>/job_<id>/manifest.json`只证明适用域计数，均不表示几何和标签已经就绪。当前状态见本目录日报。

`all_rows.parquet`保留原文件、原行号、原始字段、官方划分、源原子映射、适用域原因与盲测备用预测标记。所有盲测行保留。ExpansionRx原始测定表只作来源，不重复计为训练集；Joung保留溶剂上下文，不将溶剂当发色团过滤。Biogen的7份官方benchmark JSON保留各任务划分，不强行合成一个划分。TDC从原ZIP流式读44个train_val/test文件，不解压小文件。

ASAP从原Zarr块通过官方numcodecs解码，无数值变换；HLM/MLM官方排除只作终点评价掩码，原560个分子均保留。pKahub先沿作者exclude规则保留97,614条记录，再做本计划适用域筛选；宏观跃迁不视为原子电离位点，预测microspecies不视为实验微观pKa。

CPU生产入口为 `workflows/benchmark_data/` 下的sbatch，限定compute-0-16、按需CPU、非exclusive。容量准入与运行期保护使用实际文件系统、inode和UID1278实时quota；元数据发布器有明确寿命和独立停止文件。新源码测试在CPU节点运行；实际构象/标签只允许生产端一次检查，不另起数值复读任务。

共享 S′/D 数据库为上述数据根下的 `geometry/shared_v1/queue.sqlite`，149,238种有序模型SMILES服务303,547条来源记录，生产尚未全部关闭。消费者使用 `workflows.benchmark_data.shared_reader.SharedB0Reader`，在原共享路径只读打开，保留来源原子映射，不复制到节点：

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

`D20`含原20维名称、F64值、valid_mask和issues。`conformers`含实际构象ID、源候选ID、UFF坐标/能量、D3和问题列表；D3原子SASA沿原顺序。`model_atom_to_source`把模型图原子映回各自输入，新增H通过结果的`model_atom_to_template`标为-1。读取返回后即释放SQL语句；不要另开长事务或对活动库做全表QA。生产结束前不能把一次遍历当作全量完成，最终以生产manifest及状态为准。

P/Pprime仍未就绪，不能从D或UFF能量伪造P特征。参考组的几何、适用域、目标及D20各有manifest；C7目标为`targets/C7H10O2/job_4536471/manifest.json`，NMR域为`domain/NMRShiftDB2/job_4536470/manifest.json`，PPE部分域/目标绑定为`domain/PPE1694/job_4536479/manifest.json`。PPE99条结构及2条目标未决明确保留；参考组原子映射/D3尚未交付。
