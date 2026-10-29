2026-10-29 当前生效：[C4 v3 正式报告](C4_EQUIVARIANCE_V3_REPORT_20261029.md)：FP64实际4524734已48/48，C4 PASS；FP32仅诊断，旧HOLD/v1/v2仅为历史，未重跑。r674保留head、LOSS_DISABLED、不追加处理。科学DECISION_RULES与TRAIN/noTEST边界不变。

# 阶段 3：标签接口、预测头与损失

日期：2026-10-25（Asia/Shanghai）。基线代码/预注册：`b71729e`。
本报告的状态是 **实现与合成验证进行中，真实数据验收未完成**。
用户已确认数据线 D-1 至 D-6 尚未交付；本线没有生成真实标签、
拟合真实归一化或声称新的训练物理格式已经冻结。

## 问题及预先规则

实现新标签层级、字段/家族/组掩码与按分子采样，同时保留已有 S 任务的
实际预测头、视图和单项损失。选择依据为 `DECISION_RULES.md` 与用户指南阶段 3。
新目标是：先对本批有效标签平均，再对组内有标签的字段平均，最后对启用
S/D/P 组等权；Huber 默认 delta=1。真实每字段 1,000 分子过拟合 R²≥0.95、
H0 不变、旋转等变、逐位恢复及分子频率卡方验收均不得由准备代码代替。

## 实现与接口边界

| 文件 | 职责 |
| --- | --- |
| `phase1/v3_contract.py` | 模型侧已解码字段、层级、单位、类别、掩码及 TRAIN 统计量验证；明确 MODEL_SIDE_DRAFT，不是 D-1/D-2 |
| `phase1/v3_sampling.py` | 均匀抽分子、再均匀抽允许构象；清单首 k / 全部 / 明确最低能构象 ID / 多样性首 k；PM7 / S′ UFF / 逐分子混合 |
| `phase1/v3_data.py` | 注入版本绑定、只读、节点本地 provider factory，worker 独立构建句柄；原子 ID 保真、字段/家族/组掩码合并、spawn 预取、按原子预算及样本端点分批 |
| `model/v3_heads.py` | P/D 层级头、H1/H2/H3、固定 sum/mean 或可学习 sum/mean 混合、对称原子对 RBF、等变向量与偶极/模长；不修改旧 SharedBackboneMFM |
| `phase1/v3_losses.py` | TRAIN 归一化、逐字段有效标签平均、组内 observed-field mean、启用组等权及逐字段 counts |
| `phase1/v3_structural.py` | 显式 S 字段绑定，原生记录的确定性三视图，分别应用各字段 eligibility，复用原 S 单项 loss/raw/count |
| `model/v3_multiview.py` | 正式 S/PD 组合入口：同一次 encoder 得到三视图 H0；S 复用原头，P/D 只读取 clean H0。P/D-only 只计算 clean |
| `phase1/v3_training.py` | 已消费样本时钟、具 COMPLETE 标记的不可覆盖检查点、RNG/AdamW/游标恢复、每 500 更新共享主干梯度、两个验证角色及原单位指标 |
| `phase1/v3_trainer.py` | 可注入绑定 adapter 的单步/样本预算训练器、seen-driven cosine/WSD scheduler、真实 tracker 协议、完整执行状态和日志/验证状态恢复；10 项 CPU 合成集成测试实际通过，真实数据接口仍待交付 |

以上路径相对 `current/phychem_mfm/`。通用 V3HeadBank 的 S 配置只用于独立
合成容量诊断；真实 S 训练使用 V3MultiViewModel 的原头桥，不能用通用分类/
RBF pair 头替代旧 element/BondPairHead。factory/shared 未修改，旧路径仍可复现。

采样使用逐样本 ordinal 的独立 SHA256 拒绝采样流，不消耗 ambient RNG。
不因构象数多而增加分子被抽中的概率。最低能与多样性次序必须由清单明确给出，
模型线不根据不明字段推断。迭代和预取不会推进游标；只有消费后的 commit_batch
推进。大数据可注入 memory-map SamplingIndex，InMemorySamplingIndex 仅为
合成/小试点投影，不宣称它已经解决全量 metadata 在多 worker 下的复制开销。

provider 输出模型侧 fp32 原单位标签，训练代码不做未经约定的物理字段转换。
预测和标签均用同一 D-4 仿射变换后计算 Huber，因此偶极模长头保持非负原单位输出。
能量元素参考只能作为 D-4 明确提供的、detached、逐图原单位预测偏置；不自行拟合。
矢量标准化必须是零中心、各方向同尺度，避免标准化本身破坏旋转等变。

矢量回归的 v3 默认损失是 `radial_huber_v1`：令标准化残差为 e，计算
`Huber_delta(||e||_2 / sqrt(3))` 后对有效向量平均。小残差区为
`0.5 × mean(e²)`，与逐分量平均相同；大残差区仍保持联合旋转下的损失不变和
梯度协变。最初合成组件版本的逐分量 Huber 留作显式 `component_huber_v0` 回放，
不作为矢量默认。S eps MSE、标量和模长的损失保持原定义。本修订不改标签或 D-4。

每个字段用一维 bool mask 指明观察有效性；矢量标签以完整三分量为一个观察。
掩码为 false 的 NaN 在任何算术之前剔除；标为有效却为 NaN/非法类别时直接报错。
无观察字段不进入组内分母。启用但本批完全缺标签的组为 detached zero，仍在
启用组分母中；停用组不进入分母、不执行其新头。分类字段报告 accuracy，
不伪造 R²。连续字段常数/观察不足时 R² 明确 unavailable。

## S 兼容与三视图

StructuralFieldBinding 必须显式指定 element/noise/bond 对应的 registry 字段，
不能猜测 D-1 名称。S 继续使用原线性 element_head、原 BondPairHead 正边五分类、
A4 EquivariantDenoisingHead 与 denoise_eps_mse。温度、标签平滑、原有 L2 与
原有熵项数值语义均来自源 compute_phase1_loss；没有修写历史熵项的 no_grad 事实。

基础记录经原 degrade_once 生成 clean/geom/topo。干净标签和实际变化元素掩码
保留原事实；监督资格另存，不能靠改 x/pos/corruption mask 伪装任务停用。
clean 上监督 P/D 和 S bond；geom 上监督 S 噪声；topo 上只监督 actual-changed
合法元素。每个 S 字段有独立分子、原子/原输出 pair eligibility。不同 eligibility
分别用复制后的 outputs 调用源损失，只抽该任务的 raw/count，避免全局 node_mask
造成任务间串扰。默认全可用路径只调用一次源 S 损失。

新的 S 聚合只平均实际有有效标签的 S 项，再与 P/D 等权；不能直接沿用旧 S
总损失的固定任务分母。原 raw/count 与其梯度是否一致由专门测试验证。
P/D 的头只注册 P/D 字段，同一字段跨启用组组合始终使用同一组参数。

## 实际验证与准备项

| 验证 | 当前证据与状态 |
| --- | --- |
| 第一批独立组件合成测试 | **实际 19 passed / 0 failed**，Slurm 4520332；6 个候选文件前后 SHA 一致，快照 `runs/model_v3_20261025/source_snapshots/unit_4520332/sa2_labels` |
| 第一批覆盖内容 | NaN/缺失标签与组均值、停用头无梯度、固定种子 alpha=.01 分子/构象频率卡方、首 k/最低能/多样性选择、未消费预取恢复、真实 spawn worker、H1/H2/H3 的各层级旋转测试、H0 512 包装接口 |
| TRAIN 设施与 transfer 修订 | **实际 28 passed / 1 skipped**，Slurm 4520333 COMPLETED/0:0、16 秒；9 文件前后 SHA 一致。唯一 skip 为需要可见 CUDA 的实际 pin/异步传输，待 GPU smoke 验证 |
| S 桥接、径向 Huber 与相关回归批次 | Slurm **4520336 实际 FAILED/1:0**，179 秒；SA-2 组 **40 passed / 1 failed / 1 CUDA skipped**。唯一失败为 S raw/count/逐参数梯度兼容测试的 `torch.equal(gradient)`，raw 数值和 count 完全相同；不能升级为桥接验收通过 |
| 径向矢量 Huber 修订 | 5 项定向测试在 4520336 中实际通过：超出 delta 的联合旋转损失/梯度、小残差二次系数、零残差有限梯度、旧模式差异、S eps/标量不变；这不豁免该批的梯度兼容失败 |
| 梯度失败诊断 | Slurm **4520338 实际 COMPLETED/0:0，7 秒**；8 个 intra-op 线程下，相同 source.raw 重复反向、重复构建 source loss、bridge 各有 3 次 mismatch，全部位于 s_noise→encoder.backbone.atom_emb.weight；maxabs=1.86264514923096e-9，relative-L2 约 7.39e-8–9.33e-8。raw/count 全部逐位相同，RNG 不变、源码前后 SHA 一致 |
| 严格梯度测试环境修订 | 同一 4520338 诊断切到 1 线程后三类 mismatch 全为 0。修订后的原失败 case 在 **4520342 实际通过**，raw/count/参数梯度均 torch.equal、源码前后 SHA 精确。仅固定该测试单 intra-op 线程，退出恢复原线程；不改 allclose，不抹去 336 原父失败 |
| 第一版训练器及全分支回归 | Slurm **4520346 实际 COMPLETED/0:0，81 秒，2066 passed / 1 CUDA skipped**；67 个测试文件，实际代码 `50788d5e079ff1d896bcec9fbaa75e45312c384b`，全部源 SHA 核对通过。包括前 9 项训练器合成集成测试，不包含下一行的 optimizer 顺序修订 |
| optimizer 顺序修订及完整回归 | Slurm **4520347 实际 COMPLETED/0:0，140 秒，2067 passed / 1 CUDA skipped**；实际代码 `28edd6169666eb35893f39f154c5bd9db58923f2`，完整冻结源检查通过。新增同形状参数在 optimizer group 内交换顺序的恢复拒绝负例；训练器合成集成测试现为 **10 项实际通过** |
| 完整训练器 CPU 集成覆盖 | 输入/model/AdamW/scheduler/RNG/provider/log cursor 中途恢复逐位一致，保存/加载不消费 RNG；双验证隔离，未知 draw/adapter 在更新前拒绝，全缺标签不更新但 seen/scheduler 前进，atom/sample 端点，execution options 校验，pending tracker 记录恢复，以及 optimizer 有序参数名绑定。unit fake tracker 只验证协议，不证明真实持久化 |
| 1,000 合成分子逐头容量诊断 | Slurm **4520349 实际 COMPLETED/0:0，20 秒，9/9 PASS_SYNTHETIC_ONLY**；各案例 1,000 合成分子、25–100 次更新，完整结果见下表。H0 为固定合成 512 维不变特征，不是完整主干输出；原 SDK core 日志存在共享路径，完整自有归档尚未验收 |
| 真实 D-3 逐字段 1,000 分子过拟合 | **未运行 / 未验收**，需要 D-1/D-2/D-3/D-4 |
| 真实 PM7/S′ 与混合几何读取吞吐 | **未测量**，需要真实节点本地 D-3 与物理接口 |
| 两个真实验证集及 2,000 步 SDP | **未运行 / 未验收**，需要 D-3/D-4/D-5 |

第一批 19 项证据保留在其原版本范围。4520346 和 4520347 分别证明上述实际代码版本的
完整指定回归套件通过，不把前一版本结果借给后一版本；唯一 CUDA skip 仍待实际 GPU 验证。
这些合成与回归结果都不是完整阶段 3 真实数据 PASS。后续改变源码须引用新测试快照。
完整回归的原日志分别位于项目根
`runs/model_v3_20261025/sa2_all_tests_4520346.log` 与 `sa2_all_tests_4520347.log`，
对应输出目录为 `sa2_all_tests_4520346/`、`sa2_all_tests_4520347/`，
逐源 SHA 清单为同根 `sa2_sources_4520346.sha256`、`sa2_sources_4520347.sha256`。

4520336 的原失败及其源快照仍保留。4520338 的证据只证明原 source 自身在
该 8 线程环境下重复反向不逐位、而本次 1 线程环境下源/桥接均逐位；本轮没有
单独隔离并归因到某个具体 index_add、embedding 或其他算子。固定兼容测试的
线程环境不代表真实多线程/GPU训练已经获得逐位确定性证明。
原诊断 JSON/日志为项目根
`runs/model_v3_20261025/s_bridge_diagnostic_4520338.json` 和同名 `.log`。

## 1,000 合成分子逐头容量实测（4520349）

全部 9 个案例使用实际代码 `28edd6169666eb35893f39f154c5bd9db58923f2`，在
compute-0-20 的 Slurm 分配内以 CPU 运行，PyTorch 2.10.0+cu126、Python 3.11.14、
每进程 2 个 intra-op 线程，CUDA_used=false。诊断数据版本为 synthetic-capacity-v1，
每例 1,000 个合成分子，H0 为固定合成 512 维不变特征。只优化通用预测头，不训练主干，
也不验证正式 S 原 element/BondPairHead 的实际标签容量。denoise 案例仅为通用 S 向量头
与 eps MSE 的合成诊断。图层级三个案例覆盖 H1/H2/H3，另覆盖原子、原子对、原子向量、
偶极向量和偶极模长。

诊断优化器为 AdamW，lr=0.01、betas=(0.9, 0.95)、weight_decay=0、clip=1、
线性 warmup=25 更新；每 25 更新评估，R²≥0.95 即停止，最高 600 更新。
矢量回归绑定 radial_huber_v1，denoise 保留 eps MSE。此独立容量诊断的优化器配置
不构成阶段 5 正式训练配方选择。以下 R² 均为同一合成训练集的拟合值。

| case | seed | 头参数量 | 实际更新数 | 合成训练 R² | W&B offline run ID |
| --- | --- | ---: | ---: | ---: | --- |
| graph_H1 | 20261025 | 513 | 100 | 0.9829617248059331 | 3gb4h3oa |
| graph_H2 | 20261026 | 32897 | 50 | 0.9948649178816065 | 9h1js1hk |
| graph_H3 | 20261027 | 32897 | 50 | 0.9952283447302109 | am0uovaf |
| atom | 20261028 | 32897 | 50 | 0.992545791270495 | jr906pgi |
| pair | 20261029 | 69761 | 100 | 0.9664153246869207 | 8jrh4pv9 |
| atom_vector | 20261030 | 71873 | 25 | 0.9821725689476434 | nsq24pk8 |
| dipole_vector | 20261031 | 32897 | 50 | 0.9895263852370249 | iwnkq291 |
| dipole_magnitude | 20261032 | 32897 | 50 | 0.9824135730768291 | o2udgn23 |
| denoise | 20261033 | 71873 | 25 | 0.9831640300898775 | tihxmtw0 |

证据根为项目根的 `runs/model_v3_20261025/head_capacity_4520349/`。完整汇总为
`summary.json`；每例 `<case>/result.json` 的 configuration 保存完整配置与逐源 SHA256
映射 source_sha256，results[0] 保存上表结果与 configuration_sha256。
源清单范围为全部 `current/phychem_mfm/**/*.py` 加诊断驱动，实际文件字节前后核对，
不只依赖声明的 code_sha。该批驱动 SHA256 为
`75908e4dc32420d7d7c2577dd397f2982a791e32fbc5c8bdf81ad6ae5e0ee464`；
wrapper SHA256 为 `c182f68b5f424e600ae47896e179ec587011ac1a637460c21693dbcd7a8db56c`。

| case | configuration_sha256（4520349 原配置，包含实际 source_sha256） |
| --- | --- |
| graph_H1 | `7c5878f6f7752e6bed2d0e24bb81b76b9577ccfb8f7eacfd68327ef2923897fe` |
| graph_H2 | `21174cc2d6e23622cb7dc8d9b95ce500e7b3f2e9d0c2327cecdc8d4afcf6920d` |
| graph_H3 | `13fc54b06584b12780552ecc79eff32aab121cda4610b294ebda30a684298b68` |
| atom | `8cdae0afab20146784513ac4a7c3a1af79e97a755c060573f8eb6556674054f3` |
| pair | `664fe02101f7256ef9473474ad44c605196decf9be4fe1d00e91404159b9cbea` |
| atom_vector | `f14f0f53434f8a715058da09e1ef779716e1bc7633003d74975051a5deaca6c2` |
| dipole_vector | `276e11d5238b590a12d1891831780fec1cd5ade52e05330c92e354ca67f500a1` |
| dipole_magnitude | `d17a943e9c83724a8ceb64b2c4422236c3960938800b28bde3937305aeda888d` |
| denoise | `b4307a96e81d50caf60b3996ea82f79cc7414e54c0a9cb5db6b5ead351ef4f84` |

每例原生 SDK 位于同目录 `<case>/wandb/offline-run-*`；stdout.log、execution.json 与
result.json 保留。4520349 未设置 WANDB_CACHE_DIR，9 个 debug-core.log 链接指向
`/share/home/zixiao/.cache/wandb/logs/`，并行案例存在共享 core 日志，严格归档器会拒绝。
因此这批的数值 PASS 与原 SDK 文件是已存在的证据，**完整自有 W&B 归档未通过**，
也不声称已在线同步。原结果与共享日志保留。驱动随后仅修复日志路径：import wandb/init
前显式设置 WANDB_CACHE_DIR=`<wandb-dir>/cache`、WANDB_DATA_DIR=`<wandb-dir>/wandb_data`，
并把两路径写入 configuration；fixture/seed/loss/optimizer/阈值不变。
该日志修复尚待以新代码 SHA 同配置重跑及原生 history/归档验收，不回写 4520349 的配置或状态。

这些 9×1,000 合成分子的拟合结果只验证通用预测头的合成容量，不替代真实 D-3
逐字段过拟合、正式 S 原头、完整 backbone、物理 adapter、真实两验证集或正式预训练验收。

## 检查点、样本会计与验证

时钟使用已消费基础样本，而非 epoch 或三个视图之和。标准保存端点为
1/2/4/8/16/32/64M，batch 在端点切开；额外恢复检查点使用新的唯一目录。
检查点不覆盖或删除旧文件，COMPLETE.json 最后发布并绑定 payload 字节和 SHA。
加载必须同时验证 code/config/registry/normalization/data 版本、运行环境、sampler
及训练时钟；weights_only 读取。Python/NumPy/Torch CPU/CUDA RNG 与 AdamW
状态一起恢复。未完成目录保留为故障证据且拒绝作为有效恢复点。

ValidationAccumulator 分开记录 VAL 和 TRAIN_UNSEEN_CONFORMATION；字段指标为
有效观察数、标准化 loss、原单位 MAE 和 R²。每 500 optimizer updates 可对同一
明确的小 probe batch 分组求共享主干梯度范数，不改已有 parameter.grad。
V3StepTrainer 把这些组件串成可运行 API；正式物理 adapter 与持久 W&B 的实际
端到端验收仍未完成，不会以 unit fake tracker 或候选代码代替运行期证据。

训练器在 provider 准备前和 optimizer 更新前核对完整 next draws、sampler/
training/scheduler 游标、adapter SHA/data version、原子预算和里程碑。全缺标签
批次不执行 optimizer.step、不改变 AdamW 矩状态，但真实 seen 样本照计，scheduler
也按 seen 前进；日志明确记录 optimizer_updated=false、lr_used/lr_next。到达未保存
里程碑后禁止继续更新，固定预算 run 会先保存。history 流式交给 tracker，不在内存
保留全语料日志列表。每步对完整 registry 记录 field_enabled 与 inactive count=0；
无标签分类 accuracy/R²/MAE 为 typed N/A，S raw 只映射到 registry 字段名一次。

可恢复状态包含 scheduler 配方/状态、adapter 的已提交状态钩子、全部 source/config/
registry/normalization/data 绑定、trainer 源 SHA、实际 performance options、逐 module
resolved checkpoint flags、数值执行设置、pending 日志/逻辑 cursor 和两个验证状态。
options 不一致必须先用相同绑定实现构建模型，不能只凭 legacy config_dict 或同形状
权重加载；resolved flags 从保存状态恢复。provider 钩子必须表示已提交的语义状态，
不保存 worker 句柄或未消费预取游标。验证与梯度 probe 均保留 ambient/provider RNG，
不推进训练时钟。unit tracker 需要显式 opt-in，不能当作持久记录通过证明。

恢复契约还绑定 optimizer 各 parameter group 的**有序 model.named_parameters 名称**。
只检查参数集合、形状或 group 超参数不能保证 AdamW 的矩状态映射正确；相同形状参数
交换 optimizer 顺序会导致恢复语义改变。新增第 10 项集成负例先产生不同的 exp_avg，
再交换同形状参数次序，确认 load 在 model/optimizer/scheduler/sampler/clock/RNG
任何改变前拒绝。该实质修订属于 28edd616/4520347，不借用 50788d5e/4520346 的通过结果。

## 日志修复后的独立复测

4520351实际COMPLETED/0:0，18秒/16CPU/32GiB，执行
`1ac3d8cc35f728ab833a04c4d90eaed1d55f352c`。只修复W&B cache/data目录归属；
九类头的R²、seed、更新次数和参数量均与349完全一致。九个真实原生run ID按上表
case顺序为`uf8drrmo`、`k64bpa7h`、`i2wj3uon`、`ghobbek6`、`77h4r4o9`、
`lbf3qadk`、`jyhlert9`、`yqoh9po1`、`i7iimnqx`。每个SDK现在只链接其本case的
cache，原生history实际行数与25步记录间隔一致，逐文件SHA归档已通过。
349原始SDK及共享core日志不删除、不改写，原缺口作为独立事实保留。

SA-2合入model-v3后，4520355再次完整回归：2,067 passed / 1 CUDA skip，
实际COMPLETED/0:0，53秒，执行合并提交
`76bceb59d5372515fb10f8916b89ec2bb42fd4ed`。真实D-3及三GPU新标签验收仍待交付。

## 决定与未解决事项

采用显式、可注入的数据线 adapter，不自创权威物理格式。模型侧具体需求列在
`03_interface_requirements.md`，待 D-1 到位后再提交“模型线意见”到双方共同契约。
真实标签可学习性、吞吐、跨 GPU 数值与恢复、规范的训练/验证/追踪入口仍需
实际交付物和实测；任何真实字段 R²<0.95 且可能源于标签/数据的问题应按指南停止
并报告，不能靠放宽阈值或修改 mask 掩盖。

旧原生S键属性的可选DecodedSample transport已整合。定向643为49通过/2CUDA跳过；完整分支648–651及Root656–659均2,388通过/2跳过、102文件。详03_s_bond_transport.md及S_native_bond机器证明；不是D1 wire或D3真实新标签验收。
