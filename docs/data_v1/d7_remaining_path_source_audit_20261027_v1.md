# D7剩余路径：源码与小型实际证据审计

2026-10-27。结论：**可以在最终Common之前独立完成PM7的逐分子几何统计、固定随机去重及可验证的排序缓存；目前没有全量D7完成证据。** canonical HOF完整时可同时生成PM7能量/多样性顺序；缺HOF时先保存几何、随机顺序和距离，不用native energy补值。Common冻结后按整分子筛选缓存并重新聚合，可免去重复的PM7分子内RMSD工作。最终S′及N1扩展池、PM7–S′交叉RMSD、物理ID顺序和人群报告仍须后续步骤。

本轮只读源码、小型历史receipt/报告及source SHA，未读LMDB、Parquet、SQLite、task/packet/逐分子科学正文，未执行Python/AST/测试/SSH/Slurm。以下`repository/...`路径以`X:\runs\data_v1_20261025`为根；历史`runs/...`路径以`X:\`项目根为准。没有发现的历史规则记为UNKNOWN，不把搜索范围等同全服务器。

## 1. 已有代码和真实完成边界

| 项目 | 实际证据或精确源码 | 可确认内容 |
|---|---|---|
| 有界准备 | `control/d7_profile_preparation_actual_closure_v1.json`；4520383 COMPLETED/0:0/180s/16CPU/compute20 | 256完整分子、1344原PM7记录，准备C0；不是全量人口 |
| 有界几何统计 | `control/d7_profile_actual_closure_v1.json`及`artifacts/conformers/statistics_v1/profile_v1/receipt.json`；4520390 COMPLETED/0:0/40s/16CPU/compute20 | 256完成、errors0、无嵌入/UFF优化/QM、原数据未写；配置16worker，但没有独立16 distinct PID观测 |
| 已闭合统计小报告 | `profile_statistics.json` 2598B，SHA `517e0969088bdfb95a1b1f2cb5d95fab36739d01445876f9debe33e213fc4fae`；文字报告`repository/docs/data_v1/conformer_statistics_pilot_actual_v1.md` | profile分布/相关/范围/交叉RMSD；样本受至多16个owner jobs及角色/大小/N分层选择约束，不能外推最终Common |
| 固定索引RMSD/源读取 | `runs/sprime_s_convergence_20261013/scripts/sprime_v6.py:14–27,30–58,173–183` | 只读LMDB、逐payload SHA、固定原子顺序/源图；重原子proper Kabsch，无反射/对称置换 |
| 真正profile去重 | `repository/workflows/data_v1_final/conformers/statistics_v1/run_profile.py:34–54,79–110` | 两侧均按固定随机顺序贪心保留距离≥0.5Å的代表；不是连通分量、DBSCAN或无序“唯一簇数” |
| 三种排列 | `repository/workflows/data_v1_final/conformers/selection.py:8–10,51–74` | seed20261025 SHA固定随机；能量升序；从最低能开始maxmin多样性；同分按能量和ID字符串稳定破同分 |
| canonical HOF | `statistics_v1/profile_common.py:17–19,103–174`；`prepare_profile.py:104–125` | pm7_B registry60/kind1/有限f64，单位kcal/mol；record/molecule/attempt/job/task五键及lane/原子数匹配current owner；按标量叶投影，不读array/text |
| 历史native诊断 | `repository/workflows/data_v1_final/conformers/statistics_tools.py:8–35` | 旧helper使用native energy排序去重，输出明确native-anchor diagnostic；不得替代上述canonical profile/最终D7 |

上述两个实际D7父合计3520分配核秒，仅为这些历史阶段成本，不是全量估计。当前已看到的小型实际receipt全部明确`common_population_frozen=false`、`population_estimate=false`。未发现全量PM7独立缓存、全Common D7或三种最终训练顺序的实际闭合receipt。

旧统计代码的计算/定义可复用，旧运行入口不能原样正式重启：`profile_common.py:38–45`限定128–256分子；46–61限定compute20和旧preflight；旧common仍有85%声明内存规则。新作业必须在独立namespace接当前中央CPU/no_mem/fresh proof和真实quota provider，不能修改这些冻结字节或借用旧资源例外。

## 2. energy_raw是否已证为原PM7生成热

**UNKNOWN：本次找到的来源不能证明`record_index.energy_raw`就是PM7 heat of formation，也不能统一保证其单位为kcal/mol。**

明确可追溯的路径是：

- `repository/legacy/descriptor/dataset/build_lmdb.py:338–353`的`build_stream_item`调用`parse_xyz_stable(stable_path)`，只导入已有优化XYZ，再附原SMILES/descriptor；不是首次构象生成器。
- `repository/legacy/descriptor/dataset/dataset_without_charge.py:55–69`要求第二行含`SCF Energy:`，解析数字，单位由文本识别为`Hartree`、`kcal/mol`或`unknown`。76–114将其直接放进`Data.energy`/`energy_unit`。该代码没有PM7方法标记或“生成热”断言，也没有将Hartree统一转换成kcal/mol。
- `repository/workflows/dataset_rebuild/scripts/wp0_unassigned_inventory.py:137–146`将原`fields['energy']`标量作为`energy_raw`，保留原`energy_unit`；`wp0_inventory.py:345,364–365`继续使用已有字段。WP0里的kcal/mol注释或WP5变量名`old_energy_kcal_mol`不是原始生成程序/方法/单位的独立证明。
- 已验收S′原科学代码`science.py:69–83`及旧`sprime_v6.py:202–206`确实用native energy选来源图/立体锚。**来源锚的既有规则**与**最终D7的canonical HOF排序**应分开记录；不能因锚用了native energy，就把native值升级成canonical HOF。

因此保留native原值/单位/来源作审计，但最终HOF范围、能量顺序及最低能起点多样性继续走canonical pm7_B registry60。现有`decode_hof`还区分字段缺失、numeric issue、明确converged=False及NULL人工review；不可用整任务PROPERTY_FAILED一刀切，也不可在缺HOF时删掉几何。最终应绑定当前SB3闭合owner/标签/QC版本；本次未宣称其全人口HOF覆盖已完成。

## 3. 原始N规则的真实出处与UNKNOWN

原始PM7第一次为每分子选择多少初始构象的规则，仍未建立。

实际已保存`artifacts/conformers/statistics_v1/prepared_v1/history_search.json`，8034B，SHA
`84fe86d3ad6c219b6b5e6f7655f5798d344a3e5c1c0ad005b82ac8134f2adbad`。
它是有界源码检索，列出的五个来源为：历史github checkout的legacy `build_lmdb.py`、`workflows/dataset_rebuild/scripts/wp0_inventory.py`，服务器`modern_ML_representation/support_scripts/MFM_descriptor/dataset/build_lmdb.py`，以及旧S′ `prepare.py`/`full_dataset_v7.py`。导入器两份SHA相同；报告中的命中未截断。

- `build_lmdb.py`导入已有XYZ；未看到首次PM7 N生成算法。
- `wp0_inventory.py:136–151`统计已有record/conformer ID数量；不决定初始N。
- 旧`sprime_v6.py:191–218`明确`n=len(rows)`，目标为已有PM7数，旧ETKDG候选`3*n`；`full_dataset_v7.py:40–51`按既有records准备队列。
- 本轮`conformers/science.py:47–64`同样把已有PM7指针数作为target。当前10N/cap300是UFF补齐候选规则，不是原始PM7首次N规则；两者不能混称。

搜索未覆盖全部服务器历史/原始PM7生成工具或未保存的命令历史；未找到不能证明没有策略。不得从重原子数、可旋转键相关性、典型N≈10或文件名推断历史公式。最终报告应写`ORIGINAL_PM7_INITIAL_N_POLICY_UNKNOWN_WITH_BOUNDED_SEARCH_PROVENANCE`，除非后续找到真实生成源/配置/receipt。

## 4. 可提前独立做的PM7工作

可以冻结**原PM7整分子超集**的内部cache authority，不冻结Common。来源可为全部1220466原分子/11231854记录，或在Root已冻结角色下选择TRAIN+ROUTINE VAL超集；两者都必须明确独立源人口、实际计数、QC/失败守恒，不能先依赖旧S′ SUCCESS资格。Common最终只会对整分子做筛选，PM7分子内几何、record ID、固定随机顺序和RMSD不因筛选其他分子改变。

可复用缓存：完整record ID集合及payload/原子序/有序图/坐标SHA；重原子数、可旋转键、环数；固定随机排列、0.5Å代表ID/唯一数/重复比例；按相同来源固定索引计算的PM7分子内距离；canonical HOF逐record有效性/范围/能量顺序/多样性。HOF尚不完整时，几何和固定随机部分仍可精确完成，能量/多样性暂不可用；之后从已缓存距离加上真实HOF生成，不拿native值填补。

当前`run_profile.process_molecule`并非PM7-only入口：62–77要求已验收S′及唯一`source_record_id`锚，87–105又验证S′。需要一个很小的独立PM7-only core，保留`SCIENCE.read/graph/ordered_graph/rmsd`及`unique_representatives/geometry_orders/selection`算法。先确定原PM7锚/图身份并验证所有记录原子序与有序图相同；RMSD只依赖原重原子索引和坐标，不依赖S′。如果为兼容既有立体来源沿用native最低能锚，仅把它作为明确的来源锚规则，不作为HOF。图/立体身份不合格保留原因、不可悄悄删行。

内部缓存可仅保存标量/ID和原定位，也可经实际CPU逐坐标SHA回读保存派生float64坐标/距离shard，以减少最终交叉RMSD时再次随机读LMDB。后者是新科学DATA和新磁盘预留，大小必须由实际probe测量，不能把缓存几何当新构象/新ID，不能不经格式/来源桥就改Common的native_lmdb locator。任一cache复用须全等比较分子record集合、payload/坐标SHA、源图、方法/版本、阈值、seed、ID和HOF owner/QC authority。源HOF变了只失效能量相关部分；几何版本变了则相关几何缓存失效。

PM7 ID使用原`record_id`；最终物理PM7 geometry_id可以按原finalizer的`pm7:sha256(record_id)`连接。最终order manifest仍必须绑定真实Common/roles/source geometry tables，不能把precommon缓存自行命名成最终训练顺序。

## 5. 必须等后续闭合/显式集成的部分

1. S′缺口90069的真实once/outcome闭合和最终Common排除审查；当前500成功不能替代完整人口。
2. 完整S′物理int64及稀疏追加映射，再按**物理ID**重新生成S′固定随机/能量/多样性与随机顺序贪心唯一数。新科学packet中的kernel rank不等于最终物理ID；不能直接复用其随机顺序。PM7原record ID稳定，故其缓存没有这个限制。
3. N1额外几何的独立池/物理ID/人口对账，见下节。
4. 最终Common上的PM7–S′全交叉RMSD。可复用PM7坐标/图缓存，但两侧最终几何池与ID必须真实闭合。
5. 按实际Common整分子筛选cache，重新算唯一数直方图、≥2/5/10、重复构象/重复分子比例、Spearman、canonical HOF完整性/范围及交叉RMSD精确分位数。保留分母、失败/QC/未知和role守恒。交叉RMSD分位是pair加权，HOF范围是分子加权，不能混成同一权重。
6. 独立最终顺序发布。`export/pipeline_v1/materialize.py:130–132,192–197`要求三种完整排列、零起rank且绑定Common/roles；有HOF缺失时不得造出完整三序PASS。P′现有协变15FAIL/2000-full HOLD不因D7缓存而解除。

精确全量聚合不能把256结果按比例扩展，也不能用近似直方图替代精确quantile。既有聚合`run_profile.py:136–164`使用NumPy `percentile(method='linear')`；全量应采用有界float64分片/外部排序或经边界等价验证的精确方法，避免把全人口JSON、坐标和全交叉矩阵一次堆成Python列表。Spearman的并列秩和常数向量null语义保持原样。

## 6. N1不得遗漏或被<=N合并丢弃

当前N1全source authority只是既有accepted baseline1的4631个分子，32导入+4599新任务。`n1_pprime2_source_full_v1/planning.py:48`固定记录5105原母表的原因：4631 ready、233 `ACCEPTED_BASELINE_COUNT_NOT1`、176 `UFF_UNSUPPORTED`、65 role FULL/missing。它不是最终v1 Common全部N_PM7=1人口，也不表示当前4631都已执行完。

233个旧baseline不等于1的分子中，若S′正式补齐后某些恢复Common、且PM7 N仍为1，需要根据**新的实际Common/accepted baseline物理证据**冻结一个独立新增N1子人口。实际数量须重新测量，不能先承诺233全部恢复。对每个新增分子检查原N1 once ledger；保持原task/seed逻辑、只做尚未消费的真实任务，不重跑4631或伪造新seed。原176 unsupported不因这项补充自动获豁免。

现有S′ finalizer的`merge_counts`在`formal_cpu_auto_v3/finalize.py:56–66,210`明确拒绝合并数超过原N。N1第二个真实UFF**不能**作为普通S′补齐候选塞进N=1这条合并路径，更不能在为N截断时悄悄丢弃。应明确区分保留N份的基础S′视图与供P′使用的N1扩展UFF池，保留额外几何的独立source manifest、原baseline引用、candidate/seed/坐标SHA和最终新物理ID；PM7_source_count始终1。

最终D7必须声明统计哪个池，并可分别给基础S′与扩展池指标；两条实际几何但<0.5Å的合法fallback是`实际行数2、0.5Å唯一数1`，不能混称“两种不重复构象”。扩展池的int64分配、三序/P′取前k及export source表需要显式新authority/覆盖检查。旧Common/merge脚本不得静默吞掉extras或复制PM7指针当第二个UFF。

## 7. 最小有界实测及按group全量方案

先做一次有限CPU正确性/成本probe，不先做大重写：32个完整PM7分子，固定hash挑16个来自已闭合256作为golden PM7投影对照，再挑16个不以S′ SUCCESS为资格的原PM7分子，覆盖file_group/大小/N、N1及能量/图错误边界。所有真实科学比较都在实际分配内读取旧profile包和原LMDB，不在login。比较原record/原子图/坐标SHA、固定随机代表ID、HOF owner/有效性、三序与PM7统计；新QM/UFF=0。HOF缺失必须精确保留，不自动放宽QC。Root选择有限wall/output ceiling，实际收集distinct worker PID、每worker任务数、RSS/I/O、逐分子elapsed/字节和实际parent成本；上限不是预测。

通过后，CPU准备一次只读整分子roster，按原`file_group`1–5再按稳定分子hash/range切分，保证同分子所有PM7记录落在同片；每片实际计数/record集合SHA、互斥union和错误/未读守恒。canonical HOF按current owner job/file分组一次标量叶扫描，避免对每分子重复扫描整个canonical文件。全量worker16、有界active任务、逐分子持久化包+逐片manifest；不一次加载全task/全部pair正文。大N必须显式资源上限/自然drain，不偷改N、0.5Å或原子映射。

正式资源复用当前中央CPU auto-memory queue，不新造queue、不复用旧compute20/85%内存入口。当前真实same-storage provider只证明node13时就只用13；16CPU、no_mem、算法RSS软上限、输出总预留+账户200GB与现有lease新鲜度都要实际guard。D7新增缓存磁盘预留需与S′182cap预留并存核算，不能挤占后者后仍宣称有reserve。其他节点/Alpha的LMDB可达性、同源路径和环境/权限需独立证明；不假装原大LMDB已可搬迁。

建议最少补一个独立namespace的五个组件，而非重写科学：`prepare_pm7_cache.py`（整分子roster/HOF标量对齐）、`run_pm7_cache.py`（复用冻结数学、PM7-only worker）、`cache_io.py`（当前guard/once产物/失败前缀及typed DATA）、`reduce_common.py`（精确Common筛选与聚合/最终顺序对接）、`test_pm7_cache.py`（fixed-index/proper rotation、0.5边界、缺HOF、跨group覆盖及缓存失效/ID等价）。原profile源码保持冻结；全量S′/N1扩展池集成另列明确接口，不用PM7-only阶段冒充完成。

## 8. 本次读取源码SHA

| 来源 | SHA256 |
|---|---|
| statistics_v1/prepare_profile.py | `e1175c45d6d25842a4a19fea2c1bb87cfd1288f54e3ef33b29410b4020fbe189` |
| statistics_v1/profile_common.py | `ae642a210ba23e11125254790569ce308a090f7e872f86b4f7164170819f7039` |
| statistics_v1/run_profile.py | `35a239330bf4378750aa29b1b08ffca8e422c4c4eb4d508571045a97437d8072` |
| selection.py | `41f21f5586c06f3c6fd7cfa9712623adc8091da996c72f6d71170dd4b716e2cb` |
| statistics_tools.py | `22422b92fde096a64c019683cf265514b99351b002fa8bc450f6eeaf932808ed` |
| legacy dataset_without_charge.py | `d921db47a01c12d3cd0d21db0b74ad04c7fc8d6346dddd4b9ff04762b7a7d752` |
| legacy build_lmdb.py | `11a63d08752c0dc8b28b3ebc8174640a859d1486809baaaab3c458d89c50871c` |
| wp0_inventory.py | `dae1d25ade45719eb8a393dc83daec8853dc85471a3d2d6ead9520cf9b4a60c7` |
| wp0_unassigned_inventory.py | `f03467ca0c4d3d020ed51cd2320e92174ebf6f73324100c32a704793efca450b` |
| 历史固定科学sprime_v6.py（配置/实际profile绑定） | `d6f1d29a6de673a1faf186e095c4fef7534a81022a09a4840ec65e5d8fa424d3` |

本报告只给审计结论和有限后继方案，没有创建上述新实现、没有提交新的probe/全量作业，也没有签发Common、int64、D7全量或生产质量PASS。
