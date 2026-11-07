# 模型 v3 网格交接

状态：启动接口已实现；M1/M2已实际接入，逐字段过拟合与SDP结果见[M2结果](M2_V31_RESULTS.md)。M3/M4 实验、两份最终冻结配置与代码标签尚待完成。
本文当前不能当作模型/配方/B* 已冻结的声明，也未启动性能实验。
最终科学口径见 [PREREG_round1.md](PREREG_round1.md)。

在开发服务器 `/share/home/zixiao/descriptor_analysis/MFM_model_v3` 使用
`tools/model_v3/v2_prepare_grid_cell.py`。它只生成配置和 Slurm 脚本；加 `--submit`
才提交。训练在指定开发计算节点执行，一卡一实验，不在登录节点或付费学校服务器运行。
模型配置和配方配置必须来自实际 M5 交付且 `status=FROZEN`；配置内含实际代码标签与 B*。
本阶段尚无这些最终文件，不用候选配置、6M 临时预算或 64M 上限代填。

下面是任意主网格单格的完整启动接口。先将大写变量设为实际交付/选择的值：

```bash
cd /share/home/zixiao/descriptor_analysis/MFM_model_v3
/share/home/zixiao/.conda/envs/chemprop/bin/python tools/model_v3/v2_prepare_grid_cell.py \
  --model-config "$MODEL_CONFIG" --recipe-config "$RECIPE_CONFIG" \
  --root "$V31_ROOT" --subset "$TRAIN_SUBSET" \
  --training-view "$TRAINING_VIEW" --normalizations "$D4_MAPPING" \
  --condition "$CONDITION" --molecules "$M" --k "$K" --seed "$SEED" \
  --order fixed_random --output "$RUN_OUTPUT" \
  --node "$COMPUTE_NODE" --gpu-uuid "$GPU_UUID" --python "$GPU_PYTHON"
```

`V31_ROOT` 是实际 D6 的 schema/manifest 根目录；加载器按manifest.split_roots读取
实际TRAIN/FULL共享LMDB及其ID map链接，schema与compact可以位于不同共享文件系统。
`TRAIN_SUBSET` 是对应 M 的真实 TRAIN
分子 ID Parquet。`TRAINING_VIEW` 为窗口二正式冻结清单；`D4_MAPPING` 为模型加载器
按字段消费的正式 TRAIN 参数映射（原 D4 的接口翻译，不能另拟合）。`RUN_OUTPUT`
为仓库外新的绝对输出目录。命令生成 `<RUN_OUTPUT>.input.json` 和 `.sbatch`，并打印
可执行的 `sbatch` 命令。确认使用该实际科学格子后，执行打印的命令，或初次生成时加
`--submit`；已生成时直接提交现有脚本，不重复生成覆盖。

`COMPUTE_NODE` 与 `GPU_UUID` 选择实际可用开发卡；脚本使用已有 UUID flock。
5090 的 `GPU_PYTHON` 使用项目既有 stage43 cu128 环境；3090 使用
`/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python`；4090 使用 chemprop 环境。
不为选择环境额外跑冒烟测试。

| CONDITION | M / K | SEED / 其他参数 |
| --- | --- | --- |
| S、P | 120000 × 1/2/5/all；240000/600000/1126937 × 1；1126937 × 2/5 | 0 或 1 |
| D | 上述十字七格，不含 1126937 × 2/5 | 0、1 都做 |
| Sprime | 120000 × 1/all | 自动使用 UFF 的普通 M17 集合 |
| S、P | 120000 × 1 | 顺序对比时将 `--order` 改为 energy 或 diversity |
| Sprime、Pprime | 120000 × 实际共同 k* | 另加 `--shared-k-star "$K_STAR"`，K 与 K_STAR 一致 |

最大 M=1,126,937 是用户在2026-11-06批准的最终D5全池，替代原120万格；
使用最终D5嵌套清单，其余格子/种子/判据不变，见预注册修订。

K/K_STAR 的 all 均写字符串 `all`。S/P/D 使用 PM7；Sprime/Pprime 自动使用 UFF。
Pprime 使用独立 Pprime D4，训练以 M18 且排除 M14；不能因旧 Pprime 标签存在而
扩大集合。Sprime 使用普通 M17 且排除 M14。未交付的能量/多样性排列、缺少的实际
分子 ID 或 Pprime 资格都不能由加载器猜测。D6 若不支持任务书某个 M，须保留实际缺口，
不能更换人口或将较小 M 冒充该格。正式 k* 仍从实际开发读数按 PREREG 求出。

每次训练保存 `configuration.json`、`architecture.json`、`losses.csv`、滚动
`recovery.pt`，并在 1/2/4/8/16/32/64M 及实际终点保存样本检查点。
训练完成不等于开发评价完成。开发读数使用冻结的 TRAIN 内层任务集；FULL/ROUTINE
与 TRAIN_UNSEEN_CONFORMATION 单独记录，不用于替代开发选型，不访问下游 TEST。

恢复时复制该次实际 input JSON 到新文件，只修改 `output` 为新目录并加入
`resume` 指向原 `recovery.pt` 或实际样本检查点；其余科学参数一致。提交相同 GPU
Slurm 脚本，将 `--configuration` 指向新 JSON、日志指向新路径。恢复继续原样本时钟、
优化器及 RNG，不从零开始并冒称续跑；旧失败/日志/检查点保留。

M4全量平台曲线可分段取得读数：实验JSON的 `samples` 始终保留完整计划预算
（最多64M），`run_until_samples` 仅指定本段终点，允许1/2/4/8/16/32/64M中尚未到达
且不超过预算的检查点，或完整预算本身。每段以实际样本检查点正常返回并标
`SEGMENT_COMPLETE_DEV_EVALUATION_PENDING`，不冒充整次训练完成。完成该点的冻结
TRAIN开发评价后，按既定平台规则决定后续倍增；继续时新JSON仅更改输出/恢复路径及
`run_until_samples`，恢复原优化器、RNG、梯度历史和样本时钟，学习率仍按原 `samples`
计划计算。已观察平台可停止，未观察平台不能把64M上限冒充B*。该入口尚未用于实际M4。

最终交接还需在此补入：两份实际冻结配置路径、代码标签、D6/正式 D4 路径、
M3/M4 结果页与实际 B*。这些依赖实际实验完成，当前未填写候选胜者或虚构数值。

2026-11-06磁盘规则：正式D6直接读取唯一共享compact副本，不分发节点本地副本。
任何新增缓存/传输/临时输出均先在实际节点核实目标文件系统字节/inode，合并同盘并发峰值；
根盘保留max(10GiB,10%)，共享账户保留既有100GB底线。新训练检查点在首次写入前估算
新增文件峰值，并于序列化期间复查余量；不足即停止新增写入并保留原检查点/已写partial，
不自动清理文件。运行前仍须按共享STATUS协调实际账户quota及各窗口待写预算。

已结束的S/M2/回归观察已按真实作业终态退役。后续训练须在实际计算节点启动
`tools/model_v3/v2_watch_disk.py`，每5秒观察根盘/输出盘字节与inode，并绑定实际账户quota：

```bash
python tools/model_v3/v2_watch_disk.py \
  --output "$RUN_OUTPUT" --state "$DISK_STATE" --node "$COMPUTE_NODE" --jobs "$SLURM_JOB_ID" \
  --growth-bytes "$GLOBAL_MODEL_FUTURE_BYTES" \
  --quota-reference "$QUOTA_REFERENCE" --quota-filesystem "$OUTPUT_FILESYSTEM" \
  --quota-concurrent-bytes "$OTHER_WINDOWS_FUTURE_BYTES"
```

此观察须与训练并行，正常结束时退出；状态由主监控读取。`QUOTA_REFERENCE` 使用实际
原生配额发布器的当前快照；`OUTPUT_FILESYSTEM` 为对应的 `/lfshome` 或 `/share`。
快照须匹配真实UID/文件系统/schema，使用发布器已有有效时间且age在0..5秒；不会重写
时间冒充新观测。quota扣账户100GB、同盘全局未来增长、其他窗口并发及8GiB突发余量。
增长预估全节点合计，不能按节点重复预算，也不是固定输出上限；每次启动更新实际预估。
后续M3/M4检查点拟用共享Lustre；原NFS输出/检查点保留，不自动迁移或清理。
容量不足/未知时仅暂停明确绑定的本UID/节点/Slurm作业，保留原训练进程；空间恢复后，
须在实际节点复核根盘/输出盘及并发quota预算，再对原作业发送CONT并重启观察。
主进度观察器同时检查其状态新鲜度，不把观察进程失联当作已完成保护。
