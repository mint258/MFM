# D1 draft4：r73有序双端basis-channel域的模型侧源码审阅

2026-10-27。状态：MODEL_SOURCE_REVIEW_DRAFT_NOT_JOINT_FREEZE。本页只评估r73，不代替其他agent的r674/units/frame等审阅。支持draft4将r73从普通atom-pair中分离、无损保留已有entry身份的方向；这不是新wire/provider已实现、基标签可训练或MODEL_DATA_JOINT_CONTRACT_FROZEN/v3.0签署。当前draft3和模型拒绝basis的门保持。未改模型/数据仓库/冻结报告W，未运行Python、AST、模型、测试、Git或Slurm，未读科学payload、NPZ、SDK或LMDB；仅读源码、小型契约/registry元数据和官方PI说明，写本MD与同名JSON refs。

## 1. 原源码实际支持什么

- 原`runs/phase1_dataset_rebuild_20261010/scripts/wp4_native_pilot_v4.py:171–195`定位SIGMA-PI BOND-ORDER MATRIX，按`[SPDF]-(SIGMA|PI|DELL|DELTA|DEL)`读字符串。每端key是打印atom号减1和该端原basis字符串；每个值append为`{atom_i,basis_i,atom_j,basis_j,value}`。193行的unordered原子对仅用于判断是否在选定近邻集合，输出端点、双端basis与append顺序并未因此canonicalize。same-atom项直接保留，不能改成普通非self bond。
- native invoke的383–385行把sparse hook传入原PARSER。实际冻结WP5入口在`runs/phase1_wp5_20261011/scripts/`：engine_v3第62/67/76行绑定native lifecycle和parser2，第352行调用NATIVE.invoke；parser2第49–50行、base parser第60–61行将同一sigma_pi hook继续传给冻结legacy parser。legacy `wp4_parsers.py:145`将结果存为sigma_pi_entries。这里核的是实际原源码路径；另处同SHA副本不能替代部署/运行provenance。
- 这些parser用`if key not in keys`登记(atom,basis)，按分页offset寻找已登记key，没有独立原打印列/轨道组/AO ordinal，也不保存原token、打印精度或完整原始matrix。数值解析失败行会continue，超出现有keys的列不会生成entry。因此新entry_ordinal只能是**已有解析列表的位置**；无损是相对该列表，不能宣称恢复了原程序所有AO/所有打印条目、修复了解析遗漏或验证了raw数值/方向。
- 当前registry确切项为`P.pm7_B.r73.value / registry_id=73 / task=pm7_B / source_path=values.sigma_pi_entries`，shape声明含双端atom/basis/value，unit声明bond-order population，canonical target为PM7|charge0|gas|native_original_PM7|ground_state|sigma_pi_entries，reference_frame仍null。相同source_path的其他task/registry不是本项。registry中的geometry_sources列表不能单独授权把原PM7标签挂到UFF或扰动geometry。

官方[MOPAC PI手册](https://openmopac.net/Manual/pi.html)将该输出描述为把atom–atom interaction分解成σ/π/δ类分量，端点类别与普通s/px/py/pz AO不同，并说明on-diagonal与杂化有关。这个语境支持保留onsite和标签身份；它没有证明本冻结程序版本、实际轴/frame、双端方向/交换或每entry旋转规律，不能据名称直接判不变标量或把字符串视作已恢复AO ordinal。

## 2. 可接受的无损wire内容，以及当前codec的明确缺口

后继**新版本**可以按一个独立entry轴E保存以下语义；名称/物理target ID与schema仍须双方冻结，不能把本表视作已实施API：

| 项 | 最小无损要求 |
| --- | --- |
| 完整owner/field身份 | 精确registry/task/path/component、method/charge/condition、record/molecule、native geometry/source refs、原atom-order及坐标hash；无权威opaque geometry时不造ID |
| src_atom/dst_atom | 原零基端点，int32范围[0,N)，保留原方向并允许same-atom；不得排序、交换或补镜像 |
| src_channel/dst_channel | 两端原UTF-8字符串分别保存；DEL/DELL/DELTA等原token不能凭名称合并。字典编码必须可逆，保留原串映射、版本和SHA；不能用AO_ATOMINDEX代换 |
| entry_ordinal | 0..E−1的已解析列表序号，保原顺序与重复；明确不是原打印列号/AO编号。复合身份还含record/field，不把同序号跨记录合并 |
| value/precision | 保留已有解析数值及来源精度provenance，训练按共同规则一次转换F32。F64容器不证明原程序/打印精度，也不能恢复未保留的token |
| valid/reason/codebook | 按原entry/leaf对齐；source/new/review集合、稀疏leaf exceptions及65535未知具体leaf原因均保留。review与exposure不回写source validity |

同atom对不同通道、乃至同(src,dst,src_channel,dst_channel)重复条目，都先保留原entry ordinal并单列review；不能悄悄平均/求和/去重或改mask。只存原onsite/所选近邻，未输出远距项既不是有效0也不是S负边。

**F64当前也未贯通。** `D/.../export/wire_v1/codec.py:12`的DTYPES是f4/i2/i4/i8/u2/u1，不含f8；`mapping.py:173`又强制target values为小端f4。因此draft4“永久F64值”不能只加entry数组就称现MFM3兼容。须明确永久源F64所在的既有权威源/独立sidecar与训练F32的hash映射，或在后继codec和family schema中同时版本化F64支持；保留旧版本拒绝未知dtype/domain。原F64表示与新F32训练表示都须有实际来源/转换证据。

当前`mapping.validate_pairs:117–127`只接受[p,2] atom pairs并拒重复原子对；directed/allow_self配置不能表达entry channel。`validate_labels:164–169`仍按该pair轴取长度，granular validator最终又调用旧family校验。故需要独立entry-domain的family/schema/索引/数量校验，不是增n_pairs或只改底层数值codec。旧普通atom pair/S bond/Wiberg域不得借此改变。

## 3. 模型必须新增的一条独立消费链

以下是接点责任清单，不是已选定head数学或已经完成的实现。H0仍512维；原sampler、普通pair/head/structural S默认语义不动。

| 接点/现状 | 后继版本最低必要变化 |
| --- | --- |
| `phase1/v3_contract.py:19–21,43–84,162–194`：level仅graph/atom/pair；FieldTarget仅values/valid/pair_index | 独立entry域与typed entry identity/channel输入契约；明确E行标量输出及mask。target_width可仍是每entry一个scalar，但不能只用pair_index替代通道/序号 |
| `v3_wire_provider.py:142–148,257–275`：显式拒basis/r73；只转置atom pairs并按field width造target | 版本化entry decoder，逐entry核owner、atom order、双端channel字典/hash、序号、值和原valid/reasons；未定义/未知channel硬拒，不能改authority字符串或静默丢字段。真实release/VAL/D3仍另验收 |
| `v3_data.py:178–225`：collate拒self，按pair列数计数；`.to/pin_memory`也只搬pair_index | 独立entry collation：两个atom端点只加所在样本atom offset，entry ordinal保留local身份，携带entry→draw/graph映射、两端channel与E行targets/masks。重复同geometry的不同sample draw也不合并；普通pair限制原样保留 |
| `model/v3_heads.py:36–55,106–107,152–160`：pair head无channel输入，采用h_i+h_j和abs(h_i−h_j)，并再拒self | 独立能区分有序两端/通道的预测入口，显式接受aligned atom indices、src/dst channel身份及需要的上下文；每entry输出。现对称PairHead连同atom不同channel的onsite也会得到相同特征，不能直接复用为r73 head。是否具备不变/等变约束须先由物理定义决定 |
| `v3_trainer.PreparedV3Batch:31–52`、model.forward_pretrain及准备路径 | 显式entry输入/output路由、device/pin移动、目标与预测逐entry对齐；provider/resume/paired fingerprint覆盖双端channel、ordinal与entry→draw映射，不只对atom pair做hash |
| `v3_losses.py:35–101`与`observed_rows:169–194` | 原source valid与recipe曝光分离；未知/非法输入拒绝，不把它当缺失跳过。有效标量entry按唯一**ordinal观测**计数，重复源entry各保留一次，不按unique atom pair计、不补镜像双计。无有效entry时count=0且不伪造标签；字段/组均值、D4/condition尺度与是否按channel划分目标必须共同版本化，不能让词典类别数静默改变loss权重 |
| `v3_wire_audit.py`、granular reason sidecar | 保留entry轴的原validity/leaf-shape/field-set+sparse-leaf-v1原因、channel/codebook及source身份。CPU不可变可pickle审计仍不随`.to/pin`上GPU或被训练mask覆盖；review不充当稠密逐叶因果 |

最终有效人口应同时报告stored entries、source-valid entries、exposed valid entries，及按已冻结策略给出的训练/验证分母；普通atom对数量不是r73监督条目数。r73原有一个registry field并不授权模型按channel拆成多个独立字段、做图级pooling或重设family/group权重。D4必须绑定真实TRAIN、condition和该最终域，不能借用PM7别项或P′尺度。

## 4. 明确不能靠机械修改解决的事

仅allow_self：仍丢双端channel、重复identity，且head/collate另有限制。仅放开unique：同atom对不同channel仍无法区分、对称head仍不能表达有序通道。排序/镜像：改变原lower-triangle row/column身份与监督人口，不能从matrix名字推断可交换。去重/平均：改变原观测值与loss权重。附带basis元数据但head不消费：预测看不到必须区分的身份。把r73转普通S bond、填缺0或任意禁用标签：改变任务和原mask，均不接受。

## 5. 真正需要数据线补的证据/共同决定

1. **物理通道与变换**：绑定实际MOPAC程序/版本、输入keywords、原输出section/单位及定义；解释SIGMA/PI/DEL类是怎样相对原子对/坐标系定义、是否以及怎样混合、换端的通道对应、onsite含义与符号/对称性。当前官方手册与字符串parser不能单独给出逐entry的旋转律。没有此定义，不用任意SO(3)合成fixture给invariance验收，更不把它们默认当一组不变scalar或AO编号。
2. **有界真实原始对照**：沿数据线既有witness/source_locator定位原task/owner和实际raw input/output及SHA，逐entry核输出方向、标签、分页/重复、atom order和原value/打印精度。现备忘里的pm7_B r73/r82 locator可用于后续有界CPU读取，不等于本次已读取或已PASS。raw缺失就记UNKNOWN；不重跑QM补证，不用假fixture替代native证据。
3. **域、mask、精度与map版本**：共同冻结有序双端channel domain、重复/序号、F64永久源/F32一次转换、entry leaf/reason轴、实际geometry/view路由、TRAIN/VAL/condition/D4与loss denominator；连raw registry→physical target→source selector→D5 geometry/order→model FieldSpec各层版本/hash。同SHA的另一部署路径不替代实际source refs。

接受方向：后继契约无损保存已解析有序entry，并给模型新独立的通道消费路径。当前结论仍是BASIS_LABELS_UNSUPPORTED_PENDING_DOMAIN_AND_PHYSICS；未共同冻结、未实现新consumer、未完成真实native对照/模型加载验收，不能称基标签已可训练或joint v3.0。所有本轮输入字节、源码行与范围见同名JSON绑定；该JSON只证明本次只读审阅的来源，不证明部署tree、执行或物理成功。
