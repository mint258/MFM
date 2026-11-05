# 训练格式接口契约 v3.0：用户决议冻结设计

状态：`USER_FROZEN_DESIGN_1_TO_4_FRAME_TEST_CONDITIONAL`；设计版本 `v3.0`，2026-10-29。本页按机器保存的用户选择 **1A、2A、3A、4A、5A附一次半小时xTB测试**定稿。它是正式设计，不是另一轮选择草案。配套机器政策与五层映射选择具有同一设计版本；实际部署引用三件文件各自的 SHA256。

本页不宣称 Model 已确认此版本、消费者已实现或数据已发布。双方发布签认仍须精确绑定同版本合同、映射、实际消费者和实际数据。5A 的带电旋转/平移测试结果尚未提供给本页，物理发布条件保留；历史六个xTB单点条件共192项缺少独立输出坐标的状态仍为 `UNKNOWN`。该历史事实不被新试验覆盖。

权威输入：`configs/data_v1/interfaces/user_D1_v3_decisions_20261029_v1.json`，真实正引用见配套 machine policy。Model 已提供条件式审阅，不再描述为“未审阅”：公开提交 `a45495e0398bc38ffda88f8384aee5d6011fc04d` 的 draft5 反馈明确不是 joint ACK。其条件中本轮需选择的精度、完整六项、中心/尺度和径向损失已由用户选择；实际实现与验收不能由选择本身代填。

## 1. 人口、身份与几何

原 WP5 catalog canonical owner、正式人口、原角色及已验收 S′为来源。精确连接原 molecule_id、record_id、attempt/job/task/lane；PM7 `native_record_id` 与 S′ `sprime_conf_idx` 为独立身份，不按名称或排列建立对应。原 LMDB 只读；不存在的整库 SHA 不新增为前置事实，原 pointer、逐 payload SHA、原子序和前后同FD frame 仍完整核验。

几何记录包含：dataset/release/contract版本、稳定唯一 geometry/export_record_id、molecule_id、geometry_source、来源内 conformer_id、source/effective_role、原生ID、owner、原子序摘要、永久F64几何摘要、真实源文件/物理行/输入双hash及来源引用。单独保留原11322条ROUTINE记录标记；它不取代全7610个ROUTINE分子的角色权威。ROLE层这些分子的全部几何属于VAL；最终所有条件共同使用 `Common∩effective_role`。5000VAL候选是 `Common∩effectiveVAL`，报告Common过滤前后人数，不给予Common外例外。

S、S′、P、P′、D共同人群须真实满足指南完整PM7和足量S′条件。TRAIN拟合人口为真实 `Common∩effectiveTRAIN`，反连接D5所有held-out base及其真实直接child几何；VAL/FULL/embargo不得拟合。每个目标必须定位自己真实输入几何和原子序，不能将扰动标签挂到base或模型任意局部噪声。实际child保存parent、recipe、seed、原始/渲染输入摘要、真实坐标来源；若只可确定性重建，明确 `RECONSTRUCTED_FROM_EXACT_ORIGINAL_RECIPE`，不得写成独立观测。

三构象顺序保留原对象、seed20261025、稳定tie-break及原来源内identity：fixed_random、energy、diversity。诊断后最低能训练构象取保留集 `training_rank=0`。固定嵌套120k⊂240k⊂600k⊂allTRAIN；50k来自120k；20k诊断要求两来源各至少2构象，各自固定random末位及全部真实直接children排除训练。N=1/N=2及不足k如实计数，不复制几何补足。

## 2. 原值、索引、有效性与存储

永久科学值和几何以原F64及原来源保存；F64容器不增加原程序打印精度。训练数值只作一次明确F32转换，并保存永久F64旁车引用和可逆对齐。原子序不重排、不拟合、不居中；atomic_numbers保存真实Z（int16），模型Z−1是明确provider变换；训练positions为F32[n,3] Å。普通bond/Wiberg pair仍采用独立既有int32[n,2]域和各自有向/无向、重复与self规则。

family LMDB沿用MFM3 magic、长度明确的规范UTF-8 JSON header和little-endian连续raw数组；禁止pickle/object。保持原6 reader-codec Source身份、payload SHA、dtype/shape/offset/边界核验、records/molecule_index/masks事务、WRITING/COMPLETE及每shard SHA。本设计选择r73旁车，不扩展旧wire白名单以虚称已有f8训练codec。新r73域的header/旁车/consumer必须版本化，不能混入旧普通pair路径。

逐field及sparse-leaf保留source/new/review三口径有效性、原因和版本化codebook（含unresolved=65535原含义）。exposure、loss eligibility与源validity彼此独立。缺失不补有效零，UNKNOWN不当作已证数值失败。原1.5检查及适用field真实分母的异常mask>1%报告/HOLD规则不变；63 N/A、10已移除壳层、无关task或Common人口排除既不稀释分母，也不伪造成异常。

## 3. r73：有序双端通道条目

精确registry：`registry_id=73`，`P.pm7_B.r73.value`，source path `values.sigma_pi_entries`。新独立wire域 `SOURCE_ORDERED_RECORDS_V1` 表示**已保留解析列表**，不是完整AO矩阵或原始AO ordinal，也不是普通atom pair。其最小逐entry字段如下。

|字段|正式含义|
|---|---|
|src_atom / dst_atom|原parser零基atom_i / atom_j，引用本条实际几何原子序|
|src_channel / dst_channel|原parser basis_i / basis_j的原样UTF-8字符串；若用整数，须版本化一一可逆codebook及SHA|
|entry_ordinal|记录/task/field内部已保留解析列表的0基顺序；不是AOordinal，也不得作为learned身份捷径|
|onsite / direction / duplicates|允许src=dst；保留原方向、重复、原顺序及同atom对多个不同通道；不合并/镜像/求和|
|value / validity / reasons|权威F64旁车、一次F32训练值、原有效性和原因；可得raw token/精度来源另引用|
|owner / condition / geometry / atom_order|与原task及真实坐标、输入双hash、registry和schema/codebook精确绑定|

MOPAC sigma/pi通道依赖原子对方向，并有特殊onsite valency语义；不得把AO_ATOMINDEX、px/py/pz或全局xyz轴套给这些字符串。DEL/DELL/DELTA没有被本设计并码。batch只给atom indices加原子offset，entry及通道不排序；反批处理须恢复原entry列表。模型须区分两端atom和两端channel，逐entry预测；旧交换对称且无channel的pair head不能冒充本域。具体网络实现由模型线完成并用精确Source/恢复索引验收，本页不假定已存在。

权威旁车对每entry保留原F64位模式/原列表身份及mask；训练wire只转F32一次。旁车→wire→batch→恢复须有真实逐entry对照；ordinary pair的no-self/unique守卫不因r73而删除。

## 4. r674：完整六项、尺度与损失

精确registry `674`，程序名不改写成其他人类别名。成员固定为 `P.xtb_singlepoint.r674.{xx,xy,yy,xz,yz,zz}`，source path `values.molecular_quadrupole_traceless_au`。每个真实task/condition/source单独实例化一个物理目标；P′不借P的拟合统计。六项组成对称3×3，源顺序、原值、分量mask/reason全部保留。

冻结源xTB定义已经包含相应1.5与trace项；禁止重复乘1.5、减trace、投影无迹、删zz或拆成六个普通不变标量目标。原打印trace非零原样保留，不以“可能舍入”改变标签、掩码或容差。已有32个样本中11个Decimal trace非零是实际有界事实，不等同新质量失败或全人口比例。

**训练eligibility选完整六项。** 同一实际几何、同一条件的全部六项原valid且必要物理政策/尺度就绪，才加入该tensor loss。partial六项仍存储、导出和审计；eligibility不足不是新增数值mask。按实际适用population、condition、TRAIN/VAL及分母口径报告retained/excluded数和比例，并分解源invalid、缺项、不同几何、政策/尺度未就绪。报告元素与可靠化学结构分层分布；结构分类不可得必须单列UNKNOWN及覆盖率，不从ID或次序猜结构。**排除率>10%预警；>20%或集中化学偏差必须论文披露**。这不替代或豁免原>1%异常mask门；集中偏差须由真实分层表和Root科学审阅判定，不发明本页未授权的统计阈值。

设原六向量q=(xx,xy,yy,xz,yz,zz)，其Frobenius范数

`F(q)=sqrt(xx²+yy²+zz²+2xy²+2xz²+2yz²)`。

只选择既有D4实际TRAIN series `physical/<registry_id>/<task>/frobenius_norm`，按原type7的q0.001/q0.999对**统计副本**缩尾，使用原 `WinsorMoments.std_ddof0` 得到一个有限正标量s。完整拟合人口、task/condition、D5反连接、量纲、series key、实际数值DATA及SHA必须绑定。冻结归一化为 **Q/s，中心c=0**；不减六分量均值，不减cI，不使用RMS、不加epsilon或默认s=1，不修改标签。常量/空/缺尺度时保存数据和原mask，状态 `LOSS_DISABLED_SCALE_UNBOUND_OR_DEGENERATE`；只不加该target loss，其余已就绪目标可继续训练。

同时报告原始完整eligibility TRAIN范数的 `mean(F)/s`；>10提示下一版本评估isotropic centering，当前不改变c=0。现有winsor统计row.mean是 `mean(clip(F))`，必须另名报告，不能冒原始mean(F)。若原始均值未计算，精确标 `RAW_MEAN_F_REPORT_PENDING`；已有尺度与其他目标不因此被无声换算法。

令E=(Qhat−Q)/s，

`r=sqrt((Exx²+Eyy²+Ezz²+2Exy²+2Exz²+2Eyz²)/9)`；

`Huber_1(r)=0.5*r² (r<=1)，否则 r−0.5`。

每个tensor是一个target、delta=1、target weight=1；先按完整eligible geometry平均，再进入既有组/目标权重框架，不乘6、不逐component先做Huber。d9与当前Model vector3的 `square().mean(-1)`（/3）约定一致；具体tensor实现与旋转验收仍需同版本实际消费者证据。权重(1,2,1,2,2,1)与单标量尺度给出固定原点旋转下的Frobenius径向损失，不宣称在任意平移下不变。

## 5. frame、偶极与实际child

行坐标固定 `X'=XR+t`；同一变换后原点对应的tensor旋转为 `Q'=RᵀQR`。若模型采用列向量约定，必须显式 `R_data=R_modelᵀ`。带电体系的平移不是上述旋转公式：必须用真实总电荷、原偶极及官方native quadrupole约定的交叉项检验。物理原点平移与统计中心化不是同一操作。

按用户5A，可信文件系统/目录连续性下的rc历史缺失推断与实际native调用Source共同作为可接受的provenance依据，但仅在这一次原版本/原数值关键字的xTB小测试旋转/非零平移（包括带电）满足冻结比较规则后，由Root科学审阅及Model同版本ACK落实到逐target物理政策。测试最多16CPU/1800秒，原proposal上限不变，无自动重试、不新增MOPAC/2000/full精度授权。本页没有测试receipt，状态 `CONDITIONAL_NATIVE_FRAME_TEST_PENDING`。若无法核实，按用户实际policy的fallback关闭原点敏感带电目标exposure，其余可确认目标走A；数据/原因保留，不能全域默认PASS。

当前192个xTB单点缺独立输出坐标仍 `UNKNOWN_NO_INDEPENDENT_NATIVE_COORDINATE`。不能从Source默认CMA=false、当前rc不存在、输入绑定或新测试替它们填独立坐标。UNKNOWN影响由逐target、条件及来源的实际政策明确决定，不自动变数值mask或笼统认定所有轴失败。

偶极维持源xyz、原单位/符号、原输入原点与实际条件；magnitude仅为另登记标量，不覆盖矢量。梯度维持原dE/dR符号与单位；force只用原冻结转换常数/符号，不猜别名。扰动梯度必须走真实child view/H0与原子序，不复用clean H0冒充。源token→parser→stored布局与实际frame证据分别列出；一个target通过不得外推到其他task或physical域。

## 6. 五层映射与发布

配套 `D1_v3_0_five_layer_mapping_selections_20261029_v1.json` 冻结以下五层设计选择。每层实际发布仍须resolved字段清单、版本、Source和DATA SHA；null不是可执行引用。

1. registry→component：稳定field_key/registry_id/task/source_path/component，146统计分量不等于146head；真实43P/26D分子标量与另有atomSASA如实映射指南42P/27D差异。63N/A/10移除不伪造值。
2. component→physical target：精确members/selector/task/condition/量纲/geometry；r674完整6一个target，r73独立ordered-entry；异条件不合并。
3. selector→stored entry/value/mask：原source physical row/owner/ordinal/双hash，原F64/原token及mask/reasons；逐field→真实geometry claim，不能task名推一view。r73旁车与一次F32，r674六项均保留。
4. actual geometry→sampling：PM7/S′独立ID、原子序/真实child、Common/角色、D5base+child反连接、三orders/seed及training_rank。
5. provider→FieldSpec/view/D4：实际wire schema/codebook/索引偏移与atom scatter、Z−1、r73双通道entry及r674tensor路径、actual child H0、condition独立尺度、eligibility/loss/count/恢复；不得以synthetic PASS冒真实消费。

最终D2尺寸规则仍 `|rho|>=.95`，HoF在TRAIN元素参考后判定；extensive/intensive按真实物理定义，不能以rho替代。D4保留原TSQR256逻辑顺序left-fold、0.1/99.9 winsor统计、energy-only元素参考、逐元素原子统计、median/MAD z20审计及全人口1.5规则。P′正式独立统计不能用15/NEW20/1200诊断替代。

正式设计到可训练release依次具备：真实Common/D5/全TRAIN拟合和质量闭合；用户5A实际结果及逐field物理政策；精确同版本Root科学签认和非conditional Model ACK；真实provider/export试点及源值/索引/mask对照；Root最终external seal绑定全部SHA。既有 `final_release_v1` 发布口继续使用其严格 `ROOT_MODEL_JOINT_FINAL_LABEL_POLICY_V1/JOINTLY_FROZEN`，本用户设计policy不冒这个schema。D3真实50k+5k、1万源对照及multiworker验收，D6须真实Model试点接受后再全量。

当前已知两个实现接合点必须据实修复/验证：旧final_release的缺/零scale会整候选raise，尚非本设计的target-local关闭；其row.mean为winsor均值，不能作为原始mean(F)。本交付不修改冻结发布器，不宣称这两处已实现。r73/tensor消费者仍须由Model交精确实现与实际验收；不再就用户已选的算法重新征求草案意见。

## STATUS可直接采用的通知

用户已冻结D1 v3.0设计1A–4A；5A依一次≤30分钟、含带电的原版xTB旋转/平移测试与逐target科学审阅有条件采用。正式合同、机器policy和五层映射选择已提供；r73采用F64权威旁车+一次F32有序双端channel域，r674保留full6、complete6 eligibility、c=0/实际TRAIN winsor范数std单尺度、d9 radial Huber(delta1)。缺scale只禁该target loss，其他就绪训练继续。报告eligibility偏差及原始mean(F)/s；>10%预警、>20%/集中偏差论文披露，原1%质量门不变。历史192独立坐标仍UNKNOWN；Model已有conditional反馈但本版本joint ACK、实际consumer与最终release尚待，不把设计冻结冒数据已可训练。
