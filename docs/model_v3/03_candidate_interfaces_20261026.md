# 阶段3候选接口：实现验收与尚未完成的全计划

本报告回答：数据线现有候选投影/真实wire代码能否接入模型采样、只读加载、掩码原因审计及原训练循环？结论仅为合成工程接口已贯通，整份指南、正式D3验收及最终模型配方尚未完成。289条全指南审计的原时间点为e47d066/公开d04af5c，见[完整审计](COMPLETION_AUDIT_20261026_v1.md)；审计源JSON按原字节保存在analysis_sources，不据后续代码进展改写原快照。

## 预定规则、配置及版本

沿用已提交的v3采样/标签/结构视图和恢复协议，原sampler、旧S head/loss与H0均保留。新A独立核验DataB投影50aceee7的PM7/UFF各自ID、数量、三种顺序、保留最低能构象与诊断排除；authority始终synthetic_fixture，不升级为最终D5。新B调用实际固定6份DataB MFM3/LMDB源码，严格只读且有效fixtures全部处于节点本地TMPDIR。CPU审计sidecar区分source validity、review与recipe exposure，保留field原因集合/稀疏leaf原因，不编造稠密原因。合成bond映射显式绑定，仅在声明fixture内有效。

A candidate 8c6db4c，Root d72bf50；B initial88326b2与夹具修订b4c59be，最终A+B执行Root3789c19865f70f80191986675cb13b606ebd210b。完整机器SHA、数据代码SHA和原Slurm回执在[机器验收](results/candidate_interfaces_20261026_v1.json)及其链接文件。代码提交前实际运行仓库检查器。没有将本报告视为阶段3总体接受或训练选型。

## 实际结果

| 验证 | 实际Slurm父 | 结果 |
|---|---|---|
| A专项 | 4520963 | 98PASS/1CUDA skip，其中新59项全部PASS |
| A分支完整回归 | 4520969–972 | 2447PASS/2CUDA skip，103文件 |
| A整合完整回归 | 4520983–986 | 2447PASS/2CUDA skip，103文件 |
| B专项初版/夹具修订 | 4520964 / 4520982 | 各66PASS/2CUDA skip，其中新26项全部PASS |
| B分支完整回归 | 4520992–999 | 2414PASS/2CUDA skip，103文件，8分片完整无重叠 |
| A+B整合完整回归 | 4521001–1004、4521007–1010 | 2473PASS/2CUDA skip，104文件，8分片完整无重叠 |
| A→B→原trainer贯通 | 4521005 | 4PASS/0skip，真实只读句柄、两spawn worker关闭与未消费预取恢复 |

最后四项贯通包含：固定真实DataB projector→A typed index/原sampler→B实际geometry/physics/descriptor LMDB→collate/PreparedV3Batch→原6×512 trainer一次更新，各S/D/P有效数与有限损失/梯度；同时拒绝未导出UFF/mixed locator及native五字段不一致。UFF仅为原projector必需的显式索引元数据，没有伪造UFF坐标/标签或混合条件归一化。它是单元验证，未用UnitTracker冒充持久化SDK训练。真实权重和LMDB不入Git。

## 保留的失败及处理

4520973–976在node17实际因ReqNodeNotAvail未启动；仅取消这四个本人未启动作业，原回执保留，改投实际可用CPU12。4520977被严格private census终止，因为负例alias symlink置于私有TMPDIR；修订仅把该拒绝路径放入预声明pytest负例目录，有效LMDB仍本地，私有census未改。4520991因既有完整512模型测试产物达到2,358,521,526字节触发2GiB guard；旧输出不删除，后续改为8个有界分片/两批执行，未放宽资源上限。上述失败仍为失败，均纳入实际父成本。

## 新发现的C4组合门槛失败

独立冻结工具在4521006实际执行57项：9控制PASS、48组合FAIL，无error/skip，源前后SHA一致。48组合为3 C1×2 view×4 H/pooling×2固定seed，每组合检查13终端与3种原先声明的刚体变换，绝对1e-5、rtol0；非零参数、原输出NPZ及case JSON保留，未换fixture/seed/阈值。

超限仅见p_extensive、p_dipole、p_dipole_magnitude，最大分别2.28881836e-5、5.14984131e-5、3.08752060e-5；其余10字段未超限，邻居集合和非空/有限性检查未失败。此结果证明旧单独encoder/head测试不能替代完整组合门槛。失败工具尚未整合进production suite；精确冻结源码快照及48原case SHA已发布。当前继续受控误差归因，不认定原因或采用任何精度改动。原始NPZ在Git之外，未用零向量或相对容差绕过失败。

## 仍缺的内容

D1仍draft.3，D2物理注册表未最终冻结，D3–D7最终数据未交。tensor6、basis索引、真实扰动几何监督和按几何条件的D4归一化仍须正确接入及真实逐字段过拟合验收；当前candidate明确拒绝这些未支持范围。两项CUDA transfer仍需真实GPU通过。代理运行器/WSD、磁盘采样cache、C4误差修复、A完整三GPU矩阵和B的2万步双种子验证仍在推进；stage5/6科学比较、B*与最终recipe/tag/PR/HANDOFF均未完成，不生成虚假冻结文件。


## 后续工具的已测来源与预注册诊断

缓存31新项及原采样测试在4521012为109PASS；代理运行器20新项及原selector在4521013为43PASS，均无skip且源前后SHA一致。代理运行器实际6×512checkpoint为199,149,689字节；模型tensor89,545,204、已物化Adam tensor109,347,172。全部参数都有双moment的268,635,356字节只是规划情景，不能当实际下界或真实D下的64M容量证明。两工具仍须完整分支与Root整合回归；缓存首次8分片4521020又因2,295,044,484字节触发原2GiB guard，现改保留已成功完整Root的固定旧测试分配、对新增模块显式预留512MiB，并保留所有失败。最后观测大小与预留是规划值，不是峰值证明；后续正加强plan/binding/runtime-source闭合，既有回执scope不回写。

原GPU矩阵4521015为实际FAILED/1:0/6秒，在str(prop.uuid)与冻结完整GPU-UUID比较处提前退出，矩阵和旧CUDA均尚未执行；其代价完整计入GPU作业账本。外层原CVD/实际NVML/公共UUID锁未放宽。新的完整128-bit UUID格式规范化及admission CPU mocks在4521030通过41项，只证明启动器格式/guard逻辑，不能当CUDA通过。原48数学源/夹具/参数/阈值逐字节保留，后续必须fresh请求及实际GPU重试。

以下固定协议先以本次Git源码快照发布，之后才执行实际诊断。4521030另有10项真实算子小测PASS。Eq归因预声明7×48完整矩阵：原公式重放、cdist direct、charge去均值、FP64 graph-feature pooling参考及三个两两组合；参数、几何、视图digest不变，baseline逐字段严格重放。FP64仅用于归因，不代表FP32验收或采用；不挑case、不改1e-5/rtol0。所有原NPZ仅引用；每variant32MiB、总2GiB原限制保持。

A06归因工具在4521031通过23项typed CPU测试，实际native诊断尚未执行。固定原457同物理5090、8ece源码/config/seed/native8M逻辑批/8workers，做15更新：原reference foreach、自由fused、借用每步reference真实clip后grad的fused shadow；shadow只clone参数、不新建随机模型或forward，核验RNG与grad全字节/None前后不变。两原路每步必须与457精确重现，否则REPLAY_MISMATCH且不归因。只记录连续误差、dispatch与小scalar，无新pass阈值/无模型采用，独立SDK读回仍需实际运行后完成。此前485仅synthetic-gradient optimizer诊断的限制保留。该短诊断不替代原20批+500步验收。


本次账本为单独时间点快照：258个实际本人model_v3父、613,152 allocated CPU秒、26,247 GPU作业秒（含4521015失败6秒）；捕获时仅4520456仍pending。采用sacct历史发现+squeue实际活动作业补齐，所有失败/取消/超时保留，GPU作业时长不是利用率或GRES预约。后续新任务不在此时间点账本内，整份目标仍active。见[原始会计与来源](results/job_ledger_candidate_interfaces_v9.json)。
