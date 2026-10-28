# D1：模型侧有限 ACK 范围与共同政策候选

2026-10-29。状态：**MODEL_POLICY_CANDIDATE_FOR_JOINT_SIGNATURE_NOT_D1_FREEZE**。

本文给出 Model 方可具体签定的接口和政策定义，供 Data 方逐项确认、Root 形成真实双方记录。新增本文不构成最终 joint ACK、v3.0 冻结、D4 已交付或真实 consumer 可执行；不修改 Data 目录、旧反馈、指南、源码、原值、mask、科学阈值或历史结果。

## 依据与指南对照

原405行指南的 Root 服务器逐字缓存已完整核读：26121 B，SHA256 `e618165501d22556c4c421d93f1c01928fab3f50202ce6d0fec3249c79921239`。缓存仅是只读核验媒介，不是新指南版本。

指南第73行要求 D4 为 TRAIN-only 且包括稳健标准化；第205–208行要求先 D4 归一化、Huber δ 默认1、组内有效字段等权、启用组等权及逐字段有效数记录。因此，先前内联讨论的 RMS 仅是未采用候选，**本页不将其冻结或视作现成 D4**；以下改提稳健径向中位数。新 tensor 定义须双方明确版本，不以本页改写普通 scalar/vector/pair 的既有政策。

| 本次实际读取的 Data 原件 | bytes | SHA256 |
| --- | ---: | --- |
| `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/docs/interfaces/D1_native_token_parser_storage_control_chain_review_20261028_v1.md` | 12956 | `18a47c0ce45c15c986ae49580b1a7b6dc774d77c90114c25d6b602e87bbd3d6d` |
| `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/docs/interfaces/D1_parameter_inventory_and_joint_freeze_candidates_addendum_20261028_v1.md` | 10642 | `9a52eb2f4f5b575abb06b269a12eb8dad294f586dd515077db9619afd6334e69` |

既有 [draft4 模型意见](training_format_v3_draft4_model_review_20261027_v1.md) 和 [draft5 条件反馈](training_format_v3_draft5_model_feedback_DRAFT_v1.md) 保留原件。本页是后继候选，不回写其时间点状态。

## 可签认的有限来源结论

新增 addendum 已关闭四份 serializer/freeze 当前原件与缓存的 bytes/SHA 比较，不再把同四件列作待补。r73 的 native→parser→retained-list 路径、r674 六序及 full 打印约定、偶极的一次单位转换、gradient/force 的符号和实际 child 绑定要求，可按两件原文所绑定的 Source/已有实际证据分别记为来源层结论；不能外推为所有 target 物理轴已验收。

对于唯一 XTBPATH 下 rc absence，Model 方愿意签认限定的 `RC_ABSENCE_SUPPORTED_BY_TRUSTED_DIRECTORY_CONTINUITY_INFERENCE`：依赖可信正常文件系统、时钟连续、同一路径/目录未替换、无快照恢复或特权时间戳操纵，以及原文绑定的当前 absence、旧目录 mtime/ctime、冻结参数清单和实际控制分支。记录 `historical_absence_absolute_proof=false`。不把有限清单冒充完整历史 census，不把未找到 installer Source 变成无限补件或重跑 QM 的理由；Root/Data 仍须在真实双方记录中确认采用这些假设。

六种 xTB single-point 的192项独立坐标观测继续 UNKNOWN。上述 inference 不把它们改为 PASS/FAIL，不生成异常 mask；已完成的 actual384/retained100/old72 等证据按原 scope 复用，不要求重复计算。

## r73：有序双端 entry 与一次训练转换

精确对象是 `P.pm7_B.r73.value / registry73 / values.sigma_pi_entries`，不能与其他 task/condition 的同名路径合并。Model 提议共同采用权威原 F64 sidecar，加 consumer 恰一次 F32 转换；F64 保存已解析值的 bit，可得原 token、打印精度和原生程序精度另留引用，不能由容器反推。

每个 retained entry 保留零基 src/dst atom、两个独立原 UTF-8 channel、onsite、方向、重复、列表顺序、entry_ordinal、全部值、原 valid/reason/codebook 和完整 owner/geometry/atom-order/source 身份。ordinal 仅用于对齐、审计与恢复，不作 learned ID；“无损”仅相对原已保留 parser-list，不补未保存的完整 AO 矩阵或远距项。DEL/DELL/DELTA 不并码，未知 channel 拒绝；若用 opaque codebook，须有可逆字典、版本及 SHA，不能仅有整数编号。

训练前转换位置、F64→F32 规则/指纹和恢复绑定须共同冻结。不可表示的转换明确 HOLD，不补有效0或改 source mask。新 FieldSpec/provider/collate/head 必须真消费两端 channel 和有序 atom 表示，保留 onsite/重复及各自输出位置；不借普通交换对称 PairHead 放行。有效监督按原 ordinal 观测计数，不按 unique atom-pair 或词典类别重计；字段/组平均和 exposure 继续分离。普通 S bond/Wiberg 默认路径不因本候选改变。该新域及其真实读取、loss、恢复仍 NONEXEC。

## r674：完整六值与 tensor loss 资格

精确对象为 `registry674 / xtb_singlepoint / values.molecular_quadrupole_traceless_au`。认可其原生 traceless 定义，但保留 full 六原值，顺序固定 `xx,xy,yy,xz,yz,zz`；不额乘1.5、不投影 source、不减 trace、不丢 zz。原生打印的 trace 舍入残差只报告，不修标签；矩阵镜像不是九份独立标签。

建议共同选定 `loss_eligibility = all(valid6)` 作为完整 tensor loss 的资格，理由是采用完整张量的闭合 Frobenius 观测，而非按实测误差挑选人口。原 partial 值、逐 component masks/reasons、有效 leaf 数及 retained/excluded coverage 全保留；loss ineligibility 不改写成新 source-invalid，不删除或重填原数据。原质量分母和 >1% 报告/HOLD 规则保持原定义，不能换成“仅 eligible”分母。partial/excluded coverage 须按 condition 和 TRAIN/VAL 分别披露。

未来若改用 partial 训练，须另行明确 frame-aware 观测算子、metric、count 和 `A′=A D(R)ᵀ`；不机械旋转 bool mask 或制造缺失 target。本页不启用该后继政策。

## 稳健单尺度候选及平均规则

模型侧建议 `c=0`。每个 condition/physical target 使用一个真实 Common∩effectiveTRAIN 拟合的 scalar：

```text
u_i = ||Q_i||_F
s = median_TRAIN(u_i) / sqrt(6)
r_i = ||Qhat_i - Q_i||_F / (s * sqrt(6))
L_i = rho_1(r_i)
rho_1(r) = r^2/2  (r <= 1);  r - 1/2  (r > 1)
```

Frobenius 平方权重按六序为 `(1,2,1,2,2,1)`；等价正交六坐标为 `(xx,sqrt2*xy,yy,sqrt2*xz,sqrt2*yz,zz)`。d=6 是此候选的固定正交坐标归一约定，不是九份标签、trace 修复或可按结果选择的分母；采用一个 tensor radial Huber，不是六个 component Huber。

D4 人口只含该 condition 的完整 source-valid、loss-eligible 物理观测，按同一 release 真实 physical-observation key 去重。重复采样、恢复、视图、epoch 不重复增加统计权；Common/角色及 D5 heldout base/真实直接 children 的 anti-join 保留。不能借另一 condition、PM7/UFF/P′、VAL 或下游数据拟合。偶数人口的 median 取中间两值算术平均；排序、累积/转换精度、人口指纹、单位、算法版本及实际结果 SHA 需由真实 D4 冻结。

空人口、s=0、非有限或按规定一次 F32 舍入后非正/非有限，一律 HOLD；不自设 floor、替用轴向统计或修改 valid。这里“不支持 F32”指不能得到正且有限的 F32，不要求所有实数无舍入精确表示。本文没有生成任何统计数值，也不声称现 D4 Source 已提供此算法；Data 方具体签定并交付前保持 NONEXEC。

每个 eligible tensor 计一个有效观测，先在字段内掩码平均；组内对至少有一个有效标签的字段等权，再对启用 S/D/P 组等权，逐步记录字段有效数。不能把 r674 当六/九个字段改变组权重，也不能按观测数量重新加权字段。局部 batch 无 eligible tensor 记 field_count=0，不冒有效零标签或质量 PASS。

## 显式 source-origin anchor 与物理待件

建议把实际 source-origin 作为显式物理 anchor O，并映射到与模型 geometry 相同的单位和 frame。对行坐标 `X′=XR+t`，同时传递 `O′=OR+t`，此时关于同一物理 anchor 的张量按 `Q′=RᵀQR` 变换。native 坐标图中的0原点不自动等于模型坐标图的0，更不能改称 COM。

若移动坐标却把原点重置为固定0，quadrupole 通常需要额外 dipole/charge 平移项；中性并不足以消去偶极交叉项。anchor 随坐标变换的表示政策，不是假称在固定0原点重新运行 native 仍满足纯旋转式。统计 `c=0` 也不解决物理原点。实际单位/符号、Å↔bohr 或系数单位映射、坐标预处理和 child/atom-order/whole-bundle 父链仍须逐 target 绑定；不可用 magic 声明替代。

独立 tensor_math 提供的数学基元及工程测试证据不构成真实 r674 consumer 支持。codebook、FieldSpec/provider/collate、tensor head/loss/count、D4/CP/cache/恢复、真实 TRAIN/ROUTINE VAL，以及同一 release 的五层 maps 仍须实际实现和验收。原逐头1000分子过拟合、三卡 SDP、H0 接口、完整 FP32 等变门及所有历史失败/未完成目标均保留。本页不缩减人口或测试矩阵，不改变阈值，不生成新运行、数据权威或 QA 证书。
