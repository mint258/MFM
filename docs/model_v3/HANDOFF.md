# 模型 v3 网格交接

状态：启动接口已实现；M1/M2已实际接入，逐字段过拟合与SDP结果见[M2结果](M2_V31_RESULTS.md)。M3/M4 实验、两份最终冻结配置与代码标签尚待完成。
本文当前不能当作模型/配方/B* 已冻结的声明，也未启动性能实验。
最终科学口径见 [PREREG_round1.md](PREREG_round1.md)。

在开发服务器 `/share/home/zixiao/descriptor_analysis/MFM_model_v3` 使用
`tools/model_v3/v2_prepare_grid_cell.py`。它只生成配置和 Slurm 脚本；加 `--submit`
才提交。训练在指定开发计算节点执行，一卡一实验，不在登录节点或付费学校服务器运行。
模型配置和配方配置必须来自实际 M5 交付且 `status=FROZEN`；配置内含实际代码标签与 B*。
本阶段尚无这些最终文件，不用候选配置、6M 临时预算或 64M 上限代填。

已交付的数据绑定如下，直接读取共享文件，不复制到节点。依据窗口二
`configs/data_v1/window2_D6_final_DELIVERY.json`、`final_Common_D5_D7_v1_DELIVERY.json`：

```bash
V31_ROOT=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/export/D6_full_v31_20261105_v1/compact
TRAINING_VIEW=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/training_view_v1.json
D4_MAPPING=/lfshome/zixiao/data_v1_20261025/window2_TRAIN_normalization_parameters_20261107_v1/routes.json
D5_FINAL=/lfshome/zixiao/data_v1_20261025/window2_final_population_20261105_v1/D5
```

主网格的 `TRAIN_SUBSET` 按 M 绑定；这些是最终嵌套人口，不将旧 provisional 的
`train_all` 用作获批的 1,126,937 全池。

| M | TRAIN_SUBSET | 窗口二交付字节 / 分子数 |
| ---: | --- | ---: |
| 120000 | `$D5_FINAL/train_120000.parquet` | 939915 / 120000 |
| 240000 | `$D5_FINAL/train_240000.parquet` | 1574278 / 240000 |
| 600000 | `$D5_FINAL/train_600000.parquet` | 3409568 / 600000 |
| 1126937 | `$D5_FINAL/train_all.parquet` | 6337465 / 1126937 |

阶段5/6代理对比继续使用已运行的原240k及其正式S240k绑定，不切换成员；
上表用于M5性能网格。M4全量S/P则不指定子集，使用D6实际完整TRAIN 1,194,551。
D6的FULL实际13,815分子用于独立未见分子诊断，不能由较早Common VAL 7,567推断其数量。
上述数量来自生产者交付，不新增数值扫描或人口复核。能量/多样性顺序由D6中的正式D7映射读取。

下面是任意主网格单格的完整启动接口。其余大写变量使用实际冻结/选择的值：

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
为 /lfshome/zixiao/model_v31_20261105/ 下新的绝对输出目录；先将实际训练输出根登记到仓库外 runs/model_v31_20261105/model_output_budget.json 的 roots，并按实际新增峰值更新同一全局预测（登记方法见 M3_M4_CONTINUATION.md）。命令生成 `<RUN_OUTPUT>.input.json` 和 `.sbatch`，并打印
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

全量S/P各保留seed0/1的实际检查点曲线，使用同条件、同选定配方/人口、同检查点的预训练种子标准差（ddof=1）。对应首段条件模板见followon_templates.json的M4_full_S/P_seed0/1_segment1M；未决模型/配方参数先由实际M3/M4结果绑定。种子读数不足则B*待定，不用S/P之间的差异、240k代理或下游readout/bootstrap噪声代替。此处补齐标准差的实际来源，原翻倍平台判据及每次64M预算保持。

最终交接还需在此补入：两份实际冻结配置路径、代码标签、
M3/M4 结果页与实际 B*。这些依赖实际实验完成，当前未填写候选胜者或虚构数值。

2026-11-06磁盘规则：正式D6直接读取唯一共享compact副本，不分发节点本地副本。
任何新增缓存/传输/临时输出均先在实际节点核实目标文件系统字节/inode，合并同盘并发峰值；
根盘保留max(10GiB,10%)，共享账户保留既有100GB底线。新训练检查点在首次写入前估算
新增文件峰值，并于序列化期间复查余量；不足即停止新增写入并保留原检查点/已写partial，
不自动清理文件。运行前仍须按共享STATUS协调实际账户quota及各窗口待写预算。

主网格脚本现在复用已在M3实际训练中使用的
`tools/model_v3/v2_run_development.sbatch v31 CONFIG GPU_UUID PYTHON`。
该入口在任何训练更新前要求输出根已登记到同一个全局模型预测，核实实际根盘/输出盘字节与inode、
原生账户quota与全部并发增长，获取既有UUID锁并确认所分配卡无其他计算上下文；
随后启动原持续磁盘观察与真实W&B登记。科学JSON原样传入v2_train_v31.py，
不会复制数据、改变抽样/优化器/RNG或补写未决冻结参数，也不必另起第二个磁盘观察器。

运行期保护状态仍在仓库外runs/model_v31_20261105/M3_controlled_<job>.state.json。
quota快照须沿用发布器的真实UID/文件系统/schema及有效时间，包含账户100GB底线、
其他窗口未来增长和8GiB突发余量；不会改写时间冒充新观测。容量不足/未知只暂停已绑定
自有作业并保留原进程，恢复时仍须在实际节点重核容量/并发后CONT，不能将未知容量当作通过。
后续性能格子的新增峰值须纳入真实全局预测；当前开发100GB不是每格再加一份，也不是固定输出硬上限。
本次仅修正交接入口，未提交或启动性能实验；网格启动相关4项定向单测验证真实命令分派与参数保留，
无额外模型冒烟或完整回归。
