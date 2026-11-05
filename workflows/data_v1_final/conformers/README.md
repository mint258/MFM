# S′ 补齐试点

这是新的只读来源适配器。旧 S′ 科学函数由 `pilot_v1.json` 固定 SHA 导入；不会调用旧 main、队列、提交器或清理代码。当前代码只准备和运行试点，不自动提交全量。

`prepare_pilot.py` 在 16 核 Slurm allocation 内，以 DuckDB 16 threads 扫描闭合分子元数据，按失败类型、file_group、重原子数和 Se/P/Si 类别固定 hash 分层选 320 个待补齐分子及 16 个充足对照。它物化选中的原记录指针和既有成功构象，不打开 LMDB。需要核验 1.24 GB 原记录索引 SHA，检索五组旧 S′ parquet，因此即使只选 336 个分子也有实际 I/O 成本。

`run_pilot.py` 必须在 compute-0-14 至 compute-0-19 的 16 核 allocation 内运行，使用 16 个 spawn workers。每个 worker 单线程 UFF。普通不足分子生成 min(10N,300)；技术/部分失败只用新种子重试一次、嵌入 maxIterations=400。UFF 的 2000 步、1e-6 能量容差、1e-4 力容差和 0.5 Å 固定源索引重原子 RMSD 不变。旧有效构象保留；追加候选先按阈值选择，再按最大最小 RMSD 补齐并标记。没有足够真实收敛候选时保留失败，绝不复制行凑数。

命令（合并后由 Root 使用仓库绝对路径）：

```bash
python workflows/data_v1_final/conformers/prepare_pilot.py \
  --config configs/data_v1/conformers/pilot_v1.json \
  --root-preflight /absolute/control/submissions/dv1_sb2_prepare_v1.intent.json \
  --output /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/conformers/prepared_v1

python workflows/data_v1_final/conformers/run_pilot.py \
  --config configs/data_v1/conformers/pilot_v1.json \
  --root-preflight /absolute/control/submissions/dv1_sb2_fill_pilot_v1.intent.json \
  --prepared /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/conformers/prepared_v1 \
  --output /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/conformers/pilot_v1 \
  --workers 16
```

两个脚本消费 Root `execution/submit_reviewed.py` 的 intent JSON：实际 request 必须 pin config 的 path/bytes/SHA；observed_at 不超过 1 小时；节点、全部用户声明内存、85% 上限和真实 quota 都由 receipt 绑定。Root 的 `estimated_peak_output_bytes` 至少为 8,589,934,592 B；加上本步输出后配额仍保留 200 GB。元数据准备建议 16CPU/32GiB/1h（最多16分配核时）；生成建议 16CPU/64GiB/4h（最多64分配核时）。这只是资源上限，不是实测成本预测。模板中的节点、intent 和新输出路径须由 Root 渲染后，核验 LF、源码 pins 和现场资源再提交。

环境使用既有 `/share/home/zixiao/.conda/envs/chemprop/bin/python`，RDKit 数字版本必须为 2025.09.5。若所在环境需要已验证的额外 pyarrow/duckdb 依赖路径，由 Root 在渲染后的脚本绑定，不能改 RDKit/xTB/MOPAC 版本。

所有产物在 Git 外的新目录，已有路径一律拒绝覆盖。新候选先保留在内存；非审计的成功样本解析、身份/立体检查后只保留所选几何。失败及固定 hash 抽样约 1% 的成功分子保存全部候选坐标、优化器状态和种子。每个分子的复现包都保留所选坐标、原子序列、几何 SHA、构象顺序；输入包保留原 LMDB payload SHA 和来源指针。持久 parquet 坐标 float64，写后全试点逐条重算几何 SHA。无新 pickle、无 GPU、无量化调用、无删除旧文件。

`test_selection.py` 的十个标准库测试覆盖阈值边界、最大最小补齐、不足不复制、几何相同但候选 ID 不同、重复 ID 拒绝、NaN 拒绝、三种顺序的排列及确定性。它们不是 RDKit 或真实样本验收；实际试点仍须由 Root 运行和审阅。

试点的构象统计和原 PM7 能量顺序只作诊断。原生 energy 是旧 S′ 固定立体的锚点来源；最终 v1 PM7 能量排序应接入 canonical WP5 生成热，再冻结正式顺序。最终共同人群需接入 SB-1 冻结的 TRAIN+ROUTINE VAL 分子清单，不能把当前元数据 source_role=FULL 自动改为 VAL。
