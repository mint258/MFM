# 当前encoder局部算子精度诊断：待公开预注册

2026-10-27。N/encoder_local_op_precision_v1_source的冻结源、最终execution request/source pins及Root静态、metadata装配、source-only audit已机器绑定。SA4最终只读审阅已完成，对相同9份核心冻结源及dependency inventory无阻断；正常仓库检查、正式公开读回和GPU提交仍待Root完成。本文件是待公开的最终metadata版本，既有DRAFT原件保留；没有GPU/model/NPZ执行、资源准入或科学验收声明，不修改W、STATUS、旧协议与v17。

## 固定候选与完整外部控制

候选保持local cf8ce66d97cd518ebf279b40ee20294919bb95e1、public f8417157dc23326d1beca8e19e4725755d9f13c6、tree2389ab046ee23f2ba92fcb61179d853dfdee8357，全六层centered_fp32_v1与原COMPENSATED stack。原48case、两seed、head policies、two/three physical views、三transform、参数/geometry/domain及absolute1e-5/rtol0不变；保留当前1776/1838物理21PASS/27FAIL、C4 HOLD，无adoption。

计划192次完整原F32 encoder forward，0次完整F64 encoder forward。每次完整forward返回后才做局部重放与独立参考，不把局部调用计作新增完整encoder前向。全部192个实际bank H0的raw-value SHA/dtype/shape/bytes须逐一匹配closed1838 typed headers；每case全52个外部终端数组（13字段×4forward，共2496数组）须与1838原始payload逐位相等，原逐case物理passmatrix/fixture/config/参数身份亦须相同。新fresh H0不是未保存的1776 internals；不以旧1561 H64代替当前H0，不重新打开未使用BANK_INPUT_STATE payload。

## 同输入的局部重放与独立参考

全48例、全部六层统一覆盖：norm1/norm2及out_norm、六个coupled attention、六个DenseFFN，另C1-0六个实际TiledDistanceMLP或C1-a/b共享Gaussian pair encoder。仅已有真实端口，shared attention不虚构weights端口；C1-0距离MLP输入为已有F32 dist2，不声称单独归因raw distance/compensated norm。各scope嵌套重叠，不能视作互斥原因。

完整forward期间，own/StageReferences hooks只保留Python输入/输出引用，不做tensor计算；全部original forward返回并移除所有observer后，再用真实原GPU输入对象、strides/storage offsets、F32权重、mask与原eval/inference/noAMP/backend上下文重放同一module。所有raw输出leaf包括padding均须逐位一致，保存实际layout/context和typed hashes。无CPU重建后再宣称原GPU重放。

独立F64参考先strict deepcopy并核原state membership/value，再只在clone内将numeric_mode/attention_aggregation_mode映射legacy、参数/buffer无损提升F64，保留cast-back原SHA与前后state审计；Gaussian仅使用既有1561 dtype-preserving reference。无随机初始化、无新RNG draws，原module/full-model/bank state不改。参考是同实公式的precision+algorithm contrast，包含补偿/centered与direct F64 reduction、dtype kernels/layout差别，不能称instruction-identical dtype-only替换。Shared attention参考提升真实捕获F32 pair_features/distances，不接另算F64 Gaussian输出；每个module只用自己的实际输入，任何reference输出都不注入model或另一reference算子。

计划每原role调用数C1-0为31、C1-a/b各26：合计5312次scientific局部F32重放及5312次独立F64 module参考，4368项module-port/transform观察。原tiny candidate/head controls在同job独立scope内执行；这些数字是覆盖计划，不是实际通过数，无新增完整回归或QA父。

## 分母、同分量与失败保留

feature统计只取实际valid native physical-view nodes；pair统计只取每physical graph实际mask外积的有序query-key/native pairs，包括diagonal；attention heads/channel分母另记。保留88/132物理nodes、6/9graphs与原dense shape；clean44仅bank输入门，不用它压缩模块GEMM。Padding包含在raw重放控制中，排除在数值max/RMS分母之外。

逐module/port/transform记录D32=Y32_t−Y32_0、同一真实F32输入的独立F64参考drift Dref，以及local residual D32−Dref；保留base/moved local errors并检signed closure。在D32、Dref、residual各自argmax处记录五个同一分量有符号值，记录实际输入drift：scalar feature/pair为invariant，坐标遵循原row-vector x@R+t。Dref仍包含继承输入drift，不是凭局部参考消去上游误差。

局部残差、不同population/scale的max、重叠模块scope均不作全模型原因排名或求和归因，不能据此自动定位GEMM/softmax/LayerNorm或选新precision candidate。数值local replay/H0/terminal不一致继续保留完整48数值矩阵，结束HOLD/nonzero；不选择case、不fallback、不改seed/backend/tolerance或自动重试。损坏source/input/context或资源失败单独记执行失败，不能冒作完整科学矩阵；原物理门失败保留且不终止该诊断。

## 有限资源与最终输入范围

只导出逐case scalar/header与复用完整terminal artifacts，不导出完整module activations/operands/weights，不生成重复bank NPZ。每case只在RAM保留四role masked CPU统计所需tensor并及时释放。实际读取source/metadata/旧terminal的合并输入与新artifact分别固定128MiB。Root最终metadata装配stat输入47060679B，小于134217728B、余87157049B；未读取或hash NPZ payload。实际worker仍须核全部真正读取文件的rawSHA/物理身份并计量，超限即拒绝；新artifact容量、实际资源与运行时耗尚未测量。

原compute-0-21/GPU-c35f2434-9137-9723-1af5-dc69b6295243/fd9公共物理锁，16CPU/32GiB、RSS28GiB、supervisor1100秒、Slurm20分钟、whole/private各2GiB、child outer-minus96MiB，以及全用户85%/fresh MemAvailable/quota/foreign-process守卫不变；无新监控、dispatcher或资源扩张。GPU/生产encoder/512维F32 H0 API不变，无训练、输出注入、层/seed选择或采用。

## 实际机器绑定与仍待完成的门

原source路径为`/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/encoder_local_op_precision_v1_source/`；下表前三项在该目录，其余三份Root证明在N根。摘要均从当前机器原件读取，并核对assembly/audit的request与pins引用相同；本文件不重新扫描1249项source图或读取科学payload。

| 原件 | 字节 | raw SHA256 |
| --- | ---: | --- |
| execution_request_v1.json | 455371 | 121c82d31f0fb0d55ef4f7284c00406d6cec32751018badd46656646507ea359 |
| source_pins_v1.json | 328979 | ef2e230fefb801d850c29186c66ec4702760503cd843fd88e69fb06259829b4c |
| DRAFT_SOURCE_INVENTORY.json | 4463 | 730b4132a0692bcbfa7402fc37d89e5ecdd241dc645a50919940411406e5e5c5 |
| Root_encoder_local_op_DRAFT_static_actual_v1.json | 6086 | 651e7c4ee9a8ad5fc1263532b7488f55f4e16daaf7f3736d4b50e45acaa458a1 |
| encoder_local_op_metadata_assembly_actual_v1.json | 1314 | 20950b86e9b1e86de6cca5dbce6ff5d354bde0f492586d61fc0c009bfaefe7e5 |
| encoder_local_op_GPU_source_audit_actual_v1.json | 5423 | 6c4f144b9c821150e71fdc7e62d04bf4ec7074d1c11815f273ffc4bd1ddf0f29 |

Root静态证明实际核1249个唯一source/metadata refs、31629198B，6个Python AST和1个bash语法；它保留装配前NOT_YET_EXECUTED的时间点字段，随后独立assembly证明已绑定最终request/pins与47060679B selected-input stat。Source audit验证源/注册投影与绑定，状态明确SOURCE_AUDIT_ONLY_NO_SUBMISSION；它不是节点空闲、实际memory/quota/GPU准入、运行或物理门验收，不能替代提交时fresh guards。没有运行模型或打开NPZ。

SA4最终冻结源审阅已完成，结论为NO_SOURCE_REVIEW_BLOCKER_NOT_EXECUTION_OR_SCIENTIFIC_ACCEPTANCE；正常checker与精确source快照/协议的公开commit/tree读回尚待Root补齐，不能把静态/只读审阅或输入stat fit称为5312/4368实测PASS。Root在这些门及实际fresh资源核验满足后唯一提交；此前不填未来jobID/C0/GPU结果。运行后以actual source前后、raw结果/失败、supervisor与Slurm真实终态闭合。无其他新工具、QA父或测试框架。

## 最终只读审阅及点时成本

SA4证明原件为N/encoder_local_op_precision_SA4_readonly_review_v1.json，8740B，raw SHA256 43196825fc6f1ecc52ad20c78b4a0aac35b7599efbf68637b61bbcbd0f09e96c。它绑定同一inventory及Root静态证明，完成9核心leaf与dependency inventory的raw-byte审阅，对完整科学接线无source blocker；没有执行Python/AST/model/NPZ/network/Slurm，不是GPU、资源、replay或物理验收。1249项源图、输入stat与SA4的各自核验范围分别保留，没有据只读审阅新增实际测量。

成本原件O/job_ledger_model_v3_active_v21.json，549981B，raw SHA256 a2ab3806d6893c75d183a9692bcc372a86710e2842995de27690718379ed2ebe。固定捕获时间2026-10-27T02:36:47.520068+00:00，466父，allocated CPU核秒1308624、GPU作业分配秒61251；活动jobIDs 4521338/4522063/4522068/4522069，尚未全部终态。这是点时分配成本，非最终成本、实际利用率或金额，也不表示本新GPU诊断已经执行或获资源准入。原v1与先前报告/账本均保留，不刷新历史快照。
