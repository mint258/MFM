# M1：v3.1 读取层

入口为 `current/phychem_mfm/phase1/v31_loader.py`。读取每 split 的单默认 LMDB、
共享 schema.json 和外部 id_map.parquet；无 v3.0 回退、文件哈希或独立重读。
新逻辑 15 项单元测试实际通过；M1 最终完成仍须 M2 真实训练跑通。

TrainingView 消费窗口二的训练清单。清单 `fields` 每项提供 name、field_key、
group、family、level、representation 及显式 D4 normalization（fit_role=TRAIN、
center、scale；需要时包含已有 element_reference）。也可由 normalizations 映射
按字段名提供参数。没有 D4 参数时不能自行拟合或用单位尺度冒充。

r73 在清单的 r73 项显式给出 reduction=sum、code_column、channels.sigma/pi、
missing_components 和 empty_sum；读取器按该约定汇总有向 pair，不自行猜测
S/P/D 轨道分类或 delta 通道归属。r73_component=sigma/pi 各是一列目标。
r674 不能启用。U 缺少标签数组时只提供其实际拥有的几何和分子级 D20。

MFM4Dataset 支持 source=PM7/UFF、order=fixed_random/energy/diversity、k=None/正整数。
先排除来源对应的 D5 holdout，再取前 k。最低能量通过 order=energy,k=1 表示；
未交付的排列不会自动用 fixed_random 替代。diagnostic=True 只访问留出构象，
应与未见分子的 FULL/ROUTINE 独立记录。molecule_indices 可绑定 D5 子集。

sample 用两个条件均匀抽样；molecule_mean 对允许构象的原始标签按有效分量求均值，
再应用同一 D4；pair 标签通过有向端点对齐。valid 严格来自 isnan。
field_weights 提供组间/字段等权和家族析因的完整条件固定权重。
enabled_encoder_fields 为无坐标编码器关闭去噪和等变矢量字段；本阶段不实现二维编码器。
样本进度在 1/2/4/8/16/32/64M 保存，已有训练 SampleClock 可截断批次到精确保存点。
