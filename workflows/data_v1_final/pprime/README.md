# P′ 2000 构象试点

此目录是新的数据线驱动。只复用 SHA 固定的 WP5 科学函数、解析器和 12 项任务，不启动历史 runner/SQLite 队列，不修改 WP5 或原 LMDB。全部真实计算仅由 Root 审阅并通过既有提交器提交。

1. `prepare_pilot.py` 在 compute-0-20 的 16CPU Slurm allocation 中读取已闭合元数据，选择已经达到原 N 且 N≥2 的 1000 个 TRAIN/VAL 分子。VAL 依据已冻结的 ROUTINE 分子级角色；FULL 其余分子不入选。它只物化前两个固定随机顺序 UFF 构象及其只读源指针，生成新的分层 1% 审计清单，不打开 LMDB 或运行 QM。
2. `run_pilot.py` 仅在 compute-0-14–19、16CPU/64GiB allocation 中执行，固定 16 个 spawn worker。每 worker 一个 QM lane，各调用沿 WP5 单线程环境。输入和输出目录必须是新的外部目录。两个 `.sbatch.in` 都是 ≤2h 模板，所有 `@...@` 必须由 Root 物化，检查 LF、资源和来源哈希后提交。
3. `close_pilot.py` 消费 Root 留存的实际 `sacct -P` 父作业行（`JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList`），计算完整 allocation 核秒/2000。所有实际失败和初始化/导出时间均计入；不加 batch/extern，不用 QM child CPU 时间替代。只有构象全12任务成功率≥99.5%且≤11.7分配核秒/构象，并通过实际终态/读回/worker 闭合后才满足试点门槛。任何本目录 CLI 都不提交全量。

`--root-preflight` 读取既有 `execution/submit_reviewed.py` 产生的 intent/receipt，复核精确配置 SHA、1小时新鲜度、节点、全部用户声明内存85%和保留200GB配额。这是既有 Root 提交证据，不是新增用户审批。

几何适配先调用原只读 `read_native`，核 payload SHA 和原子顺序；随后 `geometry.adapt_native` 以已验收 UFF 坐标替换对象坐标，按该几何重算 4Å pair 集并保留源图的键。原函数和原文件均不替换。原 PM7 坐标 SHA、UFF 坐标 SHA、Z+UFF坐标 SHA 分开记录。`native.energy=None` 使旧源 PM7 HOF 不进入新几何 Q02；Q02 保留 NULL，并显式标 N/A 原因。其它任务、版本、关键词、900秒调用超时和 QC 不放宽。历史输入模板的说明性注释仍含 “native PM7” 字样；真实传入及所存坐标为 UFF，实际输入 SHA 和 `geometry_source=uff_sprime` 才是几何证据，不能按旧注释推断输入。

`raw_archive.py` 复用 WP5 的 failure/audited-record 保留判定及 output-bundle 格式，用新的 FULL-synchronous SQLite/gzip 容器保存；每个保留调用在允许本地 scratch 删除前实际读回并核 SHA。输入正文禁止归档。`RawReader.get(record_id,calc_type,execution_id)` 可读回失败/审计输出；显式 execution ID 防止把部分尝试当完整结果。新复现 manifest 引用原冻结软件/环境/科学协议，同时绑定本轮代码、选择清单和新 audit membership。每 worker 的 raw 和解析 staging 有独立预算，合计计入8GiB试点输出上限。

永久输出沿 WP5 float64 registry-cell 家族 schema，并增加 UFF 来源/坐标 SHA、角色和 Q02 适用性字段。每个试点字段按 float64 bits/类型全量读回；没有 pickle 科学落盘。内部 JSON staging 对非有限 float 使用显式位模式标签，不输出非标准 NaN token。正常/失败均等到已经运行的 worker 退出，不用 terminate/scancel；worker 显式 close LMDB/scratch 后，父进程核16个真实 child 退出码与 join。

受控验证（只合成数据，不启动 QM/LMDB/GPU/Slurm）：

```bash
python workflows/data_v1_final/pprime/test_pprime.py \
  --config configs/data_v1/pprime/pilot_v1.json \
  --sb2-selection /absolute/path/to/conformers/selection.py
```

真实试点尚需 Root 实际提交。P′ 的全人群异常扫描、P/P′ 逐字段分布对比、最终共同人群及真实输出矢量参考系核验尚未完成；合成序列化通过不代表这些科学验收通过。N=1 不入此次试点，选择报告会统计其候选数，不能复制构象凑2条。

实际受控验证：2026-10-25在compute-0-20，10项PASS/退出0/11.655秒，日志在仓库外本轮 `control/sb4_synthetic_v1.log`，执行收据为 `control/sb4_sb5_code_tests_v1.json`。QM_calls=0、LMDB_opened=false、GPU_used=false、Slurm_submitted=false。
