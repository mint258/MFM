# v1 原始输入 X01–X05 回归：可提交计划

本入口不使用仅保留分子的样本去估计总体一致率。数据范围必须覆盖全部
15,879,477 个原始物理记录，包括原 TRAIN/FULL、未分配的8,259条、后续被
排除的记录和无法解析的输入。原始 LMDB 只读且此脚本不打开它；重用已保存
的逐记录原始 SMILES、native 元素/电子数与原始 payload SHA、shard/path/index。

## 具体来源

| 来源 | 原始作用与规模 |
| --- | --- |
| `runs/phase1_dataset_rebuild_20261010/record_index.parquet` | 全部原始输入、原 X flags、原始 SMILES/图摘要、native 元素与电子数、物理指针；15,879,477条，2,005,784,925 bytes |
| `runs/phase1_screening_20261011/a_retained/relaxed_quality_annotations.parquet` | 名字含 retained，但文件本身仍是全部15,879,477输入；retained 列才标出11,236,754条；2,529,572,637 bytes，既有SHA f59a82954be5b68b5ec7bf301bcc552c074c67864379c3d1cf207d67a73334e5 |
| `runs/phase1_wp5_20261011/population/formal_record_index.parquet` | 除去4900条未分配隔离记录后的正式记录索引；11,231,854条，1,242,386,629 bytes |
| 新共同人群 molecule manifest | 待 S′ 补齐和角色闭合后绑定；没有该来源时不声明完整数据集v1的最终入选一致率已通过 |

这些文件均在 `/share/home/zixiao/descriptor_analysis/` 下。Root 必须在自己的
Slurm source-pin 准备阶段取得/验证所有实际 SHA；模板中的空 SHA 不可执行。
脚本在计算节点重新验证实际字节、完整 SHA、行数/唯一 record_id 和逐记录
join。不能把另一个 retained-only 导出换进来。三份主要 parquet 共约5.78GB
输入，保持只读；hash/read/join 成本单列，不将固定I/O成本按试点条数线性放大。

Root 的登录提交器只绑定代码、plan和小型 source-pin receipt，不把5.78GB文件
放进会read_bytes的request.source_references。plan.data_authorization_receipts
绑定Root实际计算节点来源核验，authorized_data_pin_jobs列准确生产job IDs；
大文件放在request.data_references。消费者只接受Root实现的精确
DATA_V1_SOURCE_PIN_RECEIPT_V1 / ALL_BOUND_INPUTS_SHA_VERIFIED / compute-0-20，
逐项匹配reference和前后相同stat、stable_file_identity，再在compute20完整SHA
读回并在计算结束复核stat。无新receipt的旧路径只允许显式开启的<=32MiB合成
fixture，真实计划默认禁止。它不修改旧Root提交guard或既有raw已运行代码。

辅助权威是 WP0 inventory.json、a_retained/input_count_validation.json 和 WP5
population/manifest.json；模板保存了它们的现存元数据 SHA。原几何补齐的
geometry_join_validation.json 已记录11,788,524条 post-X几何恰好一条对应、
没有缺口。这里复用这些封存几何/身份决定，不重新生成坐标或计算量化。

## 三类比较必须分开

1. **规则重放**：用固定 RDKit2025.09.5重算原SMILES的组分、形式电荷和自由基；
   用原native元素和电子总数重放原X02/X05。原来X01若已有缓存几何多组分增补，
   单列该几何来源，不能叫SMILES规则改变。
2. **可移植图输入比较**：PubChem只有图输入，因此也用 Chem.AddHs 的元素与
   原子序数和重算X02/X05；原native与SMILES的氢/元素不一致逐条记录真实差异。
   不剥同位素、不重置立体信息、不引入重原子上限。
3. **完整入选比较**：在固定的已封存几何/G/C/relaxed-I01规则下重放保留/排除，
   再与正式人口和新共同人群对应。明确这是条件于同一批既有几何/身份的比较，
   不能声称新PubChem已经有PM7几何或所有结构已通过新3D核验。

所有不一致保存原记录ID、物理指针/payload SHA、原SMILES、五个原flag、native
重放flag、可移植图flag、原因代码和入选决定；不只保存20例。未解释的缓存规则
漂移不能自动改成已解释。原始数据、QC容差、字段值和已有验收均不修改。

## 试点与全量

配置模板：`configs/data_v1/expansion/x_regression_plan_template_v1.json`。
Root 新建 READY plan并绑定实际源，使用现有 submit_reviewed intent；准确argv：

```bash
python -B -m workflows.expansion.regression_x_v1 \
  --plan /absolute/reviewed_regression_plan.json \
  --root-submit-intent /absolute/control/submissions/<name>.intent.json
```

试点为16个真实spawn worker；按source family、重原子区间、五个flag的三值
模式、TRAIN/FULL/unassigned角色及原保留/排除状态分层，固定seed20261025。
每层最多32条，总上限10,000；必须覆盖每个实际出现的层。分层试点包含拒绝、
未知和隔离输入，其未加权频率不是总体率。试点只证明代码重放/差异可解释及
实际成本，不把它称为全输入99.9%证明。

初始申请16CPU/32GiB/1小时，DuckDB8GB、spill8GB、总新输出峰值16GiB，启动
需真实<=300秒quota且扣除完整峰值后仍剩200GB。实际输入SHA/join与worker阶段
分别记耗时。Root核实试点状态、成功率、核时和空间后，另建full plan；禁止
自动跳过试点。运行于Root真实分配的计算节点，不用登录节点或学校付费节点。

全量必须处理全部原始记录；逐记录及逐分子的入选一致率都至少99.9%，缓存
规则重放不得有未解释漂移。没有新共同人群物理来源时，仅标
FULL_X_RULE_PASS_COMMON_SCOPE_PENDING，不能发布最终v1 selection PASS。全覆盖、
共同人群和所有比较真正闭合后，receipt 才可供扩充 release gate 使用。

新合成测试命令（不重复旧16项）：

```bash
python -B -m unittest workflows.expansion.test_regression_x_v1 -v
```

此文档没有预先填入真实试点/全量的统计、核时或验收状态；它们均由实际脚本
和Root终态收据生成。
