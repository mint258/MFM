# M1：v3.1 读取层

入口为 `current/phychem_mfm/phase1/v31_loader.py`。读取每 split 的单默认 LMDB、
共享 schema.json 和外部 id_map.parquet；无 v3.0 回退、文件哈希或独立重读。
M1 最终完成仍须 M2 真实训练跑通；格式、采样、字段及缺失规则有单元测试。

TrainingView 直接消费窗口二正式冻结的 training_view_v1.json；字段名取 field_key，
按 selectors 选择实际列，family/level/representation 来自共享 schema。原始完整
target_id 相同的独立分量仍分别选取，不扩展成整个目标。显式 D4 参数可由
normalizations 映射按字段名提供（fit_role=TRAIN、center、scale；需要时包含已有
element_reference）。亦保留旧模型侧显式字段和 target_id 接口。
选择与R²保留列名；训练损失仍按原physical target：共享target_id的偶极xyz重组为
一个等变向量、一个原径向Huber及一个组内权重，不改成三个独立标量Huber。
矢量D4零中心且各分量同一尺度；完整观测资格沿用原逻辑，组件mask仍保留。
没有 D4 参数时不能自行拟合或用单位尺度冒充。
D4 缩尾仅用于统计拟合；加载时不裁剪原始训练标签。

r73 优先读取 schema.derived_r73_pair_targets 声明的 array27 列（原 F64 分块求和后
单次转 F32）。历史 D3 无此映射才按实际 schema 码表的标签及清单后缀规则聚合原
F32 K，保留已有舍入；两个轨道轴均属 sigma 或均属 pi 才纳入，mixed/delta 不纳入。
保留有向 pair、自环与重复贡献；所选项任一无效则该和缺失，无项为 NaN。
不把试点整数码映射当作全量通用码表，兼容旧显式列分类接口。
r674 不能启用。U 缺少标签数组时只提供其实际拥有的几何和分子级 D20。

MFM4Dataset 支持 source=PM7/UFF、order=fixed_random/energy/diversity、k=None/正整数。
先排除来源对应的 D5 holdout，再取前 k。最低能量通过 order=energy,k=1 表示；
未交付的排列不会自动用 fixed_random 替代。diagnostic=True 只访问留出构象，
应与未见分子的 FULL/ROUTINE 独立记录。molecule_indices 可绑定 D5 子集。
全量D6普通UFF训练还使用M17；pprime=True的TRAIN只使用M18且排除M14，
不根据标签是否存在或原source行推断资格。通用训练/验证入口在UFF+P时自动选择该模式。
M18只用于训练，FULL的P′评价读取真实U标签及其NaN掩码；D5诊断按M14访问
全部实际留出，包括不在普通U排列中的addressable几何。若M18缺失或合格几何未有
相应已发布排列，明确报错，不用存储序号或M17猜测P′资格/顺序。旧D3普通UFF无M17
时仍消费其原已发布排列，不能借此启用无M18的P′训练。

sample 用两个条件均匀抽样；molecule_mean 对允许构象的原始标签按有效分量求均值，
再应用同一 D4；pair 标签通过有向端点对齐。valid 严格来自 isnan。
field_weights 提供组间/字段等权和家族析因的完整条件固定权重。
这里的训练字段指物理字段，不能因xyz分列重复计算三个训练权重。
enabled_encoder_fields 为无坐标编码器关闭去噪和等变矢量字段；本阶段不实现二维编码器。
样本进度在 1/2/4/8/16/32/64M 保存，已有训练 SampleClock 可截断批次到精确保存点。

`v31_validation.py`和`tools/model_v3/v2_validate_v31.py`逐split读取实际ID映射，FULL
（或其ROUTINE子集）与TRAIN_UNSEEN_CONFORMATION分别输出物理字段损失/有效数、
原始单位下逐列R²/MAE；仅在实际有标签的记录上评价，不作开发选型依据。
通用训练入口`v2_train_v31.py --configuration FILE`支持S/P/D/SDP、C1、视图、H1/2/3、
池化、几何来源/k/顺序、构象平均与固定完整条件权重；实际训练仍按阶段依赖启动。
有效批次的梯度累积按原字段观测数加权。S的分母从已生成CPU视图掩码、原正键
选择器计算，不做一次额外的编码器/预测头前向；原生S和通用SDP入口共用此逻辑。
梯度阶段仍使用原视图、原头和原损失，不改变样本数、B0或字段权重。
通用训练的可选 `run_until_samples` 在既定样本检查点结束本段执行；`samples`仍是
学习率/时钟的总计划预算。检查点包含优化器、RNG、全程梯度历史、累计时间及可知的
累计GPU峰值，后续段修改执行终点而不修改科学配置；阶段状态与完整训练完成分开。
