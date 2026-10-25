# D-1 数据适配与模型消费边界核对

2026-10-25。本次只读核对现有源码，新增一个按来源投影的小型候选桥接及六项增量fixture源码。未运行测试或真实数据；D-1仍为draft.3，未双方签为v3.0；不据此宣布D3/D5完成。

|事项|数据侧已有实现|实际剩余边界|
|---|---|---|
|r674 对称tensor六分量|wire_v1/mapping.py显式检查xx,xy,yy,xz,yz,zz，支持symmetric6或对称3×3并保留mask；契约已明确它是一个物理tensor目标|模型current/phychem_mfm/phase1/v3_contract.py的REPRESENTATIONS仅scalar/vector/magnitude。需要模型线明确tensor消费与等变头，不能把六分量静默拆成不变标量来声称兼容。实际参考系验收仍待完成。|
|PM7与UFF顺序、身份|pipeline_v1/materialize.py按molecule_id、geometry_source、order_type分别生成training_rank；materialize_v2.py已修正UFF物理身份为molecule_id+sprime_conf_idx，native_record_id仅为来源|模型MoleculeEntry当前只有一个conformers序列、一个minimum_energy_conformer_id。不能把两来源原构象号对齐成同一个ConformerRef。新桥接给出两个独立来源entry，或由调用者在分子层明确选择一个来源。|
|最低能训练构象|D5已先anti-join诊断base及其派生view，再生成training_orders；energy training_rank=0已经表达剩余训练构象的最低能位置|尚缺面向模型的明确minimum_energy_conformer_id投影。新桥接仅从保留后的energy training_rank=0取ID，原rank可以大于0，不从全体原order rank=0取值。|
|mask原因粒度|pipeline_v1/masks.py及granular_store.py已保留精确leaf validity、source/new/review字段原因集合及稀疏leaf异常，拒绝伪造稠密leaf因果；生产export需双方明确接受field-set+sparse-leaf-v1|模型FieldTarget目前承接values/valid/pair_index，不承接完整原因账本。训练可依据valid选择监督，但审计原因仍须由provider/sidecar保真访问并绑定codebook。新桥接只投影exposure，不改标签validity或原因。|

上述四项不宜统一表述为“数据侧均未实现”。已有候选编码与清单逻辑应保留，尚缺真实数据及模型消费验收。模型需求文档是审阅清单，并非正式反对意见或双方签署。

新增来源：

- workflows/data_v1_final/export/wire_v1/sampling_projection_v1.py：纯粹的单分子训练投影，输入必须由调用者从已认证D5的training_geometry、training_orders、diagnostic target及canonical geometry原子数取得。输出状态固定为CANDIDATE_PROJECTION_NOT_RELEASE，不自行证明任何manifest已冻结。
- workflows/data_v1_final/export/wire_v1/test_sampling_projection_v1.py：六项新增边界测试源码，未执行。

桥接为PM7和UFF分别返回MoleculeEntry形状的字典，使用D5的opaque geometry_id作为投影conformer_id和provider locator；原native_record_id/sprime_conf_idx逐条保存在native_conformer_identity sidecar中，不改变原物理ID。两来源构象数、固定随机顺序和多样性顺序可完全不同。每个ConformerRef只有其自身来源的一个locator。消费方必须用相同来源的entry构造index；mixed时须在每个分子上显式选择一个来源entry，不能串接或伪造跨来源对应。

该函数拒绝诊断base或其child混入training rows、跨来源geometry_id碰撞或order引用、重复基础物理身份、缺失/重复/非连续training_rank、训练顺序与原rank次序不一致、缺少任何一种来源顺序、缺少真实原子数，以及非bool exposure。off-equilibrium views不进入基础构象采样。默认4096行是单分子Python投影的内存边界，调用方可显式设置；不用于改变科学共同人群或截断构象。

Root后续可在已批准的有限CPU测试范围运行：

~~~
python -B -m unittest workflows.data_v1_final.export.wire_v1.test_sampling_projection_v1 -v
~~~

六项分别验证：两来源独立ID/顺序与诊断后最低能；诊断base/child不得回流；training_rank不能被原rank替代；跨来源碰撞/引用与重复物理身份拒绝；view不作基础构象且三种顺序完整；明确原子数、exposure类型、TRAIN角色与内存边界。

该候选桥接没有provider文件读写、LMDB句柄、真实node-local证明、tensor head适配或全人口生成入口。最终共同人群、geometry/order/diagnostic冻结、原子数权威、真实导出和模型线实际加载仍是必要依赖；不改模型树，不修改旧冻结源码和契约。
