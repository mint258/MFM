# 动态稀疏pair：source_v2候选入口

原source.py、export.py、verify.py和wire源码字节不改。source_v2.target_arrays为每个field从它自己的pairs selector计算n_pairs，显式shape=[n_pairs]，0pair为[0,2]索引和[0]值/掩码，不把别的字段的稀疏索引套进来。selector必须声明pair_index_base=0；不自动减1、排序、镜像、补行或去重。原pair_index_policy的directed/allow_self约束照常检查；若源与已决定的policy不一致，拒绝，不能改写源来通过。

export_source_v2通过16个spawn worker的initializer显式安装新adapter；verify_source_v2在每个原Parquet读回group worker安装同一adapter。原最终生产门保持：真实D5/common/roles/orders/diagnostic和源pins、共同physical target grouping、unit/family/frame、模型/数据共同签署契约缺任何项均拒绝最终生产。候选源码不意味着这些输入存在、实际50k/D3已运行，或co-sign已经发生。

未来Root渲染实际作业使用三个版本入口：D5用pipeline_v1.materialize_v2，导出用pipeline_v1.export_source_v2，源读回用pipeline_v1.verify_source_v2；参数分别与对应v1相同。variant会另存receipt绑定新adapter/driver与baseline源码SHA。原通用Slurm模板保留为基线，Root必须显式替换这三个模块入口并登记source pins。

增量验证只运行 python -B -m pipeline_v1.test_source_pairs_v2 --output <fresh_external_fixture_dir>：0pair、非零每字段独立pair及源顺序/方向、pair越界、值长与自身pair数不一致，共4项。不生成镜像对，不重复完整10项pipeline fixture；新driver完整真实数据/16spawn集成仍需将来的实际D3作业，不用这4项代替。
