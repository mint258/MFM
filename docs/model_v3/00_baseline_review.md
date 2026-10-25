# 阶段 0：现有模型与训练路径审阅

日期：2026-10-25（Asia/Shanghai）。基线提交：
`037546cd7f07b32dbb46bc21a69109dfd273f8da`，仓库 `mint258/MFM`。
本阶段仅审阅代码、统计参数并用合成输入核对 H0；不读取真实标签或下游结果。
状态：实际参数审计通过；阶段验收以本报告和仓库检查的提交为准。

## 问题、范围与来源

目标是明确 6 层、512 维基线的真实实现，而不是把旧 4 层、384 维
S 实验的规模、数值和性能直接沿用。审阅包括 factory、shared、backbone、
attention、heads、routes、Phase1 objectives、geometry/degrade、full corpus
loader、S runner v8/训练组件、下游训练/readout/provider/Stage60 worker。
逐文件 SHA 与合成 H0 输出形状由 `tools/model_v3/baseline_audit.py` 记录。

历史补丁原件位于服务器
`runs/s_denoise_repair_20261016/reports/core_repair_patch_v1/s_denoise_core_v3.patch`。
当前主分支已收入对应的 EquivariantDenoisingHead 和 objectives 修改；不重复
套用补丁，不修改历史 source_v3、冻结配置或 SOURCE_MANIFEST。

## 1. 模型与参数量

`factory.build_model` 构建 SharedBackboneMFM。每层为 pre-norm 注意力和 FFN，
原子嵌入后密集 padding，最后 out_norm；默认 shared-light 的 adapter 无参数。
本阶段基线固定 dim=512、layers=6、heads=8、ff_mult=2、119 类原子/保留类型，
其余参数沿 A4；这不是旧 S 配置的覆盖或新架构的胜出决定。

实际 CPU 参数统计如下（A4、6×512）。

| 模块 | 参数量 |
| --- | ---: |
| backbone | 12,709,424 |
| energy_head | 1,052,164 |
| charge_head | 513 |
| element_head | 61,047 |
| geometry_head，A4 | 71,873 |
| bond_head | 792,581 |
| 23 个 graph_descriptor_heads 合计 | 6,076,508 |
| 3 个 charge_descriptor_heads 合计 | 792,579 |
| 3 个 element_descriptor_heads 合计 | 796,170 |
| graph_pool / shared-light task_adapters | 0 / 0 |
| 完整模型 | **22,352,859** |

各 graph 字段均为 264,196 参数；acceptor、donor、estate_index、is_aromatic、
is_in_ring 各为 264,193；min_ring_size 为 267,784。A4 之外的预测头合计
9,571,562，所有预测头合计 9,643,435。只启用 S 时相关主干与三个 S 头共有
13,634,925 参数；这是模块归属计数，不是逐步实际非零梯度测量。

对照：同样 6×512 加旧 residual 头为 22,297,595 参数（geometry_head=16,609）；
旧 4×384 S 模型完整参数为 10,216,035。因此“约 1,000 万”不是新完整模型的
实测值。本线保持要求的 6×512；未来 H1/H2/H3 比较可能改变预测头参数量。

合成两个分子、5 原子实测：encode_atoms(batch) 输出 [5,512]，
encode_graph(batch, pooling="mean") 输出 [2,512]；两个 API 签名不变。
逐模块/逐字段和三套完整配置见 `results/baseline_parameters.json`。

## 2. 精度和实际入口

`training/engine.py` 有可配置的 bf16 autocast（evaluate 与 train 路径）。
但 `workflows/sprime_s/scripts/s_convergence_runner_v8.py` 没有调用这个 engine，
也没有 autocast/GradScaler：它自行创建 fp32 模型，直接 forward_pretrain、
compute_phase1_loss、backward、clip_grad_norm_、AdamW.step。
因此旧 S runner v8 的实际训练是 fp32，不能因通用 engine 支持而声称已用 bf16。
AdamW 此入口没有指定 fused=True；未来开关的收益和数值需重新实测。

## 3. 激活检查点

| 位置 | 触发与语义 |
| --- | --- |
| `current/phychem_mfm/model/backbone.py:73` | backbone.activation_checkpointing=true 且训练、启用梯度时，每个完整 Transformer 层 non-reentrant 重算 |
| `current/phychem_mfm/model/routes.py:128` | Expert adapter 的独立 activation_checkpointing 开关，训练且 H0 requires_grad 时 reentrant 重算；shared-light 不走 Expert |
| `current/phychem_mfm/model/heads.py:152` | 等变头可选 scalar message 的每个 pair chunk，启用梯度时 non-reentrant；A4 message_layers=0 不执行这条路径 |
| `current/phychem_mfm/model/heads.py:158` | 等变去噪预测每个 pair chunk，启用梯度时 non-reentrant；没有独立关闭开关 |
| `workflows/sprime_s/scripts/s_model_memory_v1.py:31` | TiledDistanceMLP 超过 pair_rows 时逐块 non-reentrant，保留 Parameter 对象和 state-dict 键；旧 runner 实际使用该构建器 |

仅关闭 backbone 开关不能宣称关闭了全部检查点。后两种分块也可能在嵌套
检查点下重复重算；必须由 profiler 测量，不能由源码推断开销比例。

## 4. 三视图及监督来源

| 视图 | sample_type_id | 实际监督 |
| --- | --- | --- |
| clean | 0 | S：正边五分类键级，无非边/存在分类；P：PM7 生成热和 NET ATOMIC CHARGES；D：保留的 graph/node descriptor |
| geom | 1 | S：几何恢复；旧 S 用距离损失，A4 用归一化噪声向量 MSE。target_pos 为未加噪坐标 |
| topo | 2 | S：仅 actual-changed 合法元素的分类；padding 和没有发生替换的原子不计入 |

当前 loader 建三个视图，topo 不删原子，geom 不做局部扭转或键长缩放，
仅加高斯噪声。geometry_level=0.2 经 DegradeConfig 映射为 sigma=0.1 Å，
不是 sigma=0.2 Å。原子 x 是 Z-1；局部 generator 保持模型 RNG 独立。
完整 loader 默认 seed+logical_index；新修复路径可显式启用 epoch 哈希。
比较必须固定并记录此选项，不将两种噪声时钟混用。

A4 默认半径 5 Å、32 RBF、hidden=64、normalization=none、message_layers=0、
pair_chunk_size=8192。它预测 Σ c_ij rhat_ij，恢复坐标由 noisy_pos−noise 得到；
loss 为对有效原子的向量平方误差按 3 sigma² 归一化。旧距离项保留诊断，
不成为 A4 总损失里的另一个 S 子任务。

## 5. 采样、预算与预取

旧 S 配置：每批最多 512 个基础结构、65,536 个 native atoms、
8,000,000 padded cost；bucket width=16、block_size=4096。
padded cost = 3 × 基础结构数 × 本批最大原子数²，乘数 3 是三个视图。
原子预算与分子上限按基础结构计算，不能把 65,536 当成展开后的总原子数。

BlockAtomBatchSampler 在有界块内 shuffle 后按原子数桶稳定排序，块顺序为
声明过的 affine permutation。它均匀覆盖结构记录，不是“先均匀分子再抽构象”；
后者需要 v3 新采样器。超预算结构保留为 singleton，末尾 partial batch 保留。
预取不推进持久游标，只有 commit_batch 推进；恢复必须丢弃未消费预取。
原 S 是 8 个 spawn workers、prefetch_factor=2、非 persistent、pin_memory，
worker timeout 经已记录修订为 600 s。旧句柄/cache/map-close 规则需保留。

## 6. 损失的真实组合与 v3 变化

旧 Phase1 policy 先平均每个任务的有效标注，再固定任务权重平均，最后按
启用组的权重平均；S/D/P 默认各 1。D 有 23 个分子回归字段及 6 个原子字段；
P 为 energy/charge；S 为 element/distance/bond_order 或 A4 的 element/
denoise_eps_mse/bond_order。停用组不进入总分母，所有启用组从 exposure 0 生效。

缺失任务目前是 detached zero，但其权重仍留在组内分母。旧连续目标对残差
除 TRAIN std 后用 Huber delta=5，分类另用 CE/BCE。这与新指南要求的
“只平均本批有有效标注的字段、Huber 默认 delta=1”不同：v3 应另设新路径，
保留旧策略和结果，不静默改历史定义。组内字段多少不应改变组间权重。

旧 element_entropy_reg=0.05 在 no_grad 中计算，只改记录的 loss 值，不提供
熵正则梯度；element_logit_l2 和标签平滑另有有效梯度。此事实应披露，
不能把旧数值损失当作有效熵正则实现。旧 S 关闭 dynamic balancer。

## 7. 下游角色及开发边界

DownstreamTrainer 只接受显式 train/train_inner_validation batch；本身校验
输入张量和掩码，不独立证明样本来源。FrozenDownstreamStore 才绑定角色成员。
对带 scaffold folds 的数据，外层 fold=t 被排除，内层验证为 (t+1)%10，
其余 8 folds 优化。这个角色不是官方最终验证集，也不能直接拿某次外层结果选型。

ExpansionRx 的旧 official contract 只有官方 TRAIN 与官方保留部分，
train_inner_validation 为空。v3 开发面板须只在官方 TRAIN 内另建、冻结分子划分，
不改官方成员或既有 provider 合同。SoM 保持 source atom IDs、候选与监督 masks。

SourceAlignedH0Readout 是 H0 后的读出，保持原子对应；冻结/微调归调用者控制。
Stage60 的 `run_formal_readout.py` 导入并调用 evaluate_outer，用于旧完整正式矩阵，
不可作为本轮快速开发评估器直接运行。新评估器应独立限定 TRAIN 内层数据。

## 验证、决定与限制

参数审计作业：4520329，compute-0-20，16 CPU / 16 GiB / 10 分钟上限，
输出根 `/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025`。
实际 job/batch/extern 均 COMPLETED、ExitCode=0:0、ElapsedRaw=251、
AllocCPUS=16；真实分配成本为 4,016 CPU 秒（1.115556 核时），无 GPU 计算。
这是参数统计和合成 H0 shape 验证，不声称完整回归测试或训练验收通过。
仓库检查在提交前单独运行，结果见外部 repository_check_stage0.json。
本阶段不做架构优选。

下一步是在阶段 0 报告与预注册规则提交后启动 SA-1 性能、SA-2 标签损失、
SA-3 评估分支；SA-4 在 profiler 结果之后。当前主分支未观察到 D-1 至 D-6
正式接口与训练导出；先做现有 S 与合成实现，真实数据验收不能用合成测试替代。
