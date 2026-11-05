# B6：已有下游结构的描述符

低优先级 CPU producer；不启动训练，不读目标/注释/成绩，不生成新几何。源为既有冻结的 QM7、QM9、CYP isoforms、AZ exact SoM、ExpansionRx 全部分子结构。配置中的 membership 固定源成员、原 fold 与 member_uid；官方 TEST 的结构可以计算，目标列不解码。

复用 `stage43_downstream_membership/run_4511949/members.jsonl` 的 source_frame。QM7/QM9 只读原 XYZ 的元素/坐标行，使用原声明单位（QM7 bohr，QM9 Å）；QM9 额外只读原 GDB SMILES 字段。CYP 只把 SDF 的 mol block（至 M END）交给 RDKit，属性区不解码；AZ 只解析原 CSV 的 SMILES 列；ExpansionRx 只 seek 已绑定的 SMILES 字段字节区间。SoM 使用现有 `missing_geometry_stage34_4511904/candidate_records.jsonl` 或原 3D SDF；ExpansionRx 使用 `stage60_geometry_cpu_launch_v1/run_4512067/geometry_inventory.json`。从不调用几何生成器。

RDKit 2D 使用当前既定 2025.09.5 的全部 `Descriptors._descList`，按名称排序（约 200 余项），首次生产把实际名称写入单一 manifest。仅在源图副本上 RemoveHs 以获得常规 2D 分子描述符；原几何与原子编号不改。未确定源图（如 QM7 作者键型仍未确认）保留 NaN/false，不感知键或假设电荷。

xTB 使用已安装的 GFN2 single point、原 WP5 parser 与 SCC 收敛规则，坐标 Å、源图明确的总电荷、可确定闭壳层的 spin=0；保留原单计算 900 秒参数。不优化、不加氢坐标。若已存 native-only 几何缺少源图的隐式 H 坐标，或电荷/spin/几何未确定，则明确缺失，不用重原子骨架冒充完整量子分子。原子 q/C6/alpha、WBO 等保留 native 顺序；另保存能量、HOMO/LUMO/gap、偶极模和原子量的 sum/mean/min/max/std，均无拟合或归一化。标准化与后续基线选择只能用 TRAIN。

运行（Root 在 B1–B5 资源空闲后统一 Slurm 提交，至少16 CPU）：

```bash
PY -B -m unittest workflows.data_v1_final.downstream_descriptors_v1.test_v1 -v
PY -B -m workflows.data_v1_final.downstream_descriptors_v1.run \
  --config configs/data_v1/downstream_descriptors_v1.json \
  --output /lfshome/zixiao/data_v1_20261025/B6_downstream_20261105_v1 \
  --workers 16 --shard-index 0 --shards 1
```

按源 ordinal 的 `--start-record/--stop-record` 或 `--shard-index/--shards` 分片；各分片使用独立 output，ordinal 分片无交集。每批一个 Parquet 和生产 checkpoint，终态只有一份 manifest（各文件 path/bytes/rows、实际列名、缺失状态）；没有新 SHA、收据、独立 QA 或二次科学读回。闭合 checkpoint 跳过；前一未登记批次已有正常结束的 xTB 输出在输入完全相同时复用，exit 未知如实标记，不重跑已得数值。新建的节点 scratch 默认保留，不删除任何既有文件。输出、原始输入和 scratch 均在 Git 外。

当前仅源码准备，8 项新单元测试待 Root 实际运行，没有启动 B6 计算。