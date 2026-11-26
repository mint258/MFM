# A6 · QM9 30,000 TRAIN 组的材料化与读出

按 USER_DIRECTIVE_20261122B.md A6 执行。当前材料化完成，四来源 frozen R3 与配对统计待完成。

现有封存包只有 8,192 个 QM9 TRAIN 分子组，不能直接当作 30,000 组。CPU4539139 首次元数据预检核实该限制；随后复用原始 target-opaque TRAIN 元数据与原 GroupedTrainingView 排序，seed20261025、fold0，取前30,000组。原2,048评价组逐项相同，原8,192组是子集；ExpansionRx/CYP成员不变，未读取TEST标签。

准备4539141 C0/28秒/4CPU，内部约20.60秒，封存选择计划与派生面板。材料化4539145 C0/91秒/16CPU，内部86.35秒，生产40,022条 native 记录：17,602条旧记录直接逐字节复制，22,420条新增QM9 TRAIN记录才调用原冻结解码器。完整native头部、记录SHA及原来源/角色/分子绑定核验保留，旧FP64坐标及其FP32字节不经张量转码。原封存器的原生顺序、完整source proof、pending再发布与分子组回放守卫沿用；没有生成新几何或改变标签。

外部训练源：
`/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/fixed_20261115/analysis_20261122/A6_materialization/native_store/training_store.json`

- source SHA256：`d2cf06142474b20ded12af10b6f2435fd55b922330e2e88c9f5a79ae415df452`。
- 完整选择manifest SHA256：`786996ba8be1a57c13abbeccac70d83b800c5ddd21289ddb7266f633502559b4`。
- QM9 原始DFT几何可用32,893条记录，包含同分子重复记录；按分子组计TRAIN30,000、评价2,048。不将记录数冒充分子组数。
- 三个新增测试只检查旧FP64/FP32字节保留、记录变更拒绝、仅新记录进解码器。旧native数学测试不重跑；完整材料化自身的一次封存回放通过。
- 首次准备4539140缺少deadline字段，在读取数据前退出1:0/6秒/4CPU；已保留失败与成本，自有树和实际根PID均消失。修正准备成功，后续材料化未失败。
- 真实TimeLimit与900秒退出窗口、CPU11/按需CPU、实际磁盘/inode/同行future保护继续。48GiB CPU峰值与2GiB输出future包括计划、proof及临时量；旧产物不删。

GPU读出4539168已普通sbatch登记到node5，依赖T1组成前向4539167；16CPU/64GiB、B32/FP32/TF32关闭、2小时TimeLimit、提前900秒保存完整R3优化器/随机状态。四来源为T5/T6/T2各自9M，以及原C1-0/three随机编码器（原reference初始化seed20261025）；R3读出seed0、30epoch、原内部选择与归一化规则不变，仅QM9四项。评价组和外层角色不变。

当前冻结P配方保持，本文不是A6样本量作用的结论或最终P报告。全研究26项仍继续。
