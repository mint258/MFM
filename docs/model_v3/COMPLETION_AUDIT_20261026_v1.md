# 全指南完成度审计 v1

整份指南尚未完成，应继续已授权工作。阶段0和阶段1具备其所需的验收证据；当前发布是阶段性源码、工具和分析证据。阶段2–7仍有科学运行、模型工具、真实数据消费或最终交接缺口。不能把公开分支、完整CPU回归、C2分析或单checkpoint开发面板跑通作为收尾。

审计时间：2026-10-25 19:40:02 UTC（Asia/Shanghai 2026-10-26）。唯一原指南为项目根《模型线工作流程：模型 v3、训练代码与训练配方（Codex A）.md》，405行、26,121 bytes、SHA256 `e618165501d22556c4c421d93f1c01928fab3f50202ce6d0fec3249c79921239`。

本审计只读源码、文档和模型自有结果/闭合元数据。没有SSH、Slurm提交、新测试、模型训练或科学重算；没有打开原生LMDB/几何、最终下游targets、lookup/NPZ、权重或H0/prediction cache。只新增本目录 `requirements.json` 与 `AUDIT.md`，生产树、数据线和冻结原件均不改。

## 身份与独立核验

| 项目 | 实际观察 | 核验方式 / 范围 |
|---|---|---|
| 本地分支 / HEAD | model-v3 / e47d066e53f000d71c05bf1c772597f2a5c42c30 | 读实际HEAD/ref；解压该Git commit对象并重算SHA1，结果一致 |
| 本地tree | 9b4bd781da1738828e04d548a04d6efcbcd3aacf | 来自实际本地commit对象；parent为91f0c40a78478447a14ef2e8e91f05c07e0f5019 |
| GitHub model-v3 | d04af5c6dd980370c70b4ee3d61e9946c08baa12 | 只读实时branch与git/commit API，同tree9b4bd781… |
| GitHub main | 037546cd7f07b32dbb46bc21a69109dfd273f8da | 只读实时main branch API；未直接更新main |
| 最终tag / PR | model-v3.0 matching refs=[]；model-v3→main open PR=[] | 只读GitHub实际collection，未创建或修改 |
| 当前完整CPU回归 | 2,390 collected；2,388 passed；2 skipped；0 failures/errors | 独立汇总656–659共16份原始JUnit XML；四supervisor均COMPLETED、exit0、first_failure=null、remaining=[] |
| 测试源覆盖 | 102个当前test_*.py与证书清单全集相同；逐份SHA无mismatch | 不是仅信合并报告PASS；当前v3_data.py SHA cb66e060fc1be637a170465157126d526032d5b35c5af243ce97001f21ea2e73也匹配实测来源 |
| primary512实际result | SHA f4715c71edda69a8670e70630b590cd6f67db92ee184e91d929acee6b5f8a693 | 重算模型自有result原始字节，与独立SDK证书绑定相同；18/9/9 cells均完整1,000 bootstrap |
| 实际D1文件 | 19,059 bytes；SHA399ee0ce… | 重算契约SHA；原15,581 bytes前缀SHA94b593e0…与append receipt一致，模型意见已追加 |

当前完整suite中两项CUDA skip必须继续明确：

- `current/tests/test_model_v3_transfer.py::test_custom_batch_pin_protocol_and_nonblocking_cuda_transfer`。
- `current/tests/test_model_v3_native_bond_transport.py::test_pinned_bond_arrays_and_nonblocking_cuda_transfer`。

原XML位于 `runs/model_v3_20261025/integration_tests_4520656`、`...657`、`...658`、`...659`，每目录 `shard_00.xml` 至 `shard_03.xml`。当前102文件逐SHA与 `s_bond_postmerge_full_v1.json`一致。没有重新执行任何测试；以上仍不授真实D3或GPU科学验收。

GitHub只读来源：[model-v3](https://api.github.com/repos/mint258/MFM/branches/model-v3)、[固定公开commit/tree](https://api.github.com/repos/mint258/MFM/git/commits/d04af5c6dd980370c70b4ee3d61e9946c08baa12)、[main](https://api.github.com/repos/mint258/MFM/branches/main)。当前ref是本审计时间点观察，固定commit/tree是不可变来源。

## 分阶段结论

| 阶段 | 审计结论 | 已有证据 | 仍缺验收 |
|---|---|---|
| 0 | complete | 4520329参数/H0机器结果；旧runner、checkpoint、views、采样、loss、inner-role事实已写清 | 保持后续变更不破坏旧路径；最终配置另属阶段7 |
| 1 | complete | 原生365/366/367三卡；20更新，369九trace，378汇总；吞吐/填充/组件与峰值范围明确 | dist_mlp因果显存主导未证实，但指南要求的是无论成立否均报告，已满足 |
| 2 | incomplete | opt-in A/B实现、三卡A00；5090 A03数值通过但无收益；原失败完整保留 | 大部分逐GPU单项/叠加与独立速度、最终容量表；真实D5 fp32/bf16各两seed×20k |
| 3 | external_dependency + 本地工作 | 采样/头/loss/trainer和当前CPU完整suite；D1草案审阅；S bond原生事实修复 | final wire/provider、真实各字段1000分子R²、D4统计、双validation/恢复、D3全链；tensor/perturbed views/reasons/condition路由等模型消费缺口 |
| 4 | incomplete | 9任务/18cells冻结；真实512冷缓存完整面板≤1GPUh；B3历史参考与独立SDK | D3真实SDP2000三GPU；实际stage5种子SD；完整可执行proxy训练→panel曲线接线 |
| 5 | external_dependency + 本地工作 | C1/C3/C4/H实现/合成，C2坐标lookup分析已闭合，20项首seed符号计划 | 6M附近平台确认、实际20首seed和top2重复、真实选择/速度/field验证指标；事前具体policy |
| 6 | external_dependency + 本地工作 | 19项recipe符号计划、样本scheduler/安全segment组件 | LR10+2B4+schedule4+SDP1、preclip p99、WSD fork lineage、D6全量S/P至64M/平台、B*及具体用户确认 |
| 7 | incomplete | 无最终产物可授验收 | frozen模型/recipe、model-v3.0 tag、HANDOFF、120k/k2/1M单格smoke、最终PR和用户合并 |

“external_dependency”只说明某条真实验收依赖权威数据或上游科学结果，并不允许停止所有独立实现/测试。`requirements.json`逐条列出可继续推进动作；没有把报告标题中的PASS直接当独立完成证明。

## 已有真实证据的边界

**模型规模。** 原指南“约1000万”与新6×512完整模型不符：实际22,352,859参数，backbone12,709,424；旧4×384完整为10,216,035。六层512要求保持，不能为套估计数字擅自缩小模型。按模块的机器细项在 `docs/model_v3/results/baseline_parameters.json`。

**开发面板。** 真实512端点544使用成功A00短500步导出486，candidate/random同512×6。完整主均值0.1269426457576085，95%分子bootstrap CI [0.08992031227612593, 0.16496880214743642]；ridge0.08735855901847464，Linear64/ReLU0.16652673249674238。两项负ridge（QM9 U0/alpha）保留。独立566验证170,295 native records / 56,738 history，clean EOF/exit0。guard含SDK finish/cleanup509.287846秒，outer Slurm512秒，满足这个冷缓存checkpoint的1h目标。它只有一个预训练seed，不能估seed SD；其Torch显存计数器是since-last-reset局部高水位，不是完整H0阶段或设备全局峰值。

**历史B3。** 437/487闭合384×4及匹配随机384；18cells、170,299 native / 56,738 history。它完成合理性参照要求，不能替代512或与512一起计算种子噪声。

**C2。** 坐标lookup分析采用559 TRAIN诊断已验收参数，603只读1,024个固定existing-S PRETRAIN_VAL records /55,650 atoms，current TRAIN geometry reads=0。606独立证书验证31 native/2 history及全部config/summary/step/exit0/EOF。component RMSE0.0654994134 Å，vector RMSE0.113448312 Å，local-pair RMSE0.0575438344 Å。无新的门槛或架构选择。旧约0.0413 Å是pair-distance分析，不能当坐标RMSE。482与595仍FAILED；旧482实际stop没有保存，不能从559诊断倒推。证书两row期望明确来自固定logger+保存输出，没有独立镜像history。audit未打开lookup/NPZ或重扫SDK。

**合成训练容量。** 349/351各9个固定合成H0头案例过拟合，支持组件实现；不能替代权威D2所有真实字段/完整主干的1000分子验收。当前CPU回归和两条precision合成恢复SDK，也不能替代真实D3/D5。

## A矩阵：控制通过与采用依据分开

下表对应唯一ID `S2-MATRIX-<GPU>-<case>`。PASS仅指该配置/数据流的原20批+500更新数值门槛；仍须独立单模型速度才能采用。CAP为当前条件容量/执行未完成，不外推其他batch/单模型。三个优化叠加不得包含已失败的前置单项。

| GPU | A00 | A01 backbone-off | A02 dist-off | A03 head-off | A04 all-off | A05 compile | A06 fused | A07 TF32 | A10/A11/A12 |
|---|---|---|---|---|---|---|---|---|---|
| 3090 | PASS438 | 未验收 | 未验收 | 未验收 | 未验收 | 未验收 | 未验收 | 未验收 | 前置未闭合 |
| 4090 | PASS405 | 456 PENDING | 未验收 | 未验收 | 未验收 | 未验收 | 未验收 | 未验收 | 前置未闭合 |
| 5090 | PASS411；fresh486 | CAP546 | CAP590 | PASS549；无加速 | 未验收 | CAP/OOM525 | 轨迹FAIL457 | 固定批FAIL589 | 前置未闭合 |

- A06：477/500 loss点不满足1e-3；第一次14，最大相对差约0.18546434在379。独立toy optimizer舍入诊断不能替代真实梯度来源解释或授权放宽门槛。
- A07：固定20批门槛失败，未进入500步。
- A03：576/579/580/583同卡单模型ABBA，基准152.070610737、候选131.706676698 base records/s，倍率0.866088957，不采用。
- A05的run_status.failure=null，但实际supervisor/日志记录MemoryError/CUDA OOM和SDK cleanup failure；不能因此写无故障。
- 原基线是global attention。已有sparse-radius实现必须保持原mask，不能暗加cutoff宣称等价。当前bucket/sort可变但改变逻辑batch的路径被paired拒绝；保持同一步逻辑batch的等价padding实现/验收仍缺。

原生每GPU17步profiler吞吐及paired双模型耗时不可相除作为A单项加速倍数。显存85%判定继续使用实际GPU容量、当前完整模型/批成本和真实进程/allocator数据。

## DataB实际状态与模型侧缺口

已直接读取 `runs/data_v1_20261025/repository/docs/interfaces/STATUS.md`。D1是可读且已审的draft.3，不应继续概括为“没有契约”。它未共同签v3.0。最终D2注册表、D3全字段约5万TRAIN+VAL双几何试点、D4权威TRAIN统计、D5嵌套人口/未见构象诊断、D6全量本地副本、D7统计报告仍未交。

数据侧已有tensor6、source-specific D5排序/diagnostic anti-join和稀疏leaf原因；不能再说这些都未实现。数据512分子小试点median/MAD或608六项sampling projection边界，也不等于最终D3/D4/D5。模型目前仍需：

1. 按权威wire/family identity join的只读节点本地provider和真实逐值读回。
2. 对tensor6的物理头/表示、RQRᵀ、norm/loss/frame定义协同确认后消费；不能拆六个不变scalar冒充。
3. perturbed几何标签对应实际扰动view，不挂在base clean或任意S噪声view。
4. 原leaf validity/reasons sidecar与codebook保真，不能被exposure masks覆盖。
5. PM7/UFF各自D5 training_rank/允许构象索引和P/Pprime条件独立统计路由；不能自行转换、去basis或补有效零。

这些边界在31-source/264-row模型审阅中已写明。S旧rdkit_bond transport缺口已由643和完整pre/post回归修复，不能仍列为待修；两项真实CUDA transfer skip及D3真实消费仍分别缺失。

现有开发面板也不必等D3：已直接读取421的 `runs/model_v3_20261025/selected_train_store_4520421/materialization_result.json`，实际status=COMPLETE_FOR_SELECTED_TRAIN、17,602记录、cohort_replay_exact=true、outer_target_records_decoded=0；它绑定 `native_store/selected_store_manifest.json` SHA294e051ead61b2325b473e169a585d2e58b4eaafe97dca860cf86463cafdc588。没有打开packed payload。此模型自有原TRAIN store闭合与新D3科学交付是独立事实。

## 可以立即推进的工作

1. **完整可执行proxy训练/评估闭环（S4-PROXY-RUNNER）。** 当前 `v3_proxy_plan.py`明确NOT_ADMITTED并要求独立source-bound runner。`SampleBudgetExperiment`已有安全milestone+最终非milestone保存、outbox/ACK、partial保留、恢复和23个合成测试。下一步是生产CLI/冻结请求/资源监督/单卡segment/controller与评估collector接线，用小合成和现有S证明端到端，不等D3才开始写工具，也不修改已测原trainer/B/bridge字节。
2. **合法SD anchor与初始曲线顺序（S4-SD-ANCHOR-POLICY）。** 明确同stage5科学配置两seed的参考身份和baseline pilot执行顺序。现在所有symbolic trial都依赖plateau_confirmed，不能因此循环等待而永远不产生首条曲线；不能拿B3/512、两个readout、bootstrap CI来凑SD。6M平台数值规则不能由本audit擅自发明。
3. **WSD分叉lineage（S6-WSD-FORK）。** 已有wsd scheduler和安全恢复，不代表已有从稳定checkpoint创建短衰减child的完整source/optimizer/RNG/sample/SDK谱系工具。应独立设计、合成端到端与恢复测试，保留原parent，不把改scheduler合同伪装原样恢复。
4. **实验前policy细化。** C3“明显下降”的metric方向/人口/阈值，WSD末10–20%的具体比例，LR spike规则，以及C1跨条件排名/计时聚合、H group R² scope、seed聚合/对应scientific identity须在实际比较前封存公开。当前纯函数遇缺项返回MISSING_POLICY，不能用一般文字或39个测试当实际policy。
5. **补两CUDA节点和完整组合绝对等变界。** 现head tests严格atol=1e-5,rtol=0；C1部分encoder测试允许atol2e-6+rtol2e-5×|expected|，并不逻辑保证完整encoder→head绝对误差≤1e-5。可新增实际坐标旋转后组合输出的最大误差证据，不放宽原门槛。
6. **继续A矩阵/容量/速度。** 使用当前空闲资源做可行同源测量/诊断；456只等待准入，不取消他人任务；失败单项不进入叠加。每GPU实际capacity与每百万base samples耗时在最终模型/配方下仍要重测。
7. **记录完整性。** 现有主要A/profile/panel/C2已有小CSV，但head-capacity、precision合成恢复等run→SDK→CSV的穷尽映射还需整理，paired父与两个SDK粒度要写清。figures/目前只有C2 PNG；可补生成器索引和小复现脚本，添加dated最新状态导航，保留原prereg和失败快照。

## 真实科学工作的剩余顺序

1. D1/D2共同定义与D3/D4/D5真实消费后：逐真实字段1000分子诊断、真实双验证/原单位metrics/恢复，三GPU各SDP2000，向数据线反馈读取吞吐和loader wait。分类字段R²不适用之处须提前明确对应验收，不伪造R²。
2. 合法baseline曲线确认预算、同配置两seed SD后：C1的S/P六项；C1胜者上的C3 S/SDP四项；胜出主干上的H1/H2/H3 P/D/SDP九项；P learned pooling一项；再做每项决策实际top-two的第二seed。约26次是估计，不能为守计数省条件/重复。
3. Stage6：5 LR×S/P=10；top2 LR×S/P在2B0=4；cosine/WSD×S/P=4；最佳preclip梯度p99；一次SDP确认。按dev/同SD选稳定小LR和可行较大batch，S/P无共同1SD内LR则报告用户。
4. D6全量PM7/all conf：S与P各一个seed，1/2/4/8/16/32/64M sample曲线到平台或上限；最早翻倍提升<1seedSD定义收敛；B*=两者较大值，>2倍差异先报告。缺平台不能宣称已收敛。
5. 把具体完成结果供用户确认后冻结模型/recipe和B*；完成120k/k2/1M单格smoke到面板，写最终HANDOFF/三卡每百万样本耗时/实际评估命令，打model-v3.0并开最终PR，由用户合并main。当前持续授权要求继续做工作，并不预接受尚不存在的科学结论。

## 证据计数与解释

逐项清单共289个唯一ID：complete=103，incomplete=80，external_dependency=86，contradicted=3，unverified=17。拆解粒度不同，不得把103/289解释为科学完成百分比。

complete只在每条明写的实现/合成/真实范围内成立；不会递归授阶段接受。contradicted三项为约1000万估计、5090 fused轨迹门槛、5090 TF32固定批门槛。unverified用于全历史权限/即时报告等本audit不能穷尽证明的约束，既不把未知当完成，也不无证据指控违规。

最新已出版账本捕获于2026-10-25T14:18:43Z：188实际父、575,712 allocated CPU秒、26,241科学GPU-job秒、4520456唯一pending。Root本轮另确认它仍pending；本audit未新跑sacct。GPU-job秒不是测量利用率、也不是GRES预约。阶段5/6成本需分别完整累计含失败，并按原严格两倍上限停止报告；不要拿全项目账本替代阶段计数。

具体每条的原指南行号、要求、完成证明应是什么、权威路径/范围、现状、下一步和依赖在 [requirements.json](requirements.json)。下表便于按唯一ID定位；它不取代JSON中的范围说明。

## 全部要求索引

| 唯一ID | 阶段 | 状态 | 要求 |
|---|---|---|---|
| G-001 | global | complete | 固定主干6层×512、H0原定义 |
| G-002 | global | contradicted | 核实‘约1000万参数’与6×512真实规模 |
| G-003 | global | unverified | 本阶段不做正式预训练/家族析因/外部基线/完整微调或S/S′、P/P′决策 |
| G-004 | global | complete | 在current/phychem_mfm下新增，旧路径可复现 |
| G-005 | global | complete | 开发分支model-v3；不直接推main |
| G-006 | global | unverified | 数据、权重、checkpoint、凭据不进Git |
| G-007 | global | unverified | 每次提交前运行python tools/check_repository.py |
| G-008 | global | unverified | 不改CodexB workflows/data_v1_final、expansion、docs/data_v1、docs/expansion |
| G-009 | global | unverified | 原始LMDB只读且不删已有文件 |
| G-010 | global | complete | 归一化与模型选择只用TRAIN |
| G-011 | global | complete | 不运行或查看下游测试集；默认测试工具先关闭 |
| G-012 | global | incomplete | 不得仅凭更低预训练loss选架构/头 |
| G-013 | global | unverified | GPU单卡单实验，UUID/真实资源核验，既有Slurm |
| G-014 | global | unverified | 可用3090×7、4090×2、5090×3，数据线CPU；不碰他人作业 |
| G-015 | global | unverified | 学校付费服务器本阶段禁止 |
| G-016 | global | incomplete | 每次训练持久W&B，记录config/code/data/seed/GPU/time |
| G-017 | global | incomplete | 离线运行后同步W&B |
| G-018 | global | complete | 决策规则实验前提交，结果后不得改规则 |
| G-019 | global | incomplete | 共享STATUS dated item/status/path；冲突报告；v3.0之后改动升版本 |
| G-020 | global | unverified | 阶段超过时间估计50%时说明原因 |
| G-021 | global | complete | SA1/2/3并行，profiler后SA4；Root整合和全测试 |
| G-022 | global | unverified | 公共文件修改先通知Root，子agent只改负责范围 |
| G-023 | global | incomplete | 每个阶段验收并提交报告后下阶段才能使用结果 |
| G-024 | global | incomplete | 阶段7后开PR到main，用户合并 |
| D-1 | interfaces | external_dependency | D1共同冻结字段/层级/shape/dtype/mask/ID/构象顺序 |
| D-2 | interfaces | external_dependency | D2最终注册表启用字段、组/家族、extensive/intensive、表示和物理mask |
| D-3 | interfaces | external_dependency | D3约5万TRAIN分子+VAL，全字段/mask/PM7及S′/顺序试点 |
| D-4 | interfaces | external_dependency | D4 TRAIN-only稳健统计和能量元素参考 |
| D-5 | interfaces | external_dependency | D5 12万⊂24万⊂60万⊂全部及已见分子未见构象诊断 |
| D-6 | interfaces | external_dependency | D6 v1全量及各GPU节点本地副本 |
| D-7 | interfaces | external_dependency | D7构象统计报告（下一阶段参考） |
| D-1-REVIEW | interfaces | complete | D1一日内审阅并在实际契约模型意见节反馈 |
| D-PILOT-IO | interfaces | external_dependency | 向数据线反馈真实试点读取吞吐与loader等待占比 |
| D-FIELD-CHANGE | interfaces | incomplete | 字段定义变更以需求提出，不在loader擅自转换 |
| S0-READ-01 | 0 | complete | 审阅factory.py |
| S0-READ-02 | 0 | complete | 审阅model/shared.py |
| S0-READ-03 | 0 | complete | 审阅backbone.py |
| S0-READ-04 | 0 | complete | 审阅attention.py |
| S0-READ-05 | 0 | complete | 审阅heads.py |
| S0-READ-06 | 0 | complete | 审阅routes.py |
| S0-READ-07 | 0 | complete | 审阅phase1/objectives.py |
| S0-READ-08 | 0 | complete | 审阅training/geometry.py |
| S0-READ-09 | 0 | complete | 审阅training/degrade_molecules.py |
| S0-READ-10 | 0 | complete | 审阅phase1/full_corpus_loader.py |
| S0-READ-11 | 0 | complete | 审阅s_convergence_runner_v8.py |
| S0-READ-12 | 0 | complete | 审阅s_training_components_v2 |
| S0-READ-13 | 0 | complete | 审阅s_denoise_core_v3.patch |
| S0-READ-14 | 0 | complete | 审阅phase1/downstream_training.py |
| S0-READ-15 | 0 | complete | 审阅downstream_readout.py |
| S0-READ-16 | 0 | complete | 审阅Stage60 runner |
| S0-PARAM | 0 | complete | 准确分开列backbone/各head参数量 |
| S0-BF16 | 0 | complete | 查清runner v8是否实际autocast |
| S0-CHECKPOINTS | 0 | complete | 列出全部activation checkpoint位置 |
| S0-VIEWS | 0 | complete | 清楚列clean/geom/topo任务监督 |
| S0-SAMPLER | 0 | complete | 512分子/65536原子/800万padding/桶16 |
| S0-LOSSES | 0 | complete | 清楚列旧损失组合和新规则差异 |
| S0-INNER | 0 | complete | 说明train_inner_validation定义 |
| S1-GPU | 1 | complete | 3090/4090/5090各一次6×512+A4原生S测量 |
| S1-COMPONENTS | 1 | complete | torch.profiler拆loader/QK-softmax-AV/dist_mlp/FFN/头/loss/backward/optimizer |
| S1-PADDING | 1 | complete | 记录真实/填充原子与原子对比例 |
| S1-THROUGHPUT | 1 | complete | 记录分子/秒与原子/秒及精确分母 |
| S1-HYPOTHESIS | 1 | complete | 报告dist_mlp时间和显存主因假设无论成立与否 |
| S2-A-IMPL-CHECKPOINT | 2 | complete | 三类checkpoint开关及按GPU/批量自动选择 |
| S2-A-IMPL-COMPILE | 2 | complete | torch.compile与动态桶选项 |
| S2-A-IMPL-FUSED | 2 | complete | 显式fused AdamW候选 |
| S2-A-IMPL-TF32 | 2 | complete | 可恢复TF32执行开关 |
| S2-A-IMPL-SPARSE | 2 | complete | 原radius mask的稀疏邻居实现 |
| S2-A-IMPL-BUCKET | 2 | complete | 桶宽/块内原子排序实现 |
| S2-A-IMPL-PADDING-EQUIVALENT | 2 | incomplete | 减少padding同时保持同一步逻辑batch/损失分母/更新 |
| S2-A-GATE-FORWARD | 2 | incomplete | fp32固定20批前向 relative L2<=1e-5 |
| S2-A-GATE-GRADIENT | 2 | incomplete | fp32固定20批逐参数梯度 relative L2<=1e-4 |
| S2-A-GATE-TRAJECTORY | 2 | incomplete | 同seed完整500更新每点loss relative difference<=1e-3 |
| S2-MATRIX-3090-A00 | 2 | complete | 3090 A00完整A数值对照 |
| S2-MATRIX-3090-A01 | 2 | incomplete | 3090 A01完整A数值对照 |
| S2-MATRIX-3090-A02 | 2 | incomplete | 3090 A02完整A数值对照 |
| S2-MATRIX-3090-A03 | 2 | incomplete | 3090 A03完整A数值对照 |
| S2-MATRIX-3090-A04 | 2 | incomplete | 3090 A04完整A数值对照 |
| S2-MATRIX-3090-A05 | 2 | incomplete | 3090 A05完整A数值对照 |
| S2-MATRIX-3090-A06 | 2 | incomplete | 3090 A06完整A数值对照 |
| S2-MATRIX-3090-A07 | 2 | incomplete | 3090 A07完整A数值对照 |
| S2-MATRIX-3090-A10 | 2 | incomplete | 3090 A10完整A数值对照 |
| S2-MATRIX-3090-A11 | 2 | incomplete | 3090 A11完整A数值对照 |
| S2-MATRIX-3090-A12 | 2 | incomplete | 3090 A12完整A数值对照 |
| S2-MATRIX-4090-A00 | 2 | complete | 4090 A00完整A数值对照 |
| S2-MATRIX-4090-A01 | 2 | incomplete | 4090 A01完整A数值对照 |
| S2-MATRIX-4090-A02 | 2 | incomplete | 4090 A02完整A数值对照 |
| S2-MATRIX-4090-A03 | 2 | incomplete | 4090 A03完整A数值对照 |
| S2-MATRIX-4090-A04 | 2 | incomplete | 4090 A04完整A数值对照 |
| S2-MATRIX-4090-A05 | 2 | incomplete | 4090 A05完整A数值对照 |
| S2-MATRIX-4090-A06 | 2 | incomplete | 4090 A06完整A数值对照 |
| S2-MATRIX-4090-A07 | 2 | incomplete | 4090 A07完整A数值对照 |
| S2-MATRIX-4090-A10 | 2 | incomplete | 4090 A10完整A数值对照 |
| S2-MATRIX-4090-A11 | 2 | incomplete | 4090 A11完整A数值对照 |
| S2-MATRIX-4090-A12 | 2 | incomplete | 4090 A12完整A数值对照 |
| S2-MATRIX-5090-A00 | 2 | complete | 5090 A00完整A数值对照 |
| S2-MATRIX-5090-A01 | 2 | incomplete | 5090 A01完整A数值对照 |
| S2-MATRIX-5090-A02 | 2 | incomplete | 5090 A02完整A数值对照 |
| S2-MATRIX-5090-A03 | 2 | complete | 5090 A03完整A数值对照 |
| S2-MATRIX-5090-A04 | 2 | incomplete | 5090 A04完整A数值对照 |
| S2-MATRIX-5090-A05 | 2 | incomplete | 5090 A05完整A数值对照 |
| S2-MATRIX-5090-A06 | 2 | contradicted | 5090 A06完整A数值对照 |
| S2-MATRIX-5090-A07 | 2 | contradicted | 5090 A07完整A数值对照 |
| S2-MATRIX-5090-A10 | 2 | incomplete | 5090 A10完整A数值对照 |
| S2-MATRIX-5090-A11 | 2 | incomplete | 5090 A11完整A数值对照 |
| S2-MATRIX-5090-A12 | 2 | incomplete | 5090 A12完整A数值对照 |
| S2-A-SPEED-TABLE | 2 | incomplete | 每GPU每单项及叠加提速倍数 |
| S2-A-CAPACITY-AUTO | 2 | incomplete | GPU型号/批成本实测驱动checkpoint选择和85%容量表 |
| S2-B-DTYPE | 2 | complete | bf16只主干矩阵乘；几何/RBF/头/loss/norm fp32 |
| S2-B-fp32-SEED0 | 2 | external_dependency | fp32 S代理20,000更新 seed0 |
| S2-B-fp32-SEED1 | 2 | external_dependency | fp32 S代理20,000更新 seed1 |
| S2-B-bf16-SEED0 | 2 | external_dependency | bf16 S代理20,000更新 seed0 |
| S2-B-bf16-SEED1 | 2 | external_dependency | bf16 S代理20,000更新 seed1 |
| S2-B-ENVELOPE | 2 | external_dependency | 每项bf16曲线位于fp32两seed逐点包络 |
| S2-B-RMSE2PCT | 2 | external_dependency | 去噪原单位component RMSE同seed差≤2% |
| S3-IMPL-MOLECULE-SAMPLING | 3 | complete | 默认均匀分子→均匀允许构象 |
| S3-IMPL-CONFORMER-SETS | 3 | complete | 清单支持前k/全部/最低能/多样性前k |
| S3-IMPL-GEOMETRY | 3 | complete | PM7/S′ UFF/按分子混合可配置 |
| S3-IMPL-MASKS | 3 | complete | 分子组/家族/逐字段有效mask |
| S3-IMPL-NODE-LOCAL | 3 | complete | 节点本地provider/worker独立句柄/原prefetch |
| S3-IMPL-GRAPH-HEAD | 3 | complete | 分子标量H1/H2/H3，extensive sum/intensive mean/learned mixer |
| S3-IMPL-ATOM-HEAD | 3 | complete | 电荷/Fukui/SASA等原子标量头 |
| S3-IMPL-PAIR-HEAD | 3 | complete | 对[h_i+h_j,abs(h_i-h_j),RBF(d)]预测pair标量 |
| S3-IMPL-ATOM-VECTOR | 3 | complete | 原子向量采用sum_j c_ij rhat_ij |
| S3-IMPL-MOLECULE-VECTOR | 3 | complete | 偶极sum_i q_i(r_i-r_center)，模长则向量取范数 |
| S3-IMPL-S-HEAD | 3 | complete | S复用A4 denoise_eps_mse、原元素/键级头 |
| S3-IMPL-NORMALIZATION | 3 | complete | 消费D4 TRAIN-only统计再损失，能量元素参考显式 |
| S3-IMPL-FIELD-HUBER | 3 | complete | 逐字段Huber默认delta1、对有效标签mask平均 |
| S3-IMPL-GROUP-MEAN | 3 | complete | 组内只平均本批有有效标签的字段 |
| S3-IMPL-ENABLED-GROUPS | 3 | complete | 启用S/D/P等权、不随字段数量变化 |
| S3-IMPL-LABEL-COUNTS | 3 | complete | 每步记录每字段有效标签数 |
| S3-IMPL-SAMPLE-CLOCK | 3 | complete | 预算用已消费base draws，不用epoch/expanded views |
| S3-IMPL-MILESTONES | 3 | complete | 1/2/4/8/16/32/64M安全保存+常规恢复 |
| S3-IMPL-TWO-VALIDATION | 3 | complete | 分别记VAL与TRAIN_UNSEEN_CONFORMATION loss/R²/原单位MAE |
| S3-IMPL-GRAD500 | 3 | complete | 每500更新小批分别测S/D/P共享backbone梯度范数 |
| S3-IMPL-RUNTIME | 3 | complete | 吞吐/显存记录和真实可复现状态接口 |
| S3-REAL-WIRE-PROVIDER | 3 | external_dependency | D1 MFM3/各family只读节点本地物理decoder→PreparedV3Batch |
| S3-REAL-REASONS | 3 | external_dependency | leaf validity/reasons sidecar保留codebook身份 |
| S3-REAL-PERTURBED | 3 | external_dependency | 真实扰动几何标签使用对应扰动view而非base clean |
| S3-REAL-TENSOR | 3 | external_dependency | D2所列tensor6正确消费及RQRᵀ测试 |
| S3-REAL-SOURCE-D5 | 3 | external_dependency | PM7/UFF来源独立D5 training_rank/anti-join投影 |
| S3-REAL-CONDITION-NORM | 3 | external_dependency | P/Pprime条件使用对应独立D4统计 |
| S3-REAL-1000-OVERFIT | 3 | external_dependency | 逐真实字段1000分子R²≥0.95，失败列出分析 |
| S3-TEST-DISABLED | 3 | complete | 关闭任务无head梯度且对总loss无贡献 |
| S3-TEST-MASK | 3 | complete | 合成mask逻辑自动化 |
| S3-TEST-RESUME | 3 | complete | 保存恢复逐位一致 |
| S3-TEST-H0 | 3 | complete | encode_atoms/encode_graph签名不变，维512 |
| S3-TEST-EQUIVARIANCE | 3 | complete | fp32旋转向量/标量误差≤1e-5 |
| S3-TEST-CHI2 | 3 | complete | 分子频率均匀卡方检验 |
| S3-CUDA-TRANSFER | 3 | incomplete | 实际CUDA pin/nonblocking TRANSFER测试 |
| S3-CUDA-BOND-TRANSFER | 3 | incomplete | 实际CUDA pin/nonblocking BOND-TRANSFER测试 |
| S3-REAL-RESUME | 3 | external_dependency | 真实D3/目标GPU训练保存恢复逐位一致 |
| S4-TASK-COUNT | 4 | complete | 冻结已有数据8–10任务 |
| S4-ADMET | 4 | complete | 回归与分类覆盖（按用户明确修订） |
| S4-ATOM | 4 | complete | 原子级SoM任务/source atom IDs |
| S4-QUANTUM | 4 | complete | 能量/HOMO/LUMO和尺寸/intensive覆盖 |
| S4-TRAIN-INNER | 4 | complete | 只原TRAIN内层划分，代码禁止role=test并自动检查 |
| S4-CONFIG | 4 | complete | configs/dev_panel_v1.json在stage5前提交 |
| S4-CACHE | 4 | complete | 冻结H0缓存一次、保护geometry/source/runtime身份 |
| S4-RIDGE | 4 | complete | 岭回归alpha只内fit group-CV选择 |
| S4-LINEAR64 | 4 | complete | source-aligned Linear64/ReLU固定20epochs/B32 |
| S4-REFERENCE | 4 | complete | 同架构同配置随机初始化参考 |
| S4-SCORE | 4 | complete | (ref_err-err)/ref_err、逐任务与跨任务汇总 |
| S4-BOOTSTRAP | 4 | complete | 按分子paired bootstrap CI |
| S4-B3 | 4 | complete | 旧S B3仅合理性参考 |
| S4-ONE-CHECKPOINT | 4 | complete | 一个真实512 checkpoint完整跑通 |
| S4-ONE-HOUR | 4 | complete | 每checkpoint评估≤1GPUh目标 |
| S4-RESOURCE | 4 | complete | 记录实际吞吐与显存范围 |
| S4-CONFIG-GENERATION | 4 | complete | 生成完整绑定config和既有Slurm单GPU请求 |
| S4-TRACKING | 4 | complete | W&B持久与全局单调step，独立SDK核验 |
| S4-CSV | 4 | complete | 小typed训练摘要写docs/model_v3/results/*.csv |
| S4-SEED-SD | 4 | external_dependency | 同一stage5配置两个预训练seed估计样本SD(ddof=1) |
| S4-INTEGRATION-TESTS | 4 | incomplete | 整合已有/新增全部测试通过 |
| S4-D3-SDP2000-3090 | 4 | external_dependency | 3090 D3全部S/D/P标签启用2000更新smoke |
| S4-D3-SDP2000-4090 | 4 | external_dependency | 4090 D3全部S/D/P标签启用2000更新smoke |
| S4-D3-SDP2000-5090 | 4 | external_dependency | 5090 D3全部S/D/P标签启用2000更新smoke |
| S4-PROXY-RUNNER | 4 | incomplete | 代理训练→样本checkpoint→开发面板→曲线的完整可执行工具 |
| S5-IMPL-C1-0 | 5 | complete | C1-0保留每层Linear1→dim→heads距离MLP |
| S5-IMPL-C1-a | 5 | complete | C1-a共享K64 Gaussian RBF+小MLP一次计算、逐层投影 |
| S5-IMPL-C1-b | 5 | complete | C1-b元素对条件Gaussian尺度和平移 |
| S5-C1-RADIUS | 5 | complete | RBF截断与实际attention半径一致 |
| S5-C2 | 5 | complete | 补坐标级lookup基线，只分析不作验收门槛 |
| S5-C3-IMPL | 5 | complete | 2view clean+both，对比原3view；键仍clean |
| S5-C4-IMPL | 5 | incomplete | 矢量头必须采用，不参与选择 |
| S5-H-IMPL | 5 | complete | H1/H2组共享MLP/H3字段MLP64–128及固定/learned pooling |
| S5-PROXY-DATA | 5 | external_dependency | D5 240k TRAIN分子、全部允许构象、PM7 |
| S5-PROXY-MODEL | 5 | external_dependency | 6×512统一模型 |
| S5-PROXY-PROVISIONAL | 5 | external_dependency | lr3e-4/AdamW(.9,.95)/clip1/2%warmup cosine |
| S5-PLATEAU-6M | 5 | external_dependency | 先一条开发曲线确认6M附近平台；不足先改预算并提交 |
| S5-RUN-C1-0-S | 5 | external_dependency | C1-0在S真实代理首seed |
| S5-RUN-C1-0-P | 5 | external_dependency | C1-0在P真实代理首seed |
| S5-RUN-C1-a-S | 5 | external_dependency | C1-a在S真实代理首seed |
| S5-RUN-C1-a-P | 5 | external_dependency | C1-a在P真实代理首seed |
| S5-RUN-C1-b-S | 5 | external_dependency | C1-b在S真实代理首seed |
| S5-RUN-C1-b-P | 5 | external_dependency | C1-b在P真实代理首seed |
| S5-RUN-C3-V2-S | 5 | external_dependency | C3 2视图在S真实代理首seed |
| S5-RUN-C3-V2-SDP | 5 | external_dependency | C3 2视图在SDP真实代理首seed |
| S5-RUN-C3-V3-S | 5 | external_dependency | C3 3视图在S真实代理首seed |
| S5-RUN-C3-V3-SDP | 5 | external_dependency | C3 3视图在SDP真实代理首seed |
| S5-RUN-H1-P | 5 | external_dependency | H1在P真实代理首seed |
| S5-RUN-H1-D | 5 | external_dependency | H1在D真实代理首seed |
| S5-RUN-H1-SDP | 5 | external_dependency | H1在SDP真实代理首seed |
| S5-RUN-H2-P | 5 | external_dependency | H2在P真实代理首seed |
| S5-RUN-H2-D | 5 | external_dependency | H2在D真实代理首seed |
| S5-RUN-H2-SDP | 5 | external_dependency | H2在SDP真实代理首seed |
| S5-RUN-H3-P | 5 | external_dependency | H3在P真实代理首seed |
| S5-RUN-H3-D | 5 | external_dependency | H3在D真实代理首seed |
| S5-RUN-H3-SDP | 5 | external_dependency | H3在SDP真实代理首seed |
| S5-RUN-POOLING-P | 5 | external_dependency | P上H1 learned pooling与registry固定对比 |
| S3-TEST-COMPOSITE-EQUIVARIANCE | 3 | incomplete | 组合完整encoder→所有新增标量/向量头fp32旋转误差≤1e-5 |
| S5-REPEAT-C1 | 5 | external_dependency | C1真实top-two配置各加第二预训练seed |
| S5-REPEAT-C3 | 5 | external_dependency | C3真实top-two配置各加第二预训练seed |
| S5-REPEAT-H | 5 | external_dependency | H真实top-two配置各加第二预训练seed |
| S5-DECISION-C1 | 5 | external_dependency | 在dev不差最佳1SD且S/P分别不差C1-0超过1SD的候选中选最快；两替代均差则保留0 |
| S5-DECISION-C3 | 5 | external_dependency | 仅S和SDP两view都在三view1SD内且masked元素/键无明显下降才改2view |
| S5-DECISION-H | 5 | external_dependency | P/D/SDP各选最佳1SD内最简单，尽量统一；H1 R²<0.5且H3>0.9组改H2 |
| S5-DECISION-POOLING | 5 | external_dependency | registry固定默认，learned在P改善>1SD才用 |
| S5-C3-DECLINE-RULE | 5 | incomplete | 比较前量化‘masked元素准确率/键级没有明显下降’ |
| S5-RECORDS | 5 | external_dependency | 每次记录dev汇总/逐任务、每field R²、去噪RMSE、吞吐/峰显存 |
| S6-CAPACITY | 6 | incomplete | 按每种GPU实测最大原子数使峰值显存≤85% |
| S6-LR-1e-4-S | 6 | external_dependency | S B0学习率1e-4真实代理扫描 |
| S6-LR-1e-4-P | 6 | external_dependency | P B0学习率1e-4真实代理扫描 |
| S6-LR-3e-4-S | 6 | external_dependency | S B0学习率3e-4真实代理扫描 |
| S6-LR-3e-4-P | 6 | external_dependency | P B0学习率3e-4真实代理扫描 |
| S6-LR-6e-4-S | 6 | external_dependency | S B0学习率6e-4真实代理扫描 |
| S6-LR-6e-4-P | 6 | external_dependency | P B0学习率6e-4真实代理扫描 |
| S6-LR-1e-3-S | 6 | external_dependency | S B0学习率1e-3真实代理扫描 |
| S6-LR-1e-3-P | 6 | external_dependency | P B0学习率1e-3真实代理扫描 |
| S6-LR-2e-3-S | 6 | external_dependency | S B0学习率2e-3真实代理扫描 |
| S6-LR-2e-3-P | 6 | external_dependency | P B0学习率2e-3真实代理扫描 |
| S6-B2-TOP1-S | 6 | external_dependency | S第1最佳LR在2B0重跑 |
| S6-B2-TOP1-P | 6 | external_dependency | P第1最佳LR在2B0重跑 |
| S6-B2-TOP2-S | 6 | external_dependency | S第2最佳LR在2B0重跑 |
| S6-B2-TOP2-P | 6 | external_dependency | P第2最佳LR在2B0重跑 |
| S6-SCHEDULE-cosine-S | 6 | external_dependency | S最佳LR比较cosine |
| S6-SCHEDULE-cosine-P | 6 | external_dependency | P最佳LR比较cosine |
| S6-SCHEDULE-WSD-S | 6 | external_dependency | S最佳LR比较WSD |
| S6-SCHEDULE-WSD-P | 6 | external_dependency | P最佳LR比较WSD |
| S6-WSD-POLICY | 6 | incomplete | WSD末尾10–20%具体比例在比较前冻结 |
| S6-WSD-FORK | 6 | incomplete | WSD稳定checkpoint分出短衰减的低成本预算评估能力 |
| S6-P99-CLIP | 6 | external_dependency | 最优LR真实训练梯度范数p99作为裁剪阈值 |
| S6-SDP-CONFIRM | 6 | external_dependency | 选定配方SDP一次确认稳定，各组都学习 |
| S6-LR-SELECTION | 6 | external_dependency | dev为主；1SD内较小LR/较大B；S/P无共同1SD内LR则报告 |
| S6-SPIKE-POLICY | 6 | incomplete | 损失尖峰/发散排除LR的规则事前量化 |
| S6-SCHEDULE-SELECTION | 6 | external_dependency | cosine/WSD在1SD内优先WSD |
| S6-FULL-S | 6 | external_dependency | D6全量PM7/all conformers S单seed到64M或平台 |
| S6-FULL-P | 6 | external_dependency | D6全量PM7/all conformers P单seed到64M或平台 |
| S6-CONVERGENCE | 6 | external_dependency | 取sample翻倍dev提升<1 seedSD的最早预算 |
| S6-BSTAR | 6 | external_dependency | B*=max(S收敛预算,P收敛预算)，相差>2倍先报告用户 |
| S6-USER-CONFIRM | 6 | incomplete | 阶段6结果/recipe/B*先由用户确认再冻结 |
| DOC-00_BASELINE_REVIEW | 0 | complete | docs/model_v3/00_baseline_review.md |
| DOC-01_PROFILING_BASELINE | 1 | complete | docs/model_v3/01_profiling_baseline.md |
| DOC-02_SPEEDUP_AB | 2 | incomplete | docs/model_v3/02_speedup_AB.md |
| DOC-03_LABELS_LOSSES | 3 | incomplete | docs/model_v3/03_labels_losses.md |
| DOC-04_DEV_PANEL | 4 | incomplete | docs/model_v3/04_dev_panel.md |
| DOC-05_ARCHITECTURE_DECISIONS | 5 | incomplete | docs/model_v3/05_architecture_decisions.md |
| DOC-06_RECIPE | 6 | incomplete | docs/model_v3/06_recipe.md |
| DOC-HANDOFF_V3 | 7 | incomplete | docs/model_v3/HANDOFF_v3.md |
| DOC-CSV-ALL | documentation | incomplete | 所有真实训练每次一行typed CSV |
| DOC-FIGURES | documentation | incomplete | figures/保存复现图脚本和小PNG，大文件外置 |
| DOC-REPORT-QUESTION | documentation | incomplete | 每份实验报告必须含明确实验问题 |
| DOC-REPORT-PREREG | documentation | incomplete | 每份实验报告必须含规则与事前公开提交 |
| DOC-REPORT-CONFIG | documentation | incomplete | 每份实验报告必须含完整config与数据版本 |
| DOC-REPORT-RESULTS | documentation | incomplete | 每份实验报告必须含结果表 |
| DOC-REPORT-DECISION | documentation | incomplete | 每份实验报告必须含决策和理由 |
| DOC-REPORT-LIMITS | documentation | incomplete | 每份实验报告必须含未解决问题/已知限制 |
| DOC-HISTORY-CONSISTENCY | documentation | incomplete | 事实/数字与负面弃用记录保留，最新状态不被旧快照误导 |
| DOC-STAGE-COMMIT | documentation | incomplete | 每完成阶段提交且message写阶段编号 |
| S7-MODEL-CONFIG | 7 | incomplete | configs/model_v3/model_v3_frozen.json |
| S7-RECIPE-CONFIG | 7 | incomplete | configs/model_v3/recipe_v3_frozen.json（含B*） |
| S7-TAG | 7 | incomplete | 最终model-v3.0 tag并记录SHA |
| S7-HANDOFF-GRID-COMMAND | 7 | incomplete | Handoff写如何指定分子子集/构象子集/geometry启动一个网格格子 |
| S7-HANDOFF-GPU-TIME | 7 | incomplete | Handoff每种GPU每百万样本耗时 |
| S7-HANDOFF-EVAL-COMMAND | 7 | incomplete | Handoff提供完整评估命令及输入绑定 |
| S7-GRID-SMOKE | 7 | external_dependency | 12万分子、k=2单格、训练1M base samples直到完整评估 |
| S7-FINAL-PR | 7 | incomplete | 完成后开model-v3→main最终PR由用户合并 |
| S7-USER-MERGE | 7 | external_dependency | main最终合并由用户执行 |
| STOP-A-EQUIVALENCE | global | unverified | A无法通过且原因不明立即停止报告用户 |
| STOP-OVERFIT | global | unverified | 真实字段R²<.95且可能标签问题立即报告并通知数据线 |
| STOP-H0 | global | unverified | 需要改变H0定义/维度/导出位置立即报告 |
| STOP-TEST-TARGETS | global | unverified | 需要查看下游test才能决策则立即停止 |
| STOP-GPU-COST | global | unverified | stage5>2×100–150h或stage6>2×150–250h立即报告 |
| STOP-SCHOOL | global | unverified | 需要学校付费服务器立即报告 |
| STOP-DELETE | global | unverified | 需要删除任何已有文件立即报告 |
| MILESTONE-1 | reporting | complete | 阶段1结束STATUS摘要：瓶颈 |
| MILESTONE-2 | reporting | incomplete | 阶段2结束STATUS摘要：实际提速倍数 |
| MILESTONE-5 | reporting | incomplete | 阶段5结束STATUS摘要：架构和头选择 |
| MILESTONE-6 | reporting | incomplete | 阶段6结束STATUS摘要：配方/B*及用户确认 |
| S4-SD-ANCHOR-POLICY | 4 | incomplete | 在候选比较前明确合法global seed-SD anchor及首条6M平台曲线的执行顺序 |
| S5-OPERATIONAL-DECISION-POLICY | 5 | incomplete | 选择器所需的跨条件排名/计时聚合/seed aggregation/field-group R2 scope在实际比较前完整固定 |

本audit是推进清单，不是新的科学协议或数据权威；不为任何未完成实验预填成功。
