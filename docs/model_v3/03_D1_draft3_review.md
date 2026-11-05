# D-1 draft.3 模型侧只读审阅 v1

日期：2026-10-25（Asia/Shanghai）。审阅者：模型线 SA-2，Root 统一协调。
状态：**草案接口审阅完成；未共同冻结 v3.0；真实 wire/provider 未验收**。
本目录仅新增审阅文件；没有修改数据线或模型生产源码，没有运行测试、科学计算、训练或 Git 提交。

本次审阅确认：数据侧已有 tensor 六分量编码、按来源 D5 顺序/诊断排除，以及精确 leaf validity 与稀疏原因账本，不能统一称为“数据侧未实现”。模型侧已具备合成采样、标量/向量头、原 S 三视图桥与训练器，但这些组件尚未形成经真实导出验收的 MFM3 消费链。

## 1. 来源与证据范围

Root 提供的当前模型树：`X:/MFM_model_v3`，本地 commit
`8fa743ecc864699e94141e60bf33ba174c6a3ed4`，公开 commit
`dbb53d289af20354d86fa9ac91289c9c7c857880`，共同 Git tree
`4a9a213d852128679efb8481a4a2f182c38f48be`。Root 报告工作树干净；最后生产整合为
`5f96bf29861e474ff953047129f42bd7ef542ddf`，此后仅文档/分析快照变化。
这些 Git 身份由 Root 提供，本子 agent 没有自行执行 Git。实际读取文件另以字节 SHA256 绑定。

下文路径别名：

- `D/` = `X:/runs/data_v1_20261025/repository/`。
- `M/` = `X:/MFM_model_v3/`。
- `W/` = `D/workflows/data_v1_final/export/wire_v1/`。
- `E/` = `D/workflows/data_v1_final/export/pipeline_v1/`。
- `C/` = `M/current/phychem_mfm/`。

完整逐文件路径、字节数、总行数和 SHA256 见本目录 `source_manifest.json`；`registry_field_audit.json` 保留草案全部 264 个登记行的状态、源字段/行号、层级、单位、参考系、家族、索引形状及上下文，未把统计行分配为正式预测头。行号均从 1 开始。

| 核心原文件 | 本次读取的 SHA256 | 原状态与精确位置 |
| --- | --- | --- |
| `D/docs/interfaces/training_format_v3.md` | `94b593e09bee300bcfc90e330a4e47c8424bbc2575491fcbf91efaef58524b87` | 第 3–5、144–146 行：v3.0-draft.3，尚未共同签署 |
| `D/docs/interfaces/STATUS.md` | `4c5872cba1ff0f9a2b220afd6119bfdce52afde219179002a4aa3bebd2f78e43` | 第 7、15 行：候选实现/4520608 六项边界；最终 D3–D6 未完成 |
| `D/docs/data_v1/model_adapter_alignment_v1.md` | `bdbe4513e5ab88df29d82194e02409a010c181eccde666d962e77679424264f8` | 第 7–10、16–21、31 行：已有实现与模型边界 |
| `D/docs/data_v1/model_adapter_sampling_actual_v1.md` | `f72a287d24e474abbd0cdf4eaeb915dfcdbc4d3ef1dc0e4aec6f1bc8bc32b009` | 第 3–13 行：4520608 合成六项 PASS，不是真实清单/加载验收 |

依据用户指南第 64、70–87、184–227 行：本线应及时审阅 D-1，缺真实交付时继续 S/合成；字段语义变更以需求提出，不自行转换。模型线短意见另见 `model_line_comments.md`，由 Root 统一写回契约；本报告不代替双方签署。

## 2. 草案 registry 的实际范围

`D/configs/data_v1/label_registry_v3.json` 的 schema_version 为 `label_registry_v3.0.0-draft.1`，status 为 `DRAFT_METADATA_MAPPED_NOT_SCIENTIFICALLY_FINAL`（第 2–3 行）。264 个 source component 中 enabled=146、N/A=103、deleted=10、legacy_inactive=5；正式源字段 N/A 口径为 63。分子标量为 43P+26D，D 另有 1 个逐原子 SASA，不能凑成 42P+27D 分子标量（同文件第 23–36 行；`D/docs/data_v1/label_registry_v3.md` 第 18–28 行）。

146 个 enabled 行按原 level/value_type 为：39 atom scalar component、11 sparse_atom_pair scalar component、69 molecule scalar component、18 molecule_vector component、3 atom_vector、6 molecule_tensor component。该表是**分量统计**，不是 146 个独立物理头。偶极 xyz 合并和 tensor 六分量聚合已有数据侧明确规则；最终 target_id、成员、condition、family、unit、pooling 和 normalization 必须来自共同确认的物理目标映射。

已读全部 264 行元数据；family_v1_final 尚未定稿，参考系字段仍有 PENDING_CONTROLLED_READBACK。例如 D20.MolMR 的单位文字明确“frozen schema does not declare a unit”（第 16671 行开始的字段块），r82.Dn/De 的 1/eV 仍注明 dimensional inference。这些文字不能被模型 adapter 当作“单位已科学验证”。`W/mapping.py` 第 10–16、55–70、92–96 行的最终预检会拒绝草案/未定稿单位、家族、frame 或不可用 Pprime；应保留此闸门。

## 3. 已有支持、真实缺口和待定事项

| 事项 | 数据侧实际已有支持 | 当前模型实际支持 | 尚缺的对齐/验收 |
| --- | --- | --- | --- |
| 普通分子/原子标量及无向非自身原子对 | `W/mapping.py` 18–96、117–127、151–194 行：独立物理目标、字段各自 pairs/masks、shape 校验 | `C/phase1/v3_contract.py` 17–84 行；`C/model/v3_heads.py` 36–55、106–122、152–168 行 | 显式 target→FieldSpec/shape 映射，单位/池化/家族冻结；真实 provider 与 D3 逐值读回 |
| tensor6 | `W/mapping.py` 6–7、79–86、99–114 行已有六分量与对称矩阵；契约 60、78–80 行 | `C/phase1/v3_contract.py` 21、59–60、79–84 行只允许 scalar/vector/magnitude，宽度仅 1/3；heads/loss 无 tensor 分支 | 模型尚不兼容，不能拆六标量冒充等变 tensor；物理定义/frame/头/损失/统计仍待双方确认 |
| PM7/UFF 独立 D5 | `E/materialize.py` 163–172 行及 `W/sampling_projection_v1.py` 41–50、119–147 行 | 单来源 MoleculeEntry、显式 minimum ID、来源 locators 与 mixed 来源开关均已有 | 纯 typed projection 包装、source-specific index/provider、真实清单绑定；不能拼成同一个跨来源构象 |
| leaf validity/reasons | `E/masks.py` 38–73；`E/granular_store.py` 15–62、88–106 行 | FieldTarget 仅 values/valid/pair_index；collate 会合并 exposure | 保留完整原因 sidecar/查询接口与 codebook 身份，不让 exposure 覆盖源原因，不伪造稠密因果 |
| MFM3→模型 loader | codec/store 已有有界编码、只读读回、COMPLETE/schema 校验 | ManifestSampleDataset 是注入接口，不是 wire decoder | 每 worker 的真实节点本地 reader、跨 family identity join、Z/shape/pair/source 转换及 PreparedV3Batch 桥未验收 |
| S 旧键任务 transport | wire 有 bond_pairs/bond_order_codes；旧模型另有原生 rdkit_bond_* 语义 | 三视图桥保留输入 Data 的原属性；provider.prepare 可直接提供完整 Data | 通用 DecodedSample/collate 路径只放 x/pos，缺旧键属性传递；这是可独立用 synthetic 修复的模型接口缺口 |
| 扰动几何标签 | registry r623/624/625 明示 perturbed context；契约 81 行要求实际扰动几何 | 当前 PD 只读取一个 clean H0 | 未有额外真实扰动 view 路由，不能把 off-equilibrium 标签挂在 base clean 坐标或任意 S 噪声视图 |
| r73 basis / r82 原子子集 | source 元数据已有 basis_i/j、atom_index；`E/source.py` 105–152 行已有显式原子 scatter | 当前模型输入只原子对索引/全 n_atoms 标签，可消费已正确 scatter 的 wire | 必须明确 lossless basis 粒度及具体 heavy-row selector/index 基数/codebook；模型不能去 basis、求和、排序或补有效零 |
| P 与 Pprime 统计 | 契约 46、56、101、142 行：同 P 组、不同几何条件、独立统计/计算清单 | 组只有 S/D/P；normalization 以 model field name 索引 | 单来源 runner 可显式绑定相应统计；同一批混合两个条件时需明确 condition→统计路由，不能复用 PM7 统计 |

### 3.1 tensor：数据未丢六分量，模型尚无消费能力

r674 的六个字段块起始行依次为 registry **15786/15854/15922/15990/16058/16126**，顺序为 xx、xy、yy、xz、yz、zz，单位 e bohr^2。`W/mapping.py` 第 79–86 行强制该顺序和 all_components；第 99–114 行支持原样 symmetric6 或无损对称 3×3。不存在“数据侧只提供五分量”的问题。

模型 `FieldSpec` 当前拒绝 symmetric_tensor，`TrainNormalization.validate_for` 第 148–153 行只为 vector 检查各向同性，`C/phase1/v3_losses.py` 第 79–94 行只区分向量径向 Huber 和分量 Huber。因此不能增加一个枚举后声称全链兼容，不能静默截去 zz、强制 trace=0，或用六个不变 MLP 输出替代 Q→RQRᵀ。本报告不选 tensor 物理头、归一化或 loss 算法；原点、无迹定义、frame 证据及算法由双方另行确认，确认前该物理目标应明确“尚未支持”。

### 3.2 D5：按来源投影可接，必须用保留集 training_rank

`E/materialize.py` 第 163–172 行先形成各来源诊断 base 及其派生 geometry target，再 anti-join 得到 training_geometry/training_orders；training_rank 按 molecule_id、geometry_source、order_type 分别重新编号。`E/materialize_v2.py` 第 14–16、52–60 行将 UFF 物理身份定义为 molecule_id+geometry_source+sprime_conf_idx，native_record_id 仅作 provenance。

`W/sampling_projection_v1.py` 第 73–98 行拒绝诊断 base/child 回流并排除 view 作基础构象；119–147 行分别产生 PM7/UFF entry。fixed_order=保留集 fixed_random training_rank、diversity_order=保留集 diversity training_rank；minimum_energy_conformer_id 来自**保留集 energy training_rank=0**（第 143 行），原 rank 可大于 0。

`C/phase1/v3_sampling.py` 第 64–86、102–115 行已能消费这样的单来源 entry；209–220 行先抽分子/构象，再按显式 geometry_source 读取 locator。最小适配应保留 opaque D5 geometry_id 为模型 conformer_id/locator，另以 sidecar 保存原 native IDs，不比较 PM7/UFF 的原构象号。两个来源需使用两个独立 index；mixed 必须每分子先明确选一个来源 entry，不能把同一 molecule_id 复制成两个总体条目、拼接两个来源的 conformers，或在抽到 PM7 ID 后读取 UFF locator。

当前数据投影第 119–126 行要求**两来源均有非空训练 base**；这是共同人群候选函数的约束，不等于任意 PM7-only 数据集也必须有 UFF。N=1/N=2/诊断后剩余数、k 超出可用数如何处理及 mixed 的分子级来源清单，仍应写入冻结清单。当前模型 first_k 会直接取可用前缀（第 106–107 行），不能无说明把不足 k 解释为恰好 k。

### 3.3 mask/reason：训练有效性与审计原因必须分开

`E/masks.py` 第 43–45、59–73 行保留精确 leaf validity；source/new/review 分开，review 不改变 validity，65535 明确表示尚不能逐叶归因。`E/granular_store.py` 第 20–29、34–60 行明确 field-set+sparse-leaf-v1，按各 member 的原 leaf_shape 保存 field reason 集与 sparse leaf 异常，不把字段原因集合伪装为每个 leaf 的全部原因。

模型 `C/phase1/v3_contract.py` 第 162–166 行不承接原因；第 173–194 行只接收每个物理观察的一维 valid。数据 wire 的 valid 与 values 同 shape（`W/mapping.py` 173–181 行），所以 scalar []、vector [3]、atom-vector [N,3] 到模型 [rows,width] 必须显式映射。vector 按 all_components 得到 [rows]，原逐 component valid 与全部原因仍需可按 export_record_id/target/member 查询。不得用“有一个分量有效”或把缺失分量补有效 0 代替。

`C/phase1/v3_data.py` 第 136–165 行把 group/family exposure 与 target.valid 合并为训练 mask，这是监督选择；provider/sidecar 必须另外保留原 source validity、source/new/review 原因与 codebook/hash。`V3Batch.to/pin_memory` 第 98–115 行目前无原因 sidecar 协议，不能宣称完整原因已透传。草案契约第 134 行的 reason 描述还应明确 field-set+sparse 的规范语义及 unresolved sentinel，避免让普通 `FamilyReader` 误作 granular reader。

### 3.4 真实 wire bridge：已有 codec 不等于模型已经读取

`W/codec.py` 第 99–152 行验证 MFM3/header/dtype/length/SHA，输出只读 NumPy 数组；`W/store.py` 第 132–161 行验证 COMPLETE 与 schema/计数；`E/granular_store.py` 第 88–106 行合并独立 mask 后验证稀疏原因。应复用并逐源绑定这些能力，不另写一套宽松解码器。

模型 loader 的现状是 `C/phase1/v3_data.py` 第 34–81 行要求已实现的 provider.read(choice) 返回 DecodedSample；训练器则要求 provider.prepare 返回 PreparedV3Batch（`C/phase1/v3_trainer.py` 第 30–52、183–189、248–265 行）。二者还不是同一个端到端 adapter。需要明确的桥接包括：

1. 同 geometry/export_record_id/molecule/role/source/frame 与 native atom order 的跨 family join；verify schema、registry、codebook、D4/D5、release/shards 的 pins。节点本地与 read_only 不能仅由布尔自我声明代替实际路径/文件清单验证。
2. atomic_numbers int16[n]→long[n,1] 的 Z−1，以及规范源行号 source_atom_ids；positions_A 保持已有 fp32 字节、不再转回 float64 后重算。不重排或旋转。
3. 数据 molecule→模型 graph，scalar []→[1,1]、atom [n]→[n,1]、vector [3]→[1,3]、atom-vector [n,3] 原样；uint8 valid 转 bool 并按声明归约；每字段 int32[p,2]→long[2,p]，collate 后只加本分子的 atom offset。
4. pm7/uff_sprime→PM7/Sprime_UFF 及 opaque locator 显式映射，原 native IDs 侧存。不得猜 source task、charge、溶剂、field component 或解析复杂 WP5 cell 的隐含布局。
5. 保留原 S transport，再构造确定性 views；PD 只读其所绑定的真实几何。最后生成含 adapter/data/role/draw 绑定的 PreparedV3Batch，保持提交游标、RNG 与双验证角色。

P/Pprime 共用 P 组符合现代码。条件独立 D4 仍要处理：`C/phase1/v3_losses.py` 第 76–78 行只以 field.name 取一个 normalizer；`FieldSpec` 没有 condition，`LabelRegistry` 第 98 行拒绝重名。不能让一个 PM7/UFF 混合批同名字段自动共享一套统计。最小候选先限制单来源/单明确 condition，混合条件统计路由另行明确，不臆造新 physical field 定义。

### 3.5 r623/r624/r625：真实扰动几何路由缺口

registry 的 r623/r624/r625 字段块分别从 **15005、15068、15136 行**开始：scalar energy、atom force、atom gradient 的 geometry_context 都是 seeded_sigma0.1A_perturbed_PM7；r625 的 frame/sign 明确 dE/dR，r624 为 force=-dE/dR。契约第 74–81 行要求保留原单位/符号并关联实际扰动坐标、parent geometry ID、seed/协议及摘要。
精确源路径行分别为 **15010/15073/15141**，perturbed geometry_context 行分别为 **15035/15098/15166**；三个物理量不能只凭同一 geometry_source=pm7 就与 base geometry 合并。

当前模型 `C/model/v3_multiview.py` 第 54–66 行仅从 views.clean_atom_rows 读取 H0 和 pos，全部 PD 预测都基于这个 clean 几何；`C/phase1/v3_structural.py` 第 129–140 行的 geom 是按局部 RNG 生成的 S 配方噪声。它不是已计算 QM 标签所对应的实际扰动坐标，不能因 sigma 都为 0.1 Å 就互换。

**需 D1/D2 明确**：每个 off-equilibrium target/记录如何定位实际 geometry/view 与 parent、是否单独记录、哪些 field 属于该 view、同 base draw 如何计数，以及诊断排除如何覆盖 child。模型随后才可实现单独真实 view/batch 的 H0 路由；当前无此实现。不能把这些值当作 base 几何标签，不能复制 clean 标签去填扰动 view，也不能擅自改梯度单位或力的符号。

### 3.6 r73：轨道基组索引不能被普通 atom pair 吞掉

registry **2900 行开始的 P.pm7_B.r73.value 字段块**将 source_path 定为 values.sigma_pi_entries，shape 为 `[n_sparse_orbital_group_pairs] of {atom_i,basis_i,atom_j,basis_j,value}`；excluded_metadata 中明确包含 atom_i/j 和 basis_i/j。这是原物理标签的身份索引，不是应丢弃的数值分量。
其中 source_path 在 **2905 行**，shape 在 **2919/2923 行**，basis_i/basis_j 在 **2930–2931 行**。

`W/mapping.py` 第 44–48 行当前把 sparse_atom_pair 映射为 pair scalar，117–127 行只接受 [p,2] 唯一原子对。模型 `FieldTarget.pair_index`（`C/phase1/v3_contract.py` 162–166 行）及 collate（`C/phase1/v3_data.py` 142–152 行）也只有两个原子索引；`C/model/v3_heads.py` 第 43–55 行的预测只依赖 h_i/h_j/d_ij，同一 atom pair 的不同 basis 身份没有输入通道。若同一 atom pair 有多个 basis 对，该表示不足；本次只读元数据，未读取真实值，未断言其实际重复数量。
数据侧另有 `E/source_v2.py` 第 12–44 行的**每字段动态 n_pairs** 候选适配：要求 pair_index_base=0、保留原顺序、0pair 显式 [0,2]，不自动排序/镜像/去重。`E/export_source_v2.py` 第 13–36 行在 spawn worker 安装该适配并保存版本收据。这些现成能力应复用，但它们仍只承接 [p,2] 的 atom pair，不能据此推定 basis 语义已经解决。

**需 D1/D2 明确**：保留 basis 对为 target subtype、额外索引/输入，还是依据已确认物理定义形成另一种目标。模型不能去重、求和、平均、删 basis 或重命名来通过 shape 检查；未明确前不得把 r73 标为普通 pair 已兼容。类似地，若任一最终 pair 允许 directed/self，需与当前对称、拒绝 self 的模型 head（同文件 54、155–159 行）逐项核对。

### 3.7 r82：重原子子集必须按原索引映射

registry **2974 行开始的 P.pm7_B.r82.Dn 字段块**的 source_path=values.super_heavy_atom_rows，shape=`[n_heavy_atom] of {atom_index,values:[3]}`；同源还包括 De 和 charge_density_q_minus_Z。`W/mapping.py` 第 163、173 行对 atom target 要求前导长度 n_atoms，模型 collate 第 140、159–163 行也要求 n_atoms 行。
其中 source_path 在 **2979 行**，重原子 shape 在 **2993/2997 行**，原 atom_index 在 **3004 行**，推断单位在 **2994–2995、3007–3008 行**。

数据侧已经有通用显式 scatter，不能称其未实现：`E/source.py` 第 105–112 行读取 selector.atom_indices 并验证整数范围/唯一性，136–152 行按该索引输出全 n 原子 values/valid/reasons。缺失位置为 NaN、invalid；若缺失 atom 没有显式 missing_atom_reason_code 则拒绝，compact sparse leaf 索引也同步映射。`source_v2.py` 第 13–16 行对非 pair 继续调用此原实现。

**需 D1/D2 明确**：原 atom_index 的基数、与所存全原子序的对应、重复/越界处理，以及氢原子是非适用还是缺失的原因码。若正式规范采用全原子输出，adapter 应按**明确的原 atom_index** scatter，未观察到的行 invalid，保留来源原因；不能把 n_heavy 行顺次贴到前 n_heavy 个原子，也不能补有效 0。Dn/De 单位当前只是推断，须先获得最终单位/normalization 权威。
具体 r82 selectors、索引基数和 codebook 被共同绑定后，应直接验收上述数据侧既有 scatter→wire→模型链，不在模型 provider 中再做一套自行推断的 scatter。

## 4. 可继续 synthetic 的最小实现建议（本次未改代码）

### A. 纯单来源采样投影包装

新增 opt-in 独立模块，例如 `phase1/v3_draft3_sampling_bridge.py`，不改旧 sampler/factory。输入为已明确认证的 D5 单分子 source_entries 或等价有界行投影及 pins；仅把字典转换为既有 ConformerRef/MoleculeEntry/单来源 SamplingIndex，保留所有 ID、三种 training_rank、energy0 minimum 与 native sidecar。

候选 fixture 必须显式 opt-in 且标记 SYNTHETIC/CANDIDATE；真实训练入口默认仍要求最终合同、registry、D5 与数据 pins。不要通过把 authority 改为 data_line 来给 draft 自动放行。PM7/UFF 单来源分别实例化；mixed 输入是每分子明确的 source 选择清单，一分子仅一 entry。绑定所选来源、projection schema、orders/diagnostic/native identity SHA 和 adapter 源字节。

有意义测试：两来源 ID/数量/固定顺序完全不同；排除原 energy rank=0 后保留 energy training_rank=0 正确；诊断 base/child 回流拒绝；training_rank 间隙/重复、跨来源 locator/ID 碰撞拒绝；只取已选来源；不同构象数仍均匀抽分子；未消费预取恢复 draw 逐位一致；N/k 边界显式执行声明规则。已有 DataB 六项只是其候选投影测试，不能借给模型 typed bridge。

### B. 带审计引用的 provider 边界 fixture

新增独立、可注入 reader 的 adapter 壳，先用已有 MFM3/granular 合成 fixture，不读真实科学标签。reader factory 在 worker 中构建/关闭，严格绑定 codec/store/granular 源 SHA、schema/registry/codebook/record identity；构建 DecodedSample 与 PreparedV3Batch 的转换独立可测。审计 sidecar 在 CPU 保留 source validity、field cause sets、sparse leaf entries、native IDs 和 byte/hash 引用；不把整个原因账本搬上 GPU。

测试应覆盖：MFM3真实编码→只读解码→类型/shape转换→collate→单步模型的合成闭环；vector 一个分量缺失时整向量不监督，但原 component valid/reasons 仍可查；review-only 不改 source validity；禁用 exposure 不改源原因；65535 未逐叶归因保持；mask/label 不同 record/source/atom-order/codebook 拒绝；每字段 pairs 独立且 batch offset 正确；损坏/WRITING/schema pin 错误拒绝；spawn 句柄隔离/关闭；从已提交 cursor 恢复不读取未消费预取。此项只证明候选边界，不能替代 D3 真实 50k+5k/1万源值对照。
原子子集边界可使用已明确索引的合成 fixture：氢原子穿插于重原子之间，经数据侧既有 scatter 后进入模型，确认原原子序、invalid 氢行和原因保持；这不替代真实 r82 selector/单位的共同确认。

### C. S bond transport：可独立于 D1 新语义修复

独立缺陷在既有模型 decoded loader：`C/phase1/v3_data.py` 第 24–31 行的 DecodedSample 无 bond 字段，129 行 `Data(x=sample.x, pos=sample.pos)` 丢弃旧 S 键监督 transport。旧结构桥本身会保留输入 Data 原属性（`C/phase1/v3_structural.py` 114、138 行）；自定义 provider.prepare 若直接保留原生键字段，可以绕过此缺口，因此不是“所有 S bridge 都缺键”。

既有模型声明已定义 `rdkit_bond_index/rdkit_bond_order/rdkit_bond_status`（`C/data/descriptor_schema.py` 第 82–85、98–107 行），正边任务只消费 clean、status=ok、原 order 1–5（`C/model/shared.py` 第 454–484 行）。最小修复可给 DecodedSample 增加可选、明确类型的**原生旧模型 bond transport**，collate 在构建 Data 时原样保留；不增加新的 wire code→class 猜测，不将缺失状态伪造为 ok，不更换旧 BondPairHead/损失，也不改 S 三视图事实。

验证重点：单/双分子带原生 bond 属性经 loader 后 pair offset/顺序/label/status 保真；同一 native 输入直接桥与 loader 桥的 S bond raw/count、单线程严格梯度相同且非零；缺失/失败 status 不变成监督，零键分子正常；P/D clean H0 和 S element/noise 不受影响；.to/pin_memory 与 spawn 保留 bond transport。该独立修复可以先做 synthetic，不需要决定 r73 basis、tensor、D1 wire bond codebook 或真实标签含义。

## 5. 当前决定边界

本次认可已有候选 wire/projection/mask 实现可以用于继续接口 fixture；**没有认可真实训练格式兼容或正式签署 v3.0**。tensor 定义/消费、r73 basis、r82 atom-index、off-equilibrium view、P/Pprime 条件统计，以及 mask 原因规范需写成双方可核对的契约意见。Root 可先协调 C 项旧 S transport 修复及 A/B 的单来源 synthetic 工作，保持 opt-in，不触碰旧路径。

最终 D1/D2 冻结、D3 真实试点、D4 最终 TRAIN-only 统计、D5 最终共同人群/诊断清单、D6 全量节点本地分发均未由本报告验收。数据 STATUS 的部分角色/小试点/CPU 合成已闭合事实保留，但不能外推为最终交付。下一步由 Root 把短意见写回契约并发布模型分支；实际接口变更、测试、正式版本签署另行记录。
