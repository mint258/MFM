# 阶段 4：TRAIN 内层开发面板与评估工具

日期：2026-10-25（Asia/Shanghai）。本文件说明已准备的实现及实际验证范围。
不包含任何下游最终成绩。本阶段尚未完成真实检查点的完整评估、三种 GPU
上的 D-3 SDP 2,000 步整合冒烟测试，也未实测每检查点一 GPU 小时目标。

## 1. 问题、依据与预注册

目标是用固定 TRAIN 内层任务选择模型、预测头及训练配方，防止用预训练损失
或最终下游成绩替代共同表示的开发证据。

原规则提交为 `3441b280bc34431bf8e7596465af28be073644b6`，对应服务器阶段 0
提交 b71729e 的等字节 Git tree。固定面板及本文件需在任何阶段 5 比较前由
主 agent 审阅、仓库检查、提交和发布；实际请求须记录该次面板预注册提交，
不能把阶段 0 提交当作尚未存在的面板文件的发布证据。

字段来自已有冻结协议：
`reproduction/linked_sources/docs/phase1/evidence/stage59_three_epoch_protocol_v1/actual_scientific_freeze_v1/phase1_three_epoch_scientific_protocol.json`，
原 SHA256 为 `cde2ca717934955f340a5f160a3390ff1dd6eda12c9ffbab93fc54fce0c8a2a4`。
`workflows/sprime_s/scripts/prepare_s_probe_data_v3.py:11-12` 列出已有原生字段。

原 ExpansionRx 九项均为回归；没有现成分子分类标签。用户于 2026-10-25
明确决定“允许用现有 SoM 二分类满足分类覆盖”。因此采用已有 SoM 二分类，
不阈值化 ADMET 连续标签，不新增标签定义。

## 2. 固定的九任务

| 任务 | 原生字段 | 层级与指标 | 单位/覆盖理由 |
| --- | --- | --- | --- |
| exp.LogD | LogD | 分子 MAE | 原始 source_label；ADMET、强度量 |
| exp.Log_HLM_CLint | Log_HLM_CLint | 分子 MAE | 保留原 log 标签；代谢性质 |
| exp.LogS | LogS | 分子 MAE | 保留原 log 标签；溶解度 |
| cyp.3A4 | 3A4 | 原子二分类，error=1-hit@1 | native PRIMARY_SOM；分类和原子任务 |
| cyp.2D6 | 2D6 | 原子二分类，error=1-hit@1 | native PRIMARY_SOM；分类和原子任务 |
| qm9.U0 | U0 | 分子 MAE | Ha；能量、广延/尺寸相关 |
| qm9.homo | homo | 分子 MAE | Ha；轨道、强度量 |
| qm9.lumo | lumo | 分子 MAE | Ha；轨道、强度量 |
| qm9.alpha | alpha | 分子 MAE | bohr³；响应、尺寸相关 |

未做 Hartree→eV 换算或元素参考扣除。SoM 未知注释保持 NaN/false，只有
原候选原子和原生监督掩码可用于损失和排名；无正例的分子不伪造 hit@1。
exact score ties 按原生原子顺序确定。分子读出统一固定原 `SourceAlignedH0Readout`
的 mean pooling；这与阶段 3/5 的预训练预测头池化选择相互独立。

面板定义为 `configs/dev_panel_v1.json`。其状态说明任务和规则已固定、实际
物理输入绑定尚待交付；没有据此宣称阶段 4 科学验收通过。

## 3. TRAIN 边界与分子分组

只允许 train/train_inner_validation 角色。scaffold 数据固定原 fold 0 的
训练角色及原 fold 1 内层角色；不载入该外层被保留人口的 target payload。
ExpansionRx 只从原官方 TRAIN 建立五个确定性分子内折，fold 0 作内层验证。
原 split 文件和 official 成员均不修改。

`member_uid` 是来源记录 ID，例如 `cyp:3A4.sdf:471`，不能代替化学分子。
必须提供字节绑定的 source-member→完整原 InChIKey 映射。同一化学分子的
多个来源记录、几何、原子和 isoform 共用一个组。无可靠映射时拒绝真实运行。
原 QM9 已披露跨 fold full-key 重复；因此在 TRAIN 内剔除与原 inner-validation
化学组重叠的优化成员，并记录所剔除 ID；原划分证据不重写。

每个数据集/fold 一次性按 SHA256([20261025,dataset,full_group]) 排序选择
优化最多 8,192 组、内层验证最多 2,048 组；不足上限全部保留。组内全部
原生记录/isoform 保留，任务共用同一成员清单；选取不读取标签。成员、组、
来源绑定和哈希在编码前写到外部运行目录；后续架构、种子和读出成对复用。

## 4. 选择性读取与完整性范围

旧 `FrozenDownstreamStore` 初始化会对整份 payload 和原输入执行校验。
新执行器不调用它，避免为检查 TRAIN 记录而读取其他 target frame。
`v3_dev_store.TrainOnlyPackedStore` 消费模型侧的 TRAIN-only 元数据投影：
原 allowed role、source UID、完整化学组、shape、offset、bytes、SHA；不包含
目标值、provenance 注释正文或新的标签转换。该侧车不是数据线 D-1 新协议。

消费者只声明：侧车文件 SHA、严格成员 allowlist、每条选中 native frame
的偏移/大小/SHA、P1DS1 帧结构、字面 F64→F32 坐标转换、原子顺序及掩码
验证。不会宣称重做了完整 FrozenDownstreamStore 构造或整文件校验；后者
的 SHA 只作为原冻结来源引用继承。无权威 TRAIN 元数据侧车或源身份映射时
执行器拒绝开始真实评价。尚未观察到可用的实际侧车路径和绑定。

## 5. 两类读出及共同汇总

对同一固定几何/原子成员、同一编码器状态只缓存一次原子 H0；输入仅 x/pos，
目标不进入 H0，也不存进 H0 cache。cache key 绑定完整 encoder state、架构、
几何、成员和维度；只有完整闭合、逐字节校验的 cache 才复用。中断产物保留
并拒绝升级，不删除任何已有文件。

H0 导出容量与读出 B32 分开：按原生原子数无标签分桶，桶内按原子数和原
ordinal 稳定排序，greedy packing 同时约束 max_graphs、max_native_atoms 与
max_padded_pairs=B×maxN²（单视图）。默认依次为 32、65,536、1,000,000，
bucket width=16；这些只是保守预置，不是任何 GPU 的 85% 容量实测值。
导出后恢复到既定来源记录顺序，逐条原子顺序/source atom IDs 不变；成员
不增删。超过预置预算的原生分子完整保留在 singleton 计划中并明确失败，
不丢弃、不截断、不静默放宽；这种失败不能被称为 GPU 容量实测失败。

预算方案 SHA 和逐数据集实际 packing-plan SHA 同时绑定 request、cache v3
和结果。metadata-only 计划只读已经绑定的 native_n_atoms/identity，打印计划
hash，可用 `--plan-output` 存外部方案。初始未绑定 request 只能做此计划；
实际 GPU 执行须重新生成绑定各 plan SHA 的请求。budget/member/plan 漂移
被拒绝，random/candidate 用同一计划。旧 cache 不覆写或升级为 v3。

checkpoint 加载经 `v3_encoder_bridge.load_encoder_pair`：只接受已知的 S、
generic training v1、full-corpus typed schema，先校验同一份权重字节的 SHA，
再用 weights_only=True 安全加载，不回退到不安全 pickle。S 必须匹配原始
完整 JSON 配置 SHA；其他来源必须通过其原生配置/typed seal 校验及完整
model_config 一致性，避免同形状、不同 radius/mask 等语义误配。state keys、
shape、dtype 和有限值逐项验证，不隐式转换权重 dtype；预训练种子与实际
checkpoint schema 同时绑定。scientific_stop=true 明确拒绝。

历史 B3 的确切配置与回执已单独冻结在
`configs/model_v3/historical_B3_H0_reference_v1.json` 及其 receipt 快照。
原配置实际 SHA 为 64f1e0a85f81b774d4a00cd4728766143662e196d9d8e5189550b69ad8bfed1f；
原 latest receipt SHA 为 8013f608dbd81e260f3aa358d5a97b0cdfab79e5770ebf7db1b9026ea2621043。
回执指向 segment_4515402/segment_final.pt，报告 33,314,316 committed records、
81,751 updates，权重 SHA f4a67719950277341017ae8f492ad65f721761a5523390ab97a654945a74c322。
最后一个 SHA 目前仅依据已冻结原回执，尚未独立重新读权重核验；执行器会
在使用前验证真实字节。不能仅凭 kind=B3 推断历史身份；缺任何物理绑定
都拒绝。历史 candidate 与 random 同用已冻结原 row-tiling helper，384×4、
完整配置相同，随机初始化来源与 checkpoint 权重来源分开记录。

H0 cache v3 还绑定执行 source inventory、实际 loader 源文件 SHA、权重
来源、实际 encoder 各自定义模块源文件 SHA、Torch/依赖版本、设备/驱动、
线程、TF32/matmul/deterministic 有效策略。缓存导出局部关闭外层 autocast，
要求原生 FP32 参数与输出，保留调用方全局精度策略；不把“FP32”当成 TF32
必然关闭的承诺。导出前后重新核验 runtime/实现与状态，无标签几何和
source atom IDs 进入独立 geometry SHA。不同精度、来源或几何生成不同
cache 身份，旧 cache 保留。真实 GPU 有效策略与容量尚待现场测量。

1. 岭回归 alpha={1e-6,1e-4,1e-2,1,100}，优化人口内五折分子组 CV 选择；
   exact ties 取较小 alpha。各折只用其拟合部分归一化，最终用整个优化人口
   重拟合，再预测 inner-validation；不根据 inner-validation 挑 alpha。
2. 原 `SourceAlignedH0Readout`，Linear64/ReLU、20 epochs、B32，固定最终
   端点。AdamW lr=.001、betas=(.9,.999)、eps=1e-8、wd=.01，foreach/fused
   均关闭。回归为 TRAIN 标准化 MSE，原子任务为观测候选上的 BCE logits。
   H0 冻结；按 source atom IDs 对齐；批内未知 NaN 在算术前索引排除。

参考点为同架构随机编码器（初始化 seed=20261025），同成员、同读出 seed=0。
旧 S B3 只作描述性合理性参照，必须配 384×4 随机参考，不能与 512×6 参考混用。

每个 task×readout 的改进量为 (ref_error−error)/ref_error。主分数固定为
18 个改进量等权平均，同时分别报告 ridge 九任务均值、Linear64 九任务均值
和所有逐任务误差。缺项或 ref_error=0 为明确 unavailable，不能剔除该项后
继续给完整面板分数，也不能做架构决策。

按完整化学分子组进行 1,000 次 paired bootstrap，95% CI，seed=20261025。
同数据集的一次组抽样共享给所有任务及读出；同分子多个原子/isoform 不作为
独立抽样单位。hit@1 仍按每条原生来源记录计算，再按化学组共同重采样。
“1 SD”是完全相同 seed-excluded 科学配置的两个预训练种子分数的样本 SD
（ddof=1），不混合架构或读出配方。

## 6. 执行与记录

- `tools/model_v3/prepare_dev_evaluation.py` 生成完整 source/file SHA 请求和
  可审阅的站点 sbatch；不自动提交。单 GPU、16 CPU、64 GiB，验证过的逻辑
  Python 入口由主 agent 传入；UUID 和实时资源由主协调者准入。
- `tools/model_v3/evaluate_dev_panel.py --request ... --request-sha256 ...`
  在自有 Slurm allocation 内执行；`--validate-only` 只验证元数据计划。
  驱动持有既有完整 UUID 协作锁，不能声称硬件隔离或预约；资源持续监督
  仍由主 agent 的站点 wrapper 负责。
- 每步 W&B 显式 commit，并保存 fsync 的全局单调 journal。不同读出不能
  各从 W&B step 0 重启。输出科学状态、请求/代码/数据/预注册/种子、GPU、
  各 readout 明细、成员/cache 绑定和耗时；独立 SDK history 校验另列，
  不把 journal 或 run ID 当作已经在线同步或已完成归档。
- `tools/model_v3/summarize_experiments.py` 只发布小型、类型化一行一 run
  汇总 CSV。仓库检查器仅放行 `docs/model_v3/results/<单层文件>.csv`，
  <=128 KiB、<=2,000 唯一 run、固定元数据列和数值 metric__ 列；仍做
  凭据扫描。真实样本、权重、H0、payload、W&B SDK 不进 Git。

所有输出根、H0 根在源码树外；失败/部分产物保留，不删除已有文件。
执行器完整性/性能和真实 W&B 闭合仍需实际作业验证。

## 7. 实际验证与未完成项

| 证据 | 实际状态 |
| --- | --- |
| 初版 CSV 安全组件，4520331 | 10 个测试实际通过；父作业因 SA-1 独立组件问题 FAILED，不能把父升级为成功 |
| 初版评估核心，4520332 | 8 个合成自动化测试实际通过，来源 SHA 前后相同 |
| 化学分组增强、数值 CSV 约束、选择性 payload reader，4520333 | 父作业 COMPLETED/0:0、16 秒；本组件 31 个合成测试全部通过，9 文件前后 SHA 一致 |
| 请求/Slurm/汇总/journal 初版，4520336 | 6 项合成实际通过，5 文件 SHA 前后一致；父 FAILED 来自 SA-2 独立断言，不升级原父状态 |
| H0 容量/packing 与 request/cache v2，4520342 | 本组件 27 项实际通过，0 failure/error/skip；来源 SHA 前后相同，快照已保存。不代表真实 GPU 容量已验证 |
| checkpoint bridge / FP32 runtime / cache v3 修订 | 真实来源架构512×6 / 384×4的合成加载与H0语义检查已实际通过；主树533–536完整2,368 passed/1 CUDA skip，521含真实512×6 source checkpoint/H0往返 |
| 真实历史 B3 权重格式兼容性 | 360实际只读安全加载/H0检查通过；437完整18单元COMPLETED，487完整原生SDK独立核验通过。仍仅historical384合理性参照 |
| 原已有全部测试 | 由主 agent 独立整合验证；本组件通过不替代全套验收 |
| 真实 checkpoint 完整九任务/两读出、耗时、显存 | 544成功A00短500步512×6权重，匹配随机512，18单元/1000 bootstrap完整；C0/512s，guard含清理509.330s，产物1,609,482,708B。566独立SDK VERIFIED170,295 native/56,738 history/exit0/clean EOF |
| D-3 SDP 三 GPU 各 2,000 步 | 未运行，数据依赖仍待交付 |

待完整科学运行实际闭合后，结果表须补运行 ID、配置 SHA、实际 source SHA、
数据版本、种子、GPU 型号、真实耗时、18 项及独立读出指标和 CI。当前不能
宣称阶段 4 完成，也不能用合成结果决定阶段 5 架构。

实际报告：[旧B3](04_B3_historical_panel.md)、[primary512短检查点](04_primary512_short500_panel.md)，
全部18单元和两个独立读出均保留。回归err为原单位MAE；SoM为1-hit@1。
primary主汇总0.126942646、95%分子bootstrap CI[0.089920,0.164969]，单个预训练
seed不能估计种子SD，QM9 U0/alpha的ridge改进为负。此短检查点只验证工具和耗时，
不是充分训练或架构优劣结论。Torch allocator计数器不代表全程/设备全局显存峰值。
现有TRAIN范围的完整评估已跑通；阶段4整体仍缺D-3全标签SDP三种GPU各2,000步。
