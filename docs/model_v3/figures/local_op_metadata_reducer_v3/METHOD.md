# 3505 局部算子：固定全48案例的标量后处理

SOURCE_ONLY，作者未运行Python、AST、模型、数组、SDK、网络、Git或Slurm。此包不修改3505或任何既有源码/结果。执行前必须绑定Root实际3505 C0/source/resource闭合证明的rawSHA；producer的CAPTURE_COMPLETE不是Root终态证书。已按实际model_v3_encoder_local_op_GPU_Root_closure_v1接线；冻结source-only并不表示本后处理已运行或通过。

唯一入口是reducer.py。它只解析3505的CAPTURE_MANIFEST.json、完整48份CAPTURE_CASE.json与48份LOCAL_MODULES.json，以及本包、原13叶源码、既有CPU监督/计量源码、Root闭合证明/封存源快照/COMPLETE/监督小元数据。Root closure的48组独立rawrefs逐一与cohort输入一致；它的实际parent/C0/资源/清理/source/counter等按原schema核对，不自由搜索文本C0。不会导入producer、Torch或local_metrics.summarize，不打开NPZ、权重、SDK或原数据。绘图阶段仅用既有matplotlib/Agg，不新增软件包；MPLCONFIGDIR明确放在原监督器实际/tmp/mv3n_JOB私有根内，缓存计入原private/joint预算，不写用户home配置。原JSON不改写。输入统一以owned regular/nlink1/无symlink/长度/SHA与读前后stat绑定；完整输入与相关源码最终重新hash并保存全部before/after refs。输入总限64MiB，输出总限128MiB，不扩大既有CPU监督的双2GiB预算。

完整性约束是固定3个C1 × 2种view × 4种head × 2个seed的原顺序48案例；192个原FP32 encoder forward、零FP64 encoder forward；每案例4个H0 header逐位控制与52个外部terminal逐位控制（共2496）。C1-0：16案例×31模块×4role=1984次本地调用，16×37端口×3变换=1776观察；C1-a/b：32×26×4=3328次调用，32×27×3=2592观察。两种本地调用各5312次，观察合计4368。重放、角色、状态映射、实际eval/inference/noAMP上下文、全部模块/端口/变换和21PASS/27FAIL原物理矩阵均保持。kind=node不是算子类别；类别用state_mapping.original_class并保留module名。out_norm/shared_pair_encoder的layer=None保留。

每条观察保留全部五项：F32_D、F64_same_actual_input_D、arithmetic_residual、base_local_error、moved_local_error；每项保存maxabs/RMS/squared_sum/分母/argmax/带符号极值。三个目标argmax各保留同一physical_row/channel_or_head上的五项signed_tuple及坐标，共15项带符号值。输入漂移保留原kind/law/统计/typed headers；位置采用原x@R+t。按原1e-10界复核保存的closure与这三个点的 D32-Dref=residual=error_t-error_0；不以不同argmax的最大值作相减。所有保存的非空人口统计必须具有正rows/channels/components及一致分母；不存在的operator/port/人口组合保留NA而不填0。

observations.csv固定4368行，保留四case因子、module/class/layer/port/transform/人口、所有五项及同分量值和input_drift JSON。CSV仅是本轮model-owned运行产物；不假定符合仓库训练汇总CSV白名单，不自动放入Git。summary.json按完全一致的C1/view/module/class/layer/port/transform/原人口分组；各组严格覆盖4head×2seed共8案例。总体RMS=sqrt(sum(squared_sum)/sum(components))，不是RMS平均值。这些8个case不是8份独立训练样本，不生成置信区间或训练seed SD。不同node/pair/head概率/距离端口及不同分母不混池。无该分组就是NA。源物理1e-5/rtol0只属于原终端判定，不被新增为局部端口门槛。

最多两张PNG：同算子族/port/人口/rows/channels分别成面板，第一张对照D32与Dref的分组总体RMS，第二张对照Dref与局部residual。点保留一个layer、transform与C1，颜色表示变换，形状表示C1；只在相同组内按平方和合并4head×2seed。symlog保留真实0，不伪造epsilon测量。图不是因果排序，不把嵌套重叠模块的残差相加。所有max及完整signed数据仍在CSV。

独立参考明确同时改变算法与精度：legacy/direct FP64、dtype特定kernel与当前compensated/centered FP32并非只改dtype。Dref还携带实际F32上游输入漂移。可描述本固定cohort的局部block对照和同分量恒等式；不能据此断言纯精度因果、某kernel/层造成整模型失败、FP64全encoder一定通过、必要API改变或adoption。保持当前C4 21PASS/27FAIL、无模型/H0/API/训练变更。

Root使用既有CPU提交器和监督器，不新增调度器、监控或QA父。原资源：CPU partition实际16CPU/16GiB，RSS12GiB，180s监督，whole/private各2GiB；实际内层工作仍遵守原监督器finalization reserve。Root现场资源/quota准入和实际CPU父C0最后独立闭合。child的COMPLETE仅表示标量后处理完成，明确待Root CPU终态。

```bash
B=/share/home/zixiao/descriptor_analysis
S=$B/runs/model_v3_20261026/encoder_local_op_metadata_analysis_v1_source
PY=$B/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
# Root提供实际闭合rawSHA、本包最终pins rawSHA、现场CPU_NODE和fresh OUT；不预填未来job/C0。
"$PY" -B "$B/runs/model_v3_20261025/run_cpu_supervised_v3.py" \
  --output-root "$OUT" --record "$OUT.supervisor.json" \
  --wall-seconds 180 --rss-limit-bytes 12884901888 -- \
  "$PY" -B "$S/reducer.py" --root-closure-sha256 "$GPU_ROOT_CLOSURE_SHA" \
  --source-pins-sha256 "$REDUCER_PINS_SHA" --expected-node "$CPU_NODE" --output "$OUT"
```

上述命令只能在实际Slurm16CPU16GiB分配内使用，CUDA_VISIBLE_DEVICES=''。Root薄SBATCH可沿用原CPU helper；本包不提交任何任务。--no-plots可明确关闭图形输出，但完整CSV/JSON与全部计数/来源/代数断言不减少。失败保留fresh目录，不自动retry、删除、补值或放宽阈值。

## 已有权威元数据绑定（不是本后处理执行结果）

| 文件 | 字节 | raw SHA256 |
|---|---:|---|
| /share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/encoder_local_op_precision_GPU_4523505_Root_metadata_closure_v1.json | 53878 | 9edc51f997bf3870818cecef6e3342ed844d4ae8563530528f02816b44b9d023 |
| /share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/encoder_local_op_precision_GPU_v1_4523505/CAPTURE_MANIFEST.json | 25122 | 2616c51384afcdb5580ce51ad1bb56171169cbf34a18bb274c1394aedeb57fef |

## v2：只改善图刻度密度

原v1三叶与实际3706的CSV/summary/PNG全部保留。本v2仅在plots()内将两轴symlog主locator的numticks设为4（约4个主刻度），并用NullFormatter关闭次刻度标签。保留原自动范围、linthresh=1e-16、真实零值、全部数据点/分面/分组/图例与所有标量/CSV计算；不做图像后处理，不删零、不调科学阈值。脚本除上述plots()内两处插入外逐字节等于v1。原方法和命令保留为v1历史；Root执行本版时仅将S改为N/encoder_local_op_metadata_analysis_v2_source并使用本版pins与fresh output，监督资源、输入与实际3505Root证明不变。

v2尚未执行。Root同一CPU重导后，应逐字节核observations.csv与O/encoder_local_op_metadata_analysis_4523706/observations.csv一致；summary.json除reducer_source_pins这个来源ref外其余字段（含完整546组和所有标量）应canonical精确一致。INPUT_SOURCE_BINDINGS/COMPLETE包含本版源码、输出路径、父job与图哈希等实际来源/运行信息，不能要求这些来源元数据冒用v1。无新增QA父、模型/数组/SDK/权重读取或科学结论。

## v3：保留窄范围原刻度，无可见刻度时补数值标签

实际v2/4523810 C0及CSV、546组统计与3706一致的历史保留；Root查看v2两图发现统一numticks=4会使部分窄范围面板没有数字刻度，因此v2图未采纳为最终图。v3仍仅改plots()：读取各轴当前原view limits，筛选原major locator在范围内的有限刻度。多于4个时按等距索引抽4个，保留首尾及原0；1–4个时原major locator和formatter完全保留；零个时使用该轴既有symlog transform与inverse，在变换范围12%、50%、88%设置3个major刻度，并用显式科学计数formatter。minor文字关闭。没有set_xlim/set_ylim/set_ticks，不改变原自动view limits、symlog/linthresh、真实0、数据点、分组或标量/CSV；无图像后处理或阈值变动。

v3尚未执行。Root执行时将S改为N/encoder_local_op_metadata_analysis_v3_source，使用v3pins与fresh OUT，同原16CPU16GiB、180s/RSS12GiB、whole/private双2GiB与两图；不新增QA父。仍要求CSV逐字节等于3706及3810，summary除reducer_source_pins来源ref外canonical全同；变化仅新来源元数据和图像。v1/v2源、3706/3810所有输出均不改写。
