# D2 全分量尺寸相关与单位语义提案 v1

状态：**待 Root 审阅，未执行新的科学 size pass，未冻结 registry**。旧 streaming/normalization/注册表/配置及其实际结果不改。本提案不把 source-TRAIN 标量ρ、D4分量统计或合成旋转测试当成非标量真实ρ。

## 146分量与129个物理统计target的闭合映射

| 源层级 | 登记分量数 | 本提案的物理统计target数 | 主标量 |
| --- | --- | --- | --- |
| molecule | 69（43P+26D） | 69 | 原标量；5个真正heat_of_formation字段改用各自TRAIN元素参考残差 |
| molecule_vector | 18 | 6 | 同一registry/task的xyz共同L2 norm |
| molecule_tensor | 6 | 1 | 对称三维tensor的Frobenius norm |
| atom_vector | 3 | 3 | 全N原子的向量norm的RMS |
| atom | 39 | 39 | 20项有明确原子贡献语义用sum；其余19项用RMS |
| sparse_atom_pair | 11 | 11 | ENPART的7项用stored-pair signed sum；其余4项用stored-entry RMS |
| 合计 |146|129|每个源field_key均映射，不以target数猜模型head数|

`build_proposal.py` 从SHA固定的585411B registry元数据生成全146行JSON和Markdown：逐行包含原单位/shape/性质、建议聚合、physical target、单位审查状态、所有待冻结项和显式空rho。它检查上述分层计数、146组件、129 target，任何漏分支均失败。另保留103 N/A、10常量删除和5 legacy ESP的计数；这些不冒充新enabled target。

## 主聚合的科学定义

对每条 canonical geometry/record，先使用已固定mask；只将该物理target变为一个分子级数值，**不把原子、原子对、xyz、tensor数组下标当成独立分子观测**。

- 分子标量：保持原值和符号。heat_of_formation_kcal_mol（pm7_B60、anion204、cation273、octanol340、water407）必须先用相同fit人群的TRAIN元素计数线性参考产生残差；五个method/charge/solvent context独立拟合、报告basis/rank/rcond/coeff/intercept/有效数，不合并。HOF_difference是另一个溶剂差值target，不冒充上述绝对HOF。其它能量可额外报告元素残差敏感性，但不得悄悄取代主定义。
- 分子偶极：`hypot(x,y,z)`，必须三分量共同有效，同一task、同一记录、同一原子/坐标来源。一个normρ回填到三个成员的size-rule出处，成员保留各自组件统计。带电体系的偶极norm仍依赖原点；这里只保证对同原点的正交旋转不变，不宣称平移不变或输入输出轴实证已闭合。
- 分子quadrupole：源顺序xx,xy,yy,xz,yz,zz；`sqrt(xx²+yy²+zz²+2(xy²+xz²+yz²))`，六分量共同有效。直接六个打印数的普通L2不等于对称tensor的Frobenius norm，不能采用。原点/实际traceless convention及source frame另待科学实证。
- 三个原子向量target（PM7 gradient、xTB force、xTB gradient）：`sqrt(sum_i |v_i|²/N)`，要求整个语义N×3目标完整有效，不从部分xyz拼向量。此选择测局部典型幅度；全3N的L2作为带明确sqrt(N)尺度因子的敏感性一起报告。两个操作都对每个原子共同施加的正交旋转不变，不能自动据此决定模型逐轴归一化。
- 39项原子标量中，用signed sum的20项：五种PM7 context各s/p/d shell population共15项、ENPART one-center的3项、FOD_atom_e、SASA_atom_A2。它们本身有“贡献到一个整体”的语义；FOD/SASA可与独立存储的整体项做覆盖/和的审计，不能把自推和冒充独立来源证明。
- 其余19项原子标量用`RMS=sqrt(mean(v_i²))`：7个charge项、6个Fukui项、SUPER三列、D4原子C6/alpha、valences。正负电荷求和接近固定总电荷、Fukui求和接近归一常数，故这些和不适合作唯一尺寸标量。signed mean和sum_abs只作为敏感性。RMS本身也可能因归一约束与N相关；因此ρ与物理广延性必须分开记录。
- SUPER只拥有源中明确打印的heavy atom rows；atom_index必须与实际原子序、Z>1和范围一致，并核唯一、完整heavy集合。其它atom标量按源定义拥有的全部N原子，不默默改成只heavy atoms。跨记录比较的x始终是该分子的完整重原子数。
- ENPART七个pair分量：按明确的源pair key一次计数，signed sum保留正负；其余bond_orders、Wiberg、Mulliken overlap、sigma/pi使用stored-entry RMS。这里定义的是**实际保留的稀疏表示**，不能补成N²全矩阵、把未计算/未打印pair当0，也不对source列表擅自去重。原子pair通常使用(i,j)，sigma/pi必须含atom与basis完整键。需先核源的unordered/directed/cutoff约定，发现重复或冲突就将该记录的聚合标为未定义并报告，不更改原label mask。

sigma/pi特别保留一个未闭合项：打印的orbital/basis子块可能依赖AO表示与阈值选择，stored-entry RMS对行重排不变，**尚不能据此声称对任意轨道基旋转严格不变**。如果源审查不能证明完整、协变的轨道子空间，需Root/模型线决定改用完整块Frobenius/trace等新目标，或将其size分类保留“未证”状态；不能拿数组排列不变冒充物理旋转不变。

## mask、零、构象权重与并列

主array聚合要求所有语义拥有的数值条目都有效；一个partial field不能因“只剩下有限值”而悄悄改变分子定义。可另给valid-row聚合＋coverage fraction的敏感性，并按heavy count分层报告缺失/partial比例。它只是rho fit eligibility，**不新增label mask、不删记录、不改变>1%新mask硬停规则**。

有限的0是观测，-0与+0在排名中合并；不取对数、不丢0、不因z>20剔除、不缩尾。NULL、ABSENT、EMPTY、shape错误、全False与partial均显式分别计数。现冻结解码器把空稀疏列表标为缺失，不能为本ρ任务改成结构零；只有独立获批的新source语义证明“完整空集合”时才能另定义数学空和。

主ρ沿现有标量pass口径：每个有效canonical record/geometry一票，x=完整heavy_atoms，y=该geometry的分子标量；不重复历史attempt、不按leaf数或pair条数加权。多个构象会让分子按有效构象数多次出现，此事实明确报告。另给“每分子取有效构象y的中位数后每分子一票”的敏感性；它不能与原标量ρ混为同一结果或不经审阅取代主结果。

Spearman为有效交集上平均tie ranks的Pearson相关，完整保留整数heavy count并列；q无缩尾。少于2对、heavy count全常量或聚合全常量时rho=NULL并分原因，不强填0。每target报告n_records、n_molecules、有效构象数分布、missingness-by-size、tie数量和主/敏感性ρ。family阈值按未四舍五入的`abs(rho)>=0.95`；size family标记不改物理extensivity或local head。

最终D2与最终D4采用相同冻结common/effective TRAIN/精确diagnostic排除人口；HOF参考fit与rho必须同scope同mask hash。该人口尚未齐时，可以在原source TRAIN做标明provisional的试点以验实现/预算，不能据之冻结最终family。P′需要自己的真实UFF源、mask、元素参考和ρ；缺P′不复用P。

## 单位、性质与实际生成链

已读取并绑定：WP5 `configs/protocol.json`、`wp5_engine_v2.py`、冻结 `c_engineering_wire.py`，以及与SOURCE_MANIFEST匹配的旧 `rdkit_descriptor_generator.py`。重要区别是：WIRE.corrected_base从原31槽graph descriptor按索引clone，**仅NumHAcceptors重算**；D3另在原PM7几何上调用RDKit（PMI带atomic masses、PBF、0.2Å volume grid、1.4Å probe Lee–Richards SASA）。因此19个旧D20的原始RDKit生成runtime，需要原LMDB build receipt；WP5运行时和2026-10-23扫描时版本都不能替代它。当前发现的旧生成源码明确调用Crippen.MolMR、MolSurf.TPSA/LabuteASA等，但源码存在及其SHA也不单独证明某版曾实际生成全部旧值。

| 项目 | 已有权威依据 | 提案/待闭合 |
| --- | --- | --- |
| MolMR | [RDKit API](https://rdkit.org/docs/source/rdkit.Chem.Crippen.html)及[Wildman–Crippen原论文](https://pubs.acs.org/doi/10.1021/ci990307l)确定是原子贡献MR估计；[版本固定源码](https://raw.githubusercontent.com/rdkit/rdkit/Release_2025_09_5/Code/GraphMol/Descriptors/Crippen.cpp)是对原子MR贡献求和 | [IUPAC Green Book p37](https://iupac.org/wp-content/uploads/2019/05/IUPAC-GB3-2012-2ndPrinting-PDFsearchable.pdf)确定其物理量纲为体积/物质的量（SI m³/mol）；常见cm³/mol数值习惯仍需原参数/生成链scale证据，不能仅从molar一词填最终数值单位。原source_unit保留“未声明”，cm³/mol只作候选，未换算原值。 |
| MolMR性质 | RDKit实现原子贡献相加；原论文同时说明这些性质本身并非严格加性 | 采用“分子级原子加和估计器”；区分bulk molar量与模型按原子pooling，不能只写一个无上下文extensive。 |
| MolLogP | 同RDKit API；分配系数的对数；实现采用加和估计 | dimensionless/intensive-like分配量，不能因估计器求和就定义为热力学广延量。 |
| HallKierAlpha | [版本固定GraphDescriptors源码](https://raw.githubusercontent.com/rdkit/rdkit/Release_2025_09_5/rdkit/Chem/GraphDescriptors.py)的原子修正累加，后接C++CalcHallKierAlpha | dimensionless atom-additive correction；旧registry默认intensive应审阅修正，不根据ρ猜物理定义。 |
| BertzCT | 同GraphDescriptors源码含连接/原子种类信息熵与count/log(count)因子 | dimensionless、非加性图信息指数；旧默认intensive不充分，应保留descriptor专类。 |
| TPSA | [RDKit Book](https://www.rdkit.org/docs/RDKit_Book.html)说明默认N/O，S/P可选；旧调用未显式includeSandP | source A²保留；实际原版默认行为和旧值仍需runtime lineage；不是UFF表面积。 |
| LabuteASA | [RDKit MolSurf](https://rdkit.org/docs/source/rdkit.Chem.MolSurf.html)指向Labute近似面积方法；旧调用无额外参数 | A²、2D图估计面积；不能与独立3D SASA条件混作相同量。 |
| PMI/PBF | [RDKit 3D API](https://rdkit.org/docs/source/rdkit.Chem.Descriptors3D.html)及冻结WIRE原子mass/Å坐标调用 | PMI质量×长度²；PBF长度。几何量有自己的缩放律，不强制落入简单sum/mean二选一。 |
| Fukui | 冻结protocol.units写dimensionless，现registry写e；Coulson/原子电荷差的源码值需明确ΔN convention | 必须协调“无量纲有限电子数响应”与“electron/charge difference数值”标注；原值、原单位不回写，不做未经证明换算。 |
| SUPER Dn/De | [MOPAC v23.0.3源码](https://raw.githubusercontent.com/openmopac/mopac/v23.0.3/src/output/superd.F90)与既有compound semantics由轨道系数平方/轨道eV量纲推得1/eV | 维度推导证据保持独立标签，不冒称源文件显式声明；D1需接受推导与原始列语义。 |
| bond-order/population | 冻结protocol对WBO/bond order使用dimensionless；旧registry使用bond-order population等语义单位 | 候选统一数值单位1并保留电子人口/键级语义，需要逐来源对齐；不因为名称接近就把Mulliken charge/overlap/Fukui互换。 |

现有单位能在物理层面支持怎样的pooling，与最终size family的ρ判据分开。几何面积/体积、质量几何二阶矩、local目标、多极矩、图信息指数均有明确类别，不再用“所有未命中的字段=intensive”兜底。全146行输出保存原tag和新建议，并逐项列其未冻原因。

进一步已找到真实C4运行receipt：`runs/phase1_screening_20261011/c_engineering/storage/storage_report.json`，694878B/SHA `6e4a1260f9df31611d7c00b801ce3309a52feee93821eba5b59131efb909f12c`，status C4_CANDIDATE_SAMPLE_STORAGE_ANALYSIS_CLOSED，job4513557/node11、10020记录、16实际PID；wire_schema.rdkit_version=2025.09.5。该同一receipt明确remaining_D19保留原scalar bits。因此这闭合了C4当次调用环境的观察，仍不证明19项原生成版本，也不自动等于全部后续WP5 invocation的runtime。旧generator及build_lmdb源码未见写入rdkitVersion字段，实际旧build环境receipt仍缺。

同一旧generator的 `_compute_graph_descriptors` 明确将RDKit结果放入torch.float32，WIRE克隆其dtype，WP5再提升为float64。现有代码链提示D19可能是保留float32有效精度的float64容器，不能据永久dtype声称新双精度重算；具体旧构建/实际dtype provenance保留待证。排名保留源中真实ties，不jitter或借新版本重算替换。另已核[2025.09.5实际C++ HallKierAlpha](https://raw.githubusercontent.com/rdkit/rdkit/Release_2025_09_5/Code/GraphMol/Descriptors/ConnectivityDescriptors.cpp)：`calcHallKierAlpha`逐原子累加类型修正/半径比修正，支持上面对该类的定义性修订建议。

元数据适配入口（不读科学label正文、不计算ρ；只核固定小源与穷尽映射）：

```
python -B workflows/data_v1_final/labels/size_semantics_v1/build_proposal.py \
  --config configs/data_v1/labels/size_semantics_proposal_v1.json \
  --output-root /external/new_size_semantics_metadata_proposal
```

输出component_proposal.json、全146行component_pending_freeze.md和metadata_receipt.json（输出逐文件SHA）。Root在compute20执行；代码与元数据检查由Root统一安排，不以静态检查替代真实科学ρ。

## Root审阅后拟实施的新pass（尚未实现/提交）

只在新variant目录消费已SHA固定canonical owner/atom order/compact masks与明确scope；旧pass不变。先16 source groups/512完整分子，16真实worker、analysis/node20、64GiB、2h、8GiB unique inode输出cap，源文件与HOF model/参考人口均绑定新Root intent。源读取只做一次聚合，再按(value,heavy_count)聚合计数并以外存排序计算精确tie ranks；不保存正常逐叶标签。每分子敏感性使用同owner组全部构象，输出有限分子标量统计scratch并计入预算。与原标量69项做相同scope/同mask读回比较；HOF在没有闭合参考时只能pending。

必要少量增量fixture：非平凡正交旋转下dipole/tensor/全N×3梯度聚合不变；六打印分量朴素norm的负例；原子/pair重排不变；component partial→聚合missing且不新mask；zero/ties/常量/empty区分；含负电荷的RMS与signed mean定义；HOF TRAIN-only参考与VAL泄漏负例；record与molecule权重不同的显式对照；完整146→129映射。合成测试只证明代码性质，不证明真实QM输出frame已验收。

本提案建议Root先确定：local target的RMS/sum选择、record-weighted主口径、最终共同人群scope，以及sigma/pi的表示依赖如何处理。获得明确结论后再实现新pass；不存在自动修改旧算法或冻结family的动作。
