# 可回填 D-1 draft.3 的模型线意见（Root 审阅稿）

2026-10-25。模型线已只读审阅 draft.3、draft registry 及候选 wire/projection/granular 实现。当前仅完成接口审阅，未共同签为 v3.0，未宣称真实 D3–D6 交付或模型加载已验收。

1. 数据侧已支持 r674 的 xx,xy,yy,xz,yz,zz 六分量、symmetric6/对称3×3、完整分量 mask。模型目前仅支持 scalar/vector/magnitude，tensor head/loss/normalization 尚无实现；不得静拆六个不变标量或删第六分量。原点、无迹定义、frame 验收与消费算法须共同确认，本次不作物理算法决定。
2. 数据侧 D5 已按来源 anti-join 诊断 base/child，并重排 training_rank。模型同意最小桥接采用独立 PM7/UFF entries/index，minimum_energy_conformer_id 取保留集 energy training_rank=0，不取原 rank=0；opaque geometry_id 作模型 locator，原 native IDs 侧存。mixed 每分子显式选一个来源，不能拼接或假造跨来源构象对应。N=1/N=2、诊断后剩余数及 k 不足策略仍需冻结。
3. 同意精确 leaf validity 与原因粒度分开：provider/sidecar 需保留 field-set+sparse-leaf-v1、source/new/review 原因、codebook/hash 与 unresolved=65535 的原含义；review 和 exposure 不改源 validity/reasons。vector 训练采用声明的 all_components mask，原 component mask/reasons 仍可审计。请在契约 mask 段明确该规范，不能声称每叶都有完整稠密因果。
4. 真实 MFM3→模型 provider 尚未完成或验收；需绑定 registry/目标成员、单位/家族、角色/D4/D5、geometry/atom order、schema/codebook/shard SHA，并明确 Z−1、molecule→graph、shape、各字段 pair transpose/offset、来源名及原生 S bond transport。候选 fixture 只能显式 opt-in，不能通过标 data_line authority 放行草案。
5. r623/r624/r625 的已登记标签属于实际扰动 geometry；当前模型 PD 只读 clean H0，S geom 是另一个本地 RNG 噪声。请明确 target→实际 view/parent/坐标/hash 的 wire 定位、排除和计数，之后实现对应 H0 路由；不能把扰动标签挂 base 坐标或替换为任意 S 噪声。
6. r73 source 保留 basis_i/basis_j，当前普通 [i,j] pair/head 未表达该身份；请明确 lossless basis 粒度/索引/物理目标，不由模型去重、合并或求和。已有 source_v2 的逐字段动态 n_pairs 不代替 basis 身份。r82 数据侧已有显式 atom_indices scatter 与缺失原因闸门；仍需共同绑定具体 selector、索引基数及 codebook，然后验收全原子 wire→模型消费，未观察行 invalid 并保留原因。不得贴前 n_heavy 行或补有效零，模型不另行猜测并重做 scatter。相关单位仍按最终科学登记确认。
7. Pprime 保持 P 组并采用对应 UFF 条件及独立 D4。当前 normalizer 以 model field name 索引；单来源 runner 可明确绑定一套相应统计，同批混合条件需要显式条件路由，不能自动沿用 PM7 统计。

独立可先推进的 synthetic 工作：单来源 typed sampling bridge、保留审计引用的 provider fixture，以及既有 DecodedSample/collate 的旧原生 S bond transport。后者只保留已定义 rdkit_bond_* 属性与旧 raw/count/梯度，不涉及决定 D1 新 bond codebook。完整行号、来源 SHA 与测试建议见 `runs/model_v3_20261025/interface_draft3_model_review_v1/review.md`；最终共同冻结前维持 DRAFT。
