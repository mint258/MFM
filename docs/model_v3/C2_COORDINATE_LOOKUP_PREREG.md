# C2 坐标去噪查表：方法与预注册草案

2026-10-25（Asia/Shanghai）。状态：方法参数已冻结，组件和真实SDK路径验证通过，
**未运行真实拟合或验证**。用户已明确答复：“按局部几何分桶查表，预测三维去噪向量（建议）”。
此决定与当前实现一致，不改变下文数学、选择或预算字段。这是独立分析项，不作架构选择门槛。
本规则及代码须由主agent提交/公开后，才能生成并冻结真实源选择；实现测试不代表
科学验收。旧Srepair GUIDE_STOP、旧模型和数据均不修改或重启。

## 输出及数学目标

已知干净坐标x、加噪坐标y，拟合目标为ε=y−x，单位Å。模型只读取输入元素类型
及noisy y：枚举同分子内0<||y_i−y_j||<5 Å的有向邻居，以有序元素对及
floor(distance/0.1 Å)构成50个距离桶。系数表为a[type_i,type_j,bin]。

ε̂_i = Σ_j a[type_i,type_j,bin]·(y_i−y_j)，x̂_i=y_i−ε̂_i。

同一桶的多个邻居贡献在线性设计矩阵同一列相加。相对坐标和有向边从noisy
几何构造；不使用clean距离筛选特征、不使用目标元素、不读取分子ID作为特征。
分子ID只作预先冻结的成员/角色核验。零距离对不定义径向贡献，贡献为零。
没有邻居或TRAIN从未出现的桶，系数精确为0，输出保持noisy坐标；全部原子仍入分母。

将每个原子的三个坐标堆成矩阵A和向量b，目标是

L(a) = ||Aa−b||² / n_TRAIN_atoms + 1e−4·||a||²。

FP64 SciPy LSQR接收LinearOperator A/√n_atoms及b/√n_atoms，damp=√1e−4。
等价地，若不缩放A/b，damp²必须为1e−4*n_atoms，**不是仅λ，也不是3*n_atoms*λ**。
相同标量a用于三个坐标轴，ridge也不依赖轴，故目标和预测保持联合旋转/反射
一致、平移不变、原子置换一致。正ridge确保唯一正则最优解。

固定atol=btol=1e−8、conlim=1e8、iter_lim=500；只接受LSQR stop 0/1/2/4/5且
有限解，0仅为LSQR的零解/退化信息终态。其他终态标记FAILED，不扩大迭代或依据
验证结果调ridge。合成测试直接对照小active-column解析解
(AᵀA+λ*n_atoms I)⁻¹Aᵀb，并验证复制TRAIN全体记录后解不变。

## 稀疏容量与停止条件

固定119²*50=708,050列，零基原生元素0–117合法，保留pad索引118不作为真实原子。
矩阵为CSR；生成每条有向边最多三个COO entry；只沿A和Aᵀ做稀疏matvec，
不生成708,050²的稠密Gram。LSQR的标量ridge通过damp传递，亦不扩充稠密单位阵。

固定TRAIN8192条原生结构/构象记录，最多524,288原子；最多16,000,000条有向边、
48,000,000个未合并COO entry。保守容量估算使用int64索引，保留三份CSR、一份
完整COO以及LSQR向量：该最大边界约3,614,561,432 bytes（约3.37 GiB），
再受8 GiB矩阵预算约束。估算不冒充总RSS：Python对象、Torch/原生reader另计。
进程RSS≤24 GiB；主agent还须为整个进程树配置自己的外层监督和Slurm32/64 GiB。

CPU Slurm至少16 CPU、隐藏CUDA；墙钟3300秒，预留30秒收尾；输出≤128 MiB。
LSQR每次matvec检查资源/墙钟，不等待迭代全部结束才检查。任何已选记录触及
原子/边/矩阵/时间上限，保留失败证据，禁止丢弃记录、增预算或自动调整超参数。
输出仅新模型侧外部目录，原LMDB只读、不删除已有文件、不写数据线目录。

## 先固定元数据，再解码几何

选择seed=20261025，NumPy PCG64；TRAIN使用此seed，PRETRAIN_VAL使用seed+1。
各角色从原逻辑索引作不放回候选抽样，最多65,536候选；只根据原atom-count元数据
筛0<N≤512，按候选顺序取TRAIN8192、PRETRAIN_VAL1024条。候选不足或TRAIN
原子和超524,288即失败，不扩大候选、不重抽、不截断到更小人口。记录数不称为
独立分子数，实际unique molecule数另由成员元数据提供。

每个选择成员冻结logical index、record_id、molecule_id、原子数和原payload SHA。
所有TRAIN/PRETRAIN_VAL成员的record_id及molecule_id不得交叠。先独立prepare并
写出选择JSON/raw SHA，随后run必须重放出同一份元数据选择，才可打开native记录。
prepare读取身份、atom-count、source哈希和LMDB stat，native_geometry_records_decoded=0。
plan内部source_request_sha256是规范JSON内容hash，用于对象重放；CLI参数和最终
input_binding/COMPLETE另绑定源request文件的原始字节SHA。两种hash不混称。
真实run的每次_native读取都核验原payload SHA及原子顺序；几何按原source geom
degrade配置生成，seed0、epoch0、epoch参与noise hash、sigma0.1 Å、无角度/键长扰动。

## PRETRAIN_VAL角色的证据链

这里不根据“full”字样猜测角色，也不使用下游final：

1. 冻结phase59协议raw SHA `cde2ca717934955f340a5f160a3390ff1dd6eda12c9ffbab93fc54fce0c8a2a4`，
   明列artifacts.full_validation_manifest及validation_population_policy的
   full_declared_validation终态。该旧协议总人口与后来WP5人口不同，不混用记录数。
2. WP5 population manifest raw SHA `d21bae7f7b6c1dfbfe9342635ded80a55ddc05baba46ebfaa66cb7831866b96e`，
   明确FULL_anchor_promotes_entire_TRAIN_component、routine_is_FULL_monitor_subset，
   当前train11,104,772、full127,082记录；原population脚本保留组件/原角色来源。
3. `workflows/sprime_s/scripts/prepare.py`将该已闭合population的split train/full分别
   投影到train_records/full_records，`prepare_s_training_inputs_v1.py`将每个native
   metadata成员逐列join回同一formal_record_index并断言其原split符合角色。
4. S输入manifest raw SHA `2f69b672350744369b08c672b62e3d276487714abc97b766a12140ec5af59997`
   绑定这些Arrow/atom-count文件。原S runner v8的evaluate(role)明确用
   MappedRecordIndex(role)，validate()只调full/routine；它们是预训练几何/结构验证。
5. 新provider仅把TRAIN映射该原train，把PRETRAIN_VAL映射该原full，复用原
   MappedRecordIndex/ManifestViewsDataset；不调用任一下游dataset、readout、final scorer。

实际source request同时绑定上述文件、原B1 S配置、原snapshot、transport及全部
新/旧reader代码SHA。原reader缓存改为0字节/1 entry，仅限制内存，不改变样本或
噪声规则。D1–D6仍未交付；上述是既有S人口，不声称D5新split或新属性标签到位。

## 指标与历史lookup

只在固定PRETRAIN_VAL上一次性报告，不用于调参/选模：

- displacement_vector_MSE_A2：Σ_i||ε̂_i−ε_i||²/N，Å²。
- coordinate_vector_RMSE_A：√(Σ_i||x̂_i−x_i||²/N)，Å。
- coordinate_component_RMSE_A：√(Σ_i||x̂_i−x_i||²/(3N))，Å。
- explicit_sigma_normalized_component_MSE：同平方和除3Nσ²，显式dimensionless；
  不把这个数写成Å位移MSE或RMSE。
- 同一x̂产生的local_pair_RMSE_A：所有clean distance<2 Å、i<j原子对距离RMSE，
  仅评价时使用clean局部pair掩码，绝不作为模型输入筛边。无合格pair记None。
- noisy identity的对应基线，known/unknown directed-edge计数，以及全部原子/对分母。

旧lookup只拟合独立pair clean距离，未重建XYZ；其约0.0413 Å属于旧人口局部pair
RMSE，不继承为本方法的坐标/噪声结果。本方法通过同一整分子x̂给出所有指标，
不能拿独立不一致的pair预测直接冒充整分子几何。

## 外部可控执行接口

`tools/model_v3/run_coordinate_lookup.py`不提交Slurm，有三个显式阶段：

1. `--mode bind --code-sha ACTUAL_COMMIT --preregistration-sha PUBLIC_RULES_COMMIT`
   在新外部output-root封印source_request.json，无native几何解码。
2. `--mode prepare --request ... --request-sha256 ...`，关闭所有source后才写出
   selection_plan.json及其raw SHA，仍无native几何解码。
3. `--mode run`须同时提供源请求和已封闭选择及raw SHA，重复核对元数据后，先
   TRAIN sparse fit，再单次PRETRAIN_VAL；全程持久offline W&B和资源监督。

原SDK保留。source/输入读者/LMDB stat/元数据结束再核验，safe JSON表和result
在新外部目录生成，SDK.finish返回后最后写COMPLETE；失败写FAILED，永不覆盖旧路径。
主agent完成组件/接口测试和公开预注册后才可调度真实bind/prepare/run。当前没有
真实拟合、性能数字或科学选模结论；数学合成结果另随实际Slurm证据登记。

### SDK及原snapshot绑定补充

真实fit的SDK目录遵循既有supervisor/archiver的规范：WANDB_DIR=output，
WANDB_CACHE_DIR=output/cache，WANDB_DATA_DIR=output/wandb_data，
WANDB_CONFIG_DIR=output/wandb_config，MODE=offline。创建普通自有目录并绑定
环境后才import/init W&B，拒绝canonical路径为symlink。SDK配置和result记录实际路径。
旧425实现的sdk_cache/sdk_data/sdk_config布局不作为真实运行依据，旧测试证据保留。

独立`tools/model_v3/probe_coordinate_lookup_wandb.py`使用真正的offline SDK，
写两条commit history并finish，原生DataStore再读回。它调用固定已测的
`MFM_model_v3_profiler_v2/tools/model_v3/runtime_monitor.py`的owned_output_bytes，
raw SHA `dbe875ab7ceec7e5002c5b70bff0608e3506f7451bdacd38e5f5bfc0700663fe`；
核验latest-run、debug.log、debug-internal.log及per-run debug-core.log四类真实link。
不mock该真实探针、不改变census/allowlist、不读取native记录、不作optimizer更新。
探针4520432已真实通过，具体证据见下文；不拿unit SDK fixture当持久性证据。

原snapshot raw SHA预先固定为
`d2e1ace1636485cd3dd0106b1177518dd37eb9741919195a9efcd846c1c2242f`。
bind和prepare/run只读复用固定已测
`MFM_model_v3_profiler_v2/tools/model_v3/native_runtime_bindings.py`，raw SHA
`ed2e069d408a671c93e8c42ec827162db3d98333587c08c9d37010fc6d7e464d`由机器值绑定，
并加入source inventory。该helper核验普通自有文件、稳定身份及原始raw SHA；
之后仅由本树冻结旧v2 adapter的deepcopy投影st_dev，inode/size/mtime不放宽。
不改原JSON、adapter或A树。每节点的实际device观察另存在prepare/input receipt，
成员选择JSON只保留稳定raw path/bytes/SHA，不用设备号制造跨节点成员漂移。

## 已执行的实现证据

4520419真实Slurm COMPLETED/0:0、19秒、16 CPU；核心10项合成测试全部PASS，
pytest2.95秒、完整子任务16.7231秒。源码前后SHA相同：

- core `a25fdb1217d969c05902bab5c45c292ec2a101e920bcc758f683e74fde6fd6c1`
- test `53617ba39575e29abff523df8b52bafd4c8e68a77388b6cf10c38af4805c3386`

原始证据为`runs/model_v3_20261025/unit_checks_4520419/coordinate_lookup.json/.xml/.log`。
覆盖解析ridge解、复制数据不变、noisy-only特征、E(3)/置换一致、未知/孤立原子
全分母、退化零表、无dense Gram/矩阵转dense、角色与成员交叠拒绝、资源和精确
人口边界、source-bound JSON。该证据只证明合成实现，不证明真实S读取/拟合或SDK持久性。
新source/runner组件已由431补验，整树整合由主agent继续统一调度，源码保持冻结。

4520425实际Slurm COMPLETED/0:0、5秒；其时source/runner九项unit测试PASS，
pytest0.64秒、完整子任务4.6410秒，源码前后SHA一致。它使用明确标记的unit
Source/SDK fixture，只验证调用顺序和收尾，未验证真实SDK路径兼容性。
日志规范修复和固定snapshot binder接线在425之后发生，需要各自的新证据。

425原JSON/XML/log保持不变。其六个源文件已经在外部
`runs/model_v3_20261025/source_snapshots/unit_4520425_reconstructed_v1/`保留，
每一文件SHA精确匹配实际425 receipt。RECONSTRUCTION.json明确说明这是测试后
按确定补丁逆向恢复的exact bytes，不声称为测试前capture；其中数学两源亦与419相同。

4520431实际Slurm COMPLETED/0:0、7秒；修订后的source/runner共15项PASS，
pytest0.52秒、完整子任务6.5851秒，前后全部六源SHA相同。数学两源仍是419版本；
新source为`37ea81d4787626f4bd5244570b746ab268bf87d721ecf74b1e5081855ca4605c`，
新runner为`bcec386e3e4a4b95d36589bf79f7712983cdc9901a4357ad7c9f28102c7a2730`。
新增验证覆盖canonical SDK目录在import前绑定、symlink目录拒绝、真实原snapshot
固定binder的只读/独立副本，以及未注册snapshot pin/path拒绝。原始证据
`runs/model_v3_20261025/unit_checks_4520431/coordinate_lookup.json/.xml/.log`。

4520432实际Slurm COMPLETED/0:0、5秒，外层监督COMPLETED/exit0、
first_failure=null、retirement=null、remaining=[]。真正W&B0.28.1 offline run
`btklm5us`的两条commit history已由原生DataStore读回，4类真实symlink全部通过
固定census。4个观察点的owned bytes为8,915/8,915/8,915/13,883；这些是各观察时刻
的目录统计，不冒充CPU进程峰值。原SDK stream为3,820 bytes，raw SHA
`2efa62d312377cf3c4e2d46bc6428b9a94d160a05a73f85475d8f2ebf7ce08fd`。
probe源SHA `bd07334b70b58e832a88e85df5b2d930dfb2082190997a27bb0bb6658738280c`，
runner及固定monitor的前后SHA也相同。零native记录、零optimizer更新、未初始化GPU、
未在线同步。证据为`coordinate_lookup_sdk_4520432/verification.json`及
`coordinate_lookup_sdk_supervisor_4520432.json`，均在同一外部runs/model_v3_20261025根。

## 后续实际三阶段CLI（仅供主agent在已核验Slurm内执行）

先完成checker、代码提交、整树回归和公开预注册。以下不提交Slurm，不代表当前已
执行真实数据；每阶段使用新job和新output，上一阶段须实际COMPLETED/0后再传其
关闭的receipt。`C2_CODE_SHA`由实际执行工作树的完整40位Git SHA绑定，
`C2_PREREG_SHA`是公开规则的完整40位SHA，两者不可因API发布树相同就混用。

三阶段共同环境（在各自compute-0-20、≥16CPU、32GiB Slurm allocation内）：

```bash
PROJECT=/share/home/zixiao/descriptor_analysis
C2_TREE=$PROJECT/MFM_model_v3_c2
C2_RUNS=$PROJECT/runs/model_v3_20261025
C2_PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
cd "$C2_TREE"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=16 MKL_NUM_THREADS=16 OPENBLAS_NUM_THREADS=16
export PYTHONPATH="$C2_TREE/current:$PROJECT/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
```

bind：从已存在的固定源文件生成封印request，零native几何解码。

```bash
: "${C2_CODE_SHA:?actual committed code SHA is required}"
: "${C2_PREREG_SHA:?published preregistration SHA is required}"
C2_OUT=$C2_RUNS/c2_bind_${SLURM_JOB_ID}
"$C2_PY" -u -B "$C2_RUNS/run_cpu_supervised_v3.py" \
  --output-root "$C2_OUT" --record "$C2_RUNS/c2_bind_supervisor_${SLURM_JOB_ID}.json" \
  --wall-seconds 3300 --rss-limit-bytes 25769803776 -- \
  "$C2_PY" -u -B tools/model_v3/run_coordinate_lookup.py \
  --mode bind --output-root "$C2_OUT" \
  --code-sha "$C2_CODE_SHA" --preregistration-sha "$C2_PREREG_SHA"
```

prepare：C2_BIND_DIR必须来自上一步真实关闭的目录，用其receipt读取raw SHA，禁止手抄。

```bash
: "${C2_BIND_DIR:?actual closed bind output directory is required}"
C2_REQUEST=$C2_BIND_DIR/source_request.json
C2_REQUEST_SHA=$("$C2_PY" -B -c 'import json,sys;print(json.load(open(sys.argv[1]))["request"]["sha256"])' "$C2_BIND_DIR/binding_result.json")
C2_OUT=$C2_RUNS/c2_prepare_${SLURM_JOB_ID}
"$C2_PY" -u -B "$C2_RUNS/run_cpu_supervised_v3.py" \
  --output-root "$C2_OUT" --record "$C2_RUNS/c2_prepare_supervisor_${SLURM_JOB_ID}.json" \
  --wall-seconds 3300 --rss-limit-bytes 25769803776 -- \
  "$C2_PY" -u -B tools/model_v3/run_coordinate_lookup.py \
  --mode prepare --output-root "$C2_OUT" \
  --request "$C2_REQUEST" --request-sha256 "$C2_REQUEST_SHA"
```

run：C2_PREPARE_DIR必须来自实际关闭且零native解码的prepare；读取其plan原始SHA。

```bash
: "${C2_BIND_DIR:?actual closed bind output directory is required}"
: "${C2_PREPARE_DIR:?actual closed metadata prepare directory is required}"
C2_REQUEST=$C2_BIND_DIR/source_request.json
C2_REQUEST_SHA=$("$C2_PY" -B -c 'import json,sys;print(json.load(open(sys.argv[1]))["request"]["sha256"])' "$C2_BIND_DIR/binding_result.json")
C2_PLAN=$C2_PREPARE_DIR/selection_plan.json
C2_PLAN_SHA=$("$C2_PY" -B -c 'import json,sys;print(json.load(open(sys.argv[1]))["selection_plan"]["sha256"])' "$C2_PREPARE_DIR/preparation_result.json")
C2_OUT=$C2_RUNS/c2_fit_${SLURM_JOB_ID}
"$C2_PY" -u -B "$C2_RUNS/run_cpu_supervised_v3.py" \
  --output-root "$C2_OUT" --record "$C2_RUNS/c2_fit_supervisor_${SLURM_JOB_ID}.json" \
  --wall-seconds 3300 --rss-limit-bytes 25769803776 -- \
  "$C2_PY" -u -B tools/model_v3/run_coordinate_lookup.py \
  --mode run --output-root "$C2_OUT" \
  --request "$C2_REQUEST" --request-sha256 "$C2_REQUEST_SHA" \
  --selection-plan "$C2_PLAN" --selection-plan-sha256 "$C2_PLAN_SHA"
```

外层supervisor的固定2GiB输出/scratch保护沿用不改；C2本身仍有128MiB输出与24GiB
process RSS边界。CPU-only Slurm任务按全用户内存<节点85%和已有队列准入，不能
为执行上述片段自行启动旧S协调器、paid学校服或绕过主agent统一调度。

### 已存在的必要引用/依赖

以下引用已在live X以存在性检查确认；真实bind/prepare仍须核验字节SHA和原始句柄：

- `$C2_TREE/workflows/sprime_s/formal_s/B1_seed0_v2.json`：只取既有S/输入/视图定义，
  不启动其中训练任务，不把旧384×4模型称为本分析使用的神经主干。
- `$PROJECT/runs/sprime_s_convergence_20261013/training_inputs_v1/manifest.json`及
  `shard_snapshot_v1.json`；同目录`train.arrow`、`train.atoms.u32`对应原train，
  `full.arrow`、`full.atoms.u32`对应原预训练full验证。必须保留原字节和原source身份。
- `$PROJECT/runs/phase1_wp5_20261011/population/manifest.json`。
- `$PROJECT/docs/phase1/evidence/stage59_three_epoch_protocol_v1/actual_scientific_freeze_v1/phase1_three_epoch_scientific_protocol.json`。
- 协议的native transport：`$PROJECT/docs/phase1/evidence/stage48_full_corpus_qa/native_qa_stats_v3.py`，
  raw SHA `16c37ed53f6007b459981b734001fd3fef9dd225257b0d5d6eb8c54a4992772b`。
- `$PROJECT/MFM_model_v3_profiler_v2/tools/model_v3/native_runtime_bindings.py`及
  `runtime_monitor.py`，固定SHA分别如上；不假定C2 tree已有SA-1工具副本。
- source inventory逐文件绑定本树C2 core/source/runner、FullCorpusViewsDataset、
  degrade_once、原prepare.py、prepare_s_training_inputs_v1.py、s_native_adapter_v1/v2、
  s_convergence_runner_v8.py、wp5_population.py。只是import只读函数或读取代码身份，
  不执行这些原历史main入口。
- 原snapshot列出的只读LMDB原文件，以及上述chemprop解释器与scan_v2/deps中的
  NumPy/SciPy/Torch/PyG/LMDB/PyArrow/W&B依赖。实际SDK432和既有S读取证明环境可用；
  本轮首次C2 source读取仍需实际prepare闭合，不由存在性检查代替。
