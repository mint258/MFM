# 固定 H0 后的 encoder 下一步诊断：源码审阅 v1

日期：2026-10-27。范围：只读源码与既有小型 JSON 元数据；未运行 Python、模型、SDK 解码或作业，未读取 H0/权重 NPZ，未修改候选及冻结源。本文件是诊断建议，不是新候选、数值验收或架构选择。

## 结论与待否证问题

`compensated_fp32_v1` 并未替换整个 encoder 的 FP32 算术。它补偿直接三维距离的加和，以及显式调用它的分段聚合；原 QKV、QK/AV、距离/RBF/FFN 的 Linear、softmax、LayerNorm 和残差仍使用原生路径。因此，“已有补偿路径但仍出现 H0 误差”不能排除 encoder 内的舍入及其传播，也不能直接归因为某一 GEMM 或 GPU 缺陷。

Root/SA4 已闭合的 CPU1503 统计为：固定实际1492 H0 后，FP64 头仍有31/48组合、65/432字段变换超过1e-5；81个 GPU 超限 argmax 中61个由继承 H0 的 H 项主导，G≤2.56e-7、I≤4.29e-11。这里引用该既有统计，没有重新计算。它支持下一步定位 encoder，不证明具体哪层、哪个算子造成误差；其他 argmax 也不能据此抹去头算术贡献。

最小可否证目标：在原48组合、每组合 baseline 加3个既定变换的192次完整 forward 中，先验证新增观测得到的 **全部实际 bank H0 与1492逐位相同**，再观察误差第一次出现及增长的位置。若不能重放，结果必须标为 `REPLAY_MISMATCH`，不能用新内部值解释旧1492，更不能称为1435的 H0。

## 实际覆盖及未覆盖路径

审阅对象为 `MFM_model_v3_numeric_stability_v1/current/phychem_mfm`。`config.numeric_stability_configuration` 将顶层 mode 同时绑定 backbone/head；`factory.build_model` 交给 `SharedBackboneMFM`；`apply_numeric_mode` 给子模块附加 mode 元数据。该元数据本身不会改写一个模块的任意运算。

| 真实路径 | 已有补偿 | 仍为原生 FP32 的运算及限制 |
|---|---|---|
| `model/v3_numeric_stability.py::_square_sum3/_Norm3` | 三项平方的加和使用 two-sum；直接坐标差按65536 pair 行分块 | 坐标相减、各分量平方、最终回写 FP32、sqrt 仍舍入；没有恢复坐标变换前的精确几何，也没有整体误差上界 |
| `compensated_index_add/compensated_pool` | 排序分组、平衡 pair 树、高低项累积；pool 显式调用该实现 | low 项自身仍经 FP32 加法；mean 的除法仍 FP32；这主要覆盖头/池化调用，不意味着 encoder 的所有 reduction 都被替换 |
| C1-0 `DenseGeoSelfAttention.forward` | distance bias 输入的三维距离平方和 | `qkv`、QK 的64维点积、dist MLP 1→512→8、logits+bias、softmax、AV 对 key 的聚合、输出投影均原生 |
| C1-a/b `SharedGaussianPairEncoder.forward` | 三维直接 Euclidean norm | C1-b pair scale/shift、softplus(width)、减中心/除宽、square/exp/RBF 归一化、两层 project 均原生 FP32 |
| C1-a/b `SharedPairAttention.forward` | 复用上述 pair feature；未另加 attention 补偿 | QKV、QK、pair projection、softmax、AV、输出投影均原生 |
| 两类 transformer layer/backbone | 保留原数学及512维 API | norm1、norm2、out_norm 的512通道归一化、FFN 512→1024→512、残差加法、mask 乘法均原生；`common.Linear` 只定制初始化，继承 `nn.Linear.forward` |

QK 的 reduction 长度64、原 fixture 的 key 长度至多32、dist MLP 隐层512、FFN 隐层1024提供了具体检查位置；这些长度不构成已证明的误差来源。LayerNorm 的实际输出可观测，但模块 hook 不能证明其内部均值/方差或硬件累加器精度。

原矩阵配置为6层、512维、8头、ff_mult=2、dropout=0、global attention、无 radius mask、Gaussian cutoff=None。不能把硬8Å截止不连续作为本矩阵解释。原 `pushed_views` 先用 double 做刚变换，再 `.float()`；变换后的输入坐标本来就存在 FP32 舍入。补偿三项平方和不能撤销这种输入差异。

C1-0 的实际源保留 `TiledDistanceMLP`，pair_rows=65536、训练时每 tile 可 checkpoint；本 fixture 最大 B=9、N=32，仅9216个 pair，且 eval/inference 下没有 checkpoint replay。这里既未测试 tile 分界，也未测训练重算。`v3_performance.py` 的 RuntimeDenseAttention/RuntimeFFN/sparse 路径不属于实际48组合，不能因 mode 属性存在就宣称该组合路径已补偿或已验证。

### 半径、邻接和 envelope 的精确来源

以下判断不能仅凭“拓扑公式相同”略过；FP64 范数可能在临界值两侧给出不同布尔结果。

| 来源/signature | 原判断和影响 |
|---|---|
| `attention.py::DenseGeoSelfAttention.forward(self,x,pos,mask)` | 仅 `self.use_radius_mask` 为真时，`dist2 > radius*radius` 的 logits 填 -1e9；等于半径的 pair 保留 |
| `v3_architecture.py::SharedPairAttention.forward(self,x,pair_features,distances,mask)` | 仅半径 mask 启用时，`distances > radius` 填 -1e9；同样保留等号 |
| `v3_architecture.py::SharedGaussianPairEncoder.forward(self,pos,elements,mask)` | 仅 `options.cutoff is not None` 时，`where(distances < cutoff, 0.5*(1+cos(pi*distances/cutoff)), 0)` 乘 pair feature；另有固定 padding pair_valid |
| `v3_architecture.py::ArchitectureOptions.validate_attention(self,backbone)` | global attention 必须 cutoff=None；半径 mask 启用才要求 finite cutoff 与 attention radius 一致 |
| `heads.py::EquivariantDenoisingHead._edges(self,pos,batch)` | `valid & ~eye & (distance < self.radius) & (distance > 1e-8)`；本矩阵 vector radius=5Å。`_features(self,h,pos,src,dst)` 另有 norm clamp_min(1e-8) 与 cosine envelope |
| `v3_heads.py::_PairHead.forward(self,h,pos,pairs)` | 默认 radius=8Å，`where(distance < radius, cosine, 0)` 门控 RBF；不会删除外部给定的 pairs，不能把它叫 attention 邻接 |

本48实际 `build_composition` 明确 `use_radius_mask=False`，C1-a/b 用默认 cutoff=None，所以 encoder 的8Å半径判断/envelope没有启用；rbf_max_distance=8只定义 Gaussian center 范围。新诊断应在 metadata 中核对实际 flag，禁把默认字段“radius8”误读为生效边界。

F32/F64 shadow 对每个实际启用边界应记录：阈值/不等号、有效 pair 人口、两路径布尔翻转计数（分方向）、最小距阈余量、padding/eye identity及最小距离 clamp 的命中数；没有启用的 attention 边界明确记 NOT_APPLICABLE。任何翻转必须保留并单列“邻接/envelope 分支差异”，不能盲称 GEMM 舍入、筛除该 case 或改 epsilon。原 `geometry_domain(views)` 只以 double 距离检查最小 distinct distance>.05Å、距5Å余量≥1e-4；case00实际5Å余量0.0028676156659992458Å。此旧控制不能代替新F64的全48实际边集合及8Å pair-envelope比较，也不能宣称已证明所有分支相同。

## 可复用证据与边界

| 原件 | 已闭合事实 | 不能据此宣称 |
|---|---|---|
| `O/C4_GPU_layer_head_4521397/DIAGNOSTIC_RESULT.json`、`CONTROL_METADATA.json`；对应 `N/C4_GPU_firstcase_replay_v1_source/probe_firstcase_replay.py` | 首个 legacy C1-0/two/H1_fixed/seed20261026；12 encoder forwards；source 前后相同；unhooked1/2 也不逐位一致（78处比较差异），hook 比较也失败 | 不证明 observer 透明；不证明差异由 hook 导致；不包含1435 H0；不是全48 |
| `O/C4_GPU_layer_head_4521406/DIAGNOSTIC_RESULT.json`；`N/C4_GPU_fixed_op_replay_v1_source/probe_fixed_ops.py` | 同首例保留实际 GPU 输入；11个头/pool/index_add 固定操作各重放3次；原策略并非全同；独立 deterministic 诊断下11个均支持且3次同；输入摘要前后不变 | 不是 QKV/QK/AV/softmax/LayerNorm 的 encoder 诊断；同输入重现性不等于刚变换不变性；不把 deterministic 结果偷换为原策略 PASS |
| `O/fixed_h0_capture_GPU_v2_4521492/CAPTURE_MANIFEST.json`、各 `CAPTURE_CASE.json` | 全48、192实际 encoder forwards；保存真实 bank 输入/状态和同 forward 的9个 PD 输出；与原完整52 terminal 对照；source 前后相同；fresh_capture_not_1435_H0 | 没有旧1435 H0，也没有1492各层内部状态；新 layer hooks 的透明性尚未验证 |
| `O/fixed_h0_shadow_cpu_v3_4521503/SHADOW_RESULT.json` | 对实际1492的固定输入作 CPU FP64 头分析；H/G/I及 head-arithmetic signed closure | 没有重跑 encoder；不是生产 FP64 候选；不授予原48门槛通过 |

O=`X:/runs/model_v3_20261025`，N=`X:/runs/model_v3_20261026`。1492的可用起点是其实际 `BANK_INPUT_STATE.npz` 及原始 capture refs；本次未打开这些文件。1435的 terminal 与1492 fresh capture 必须保持不同 lineage，不能由 terminal 输出倒推出缺失的旧 H0。

1492保留的透明边界可复用：原 builder 委托一次；bank hooks 只保留 Python tensor 引用，返回 None；完整原 `forward_pretrain` 返回之后才复制到 CPU；原返回对象不替换；bank 参数前后 hash；9 PD 输出逐位对应同一次 untouched terminal；finally 移除 hook/恢复 builder。旧1406的固定输入/前后摘要/独立策略恢复机制也可复用，但不能复制其“已经支持”的结论到新 encoder 算子。

## 下一诊断的最小捕获与解释

### 1. 先通过完整 replay 门

固定1492原 source、参数 seed、同一 c35 RTX5090、原 PyTorch/CUDA/数值策略、case 顺序、输入/变换与 head 配置。原 policy 的 TF32关闭、float32 matmul highest、autocast关闭、threads=1保持；原 deterministic_algorithms=False 不在主路径偷偷改为 True。

全48×4逐位比较实际 clean bank H0，以及 bank state、pos、batch、pair kwargs 的 identity/shape/dtype；保留原52 terminal 对照，避免只通过 clean H0 而漏掉 noisy view 的 S 路径变化。PD bank 的 H0 是44×512；完整 encoder packed H0 是两视图88×512或三视图132×512，不得混用这些人口或形状。任何不一致都保留原始差异并停止对1492的因果归因；不靠重试筛选“碰巧一致”的 seed/case。

### 2. 最少的真实 module 捕获点

| 源函数及真实 signature | 最少捕获内容 |
|---|---|
| `shared.py::SharedBackboneMFM.encode_atoms(self, batch)` | 原 API 返回的完整 packed H0；仍为 source atom order、512维 |
| `backbone.py::RealCoordTransformerBackbone.forward(self, data)` | atom embedding 后、各层 pre/post、out_norm pre/post、最终 packed 返回 |
| `v3_architecture.py::SharedPairBackbone.forward(self, data)` | 同上；另记录实际 pair encoder 输出 |
| `attention.py::RealCoordTransformerLayer.forward(self, x, pos, mask)` | 每层实际输入/输出；norm1、attn、norm2、ffn 的模块边界 |
| `v3_architecture.py::SharedPairTransformerLayer.forward(self, x, pair_features, distances, mask)` | 同上；绑定共享 pair feature/distance 与 mask |
| `attention.py::DenseGeoSelfAttention.forward(self, x, pos, mask)` | 原返回 `(output, attn)`；qkv、dist_mlp、proj 的真实模块输入/输出 |
| `v3_architecture.py::SharedPairAttention.forward(self, x, pair_features, distances, mask)` | 原返回 output；qkv、pair_projection、proj 边界 |
| `v3_architecture.py::SharedGaussianPairEncoder.forward(self, pos, elements, mask)` | 原返回 `(pair_features, distances)`；project 的模块边界 |
| `attention.py::DenseFFN.forward(self, x)`、`nn.LayerNorm.forward(self, input)` | FFN及每层norm1/norm2、最终out_norm输入/输出；不声称观测到内部累加器 |

建议首版以六层输出、末 norm、pair/distance 为主，不必先把所有功能算子做成新门禁。若需要在单层内进一步区分，原生实际调用点是 `torch.matmul(q,k.transpose(-2,-1))`、`torch.softmax(logits,dim=-1)`、`torch.matmul(weights,v)`，以及 RBF 的 affine/softplus/div/exp；纯 module hook 不足以捕获这些中间值。可用有严格 layer/phase 标识的 scoped TorchFunctionMode 委托原函数恰好一次，记录实际输入/输出引用。没有实际命中就写 NOT_OBSERVED，不能重算一个近似值冒充真实中间值或声称 Flash 内部精度。

hook 中只保留引用，不 clone/cast/同步/重排，不替换输入或返回；原完整 forward 返回后再做拷贝、摘要与比较。不得在同一原 forward 内提前做 scalar `.item()` 或 CPU digest。所有 wrapper/hook finally 恢复，模型状态、source 及 RNG 控制必须可核对。

### 3. 明确可否证的读法

对 baseline 与三个既定刚变换，按同一 valid atom/channel 对齐，记录每个捕获点的 maxabs、RMS、范数和误差分布摘要；clean view 与完整物理视图分别统计。可记录同一误差链的 pre/post 比值作为经验敏感性，不能称为形式条件数或仅凭不同 argmax 的比值证明放大。

- 若相同元素/顺序的 embedding 或几何进入前的相同 norm/QKV 输入已经得到不同输出，先标记同输入 repeatability 问题；不能把该差异归为距离扰动传播。
- 若首先在 distance/RBF 出现可见差异，随后在某层 QK/softmax/AV/FFN/LayerNorm 边界增长，可将该边界列为进一步固定输入诊断的位置；这仍不是单个算子的最终因果证明。
- 若层输出到末 out_norm 的误差明显增长，可直接否证“误差全部已在最早几何端固定且之后无放大”的假设；反之也能否证该假设的对应版本。
- 只有必要时才在完整原测量结束后，对已保留的某个实际输入做原策略固定算子重放；额外 deterministic 阶段必须单独标诊断并恢复控制，不能改原验收策略。

SA4另行准备的192次 FP32 加192次 FP64 encoder shadow可复用此逐位门和层级摘要。FP64只能是诊断反事实：明确哪些 dtype-preserving 打包/FP32 guard 在 shadow 副本中改变，不能把它当已满足生产FP32、原补偿算法或1435 replay。此审阅不实施该 shadow。

## 预算与有限输出建议

1492原实际 capture：16CPU、同一 c35 RTX5090；192 forwards；监督 elapsed47.745s、Slurm48s；输入/输出 capture 在 manifest 前87,695,148B，原128MiB capture cap内。case00峰值 allocated130,524,672B、reserved140,509,184B只代表该原观测，不是新 hooks 的全矩阵容量证明。

新逐层 replay 的时间尚未实测。计划可沿用16CPU/32GiB、RSS28GiB、原1100s级监督窗口、whole output≤2GiB/private≤2GiB、85%容量及公共 UUID 锁等既有守卫；不为本诊断新增长程预约或扩大上限。原48s是下界参考，新增拷贝/汇总需余量；不能把粗略倍数当已测 throughput。若与SA4的额外192 FP64 forwards合并，必须明确总384，仍由Root按同窗口准入。

静态体积：最大 dense node activation `[9,32,512]` 为589,824B；packed132×512为270,336B；clean44×512为90,112B。仅“六层×192次”的 clean FP32 H0原始值约103.8MB；保守按全部132 packed行算约311.4MB。单个最大 dist MLP 隐层 `[9,32,32,512]` 约18.9MB，六层四 role 若全保留会显著增加显存。不得把全部 QKV/RBF/FFN/attention 张量写成大 trace。

推荐每个完整 forward 返回后尽快汇总、按 case释放引用，只落有限 per-layer JSON/CSV（例如≤64MiB）及必要 clean-layer 对照；如需原始层 H0，事先限额并计入 whole2GiB，而不是在看到结果后扩大预算。记录实际 sampled/allocator peaks，不能把采样 max 称为精确峰值。任何资源拒绝如实保留，不能当数值 PASS/FAIL 的替代。

## 本次机器读取的关键 SHA256

下列均为本次小文件只读 hash，不包含 tensor/SDK body 重读：

| 文件 | SHA256 |
|---|---|
| candidate `model/v3_numeric_stability.py` | `2c6ae1e6e7df199495f48852e4a66b0087cdff521b5399c2c32a5b204af06cf3` |
| candidate `model/attention.py` | `e0e51968d1dd46a91faca71c064c517b20b9027bbced3723178a9db590553aff` |
| candidate `model/v3_architecture.py` | `c2373eed4297e8ef5a0b2008c2cf9d26b8fcd1ce52d7dc17bb78da4cdeaee507` |
| C4 firstcase probe | `74d69c2b0ec398d1f07889f8ac3a7170293251f8c480b0174e1ecd97455f6f33` |
| C4 fixed-op probe | `4bfa543a0166e27874b4d8b764c67a1d62b27ad1dd7cdfea243175bccc64cced` |
| actual1492 capture producer | `ccf532df21b5801bf040a40444c7eb5ea9dc68ed1e16fc84357b49193d8d1db9` |
| actual1397 DIAGNOSTIC_RESULT | `a7d988be5b9ac6e8a437cf05af63b6292460d1d3fdda5692ef06fd0e5f26e69c` |
| actual1406 DIAGNOSTIC_RESULT | `26555ed97abfca64b5da73f7f3cfe6bd86c0ab6a5dd98bb8fcf1a9c670412ef2` |
| actual1492 CAPTURE_MANIFEST | `670bf0a21b113d1b11bad4cb82e7e6a3995ac789524fb48b285e4ab33ef713a4` |
| actual1503 SHADOW_RESULT | `112bef0fd9523d6435be35d9bb49a42a6dfe4ac2e508f4cc9c89bbb37146500b` |

保留原48组合、1e-5绝对门槛、原seed及512维 H0数学/API。没有因预训练 loss 选择架构，没有建议生产FP64、量化、距离截断、放宽阈值或排除失败字段。下一步新增观测本身仍需真实透明 replay；本报告不授予其成功。
