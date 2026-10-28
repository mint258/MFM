# 模型 v3 完整科学进度 v6（2026-10-28）

**整体阶段0–7尚未完成，未冻结模型/配方/B*，未开始学校正式预训练。** 本稿承接 [v5 / 公开v25报告](PRETRAINING_PREPARATION_20261028_v5.md) 的完整目标和未完成矩阵。新增闭合的是同源head-off的完整20批+500步、四条R1与日志/同步、head被动捕获及保持FAILED的CPU代数分析；本次再补A5严格梯度门负结果、最大N原生单例R1与SDK闭合，以及新FFN独立CPU回归、代码公开和完整48 GPU负结果。原阶段1三卡基线已实际做完，不能把后续优化覆盖缺口写成原基线未做。

报告点时为 2026-10-28T02:49:28.214826+00:00。本报告由冻结DRAFTv2生成，按实际Root证据补入A5两失败SDK闭合、FFN完整48 GPU负结果和ledger48；旧DRAFT、旧报告及原始失败均保留。当前已核验同步的原run共87，包含失败run。原指南0–7、数据最终验收、架构和配方预算范围完整保留；详细来源与读取边界见 [compact evidence](pretraining_preparation_compact_evidence_20261028_v6.json)。Root只读源码、JSON/XML和资源元数据，终端NPZ/权重/SDK/训练journal正文未在登录节点解码。

## 本轮真正增加的A1证据：部分关闭head checkpoint

执行代码保持9e16d4c5a15c558051499d3dc0c55c9bd3787734，原公开方法 [8147f44b](https://github.com/mint258/MFM/commit/8147f44baa1ea1ecc3822af7affd0a95401ed248)，Native S/seed0/原8M logical sampler/三视图/6×512不变。a03仅将head_checkpointing改为False，distance/backbone仍True，未改模型数学、损失、数据和原阈值。

GPU4524580实际C0/2445秒/node21，强Root v2明确闭合完整20批前向、全部named-gradient/None门与500步损失轨迹；最大前向相对L2、梯度相对L2、轨迹相对差分别为 **0、0、0**。原阈值仍是1e-5、1e-4、1e-3，201,216 base records保持，未放宽。此项是resident_models=2的数值资格与该流前缀观察，不自动成为resident1、全TRAIN最大形状、跨卡或任意训练入口容量。

CPU4524584实际C0/29秒：reference go2ye4dx、candidate oo1dj13d各500行、step1–500，原生全config、summary、CRC/片段/EOF、exit与原字节前后绑定全部独立核验。CPU4524585实际C0/34秒：两份精确stage copy同步并API读回finished/500行/1–500；原SDK保留。旧SDKv1因installed-source换行字节不一致而提前拒绝的记录不改，不倒写成成功。

| 角色 | 实际原run | 独立审计与同步 |
| --- | --- | --- |
| R2 reference | [go2ye4dx](https://wandb.ai/mint_leaf258/mfm_model_v3_development/runs/go2ye4dx) | 4584完整500行；4585精确复制/API回读 |
| R2 candidate，T/T/F | [oo1dj13d](https://wandb.ai/mint_leaf258/mfm_model_v3_development/runs/oo1dj13d) | 同上；非all-off或auto选择 |

## A03 R1：本次约5.6%观察，显存开销上升

固定series=A03_head_off_R1_C35_9e16_v1，原顺序reference→candidate→candidate→reference，同C35和同测量输入，各2warmup+20measured，resident_models实际为1。四父均真实C0：

| 位置 / role | 实际GPU父 / elapsed | 原run | measured allocator峰值 |
| --- | --- | --- | ---: |
| 1 / reference | 4524587 / 77s | [gw6qi1ml](https://wandb.ai/mint_leaf258/mfm_model_v3_development/runs/gw6qi1ml) | 5,364,701,696B |
| 2 / candidate | 4524588 / 71s | [x79rzlbz](https://wandb.ai/mint_leaf258/mfm_model_v3_development/runs/x79rzlbz) | 14,600,138,240B |
| 3 / candidate | 4524589 / 73s | [dl5wwm37](https://wandb.ai/mint_leaf258/mfm_model_v3_development/runs/dl5wwm37) | 14,600,138,240B |
| 4 / reference | 4524590 / 74s | [re455yrv](https://wandb.ai/mint_leaf258/mfm_model_v3_development/runs/re455yrv) | 5,364,701,696B |

CPU4524591实际C0/7秒，四SDK各22行、step1–22的原single logger投影、全typed配置、role、递归last-leaf summary、exit0/完整EOF和原字节/来源闭合。原single SDK没有gradient_norm或input_receipt字段；这些保存journal内容没有被伪造成SDK字段。原a_speed_report在同父实际调用并绑定4580新数值门，非借用旧all-on gate：

| pooled base records/s | reference | candidate |
| --- | ---: | ---: |
| 原报告值 | 153.29317646044404 | 161.88264900789656 |

candidate/reference= **1.056032973846484**，本次同卡ABBA观察约5.6%；没有统计稳定性、两seed包络或跨卡最优结论。关闭head checkpoint的allocator峰值更高，不能写成显存下降。reference仍用原builder；其effective_options.backbone_checkpointing=null保留原activation_checkpointing=True，不能把null伪造为一次新的自动bool选择。

CPU4524593/4594分别C0/19秒、C0/18秒，明确2+2同步四个原ID，API均finished/22行/1–22。远端回读范围是route/state/行数/step端点，未再次逐metric重比；完整metric证据来自独立离线SDK审计。当时已知online **84=旧78+本轮R2两条+R1四条**，这是Root登记已闭合的已知集合，不是本作者API全量重盘或统一CSV/HTML全部完成声明。

原A00四R1及CPU4571的ratio0.9932396351继续保留为“无提速的all-on校准”，不与本次A03混合。旧8ece/4090的A01资格、旧1338/4558及历史失败不迁移或重启。

## 阶段1原基线已完成；优化后逐卡/单项/叠加仍缺

原6×512+A4+S在3090/4090/5090的GPU4520365/366/367已实际C0，369分析与378汇总已做。原profile拆解、填充比例、吞吐和峰值保留；距离MLP是代表trace中最大的已归因GPU计算组件，并非已经证明“主导所有形状的全局显存峰值”。不重做这组基线来填后续优化缺口。

| 指南A项 | 已有实现与真实观察 | 仍未完成或拒绝边界 |
| --- | --- | --- |
| A1 checkpoint配置及自动选择 | all-on manual3976/auto4551完整门；旧4090 A01/456完整门；新9e A03/4580完整门和四R1；CPU机制/严格源图consumer已闭合 | a03仅关闭head，非all-off；auto按相符记录顺序选首个，不是最优搜索。R2不借给R1，UUID/source/workload/layout/residency不得跨借；全局max712单例真实R1/日志已闭合，但不授全8M、8worker队列或auto资格；三卡各策略/容量仍缺 |
| A2 compile配合bucket | 显式compile/原分桶入口存在 | 5090/525原固定批CUDA OOM/85%负结果未形成完整门；不盲重试同条件。改变logical batch的旧sampler重分桶/排序不能更名为等价通过；新明确条件与叠加仍待真实门和冷启动/重编译报告 |
| A3 fused AdamW与TF32 | 显式开关存在；fused457固定20过但500有477点超1e-3，1091诊断没有翻门；TF32/589固定门失败 | 当前失败候选未采用，不降低阈值或绕requires_pass。不能把一张卡的失败推成三卡普遍结论，三卡/叠加及真实适用范围仍缺 |
| A4稀疏半径mask | sparse实现存在 | 当前S原基线use_radius_mask=false；直接加radius会改全局注意力数学。须在真实同语义radius参照下验证，不能把此项从指南删除或宣布当前baseline等价加速 |
| A5减少padding | 9e同logical batch chunks已接真实encoder路径；99专项及同源完整回归已闭合，保完整graph/三视图/噪声mask/RNG/全局loss分母与行序 | GPU4601实际完整固定20前向通过，但120项近零bias梯度按原相对门失败；未500/未R1，无速度资格。旧sampler变更不是它的验收，不能借A03/all-on门或改绝对容差放行 |

完整三卡逐项与叠加速度表、不同GPU/批预算的真实选择边界仍是目标。原A03当前结果不完成整个A1，更不完成阶段2。

## A5固定20真实负结果：前向通过，原梯度门保留失败

GPU4524601实际FAILED1:0/127秒/node21。20批每批8个浮点输出全部通过，最大前向相对L2为1.9975306379930165e-6。329参数×20的全部梯度检查中，失败仅为6层backbone.layers.{0..5}.attn.dist_mlp.2.bias，共120项；失败项最大绝对差9.506493370281532e-10，其他梯度最大相对L2为6.803597377699175e-5。

近零bias的绝对差很小，不使原相对梯度门1e-4自动失效。原固定门结果仍为失败，未引入绝对容差floor、剔除bias、跳过层或放宽阈值。科学child exit2映射为outer FAILED1，来源/资源闭合不把它变成PASS；500步未开始，R1未开始。这里是同logical batch chunks的真实数值负结果，不是“尚未运行”或资源OOM，也不解禁旧sampler重分桶。A5实现/CPU机制证明和GPU数学等价验收继续分列。
CPU4524605实际C0/2秒独立核验两个原SDK：89mp3smr为reference、9j1swwgi为candidate，角色来自实际RunRecord/config，完整typed config、原summary私有字段规则、CRC/完整EOF、native exit1和零history均通过。CPU4524606实际C0/17秒精确copy同步，两原ID均回读failed/0行、step端点None；没有伪造summary/500步或改原科学父FAILED1:0/child2。当前已核验online87=此前85+这两个失败run；完整日志闭合不改变A5严格梯度门负结果。

## 全TRAIN最大计数、最大N探针与B类仍是独立缺口

实际CPU4574已绑定11,104,772 TRAIN counts：maxN712、3views、最大singleton padded cost1,520,832，21条singleton超过500k目标，原前500更新未含全局最大。singleton_no_discard未改，未丢大分子；500k新前缀不借8M资格。计数不是VRAM上界；8M all-off既有NoGo保持，不试OOM。

最大N GPU4524600实际C0/48秒/node21。完整counts扫描发现6个712并列最大，按预注册固定首ordinal策略选择一个原生record；精确选择/原输入hash留在Root原件。原MappedRecordIndex/transport/ManifestViewsDataset/collate保留完整三视图，实际dense3×712、2136物理原子、P=1,520,832，tiled pair_rows=65536，单6×512/T/T/F模型完整2+20真实Adam更新。whole allocator峰值872,654,848B、reserved1,121,976,320B，原85%/whole-private双2GiB未放大。

这证明该选定最大N单例及其真实标签/形状可运行，不证明全部6个并列record、全部8M形状/边人口/8worker预取队列或任意optimizer状态的全局上界。它不是原sampler的R1 ABBA或20+500数值门，旧auto消费者没有因此新增资格；all-off/auto最优仍未接受。

原离线SDK pnugbb4q已完成CPU4524603 C0/2秒独立核验：122个native packets不等于122history；实际history仅22行、step1–22，exit0、CRC/EOF及全typed config/summary、原字节绑定通过。CPU4524604 C0/10秒按精确copy同步，Root回读[finished/22行/1–22](https://wandb.ai/mint_leaf258/mfm_model_v3_development/runs/pnugbb4q)。此项完成时online已知 **85=原84+此1条**；随后加入A5两失败原run，当前已知87。在线只重核route/state/count/endpoints，不再次逐metric重比；原SDK/旧v1缺SDK的未执行源码都保留。
B类代理S要求fp32/bf16各2seed、各20,000更新、真实曲线包络和去噪RMSE差异≤2%；仍未闭合。existing_native_S可以独立推进，不整体等待final D5；但它也不变成D5正式科学验收。Native10k开发评估、短profile、单seed或合成恢复测试都不能补成这四条20k。本phase四成员20k目前0/4完成。已闭合的seed0 FP32为17,000步、6,929,834样本，slot018/4522911；对应COMPLETE的198,776,105B payload仅按已封账metadata记录，Root未重读payload。其余三个成员未有本phase的20k完成证据。最新实际核对slot019没有intent/submitted且旧协调器已终止；22e卡仍有626543/514MiB外部context，原严格guard保持拒绝。下一段仍是原v4、原GPU和source的17,000→18,000，不迁移或重置时钟。

## 几何/矢量物理门：15/33未变，head分析保持FAILED

独立geometry候选03e26bea/public498ecbe7/tree2d3b8f17的CPU4576完整116模块2816PASS+3原optional SKIP是工程证据。实际GPU4579仍FAILED1，完整48为15PASS/33FAIL；原正式C4的21/27、projection4550/passive4563的12/36各自保留，不混成同一候选接受。所有原48人口、参数/seed/fixture和abs1e-5/rtol0不改。

GPU4524595实际C0/67秒，仅被动捕获当前同一次原forward的head/moment端口：192FP32前向、0FP64模型/局部重放、2496终端逐bit等于4579，1269个current source/control refs由Root闭合；1728stage、512geometry、2304projection、384head、192norm观察完成。输出445,643,336B受原512MiB trace cap约束；原whole/private限额未放大，模型原返回不改。这里C0是捕获/来源/资源闭合，物理仍15/33，未采纳。

CPU4524597实际 **FAILED1:0/43秒/16CPU/node14**，Root negative closure rawSHA为450cace9ec362452a9045c84270d8ac7b2525e0e937294c12c4cb55b9351394d。全48、192保存档案、720记录、384小MLP参考和原51条dipole类失败的saved-operand代数已做完；最大报告closure error3.940973253031138e-16，小于预注册局部代数bound1e-10。这是保存操作数的局部代数闭合，不是物理1e-5门被改变，也不是全模型因果定位完成。

六个p_dipole_magnitude norm端口CPU/GPU逐位重放失败，差异为1.49e-8至5.96e-8量级，**仍全部HOLD**；不因数值小而放宽bit gate、不删除case、不把FAILED改为C0。原51条dipole/vector-magnitude失败继续保留，另5条extensive失败未被该头实验解释。全48代数完成与6个replay HOLD可以同时成立；不能据此宣称norm单独致因、编码器或head已修复，也不推出普遍FP32下限。

相关FP64仅是保存终端/局部操作数的离线分析参考，不注入FP32模型、不改变512维H0/API、不选择层/seed/幅度/头权重。真实D3过拟合和C4全物理通过仍须完成，不能用短loss或预训练loss选架构。

## 新FFN候选：完整48 GPU为14通过/34失败，未采用

独立候选本地e4b21193be60fcb396ab1d2d56c1cba6736078dd/tree55eb3d963668e597f4ba3cba16e166465ba4588f，已公开[9977c6b4](https://github.com/mint258/MFM/commit/9977c6b4995b97eb5537b15aaf85cea67e0647bf)。默认legacy保留，opt-in为固定K64 compensated FP32的6层12个FFN线性站。CPU4524602实际C0/128秒/16CPU/node14，117模块2881收集=2878PASS+3原optional SKIP，0FAIL/0ERROR；它仅是同源工程回归。

v1方法与FINAL绑定曾完成，三次资源准入都因串行SSH采样超过原30秒而在sbatch前拒绝，job_id均null，原6条观测和无frame事实全部保留。一次清单码转录错误亦在准入前拒绝，后续使用与已审计源一致的机器哈希。v2只把Root三项独立SSH采集改为并行，保存原命令/真实起止/elapsed/原rawSHA，保留30秒、Root120秒、85%、quota、UUID/fd9及worker本地复核；原科学实现、权重和门槛不变。方法[ e56f9036 ](https://github.com/mint258/MFM/commit/e56f90364992958b145fb403f1dd506ba8439883)先公开后执行；本次实际Root采集1.0297036916017532秒。

GPU4524610实际 **FAILED1:0/78秒/16CPU/node21**，完整48为 **14PASS/34FAIL/0ERROR/0SKIP**，failure=null，属于完整物理负结果。实际192次FP32 encoder forward、0FP64；FFN2304次helper/69120个K64叶，原QKV2304/geometry512均逐站核齐。48项完整参数哈希均匹配原4521492捕获；1492在这里是原捕获任务的编号后缀，不是参数张量个数。每case原3变换×13字段、52份终端header完整，2496终端数组保留；Root只stat NPZ，SHA来自实际GPU producer。Tiny解析一二阶控制通过且encoder次数为0，不能代替48物理门。

| 失败输出 | 失败的变换测量数/144 | 最大绝对误差 |
| --- | ---: | ---: |
| PD/p_extensive | 10 | 1.71661376953125e-5 |
| PD/p_dipole | 31 | 1.9415126989275056e-5 |
| PD/p_dipole_magnitude | 15 | 1.634657382965088e-5 |

其余十类输出各144项均过原1e-5/rtol0门。上表单位是字段×变换测量，不能与34个失败case混数。Root重核1872个字段门、全部current源/48case JSON/原参数capture、JUnit及33份资源样本；最大观察RSS2,182,098,944B、GPU used867,172,352B，全部已知且GPU85%/原双2GiB/清理门闭合。原census重执行的child15,666,506B、含外部控制及保守预留18,153,888B均在原界内；采样最大值不冒精确峰值。

本候选未过物理门，未采用。它与geometry4579的15/33、projection4550的12/36分别保留；没有删除seed/字段、改幅度、引入FP64模型路径或放宽阈值。当前证据只否定此固定FFN方案足以通过原门，不能据此完成全模型因果定位或宣布普遍FP32数值下限。

## 完整阶段0–7未完成矩阵

| 原阶段 | 已有实证 | 仍须完成的原目标 |
| --- | --- | --- |
| 0 代码审阅/整合 | 6×512/H0兼容；原子训练链121模块2905PASS+3原SKIP；独立geometry116模块2816PASS+3原SKIP；新FFN117模块2878PASS+3原SKIP及各自同源全套 | 新组合必须有精确对应source/完整回归；候选、runtime和旧producer范围不得互冒；工程通过不替数据与科学验收 |
| 1 原性能测量 | 3090/4090/5090原365/366/367、369/378实际完成；distMLP、attention/FFN/head/loader/优化器及padding观察保留 | 原基线不重做；优化后的三卡、单项/叠加、批条件/容量/吞吐表仍要补齐，归阶段2持续验收；不能借R2容量作R1速度 |
| 2 A/B提速 | all-on manual/auto及A03完整20+500；A00校准和A03四R1/SDK/同步真实闭合 | A1完整适用策略/auto边界/all-off、A2/A3/A4/A5单项和叠加及三卡真实验收；S fp32/bf16各2seed×20k、曲线包络及去噪RMSE≤2%；最大N单例R1/日志已闭合但非全8M；A5固定20梯度失败、未500/未R1 |
| 3 标签/头/损失/采样 | loader/FieldSpec/多层级头/分母/恢复工程、被动逐位捕获及离线诊断 | C4、geometry15/33及新FFN14/34物理门均未通过；D1/D2真实语义共同冻结、D3全字段1000分子过拟合/所有头R²、真实D3 SDP2000步三卡、D4真实TRAIN统计、真实两验证人口/采样频率；不是合成或旧S替代 |
| 4 开发集/评估 | 原TRAIN内层9任务×2读出冻结；旧S B3与NativeS10000各自完整评估与后者日志闭合 | 新端点/模型各自评估、分子bootstrap与逐任务表、同配置双预训练seed SD；单seed不是SD，旧B3不是Native同条件学习锚，禁止下游test |
| 5 架构/头对比 | 候选配置、预注册规则、全48负结果/数值诊断保留 | 真实D5的24万分子/全部构象PM7、600万样本平台确认；C1六次/C3四次、H九次/池化一次、约六次重复/种子SD；按开发集1SD规则决策，不按预训练loss，C4必须通过 |
| 6 训练配方/预算 | proxy/CLI/grid/WSD/CP/恢复/FP32H0工程入口和完整人口p99机制已接通 | 19项真实LR/B/WSD/S/ P/SDP扫描、真实TRAIN preclip p99和用户规则；D6 S/P各至64M或平台、翻倍改善<1SD的最早预算、B*取较大者且差>2倍先报告；未有最终recipe/B* |
| 7 冻结/交接 | 合成6×512真实CLI→safeCP→新进程恢复→H0/随机/ACK链 | 真实120k/k2/1M端到端到评估；完整数据/科学接受、用户确认recipe/B*、配置冻结、model-v3.0 tag、HANDOFF/PR/用户合并；学校正式预训练未启动 |

D1–D7最终交付均未被本报告接受：D1字段/entry/channel/单位/符号/属性轴及版本须共同冻结；D2注册表须真实接受；D3试点全字段/掩码/两几何/构象顺序和验证人口、D4 TRAIN-only能量参考/标准化、D5嵌套清单/未见构象、D6全量与本地盘分发、D7统计仍按各自真实交付与模型验收闭合。旧S/native和synthetic不改名为final D，也不冒D3/D5/正式data-line authority。数据线持续生产或收到条件式draft反馈不等于双方joint freeze。本文无新的D最终接受proof。

## 已公开方法、数据依赖与点时成本

最新方法[ e56f9036 ](https://github.com/mint258/MFM/commit/e56f90364992958b145fb403f1dd506ba8439883)，本地215762544797c7ff2ebf400bda315bec28609f13/tree d0fc438de5a114aaff07e079cb5f3d63aa89723f，14个blob与branch/commit/tree已由Root精确回读。CPUchecker4524609实际C0/90秒、2993文件。此前v29/a8f04cfb及v28/3ac6b67b保持原点时，不反写旧报告。方法归档不代表物理或阶段接受。

数据线STATUS当前hash 0e26d6b72f0aaf57d2439c1fc9c84210c5dc6ea6c16152f370b1c0db50102a81，最新单日进度仍明示D1未jointfreeze、D1–D7及扩充最终交付尚未完成；9/11部分READY、407份P′留存物理事实及生产进度均不冒最终模型接受。最新仅状态文本核对见compact，未读科学payload。

实际ledger48点时 2026-10-28T02:43:50.164308+00:00：**571个登记父，407显式CPU登记、97个ledger标记GPU父、67个其余历史父**。CPU分配 **1,705,648核秒**；GPU节点作业分配 **83,394秒**。571−407=164只是余组，不称164次实际GPU；97个GPU标记父的elapsed才对应83,394秒。包含所有已登记失败和新的4524609/4524610；三次无sbatch的准入拒绝没有虚构GPU父。活跃登记仅4521338/4524558，点时均PENDING。此快照不预填之后本报告检查/发布作业。

v46的566父/1,702,592CPU核秒/83,316GPU节点秒和v45的运行中快照均按原点时保留。allocated成本不是利用率、金额或最终全目标成本；释放本方已闭合hold不删除原文件、checkpoint或失败。不得据总量推算各阶段已完成预算验收，超过预估两倍的报告规则仍保留。

本报告全部0–7未完成项继续有效，模型/配方/B*未冻结，学校正式预训练尚未启动。
