# 阶段 2：等价提速与选择性 bf16

## 2026-10-29 current A-v2 evidence

This section supersedes the historical status/rules below. Original A5-v1
failure is retained. User-approved gradient v2 is the existing per-parameter
absolute+relative rule1e-8+1e-4*abs(reference), with both norms<=1e-8 for
analytically zero-gradient parameters. Original fixed20 forward and500-loss
trajectory checks remain. A-only distance-head bias parameters remain unchanged;
the equivalent bias=False removal belongs only to C.

Eight of nine previously passing A cases have now passed current full20+500
A-v2 rechecks. The ninth original3090/node0 case has no current result: its
published, bounded readonly waiter is live until the original node has16 actual
free CPUs. Historical PASS/timing is not substituted. Fused/TF32/A5 failures
and all other failed candidates remain recorded; no blanket A acceptance.

Seven complete same-card R1 ABBA groups are below. All28 actual timing runs
have full native22-row typed SDK certificates, official selective sync, cloud
route/state/count/endpoints readback and actual GPU-parent C0. Each uses
2warmup+20measured updates. The ratio is the original pooled candidate/reference
throughput from the unchanged speed-report tool; it is not a per-member estimate.

| R1 cohort | GPU | Compared execution | Original pooled ratio |
| --- | --- | --- | --- |
| Original A00 current-v2 | 5090/C35 | A00 control | 0.9918131766322366 |
| Original HeadOff current-v2 | 5090/C35 | head checkpoint off | 1.0584113049897554 |
| routing7 old405 | 4090/ec788 | A00 control | 0.9982591653241504 |
| routing7 old486 | 5090/C35 | legacy A00 control | 0.9997377878334807 |
| routing7 old456 | 4090/ec788 | backbone checkpoint off | 1.2248576848497117 |
| routing7 old411 | 5090/C35 | A00 control | 1.0053769622391804 |
| routing7 old549 | 5090/C35 | legacy head checkpoint off | 1.0693858781321288 |

[Standard28-run CSV](results/performance_R1_20261029.csv),
[exact bindings and original-source references](results/performance_R1_20261029_bindings.json)
and [field/elapsed/peak semantics](results/performance_R1_20261029_README.md)
retain real run IDs, raw configuration SHA distinct from canonical SHA, GPU
UUIDs, actual parent elapsed, input snapshot and independent numerical closures.
The five new Root joins and original-tool reports are in
[closed evidence](results/remaining_R1v3_ABBA_closed_20261029_v1/).
The measured backbone/head checkpoint effects are engineering evidence; final
GPU-specific recipe adoption awaits the remaining guide requirements. Allocated/
reserved peak fields are original PyTorch measurements, not physical GPU maxima.

B is still incomplete. Original four20k plan currently has fp32seed0=20000,
bf16seed0=9000; original segment9000->10000 waits for its5090 UUID.
Both seed1
members have not started. No full four-member41-point envelope/noise2% pass
is claimed. Existing Native S enables this authorized work before Data D5;
actual DataD2-D6 remains missing. Final source/config/tag/HANDOFF/PR and formal
training have not been frozen or started. No downstream TEST results are used.

## Historical report retained unchanged below


日期：2026-10-25（Asia/Shanghai）。状态：独立候选与门槛工具已实现，
A03通过完整A类数值验收，但单模型ABBA未见加速，暂未采用A优化；B类真实精度
验收仍待D-5，默认旧路径未修改。

最新真实执行见[逐作业状态](02_A_actual_runs_20261025.md)：三种GPU的A00完整
控制已通过；A06轨迹失败，5090当前设置的A05/A01/A02因OOM或85%容量失败，
A07固定20批数值门槛失败；A03原20/500通过、ABBA观察0.8661倍而不采用。
其他GPU的优化速度与D-5真实bf16验收仍未完成。B执行、验证、恢复控制器已整合并完成
专项与全量回归，513/514独立CPU合成CLI闭合；下文早期“B执行尚待实现”段落
为历史阶段说明，以[当前B实现](02_B_precision_execution.md)及EXECUTION为准。

## 问题和预注册

问题：能否保持旧路径可复现，在可审计的数值与训练轨迹约束下提高吞吐并降低
内存？bf16 是否在两组预训练种子的波动内保持所有 S 验证指标？
预注册见 `3441b280bc34431bf8e7596465af28be073644b6` 的
`docs/model_v3/DECISION_RULES.md`；更细的执行绑定应在相应实验前提交。

## 实现范围

新增 `current/phychem_mfm/model/v3_performance.py`：

| 候选 | 实现 | 采用条件/当前限制 |
| --- | --- | --- |
| 关闭 checkpoint | 主干、距离 MLP tile、等变头 chunk 三个独立开关 | 不只关闭 backbone；自动选择须有同模型、同实际 GPU 容量、相应 batch cost 的 all-off 实测证据，否则全部保守开启 |
| compile | 编译 backbone 的 bound forward，保留 state keys 和 H0 API；dynamic shape 可配置 | 实际编译、重编译次数与速度未验证；Python/图中断不能当作加速成功 |
| fused AdamW | 显式 fused=True CUDA 候选 | 保留默认 optimizer 路径；先验证数值与轨迹 |
| TF32 | 可恢复的执行 context，离开后还原两项全局开关 | 不能假定它满足 fp32 1e-5/1e-4 的门槛 |
| 稀疏 radius | 按查询块构造邻居，仅算有效邻居 score/bias/softmax/聚合 | 原配置必须已经启用 radius mask，且 dropout=0；不得截断原全局注意力。基线 use_radius_mask=false，故默认配置不能由该候选宣称稀疏收益 |
| 较少 padding | `phase1/v3_padding.py` 可调桶宽及块内按精确原子数排序 | 保留 singleton/tail/已消费恢复；排序有独立 sampler contract，可能改变 batch 和训练轨迹，必须实测，不能当作自动数学等价 |

所有新执行模块复用原 Parameter、子模块名称与 state-dict 键；没有修改
factory.py、shared.py、attention.py、heads.py 的历史实现。新模型通过
build_performance_model 显式构造；仅在所选路径上启用候选。

bf16 只包裹主干 QKV、QK、AV、projection 和 FFN 的矩阵运算。参数保持 fp32，
层归一化、位置、平方距离、距离偏置 MLP、RBF、等变头和最终 H0 保持 fp32。
performance_forward_pretrain 显式关闭外围 autocast，避免误把所有头转为 bf16。
这是一条待验证的保守实现，不是全模型 bf16 或旧 runner 已支持 bf16的声明。

## 数值与实验门槛

`training/v3_performance_acceptance.py` 将数值判定与实现分开：

- 固定20批：逐个 floating 输出和逐参数梯度的 L2 相对误差分别≤1e-5、≤1e-4；
  分母 max(reference norm,1e-12)，审计累积用 fp64，缺失梯度/形状/非有限值
  单独判失败。停用头两侧都无梯度是合法情况，单侧无梯度失败。
- 相同种子500步：每个更新都要有记录，每步 loss 相对差≤1e-3。不能只检查
  最终值或平均曲线；步数缺失、重复或非有限值不能升级为通过。
- B类：fp32与bf16各两个不同且配对的预训练种子，每次达到20,000更新，使用
  完全相同的验证时点和字段。每条bf16曲线逐点位于两个fp32种子的范围内；
  去噪RMSE另外按相同种子配对，逐点相对差≤2%。原始曲线和负面结果保留。

门槛函数自身不能证明数据/模型/运行来源匹配；执行器和主 agent 必须另核
配置、真实输入顺序、源 SHA、实际种子和 Slurm/W&B终态。

## 测试与结果

默认环境的A00 synthetic固定批375未通过原逐参数门槛，保留失败。随后同源、
同toy、同初态的独立诊断381证明旧模型自身R1→R2/R3也失败；仅六层
`backbone.layers.{0..5}.attn.dist_mlp.2.bias`，原梯度范数约1e-9至6e-9，
绝对差约1e-10至1e-9。R2=R3能重复，但不能据此删除首遍或参数。

384在Torch导入前绑定`CUBLAS_WORKSPACE_CONFIG=:4096:8`，开启严格
deterministic algorithms（warn_only=False）及cuDNN控制后，6组比较的全部
forward/逐参数gradient原门槛通过，逐项差为0，含同实例三次、第二原模型与
A00。两个mode输入和初态SHA相同，bias的舍入残差仍非零，没有被清零。
这是可重复性诊断，不是原生20批/500步或A类验收；尚未定位到单一CUDA算子。

据此新增显式opt-in `--deterministic-controls`，供paired及单模型CLI共同使用：
在任何Torch导入前绑定CUBLAS，再在CUDA初始化前应用Torch/cuDNN/TF32基础
控制；reference和candidate同控。原PerformanceOptions声明的TF32候选覆盖
仍独立保留。未传flag时不修改既有环境或Torch开关；配置/环境receipt记录请求、
导入前状态、实际状态和执行签名。ABBA及其numeric gate要求执行签名一致。
阈值、分母和参数集合不变，375/381失败不改写。此新增接线尚待CPU回归和
新原生运行，不继承384对单个toy的通过结论。

确定性控制的CPU实际396已32项PASS，前后源SHA一致；提交
`0e984c1aee9bb875bdbee6c6cbac254e7b5bdbcb`。其后发现并独立修正优化器
route：Torch2.10只有fused与foreach均None时保留默认自动foreach选择，因此
未请求fused时必须省略该参数，不能传False而改变控制组的执行路径；请求时
仍显式fused=True，不强制foreach。新增真实CPU defaults/配置保持及CPU拒绝
fused测试待根调度。此修正不更改A数学门槛，也不授予CUDA轨迹通过。

新增 `current/tests/test_model_v3_performance.py` 检查：稀疏/密集输出与梯度、
padding、拒绝全局截断和不兼容 dropout、checkpoint 开关的参数/数值一致性、
选择性 bf16 的实际 dtype 边界、compile API 包装后的 key 不变、容量证据的
保守选择、精确排序的覆盖/尾部/singleton/恢复，以及门槛负例。

实际4520333在compute-0-20的CPU allocation中通过上述8项候选测试，以及阶段1
此前失败的synthetic fixture补测，共9项；父作业COMPLETED/0:0，16秒。
编译这一项只检验API封装与state keys，没有执行真实Torch编译，不能当作编译提速
或数值验证。CPU合成测试不替代20批真实前向/梯度、500步轨迹、三GPU性能
或20k步bf16对照。

新增执行器 `tools/model_v3/paired_a_acceptance.py` 准备将真实native S固定20批
按批比较输出和梯度，清理预取后重置已消费游标，再比较500个相同输入的更新。
门槛失败时保留证据，不自动把候选采用。两模型同卡常驻，记录的compute timing
只是成对诊断值，不是独立生产吞吐。`--smoke`/synthetic不能授予A类验收。
其S流reset/关闭测试已纳入4520339完整2040项PASS回归；这不代表GPU执行器
或真实20批/500步已通过。CLI审阅、逐GPU单项/叠加矩阵、容量与恢复规则见
`02_A_execution_matrix.md`；选项JSON位于`current/configs/model_v3/performance/`。
独立A工作树已补原snapshot rawSHA/完整配置/storage绑定、输入/消费receipt，
并实现单模型无profiler速度成员及ABBA汇总；尚待CPU/GPU验收。改变batch组成
的bucket/sort仅作单模型探索，paired早拒绝，不冒称A等价。中途checkpoint/resume
明确不支持，失败保留partial并fresh重跑。原native工作树Python继续冻结。

4520350实际新增native pin/trace归因/私有存储及既有定向回归31/31全部PASS；
343旧synthetic trace另已实际生成`attribution_v1.json`，唯一kernel3102、重复0。
旧trace没有新tile标签的部分不补造。真实3090/4090的4520352/353均完成
2warmup+20测量更新，随后分别因RSS上限、trace触及预留输出空间而FAILED；
不是A数值失败。原费用与partial保留，不放大56GiB/2GiB限额。5090的4520354
尚未闭合，未据此填写A类数值、提速或B类结果。阶段1代表步小trace补救由根
协调者在另一个独立工作树处理，与本A实现分开绑定。

| GPU | 候选单项/叠加 | 原始吞吐 | 候选吞吐 | 倍数 | 前向/梯度/轨迹 | 当前决定 |
| --- | --- | --- | --- | --- | --- | --- |
| 3090 | 待测 | — | — | — | 未验收 | 保留旧路径 |
| 4090 | 待测 | — | — | — | 未验收 | 保留旧路径 |
| 5090 | 待测 | — | — | — | 未验收 | 保留旧路径 |

## 未解决问题

三类 GPU profiler、无 checkpoint 容量表、真实 compile/fused 数值、500步轨迹和
代理规模20k步四次精度训练均未闭合。D-5嵌套代理分子清单尚待数据线交付时，
不得把其他临时子集冒称规定的240k代理人口。速度选择只能在数值验收之后进行，
当前没有采用任何候选，也没有启动正式预训练。

## 首个完整优化候选的实际负面结果

5090 fused AdamW候选4520457完整执行20固定批与500更新，Slurm
FAILED/1:0、2272秒。固定前向/梯度全过，但477/500损失点超过原1e-3门槛；
首个失败为step14，相对差0.0029128788627426007；最大为step379，
相对差0.18546434093044833。500步消费201,216个base records，未放宽门槛。
因此当前不采用fused，不授予A类验收，也未导出checkpoint。

只读机器对照证明457的reference与同GPU的A00/411，500步loss、gradient_norm
及input receipt SHA逐项完全相同；候选唯一科学选项差异为fused_adamw。
两个Git执行提交不同，54共同源中51字节相同，其他三项为export/source与监督接线；
模型/性能数学源相同。该证据定位到优化器执行路径，尚不证明单一内核的完整轨迹因果。
独立同参数/同梯度/同AdamW状态的短CUDA舍入诊断另行准备，不重跑500或修改结论。
机器原始收据位于外部a06_optimizer_diagnostic_v1_source，包含各原文件raw SHA。
