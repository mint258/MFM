> 当前正式用户设计以 [v3.0合同](training_format_v3_0_user_frozen_design_20261029_v1.md)及其机器政策和五层映射选择为准。1–4已获用户选择，5A限定物理测试和同版本Model签认待实际完成。本文以下保留早期接口历史。

# 训练格式接口契约 v3 草案

状态：DRAFT v3.0-draft.3，2026-10-25。D-1 的候选接口；尚未与模型线共同冻结为 v3.0。候选codec/family LMDB已有合成往返与16个spawn worker关闭验证；真实科学数据导出及模型加载器尚未验收，不能据此宣布 D-3、D-4 或 D-5 完成。

数据线负责人：Codex B。模型线意见保留在文末；双方共同确认后才冻结版本、格式及全部哈希。所有现有 WP5、S′、LMDB、原角色及历史源码保持只读。

## 1. 权威、索引与身份

v1 以 WP5 最终 catalog 的 canonical latest owner、正式 molecule/record population 和已验收 S′数据为输入。不得把历史 attempts 简单合并为新记录；canonical 行按 record_id、molecule_id、attempt/job/task/lane 精确连接。原始 LMDB 是来源，最终 family parquet 为新标签来源，二者不能因同名字段而混用。

每条几何记录必须包含以下元数据。

|字段|类型|语义|
|---|---|---|
|dataset_version|UTF-8 string|定稿后固定为 v1；候选导出另列 release_status|
|contract_version|UTF-8 string|本草案为 v3.0-draft.3|
|export_record_id|UTF-8 string|导出内全局唯一且稳定的几何 ID；其生成规则与碰撞检查在冻结配置中登记|
|molecule_id|UTF-8 string|原权威分子 ID，保留原值|
|conformer_id|UTF-8 string|该几何来源内的构象 ID，不假设 PM7 与 S′ ID 相等|
|geometry_source|enum|pm7 或 uff_sprime|
|source_role|UTF-8 string|原 authority 的角色字面值（包括原 UNASSIGNED 如适用）；原字段原样保留|
|effective_role|enum|本轮最终 TRAIN/VAL/FULL/embargo；VAL按ROUTINE分子来源角色已冻结；共同人群及诊断清单仍待冻结|
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

原人口仅有 TRAIN 与 FULL；routine 是 FULL 内的监控子集。用户已纠正此前整家族留出的信息，明确ROUTINE用作VAL。权威为已绑定的training_inputs_v1/routine.arrow：原11,322条record包含7,610个molecule_id，且是FULL子集。effective VAL以这些分子ID决定，覆盖其全部PM7及S′几何；legacy_routine_member仅保留原record成员。TRAIN原成员保持，FULL未入选的分子保留FULL。来源角色已由job4520334实际闭合并读回18份文件SHA：VAL为7,610分子/72,525条PM7记录，TRAIN为1,206,608分子/11,104,772条，剩余FULL为6,248分子/54,557条。权威为configs/data_v1/export/roles_authority_v1.json；它只冻结来源角色，不代表共同人群、诊断清单或最终训练记录已冻结。不能把原11,322条record数冒充全部VAL几何数。具体对照见 ../data_v1/validation_population_review.md。

## 2. 字段目录与几何上下文

每个可训练字段均由 configs/data_v1/label_registry_v3.json 单独登记；当前已有draft.1元数据登记，但最终family/rho、部分单位/参考系、掩码及归一化仍待定稿。导出器必须拒绝缺少以下元数据的启用字段，不能用默认物理单位或形状填补未知项。

|登记属性|必须明确的内容|
|---|---|
|field_id / source_registry_id / source_path|稳定的导出字段 ID、原 registry ID（不适用时为 null）与精确源路径|
|status / reason|enabled、N/A 或 removed，以及依据|
|group / condition|group只取S、D、P；Pprime是P在UFF几何上的condition，复用P物理定义，不增加第四个总loss组|
|family|D/P 家族 v1；尺寸归类以 TRAIN 的 HeavyAtomCount Spearman 及元素参考规则确定|
|level|molecule、atom 或 pair|
|value_type|scalar、vector 或 symmetric_tensor；source component与物理目标另行映射|
|shape|标量 []；原子 [n_atoms] 或 [n_atoms,3]；矢量 [3]；对标签 [n_pairs]；对称tensor为[3,3]或明确顺序[6]|
|unit|逐字段明确；不得从名称猜测|
|pooling_character|extensive/intensive 及物理定义；不能仅靠相关性替代定义|
|geometry_source|pm7、uff_sprime 或明确的拓扑字段来源|
|coordinate_frame / sign|矢量对应的坐标与符号；无关时为 N/A|
|validity_rule / reason_codes|来源状态、源 mask、有限性、物理范围及一致性规则|
|normalization_ref|本字段 TRAIN-only 统计及其哈希；Pprime 使用独立统计|

当前审计中的146项是非空且非常数的统计分量口径，不直接等于146个预测头。真实分子级非空标量为43P＋26D，另有逐原子 SASA，合计27个D字段；这与指南42P＋27D分子标量的文字口径有差异，须按原登记字段逐项说明，不更改原标签凑数。63个按正式任务范围预期全缺失的原字段列为 N/A，10个常量壳层分量移除；原科学存储仍保留。

物理目标映射独立于统计行：每个target显式给出target_id、group、condition、family、unit、level/kind、geometry_source及精确members（field_key/source_path/registry_id/component）。偶极xyz必须组合为一个矢量；r674的xx,xy,yy,xz,yz,zz保留为一个对称二阶tensor目标，不自行丢弃无迹约束下的第六个存储分量。source_shape与export_shape必须区分；例如r52.x的源[3]描述不能让一个分量再次展开三次。尚未共同决定的head/loss单位不按146行自动推断。

逐分子group_exposure_mask和family_exposure_mask独立于逐字段有效mask；关闭组/家族与源标签无效必须分开记录。新实现wire_v1/mapping.py默认最终预检拒绝draft登记、未验证单位/参考系或未定稿family；候选模式不能升级为可训练状态。
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

r674二阶tensor的源顺序为xx,xy,yy,xz,yz,zz，单位e bohr^2。候选编码可按该六分量保存，或无损重建对称3×3。坐标原点、实际无迹定义及Q_rot=R Q R^T验收仍为PENDING；不会用普通不变标量头的六项输出冒充tensor等变性。

矢量/tensor归一化必须与输出对称性共同确认：逐轴非零均值或不同缩放一般不与旋转可交换。保留逐component审计统计，同时共同确定物理目标的尺度、中心化和Huber聚合方式；不能默认逐component统计就是物理头/loss单位。实际模型反馈与科学验证前不选定此算法。
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
- header为规范JSON，保存format/version、身份元数据、payload SHA256及各数组的name/dtype/shape/offset/nbytes；拒绝重复键、非规范编码及损坏校验；
- payload由C-contiguous、明确little-endian数组构成；float32=<f4、int16=<i2、int32=<i4、int64=<i8、原因码uint16=<u2、布尔以|u1存0或1；int8源值可无损升为int16；
- scalar形状为[]；所有offset相对payload开始；解码器必须检查负值、溢出、重叠、长度和dtype白名单，拒绝object dtype；
- 每个family LMDB使用records named DB保存UTF-8 export_record_id键、dupsort molecule_index保存分子到记录索引；labels另有独立masks named DB。值和mask同事务提交，metadata主库保存__schema__、__len__、__molecules__及WRITING/COMPLETE状态；样本键不得使用保留前缀；
- family字段顺序由schema冻结；一条记录只包含声明的字段，未知字段/缺少必需字段须显式失败。

候选实现位于workflows/data_v1_final/export/wire_v1/，已经过合成损坏payload/shape/pair/mask/float32一次转换、family LMDB事务与分子索引，以及16个spawn worker实际读回和退出验证。它尚未与模型线共同决定采用，也没有真实D3/全量科学记录读回或训练吞吐证据；完整freeze仍需模型加载器的实际验收。

mask与reason独立于标签数值。每个标量/原子/对/矢量/tensor分量保存bool有效性及uint16原因码，原因码字典版本化。缺失或不合法数值不得伪装为有效0；训练加载器仅凭mask选择有效标签。缩尾只用于TRAIN统计，源训练标签保持原单位、未经缩尾。未知收敛标记不直接等同于已证实不收敛。

## 7. 版本、哈希与验收

每个release至少绑定：契约版本、registry版本、mask规则、归一化、分子/构象清单、角色及去污染来源、原科学配方/版本、生成代码commit与各文件SHA256。大文件留外部，仓库只保存小型引用与清单。原 SOURCE_MANIFEST 不回写为新版本。

D-3验收需真实50k+5k试点导出，与manifest一致的计数、1万条随机源值对照（仅float32转换误差）、多worker读取、文件SHA及实际峰值空间。D-6须等待模型线确认试点加载成功，再全量导出；分发前检查每个GPU节点/tmp容量，分发后逐文件哈希。读取吞吐是CPU数据加载测试，不占GPU。

D-4只拟合最终有效TRAIN：元素参考仅能量字段；按0.1/99.9百分位缩尾计算均值/标准差而不改标签；逐元素原子统计与Pprime独立统计全部保存。VAL/FULL/embargo/诊断heldout几何不参与拟合。元素参考、异常阈值、随机子集均绑定最终角色清单。

## 模型线意见

待模型线填入。尚未确认：wire编码、registry字段及形状清单、矢量参考系的实际验收、最终共同人群及诊断几何清单（ROUTINE来源角色已闭合）、N=1/N=2与诊断后可训练构象数、固定随机seed、release/shard大小和加载器调用。存在意见冲突时按指南报告用户。双方共同定稿前保持DRAFT，不宣传v3.0或真实数据已可训练。

### 2026-10-25 Codex A：draft.3 审阅意见（未共同冻结）

2026-10-25。模型线已只读审阅 draft.3、draft registry 及候选 wire/projection/granular 实现。当前仅完成接口审阅，未共同签为 v3.0，未宣称真实 D3–D6 交付或模型加载已验收。

1. 数据侧已支持 r674 的 xx,xy,yy,xz,yz,zz 六分量、symmetric6/对称3×3、完整分量 mask。模型目前仅支持 scalar/vector/magnitude，tensor head/loss/normalization 尚无实现；不得静拆六个不变标量或删第六分量。原点、无迹定义、frame 验收与消费算法须共同确认，本次不作物理算法决定。
2. 数据侧 D5 已按来源 anti-join 诊断 base/child，并重排 training_rank。模型同意最小桥接采用独立 PM7/UFF entries/index，minimum_energy_conformer_id 取保留集 energy training_rank=0，不取原 rank=0；opaque geometry_id 作模型 locator，原 native IDs 侧存。mixed 每分子显式选一个来源，不能拼接或假造跨来源构象对应。N=1/N=2、诊断后剩余数及 k 不足策略仍需冻结。
3. 同意精确 leaf validity 与原因粒度分开：provider/sidecar 需保留 field-set+sparse-leaf-v1、source/new/review 原因、codebook/hash 与 unresolved=65535 的原含义；review 和 exposure 不改源 validity/reasons。vector 训练采用声明的 all_components mask，原 component mask/reasons 仍可审计。请在契约 mask 段明确该规范，不能声称每叶都有完整稠密因果。
4. 真实 MFM3→模型 provider 尚未完成或验收；需绑定 registry/目标成员、单位/家族、角色/D4/D5、geometry/atom order、schema/codebook/shard SHA，并明确 Z−1、molecule→graph、shape、各字段 pair transpose/offset、来源名及原生 S bond transport。候选 fixture 只能显式 opt-in，不能通过标 data_line authority 放行草案。
5. r623/r624/r625 的已登记标签属于实际扰动 geometry；当前模型 PD 只读 clean H0，S geom 是另一个本地 RNG 噪声。请明确 target→实际 view/parent/坐标/hash 的 wire 定位、排除和计数，之后实现对应 H0 路由；不能把扰动标签挂 base 坐标或替换为任意 S 噪声。
6. r73 source 保留 basis_i/basis_j，当前普通 [i,j] pair/head 未表达该身份；请明确 lossless basis 粒度/索引/物理目标，不由模型去重、合并或求和。已有 source_v2 的逐字段动态 n_pairs 不代替 basis 身份。r82 数据侧已有显式 atom_indices scatter 与缺失原因闸门；仍需共同绑定具体 selector、索引基数及 codebook，然后验收全原子 wire→模型消费，未观察行 invalid 并保留原因。不得贴前 n_heavy 行或补有效零，模型不另行猜测并重做 scatter。相关单位仍按最终科学登记确认。
7. Pprime 保持 P 组并采用对应 UFF 条件及独立 D4。当前 normalizer 以 model field name 索引；单来源 runner 可明确绑定一套相应统计，同批混合条件需要显式条件路由，不能自动沿用 PM7 统计。

独立可先推进的 synthetic 工作：单来源 typed sampling bridge、保留审计引用的 provider fixture，以及既有 DecodedSample/collate 的旧原生 S bond transport。后者只保留已定义 rdkit_bond_* 属性与旧 raw/count/梯度，不涉及决定 D1 新 bond codebook。完整行号、来源 SHA 与测试建议见 `runs/model_v3_20261025/interface_draft3_model_review_v1/review.md`；最终共同冻结前维持 DRAFT。
