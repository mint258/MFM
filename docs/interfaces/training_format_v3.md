# 训练格式接口契约 v3 草案

状态：DRAFT v3.0-draft.2，2026-10-25。D-1 的候选接口；尚未与模型线共同冻结为 v3.0。本文提出的二进制格式尚未有真实导出/加载器验收，不能据此宣布 D-3、D-4 或 D-5 完成。

数据线负责人：Codex B。模型线意见保留在文末；双方共同确认后才冻结版本、格式及全部哈希。所有现有 WP5、S′、LMDB、原角色及历史源码保持只读。

## 1. 权威、索引与身份

v1 以 WP5 最终 catalog 的 canonical latest owner、正式 molecule/record population 和已验收 S′数据为输入。不得把历史 attempts 简单合并为新记录；canonical 行按 record_id、molecule_id、attempt/job/task/lane 精确连接。原始 LMDB 是来源，最终 family parquet 为新标签来源，二者不能因同名字段而混用。

每条几何记录必须包含以下元数据。

|字段|类型|语义|
|---|---|---|
|dataset_version|UTF-8 string|定稿后固定为 v1；候选导出另列 release_status|
|contract_version|UTF-8 string|本草案为 v3.0-draft.2|
|export_record_id|UTF-8 string|导出内全局唯一且稳定的几何 ID；其生成规则与碰撞检查在冻结配置中登记|
|molecule_id|UTF-8 string|原权威分子 ID，保留原值|
|conformer_id|UTF-8 string|该几何来源内的构象 ID，不假设 PM7 与 S′ ID 相等|
|geometry_source|enum|pm7 或 uff_sprime|
|source_role|UTF-8 string|原 authority 的角色字面值（包括原 UNASSIGNED 如适用）；原字段原样保留|
|effective_role|enum|本轮最终 TRAIN/VAL/FULL/embargo；VAL以用户指定的ROUTINE分子成员定义，清单待实际冻结|
|legacy_routine_member|bool/null|原11,322个PM7 record的ROUTINE成员标记；UFF记录为null，不用它取代分子角色|
|legacy_routine_molecule|bool|molecule_id是否属于ROUTINE的7,610个分子|
|common_population_v1|bool|PM7完整且S′数量满足冻结规则的共同人群成员|
|common_population_manifest_sha256|hex string|共同人群清单身份|
|native_record_id|UTF-8 string/null|原 PM7 record_id；S′另保存其 source_record_id 对应|
|native_shard_path / native_real_index|UTF-8 string/int64/null|原只读 LMDB 的定位，路径不作为化学身份|
|source_payload_sha256|hex string/null|原 LMDB payload 身份|
|wp5_owner|structured map/null|attempt_id、job_id、task_id、lane 及 catalog/receipt 引用|
|sprime_conf_idx|int64/null|UFF 来源的原生成索引|
|native_atom_order_sha256|hex string|所存坐标对应的原子序|
|geometry_float64_sha256|hex string|源永久精度几何的规范字节摘要；规范化方式冻结后写入 schema|
|source_references|structured list|parquet 文件哈希、row group/行定位及源字段/registry 路径|

原人口仅有 TRAIN 与 FULL；routine 是 FULL 内的监控子集。用户已纠正此前整家族留出的信息，明确ROUTINE用作VAL。权威为已绑定的training_inputs_v1/routine.arrow：原11,322条record包含7,610个molecule_id，且是FULL子集。effective VAL以这些分子ID决定，覆盖其全部PM7及S′几何；legacy_routine_member仅保留原record成员。TRAIN原成员保持，FULL未入选的分子保留FULL。角色清单须由freeze_routine_roles.py实际生成并验收后使用，不能把原11,322条record数冒充扩展后全部VAL几何数。具体对照见 ../data_v1/validation_population_review.md。

## 2. 字段目录与几何上下文

每个可训练字段均由 configs/data_v1/label_registry_v3.json 单独登记；该完整文件尚待 SB-3 产出并审阅。导出器必须拒绝缺少以下元数据的启用字段，不能用默认物理单位或形状填补未知项。

|登记属性|必须明确的内容|
|---|---|
|field_id / source_registry_id / source_path|稳定的导出字段 ID、原 registry ID（不适用时为 null）与精确源路径|
|status / reason|enabled、N/A 或 removed，以及依据|
|group|S、D、P 或 Pprime；Pprime 复用 P 的物理定义并指定 UFF 几何|
|family|D/P 家族 v1；尺寸归类以 TRAIN 的 HeavyAtomCount Spearman 及元素参考规则确定|
|level|molecule、atom 或 pair|
|value_type|scalar、vector 或 component|
|shape|标量 []；原子 [n_atoms] 或 [n_atoms,3]；矢量 [3]；对标签 [n_pairs] 或登记的分量数|
|unit|逐字段明确；不得从名称猜测|
|pooling_character|extensive/intensive 及物理定义；不能仅靠相关性替代定义|
|geometry_source|pm7、uff_sprime 或明确的拓扑字段来源|
|coordinate_frame / sign|矢量对应的坐标与符号；无关时为 N/A|
|validity_rule / reason_codes|来源状态、源 mask、有限性、物理范围及一致性规则|
|normalization_ref|本字段 TRAIN-only 统计及其哈希；Pprime 使用独立统计|

当前审计中的146项是非空且非常数的统计分量口径，不直接等于146个预测头。真实分子级非空标量为43P＋26D，另有逐原子 SASA，合计27个D字段；这与指南42P＋27D分子标量的文字口径有差异，须按原登记字段逐项说明，不更改原标签凑数。63个按正式任务范围预期全缺失的原字段列为 N/A，10个常量壳层分量移除；原科学存储仍保留。

S 结构字段至少包括 atomic_numbers、positions_A、bond_pairs、bond_order_codes。D 包含 D20、D3 及按冻结登记启用的原子字段。P/Pprime 的物理字段严格绑定相应计算任务、电荷、溶剂和几何，不将同名异上下文值合并。

## 3. 矢量、坐标与符号

所存坐标为 Å；原子序与该条记录的 atomic_numbers 完全一致。不得为导出悄然重新对齐、旋转、镜像或 canonicalize 原子顺序。若以后需要刚体变换，必须同变换坐标与所有矢量并升级契约。

已核对的源布局如下；仍需受控读回证明输出轴与输入坐标轴一致，不能仅凭形状/元素次序宣称这一验收已通过。

|物理量|源布局与单位|候选导出布局|
|---|---|---|
|PM7/xTB 偶极矩|float64[3]，Debye；是xyz矢量，不是模长|float32[3]，保留单位与方法上下文|
|PM7 AUX 梯度|可能是扁平 [3*n_atoms]，kcal mol^-1 Å^-1|经可验证的连续xyz reshape 为 [n_atoms,3]，不换轴|
|xTB 扰动梯度|[n_atoms,3]，Eh/bohr；dE/dR|float32[n_atoms,3]，保留源单位|
|xTB 力|[n_atoms,3]，eV/Å|force = -gradient × EH_TO_EV / BOHR_TO_A；常数值与原 WP5 来源绑定|

扰动梯度必须引用对应的实际扰动几何，而不是无扰动 PM7/UFF 坐标。每种 off-equilibrium 视图保存 parent geometry ID、扰动 seed/协议、实际坐标及其摘要；Pprime 扰动遵从同一 WP5 协议。偶极模长如被启用，必须为独立登记字段并与其来源矢量做一致性检查，不能用模长覆盖矢量。

## 4. 原子序与原子对

atomic_numbers 为 int16[n_atoms]，表示真实 Z；模型需要 Z−1 时由模型加载器按公开规则生成。positions_A 为 float32[n_atoms,3]。源 float64 坐标与 float32 目标的差异只允许来自一次转换，另存 float64 源摘要。

bond_pairs 与其他 pair 索引均为 int32[n_pairs,2]、零基、引用同一几何的原子行。每个字段声明有向/无向及是否含对角；无向键候选使用 i<j，并保存对应 order code。不得把一个字段的 pairs 用于解释另一个字段的数值，也不靠排序猜测缺失原子映射。导出需检查索引范围、重复与 values/pairs 长度；异常显式失败或逐标签掩码，不能静默更改源图。

原子数组或对数组的数值、有效掩码和原因数组必须具有相同索引基准。向量有效性以登记规则决定；完整向量监督不得把缺失xyz分量补零后当作有效。

## 5. 构象顺序、去重与子集

每个分子、每个 geometry_source 分别保存 random_rank、energy_rank、diversity_rank，以及稳定的 conformer_id 列表。rank 从0开始，列表必须是该来源可用构象集合的置换。能量顺序为 PM7 HOF 或 UFF 能量升序，稳定 tie-break 按原构象 ID；多样性从最低能构象开始，随后最大最小 RMSD。

固定随机顺序的 seed、哈希算法、排序规则与实现版本须在冻结配置中给出；本草案不借临时 seed 冒充已冻结规则。其前k个构成构象网格默认嵌套顺序。S′重原子固定映射的 proper Kabsch RMSD沿用原0.5 Å；保存 below_dedup_threshold、重复/补入标记及最小已选 RMSD。补入标记不能覆盖原失败或不收敛状态。

分子级子集为120k⊂240k⊂600k⊂全部有效TRAIN，固定seed均匀随机。试点50k TRAIN来自120k子集，另加5k VAL。ROUTINE指定的全部VAL分子在这些TRAIN子集与归一化拟合之前排除；整家族新划分不再执行。

诊断集固定20k TRAIN分子，PM7与S′均至少两个构象，各来源固定随机顺序的最后一个为 held-out conformer。该几何从所有训练清单（包括P/Pprime条件）排除；molecule_id 仍属于TRAIN。这是指南明确的同分子跨侧例外，仅诊断预训练损失，不用于模型选择。N=1、恰好N=2及诊断后剩余构象不足的处理须随构象清单明确，不复制同一几何凑数量。

Pprime 计算清单按S′顺序前两个构象冻结；计算清单、训练清单及诊断清单分别保存，不能因已有标签就重新纳入诊断几何训练。

## 6. 存储候选格式：分家族 LMDB，禁止 pickle

永久family parquet继续float64；训练导出数值为float32。所有LMDB是新建产物，存放仓库外，与原LMDB物理路径分开。候选目录：

~~~
release/
  manifest.json
  schema.json
  geometry/pm7/
  geometry/uff_sprime/
  labels/pm7/<family>/
  labels/uff_sprime/<family>/
  masks/pm7/<family>/
  masks/uff_sprime/<family>/
  indices/
  conformer_orders/
~~~

每个叶目录可以含多个确定编号的LMDB shard。manifest声明每个shard的范围、record/molecule/conformer计数、文件字节数、SHA256及schema/registry/normalization/population引用。几何记录通过 export_record_id 连接；分子级拓扑标签可保存一次并由 molecule_id 引用，必须显式声明，不能让加载器猜测记录粒度。

候选value编码使用“固定magic＋长度明确的UTF-8 JSON header＋连续数组raw bytes”，无Python对象序列化、pickle或可执行扩展：

- magic为4字节 ASCII MFM3，随后4字节 little-endian unsigned header长度；
- header为规范JSON，保存身份元数据及各数组的name/dtype/shape/offset/nbytes；
- payload由C-contiguous、明确little-endian数组构成；float32=<f4、int16=<i2、int32=<i4、int64=<i8、布尔以|u1存0或1；
- scalar形状为[]；所有offset相对payload开始；解码器必须检查负值、溢出、重叠、长度和dtype白名单，拒绝object dtype；
- LMDB key为UTF-8 export_record_id；保留__schema__、__len__等明确列出的metadata key，普通样本key不得使用保留前缀；
- family字段顺序由schema冻结；一条记录只包含声明的字段，未知字段/缺少必需字段须显式失败。

以上是供模型线审阅的候选wire，尚未实测决定采用。最终冻结前需双方加载器读写往返、随机读取和多worker退出验收；不把草案示例当真实训练产物。

mask与reason独立于标签数值。每个标量/原子/对分量保存bool有效性及uint16原因码，原因码字典版本化。缺失或不合法数值不得伪装为有效0；训练加载器仅凭mask选择有效标签。缩尾只用于TRAIN统计，源训练标签保持原单位、未经缩尾。未知收敛标记不直接等同于已证实不收敛。

## 7. 版本、哈希与验收

每个release至少绑定：契约版本、registry版本、mask规则、归一化、分子/构象清单、角色及去污染来源、原科学配方/版本、生成代码commit与各文件SHA256。大文件留外部，仓库只保存小型引用与清单。原 SOURCE_MANIFEST 不回写为新版本。

D-3验收需真实50k+5k试点导出，与manifest一致的计数、1万条随机源值对照（仅float32转换误差）、多worker读取、文件SHA及实际峰值空间。D-6须等待模型线确认试点加载成功，再全量导出；分发前检查每个GPU节点/tmp容量，分发后逐文件哈希。读取吞吐是CPU数据加载测试，不占GPU。

D-4只拟合最终有效TRAIN：元素参考仅能量字段；按0.1/99.9百分位缩尾计算均值/标准差而不改标签；逐元素原子统计与Pprime独立统计全部保存。VAL/FULL/embargo/诊断heldout几何不参与拟合。元素参考、异常阈值、随机子集均绑定最终角色清单。

## 模型线意见

待模型线填入。尚未确认：wire编码、registry字段及形状清单、矢量参考系的实际验收、ROUTINE分子VAL角色清单、N=1/N=2与诊断后可训练构象数、固定随机seed、release/shard大小和加载器调用。存在意见冲突时按指南报告用户。双方共同定稿前保持DRAFT，不宣传v3.0或真实数据已可训练。
