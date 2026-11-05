# A类逐GPU执行矩阵与B类待交付条件

日期：2026-10-25。计划状态：已准备、未运行。A实现只在独立`MFM_model_v3_sa1_a`
工作树修改，原`MFM_model_v3_sa1`的native三卡执行源继续冻结。
起点提交`f9245bda42f4ce9933f046c0a6b373a74546338e`，实际运行时必须重新
记录包含必要接线的真实code SHA、选项JSON SHA和配置SHA。
选项位于`current/configs/model_v3/performance/`，`a_matrix_v1.json`为机器可读清单。

## CLI审阅结论与执行前依赖

`paired_a_acceptance.py`已有以下真实参数：`--candidate-options`、`--output`、
`--code-sha`、`--prereg-sha`、`--expected-gpu`、`--input`、`--reference-config`、
`--seed`、`--workers`、`--max-padded-cost`、`--smoke`。正常模式固定20批+500更新，
无需另传不存在的`--steps`。`--smoke`只有2批+2更新，不能授予A验收。
此执行器明确拒绝`precision=bf16`，不能用B选项绕过该限制。

新增`--shard-snapshot-sha256`、`--atom-bucket-width`、`--exact-atom-sort`及
显式拒绝的`--resume`。paired拒绝改变bucket/sort，因为这会改变optimizer逻辑
batch；只有单模型`single_a_benchmark.py`可将它们作为未验收容量/吞吐探索。
此CLI可表达checkpoint、compile、fused及TF32，没有B类训练或断点续训能力。
独立A树现已补接下列证据，仍待CPU/GPU实际验收：

- `SInputStream`显式绑定原`shard_snapshot_v1.json`的预先固定rawSHA，并记录
  native transport、原始manifest和完整sampler/loader配置。现有原S流不等于D5 proxy。
- paired入口自身显式source SHA、reference/A4原始配置SHA、完整loss weights、
  loss policy、supervision、归一化/几何精度边界及supervisor storage receipt进入配置。
  相对`__main__.__file__`不能靠动态源码枚举代替显式入口绑定。
- 核验两个W&B offline run在同一根的真实SDK布局与commit history；500步保存
  实际消费ID、原子数/对数、有效标签计数及已commit采样游标。每步保留资源观察，
  外层supervisor覆盖所有阶段的墙钟、RSS、实际GPU进程和存储上限。
- `single_a_benchmark.py`每个进程只常驻一个模型，无torch.profiler；
  `a_speed_report.py`核验ABBA四成员及可选20批/500步门槛文件，速度报告不能
  颁发数值验收。中途失败明确不支持恢复训练。

只补测试fixture或通过小批smoke不证明完整A通过。根协调者完成CPU回归和
有界GPU控制组smoke，再安排完整矩阵；本文件没有执行任何计算。

## 每张GPU的单项与叠加

三张表分别独立执行3090、4090、5090；不共用另一型号的容量证据。
每项都与同GPU、同seed=0、同20批及同500步流的原tiled路径比较。
旧路径6×512/A4、tiled65536、fp32、TF32关闭、标准AdamW和三类checkpoint开启。
LR=3e-4、betas=(0.9,0.95)、weight_decay=.01、clip=1；本A诊断使用固定LR，
不是旧S正式学习率曲线，也不用于决定训练配方。

| 顺序 | options JSON | 相对旧路径的单项改变 | 每张GPU要求 |
| --- | --- | --- | --- |
| A00 | a00_control.json | 仅通过候选包装层，三个checkpoint均开启 | 先20批+500步，隔离包装层差异 |
| A01 | a01_backbone_off.json | 仅关闭backbone checkpoint | 容量合格后20批+500步 |
| A02 | a02_distance_off.json | 仅关闭每tile checkpoint，保留tile | 容量合格后20批+500步 |
| A03 | a03_head_off.json | 仅关闭去噪chunk checkpoint | 容量合格后20批+500步 |
| A04 | a04_all_off.json | 三种checkpoint共同关闭 | 容量合格后20批+500步；不是A01的别名 |
| A05 | a05_compile.json | 仅compile backbone bound forward，dynamic=true | 实际编译、图中断/重编译、cold/steady分开记录 |
| A06 | a06_fused.json | 仅fused AdamW | 固定批门槛仍执行；优化器差异主要由500步检验 |
| A07 | a07_tf32.json | 仅启用TF32 | 与其余项完全相同门槛；失败保留舍入证据 |
| A10 | a10_fused_compile.json | A06+A05 | 两个单项各自通过后，组合重新20批+500步 |
| A11 | a11_all_off_fused_compile.json | A04+A10 | all-off容量匹配且前置项均通过后，重新20批+500步 |
| A12 | a12_all_off_fused_compile_tf32.json | A11+A07 | TF32单项通过且A11通过后才运行；不得强行叠加失败项 |
| A-radius | 无global配置 | 原基线use_radius_mask=false | N/A；不能添加半径后宣称数学等价 |
| A-padding | 清单内声明width8/4、exact sort | 改变原width16/块内顺序 | paired早拒绝；单模型探索标未验收，不参与采用 |

每个GPU的完整矩阵为11个有条件数值实验，上限共33个；不把N/A、容量不合格或
前置门槛失败写成通过。A01/A02/A03若有更优的可行部分关闭组合，可在观察其
单项结果后另存完整options及依赖SHA、先提交再比较；不得把结果最好的开关
组合倒填进A11已经冻结的all-off配置。单项和组合都保留原始负面结果。

padding候选另有输入语义问题：较小桶/精确排序可能改变每批成员，不能把两个
不同batch的同名输出直接相减，再把差异归给浮点精度。最小版本明确拒绝给
新流跑500步后声称A等价，保留默认width16。只有未来在同一原逻辑batch内部
减padding/分块并恢复样本与原子顺序、原损失分母及同一步更新的实现，才有
条件走原20批+500步门槛；当前未实现，单模型探索不能代替它。

A00自身失败时先解释包装层/输入/环境差异，暂停后续候选。未解释的A误差失败
上报主agent并遵守指南STOP条件；已经定位的TF32舍入失败仍按原门槛判失败，
不增加epsilon、不删近零梯度参数、不提高1e-5/1e-4/1e-3门槛。

## 固定输入、容量和失败闭合

每张GPU先固定共同padded-cost条件C_g。可探测的预算阶梯预先声明为
250k、500k、1M、2M、4M、8M；这是候选条件，不是已测容量。先审阅阶段1实际
峰值和张量尺寸下界，对明显超容量的关闭方案直接标容量不合格，避免故意OOM。
较小预算下的配对只授予该预算/输入人口的数值结论，不外推8M；如要比较另一
预算，基线与所有相应候选均用同一新预算和新流重新固定。不得只缩小候选批量。

BlockAtomBatchSampler保留超过预算的intrinsic singleton，因此预算不是严格
最大显存保证。记录实际每批B、maxN、Σn、3BmaxN²及超预算singleton；不丢大
分子、不截断原子、不丢尾批。不能用理论tile大小或营销显存替代实际峰值。
两模型同卡常驻还有双份参数/梯度/Adam状态开销，独立基线的安全峰值不证明
paired可容纳。显存保护同时检查Torch allocated/reserved与实际本作业GPU进程
占用不超过物理85%；RSS≤56GiB，持久产物≤2GiB，私有scratch/cache≤2GiB。
其他GPU进程出现时记录风险、不发信号，速度结果不用于选择。

运行必须在根协调者现场核验的自有Slurm allocation内，至少16CPU/64GiB、
一张明确物理UUID；同一GPU不并发实验。先建立有界控制组smoke，只验证执行器
和容量，不用于科学通过。每个完整case采用fresh目录和独立supervisor record，
到墙钟/内存/输出上限后记录真实失败与已完成步数，不自动加预算或伪称500步。
墙钟由控制组实测估计后、提交前冻结；外层支持≤7200s，当前例子6900s只是一
项明确上限，不承诺所有compile/双模型500步都能在该上限完成。

同一GPU上A00固定前20批的ID/顺序/实际形状/噪声seed组成不可变输入receipt。
候选从相同seed=0、epoch=0和初始参数重新开始，前20批不更新参数；不能把
阶段1“2warmup之后的20批”默认为这里“从头20批”。每个固定批逐个floating
输出与逐参数梯度检查相对L2；所有参数初值与state keys匹配。

20批完成后先实际关闭/加入workers，丢弃未commit预取，再恢复深拷贝的初始
sampler状态；重新获取的batch0必须匹配receipt，500步再从头消费。两个模型
每步使用同一个真实batch，交替先后顺序只减少计时次序偏差。只有两边完成本步
才commit sampler；从未commit的预取不得推进已消费计数。

现有RecoveringLoaderIterator仅对精确DataLoader timeout进行最多3次重建，
恢复已commit游标并保留父CPU RNG；原loader的600s等待阈值、8workers和
prefetch_factor=2不因提速试验暗改。非timeout错误立即保留原异常，不能无限重试。
reset是同一次实验的20批→500步转换，不是断点续训。当前paired脚本没有
checkpoint/resume CLI；进程失败后保留partial并以fresh目录完整重跑，所有失败
成本保留。不在缺少两模型、两optimizer、RNG、采样cursor及options绑定时接续。

## 当前CLI的可执行命令模板

数值比较新增明确的`--deterministic-controls`选项，默认关闭，原默认行为不变。
准备首个原生A00时显式开启，reference与candidate同时受控；其来源是381默认
旧模型自身重复未过、384确定性诊断全部原门槛通过。它没有修改误差规则，也不
把单toy诊断当20批/500步通过。必须使用包含该接线且CPU验收后的真实提交SHA。
单模型ABBA四成员使用同一选择，汇总会拒绝与numeric gate的控制签名不一致。

下面只展示真实已存在参数，必须先完成前述验收并由根协调者填入实际环境。
`TASK_CASE`只能选矩阵中的options JSON；不能传a_matrix或b_proxy_plan给候选CLI。
命令在allocation内执行，本文件不启动任何作业。

```bash
TASK_REPO=/share/home/zixiao/descriptor_analysis/MFM_model_v3_sa1_a
TASK_CASE=a00_control
TASK_GPU_TYPE=4090
TASK_CODE_SHA=ACTUAL_REVIEWED_COMMIT
TASK_PYTHON=/share/home/zixiao/.conda/envs/chemprop/bin/python
TASK_PADDED_COST=8000000
TASK_OUT=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/A_${TASK_GPU_TYPE}_${TASK_CASE}_${SLURM_JOB_ID}
"$TASK_PYTHON" -u "$TASK_REPO/tools/model_v3/run_supervised.py" \
  --output-root "$TASK_OUT" --record "${TASK_OUT}.supervisor.json" \
  --gpu-uuid "$CUDA_VISIBLE_DEVICES" --wall-seconds 6900 \
  --rss-limit-bytes 60129542144 --output-budget-bytes 2147483648 \
  --private-scratch-root "/tmp/mv3n_${SLURM_JOB_ID}" \
  --private-storage-budget-bytes 2147483648 -- \
  "$TASK_PYTHON" -u "$TASK_REPO/tools/model_v3/paired_a_acceptance.py" \
  --candidate-options "$TASK_REPO/current/configs/model_v3/performance/${TASK_CASE}.json" \
  --output "$TASK_OUT" --code-sha "$TASK_CODE_SHA" \
  --prereg-sha 3441b280bc34431bf8e7596465af28be073644b6 \
  --expected-gpu "$TASK_GPU_TYPE" --input native_s --seed 0 --workers 8 \
  --deterministic-controls \
  --shard-snapshot-sha256 d2e1ace1636485cd3dd0106b1177518dd37eb9741919195a9efcd846c1c2242f \
  --max-padded-cost "$TASK_PADDED_COST"
```

GPU型号只替换3090/4090/5090，UUID与逻辑Python由现场受信wrapper确定；5090
使用已验证的`stage43_5090_environment/install_4511929/venv/bin/python`环境，
不照搬上面的chemprop示例，实际Torch/CUDA/driver版本随运行记录。PYTHONPATH沿用
既有deps overlay。私有scratch由supervisor首次创建，不允许wrapper先mkdir。
无compile复用时不传cache选项，首次编译成本和临时缓存全部计量；可复用cache
必须绑定兼容key并独占锁，分别记录已有字节、复用状态、观测增长及采样最大值。

旧版本模板2400s不能预设足够；本版首个完整A00使用6900s。阶段14090单模型17步
完整墙钟均值约3.32s，按双模型×520次估算约58分钟，尚不含确定性实现变化、
冷启动及固定批CPU比较余量。建议首个native A00采用16CPU/64GiB、同一4090，
2小时allocation、外层6900s上限；RSS仍56GiB、持久/私有存储各2GiB，不扩内存
或误差阈值。该时长是提交前估计，确定性额外开销未测；到上限保留partial，
不声称500步完成，不自动接续。首轮实际时长再用于后续case估算。

## 提速表与B类精度计划

paired历史中的两模型同卡耗时只作诊断；不能填“原始吞吐/候选吞吐/倍数”。
数值通过后另作单模型ABBA：相同GPU/批流/有效计时窗口，分别启动原路径、
候选、候选、原路径，排除其他进程干扰。训练更新、模型初值、warmup、冷编译
和steady窗口在提交前固定，顺序间不继承训练权重；按真实消费结构/原子数及
实际墙钟汇总，输出每个单项和合法叠加的raw值、配对比和差异。compile额外列
首次启动总耗时、实际编译/重编译和cache状态。不得拿有profiler的阶段1吞吐
除以无profiler的候选吞吐作为提速倍数。这个独立驱动已实现、尚待运行。

预先采用每个ABBA成员2个warmup更新、随后20个计时更新，无torch.profiler；
均从同seed参数与同batch0开始、无checkpoint权重继承，四份输入receipt一致。
两份A与两份B分别用计时窗口真实消费结构总数/墙钟总和汇总，再计算B/A；
同时列每次raw值、atom/s、padding与allocated/reserved和进程峰值，不只给倍数。
compile第一次和复用cache分作不同实验条件。2个warmup未覆盖的形状若仍触发
编译，其开销保留在计时窗口并单独记录；不能把这个窗口无条件称作纯steady。

执行每个成员时，将上面的child入口换为`single_a_benchmark.py`，保留所有
模型/输入/来源参数，并依次传`--role reference --abba-position 1`、
`--role candidate --abba-position 2`、`--role candidate --abba-position 3`、
`--role reference --abba-position 4`和相同的`--series-id`。每个成员使用fresh
输出和独立Slurm job/scratch；四次传相同candidate options，reference仍构造
原模型，不能为reference改传另一个options。末尾用以下实际CLI汇总：

```bash
python tools/model_v3/a_speed_report.py \
  --runs A1_ROOT B1_ROOT B2_ROOT A2_ROOT \
  --supervisors A1_SUPERVISOR.json B1_SUPERVISOR.json B2_SUPERVISOR.json A2_SUPERVISOR.json \
  --numeric-gate MATCHED_PAIRED_ROOT --output FRESH_ABBA_REPORT.json
```

没有匹配的完整numeric gate可省略该参数，报告只能是未验收的观察；synthetic、
smoke、不同GPU/代码/配置/真实输入、未闭合cleanup或foreign风险均不能变成
合格速度比较。native输入若regroup，报告保留各自raw吞吐、倍数为null。

`b00_fp32.json`和`b01_bf16.json`仅相差precision，均保留checkpoint、标准
AdamW、TF32关闭和compile关闭，隔离精度效应。B计划在`b_proxy_plan_v1.json`；
当前D5未交付，population/validation manifest和SHA保持null、训练数为0。
不得把旧S的11,104,772个record采样器、任意前缀或1206608分子原库称作240k proxy。

D5 READY且权威分子清单/允许构象/PM7绑定后，先冻结TRAIN内层分子划分和
验证字段，使用分子均匀→允许构象均匀的流；再固定一个GPU型号和环境，做
fp32/bf16各seed0、1，共4次20,000更新。验证计划为0起每500步至20,000，
同一固定分子/构象/噪声与完整指标/有效计数；若权威接口要求调整，必须在首次
训练前提交变更，不能在见到曲线后删点或换字段。每条bf16曲线每个点都需落在
两个fp32 seed包络内，RMSE另按同seed fp32配对≤2%；门槛无放宽。
所有H0、坐标、距离、RBF、几何头、损失、归一化和参数保留fp32，只有主干
矩阵乘走选择性bf16；运行期验证dtype和finite梯度。现有paired CLI不是B训练器，
完整B执行/验证/恢复链尚待实现，不启动正式预训练或学校服务器。
