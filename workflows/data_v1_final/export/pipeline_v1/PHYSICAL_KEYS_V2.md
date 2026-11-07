# 正式D5入口：materialize_v2

v1基线已登记为f053c672da22936607579120d79ccc14285f34d1，并在真实Slurm4520395通过10项fixture；它对UFF parent/view额外比较了trace native_record_id，过于严格。旧源字节保持不变。

未来D5物化使用 python -B -m pipeline_v1.materialize_v2 --config <config> --output <fresh external directory>。参数、输出标准schema、冻结门、16worker、quota和原materialize相同。新入口只替换已知父几何身份谓词，其他检查原样执行；未找到唯一旧谓词或出现其他validator覆盖即拒绝。另写physical_parent_keys_v2_receipt.json，绑定D5 manifest与两个源码SHA。

PM7 parent/view必须同molecule_id、geometry_source、native_record_id。UFF必须同molecule_id、geometry_source、sprime_conf_idx；UFF native_record_id只是溯源字符串，可与父不同。该修正不会放松直接base父键、同侧role、构象顺序、诊断排除或canonical source owner检查，与SB3 D4既定物理键一致。

原run_pipeline.sbatch.in保留为v1测试基线；Root渲染实际作业时必须将materialize的模块入口改为pipeline_v1.materialize_v2并记录新source pins。不要用旧入口生成最终D5。此变化不代表D5或D3已实际生产，也不是模型线共同签字。

增量验证仅运行三项：UFF同mol+idx但不同native trace应PASS，UFF不同idx应FAIL，PM7不同native应FAIL。CLI为 python -B -m pipeline_v1.test_parent_keys_v2 --output <fresh external fixture directory>；不重复整套大表fixture，不读取科学数据。
