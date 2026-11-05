# N1 第二 UFF 的几何域与晚到人口：静态接合审计

SOURCE FINAL / STOPEDIT。只读源码及既有小 metadata；未执行 Python、AST、测试、SSH、Slurm、QM/UFF，未打开 canonical/Parquet/LMDB/packet 正文。以下是接合方案，不是实际 Common、物理 ID、全部 N1 或 D1/D5 放行。

## 结论与已确认接口

保持 **PM7 原 N、普通 S′ 补齐目标 N**；N=1 的第二真实 UFF 放在独立 P′ 扩展几何域/sidecar。D1 的 `geometry_source` 仍为 `uff_sprime`，不能自行增加第三个来源 enum。域/使用清单与化学来源是不同层：同一个 baseline 物理几何只存一份，普通 S′ 训练清单保留原 N，P′ 计算清单可引用 baseline 与真实第二几何。把第二几何直接并入普通 fill 包会拒绝，直接并入普通 D5 全部 UFF base 集则会改变 N1 的训练构象集合；两种做法均不合适。

下表源码路径相对 Root `repository/workflows/data_v1_final/`，`docs/`路径相对repository；行号为本次实际读取源码行号。

| 来源 | 确定事实 / 接合限制 |
|---|---|
| `conformers/formal_cpu_auto_v3/finalize.py:59–66,210–217` | `merge_counts` 对补齐结果要求 `old_count + generated <= S_conformers`。这是普通 fill 的边界，保留。**该检查不等价于对所有 unchanged old rows 全局断言 old_count<=N**；晚到名单仍须读最终实际计数，不能假定原 233 全为零 baseline。 |
| 同文件 `:35–41,262–263,269–320,338–342` | 只接受普通 fill origin；导出 N1 pending、普通物理 map/identity，明确 orders 未冻结。没有读取 N1 source sidecar。普通 old map 的 `geometry_sha256` 列 `NULL`（`:274`），不得把这个占位当已核 SHA。 |
| `conformers/n1_pprime2_source_full_v1/contract.py:159–180` | 分开要求 PM7/source_N=1、accepted_baseline=1、UFF_desired=2；当前旧 baseline 必须实际 `sprime_conf_idx==0`，且 seed 不等于新 seed。 |
| 同目录 `core.py:145–158,160–161,210–227,247–261` | baseline 规范行 SHA、原子序及真实 f64 geometry SHA 留存；实际候选仍10个，extra 自带 native ID/geometry ID、seed/candidate、UFF能量、RMSD与 fallback。`original_PM7_pointer_count_changed`、`original_Sprime_count_changed` 都为 false。 |
| 同目录 `planning.py:15–35`；`reduce.py:84–99`；`n1_pprime2_source_close_v1/reduce.py:174–191` | N1 结果是 source-only；physical extra int64 明确未分配，最终 Common/reference 未签。既有已闭合批次只能证明其真实成员，不能外推4631全部完成或全部最终Common。 |
| `docs/interfaces/training_format_v3.md:19–33,46–63,93–101,153,158` | PM7/UFF各自身份；UFF int64物理索引；P′是P组的UFF条件、独立D4；同来源三种顺序，P′计算前两个与训练/诊断清单分开；契约仍 draft.3。 |
| `export/pipeline_v1/materialize.py:17–25,56–76,123–132,156–172`；`materialize_v2.py:15–16,57–58` | 两来源 enum、UFF非负整数物理键、base唯一、三种顺序完整置换；view是实际扰动子几何，与对应UFF parent用同一物理构象索引。诊断同时排除 base 与 child。 |
| `export/wire_v1/sampling_projection_v1.py:48–53,80–119,136–154` | opaque geometry_id可作模型locator；UFF仍必须有实际物理索引，且两来源分别排序。当前D5/投影无独立“普通S′ vs P′ extra”的条件成员轴。 |
| `pprime/formal_common_v1/prepare_v1.py:78–85,93–126,179–203,279–290` | 当前正式候选 planner明确拒绝 opaque/null N1扩展、未知N1审计namespace；gzip reader只认 `packet['conformers']`。N1的 `packet['supplement']` 不能冒充这个旧格式。 |

## 最小新接合方案（需独立 CPU 实现/Root review）

1. **只读闭合与选择。** 从真实最终 Common manifest/membership/普通 physical maps、完整 S′ completion，以及实际 N1 registered terminal close/reduction 导入。保留失败/TIMEOUT/UNKNOWN和各 endpoint 会计；无包或身份冲突不分配 ID、不重跑。只取实际 Common 的有效 N1第二几何。未入Common的源包仍保留，列为未选，不删除。

2. **一个物理 catalog，分开的使用域。** 新独立 manifest 绑定普通map及 `pprime_n1_extra` sidecar；普通PM7/S′成员和counts不回写。sidecar保存 `geometry_source='uff_sprime'`、独立 `identity_namespace='data_v1_n1_pprime2'`、native extra ID、原packet geometry ID、taskKey/seed/candidate、origin endpoint/UID/job/worker/start/claim/source refs、真实 f64/atom-order SHA、baseline物理映射、原0.5Å唯一数/真实行数/fallback。

   baseline 的 `accepted_sprime_source_row:...` producer ID 与 finalizer 的 `uff_sprime:sha(mid:idx)` **不是相同字符串**。通过同mol、原物理idx、源完整ref+行定位、完整 baseline row SHA、seed/atom/coordinate SHA建立显式一对一 alias，不复制第二个baseline。extra 已有 opaque geometry ID可保留为新canonical候选ID（全局碰撞校验，规则独立冻结），同时保存全部producer ID。

   新 int64 必须晚于同mol **全部历史 attempted ID、普通fill实际物理ID和已登记额外ID**，检查重复/溢出；不能用候选 rank、包中第1行、`candidate_id`或“总是1”替代。复用原 `identity.py:14–42` 的非负int64/稀疏追加边界，另立 N1 namespace，不冒称 `data_v1_fill`。当前只提出规则，不生成任何 ID。

3. **第二UFF是新的 base，不是扰动 view。** 对extra的D5几何行应 `parent_geometry_id=None, view_id=None`。N1包 `expanded_view.view_id='pprime_parent_expanded_v1'` 是两构象扩展集合的标记，不能直接填入D5的物理view字段。`baseline_geometry_id`只是生成溯源。以后真实 noisy child 的 parent才指各自baseline/extra，保存真实扰动coords/SHA/seed与同一物理构象键。

4. **冻结新域的顺序与使用清单。** 普通S′仍用原物理ID/原N。P′ expanded域对baseline+extra按已分配物理int64、原source字面值`uff_sprime`和seed20261025生成fixed_random/energy/diversity三份置换；energy仅用对应UFF能量，distance用原固定映射proper Kabsch。N1包原native顺序用 `0`和字符串`n1p2:seed:cid`（`contract.py:224–227`），其哈希结果不保证与新物理int64顺序相同，必须保留为producer provenance，不能谎称已是最终order。

   单独保存 `ordinary_sprime_training`、`pprime_compute_first2`、`pprime_training_after_diagnostic`成员/顺序引用。**现D5没有这个条件轴**：`materialize.py:170–172`按全部base做训练集合，`export.py:229–257`按source/view导出。最小先做独立P′计算sidecar与新有界reader/planner；最终训练导出需共同契约显式接纳condition/domain成员，或独立P′条件入口。不得直接把extra塞进普通D5来偷偷令S′ N=2，也不能把extra伪装成view绕过base计数。

5. **读取与审计接头。** 新独立adapter识别真实N1 `supplement`，做有界gzip/CRC/完整packetSHA与f64坐标SHA读回、graph/stereo/seed/claim/start/actualterminal parent核验。可在CPU物化只含合法额外几何的f64 sidecar Parquet，以原packet/成员指针保留证据；不改旧reader或给旧`conformers`字段造假。跨端点身份用 `(endpoint,UID,job)`，不能用同名sonmi或单独UID；Alpha来源须另经真实部署/输入映射/返回验收/import协议，不能冒用Main1278 proof。

`pprime/geometry.py:12–23` 与 `conformers/common.py:173–179` 均为 LE int64 Z + LE float64 xyz SHA；coordinate-only SHA另存，勿混名。`pprime/geometry.py:56–66`明确 adapted energy=None、Q02=N/A；PM7原geometry HOF、UFF能量和UFF几何上新算PM7单点HOF是三种上下文，不串用于排序或差值。现15个协变FAIL/2000及full HOLD仍有效；本方案不放行新QM。

## 晚到 N1：不能用4631替代最终Common

原prepare `prepare_cpu.py:158–194`先统计全5105 `S_conformers=1`，按role/PM7严格可用/unsupported/真实baseline计数等原因分解，eligible4631只是有合法旧baseline1的子集。233 `ACCEPTED_BASELINE_COUNT_NOT1` 的实际0、>1、恢复/排除分布不能预分配。

在真实全部S′completion与最终Common存在后，CPU建立 **整个 `common_population AND S_conformers=1 AND effective_role IN(TRAIN,VAL)`** 清单。按实际final物理UFF、N1已消费ledger、packet验收及源任务键分类：已有合法第二包；真实原有≥2（须检查独立geometry身份/计数异常）；恰1且N1 key未消费的late eligible；已消费UNKNOWN/CONFLICT/pending不可重试；输入/几何验证失败。逐类别计数守恒，同时输出原5105/4631/233交集计数。原`pprime_n1_pending.parquet`只是一条普通S′数量提示，未关联真实第二包，不可单独当未生成名单。

late候选必须重读真实final baseline来源和PM7单指针。恢复baseline可能是普通fill的非零稀疏ID和生成来源；现 `contract.py:176–177`、`planning.py:19`、`core.py:157–158`固定旧baseline idx0，不能把恢复baseline伪改成0来复用。需最小独立late source validator/authority，保留真正baseline物理ID/seed/来源、原科学函数/10候选/原N1 taskKey和seed域，校验共享once账本以及Main/Alpha明确归属；已消费键绝不通过新namespace变成可重试。Root再批准实际未消费人口，不把233全量当授权名单。

## Root最少实际证据

- **现有小footer证据已足以反证“必缺canonical_smiles”**：`control/source_schema_probe_v1.json` 11742B SHA `16b54ea1b468733c366c94bb1b5778e1a7d9ca7ec72dbb7f625edbef5701d5ba`，记录compute-0-20、同1242386629B canonical路径、11231854rows/86RG，含`canonical_smiles:string`及`smiles/isomeric_smiles`。它没有当次新CPU全SHA/完整会计链；保留历史事实，不升级当次完整性证明。
- `control/sb2_sprime_footer_schema_v2.json` 6527B SHA `11b4ca8cde4d57e760fe1daada46055cde1b8039d42898c2296abad783dc0547`，五旧S′part均有`idx:int64`、f64 coordinates、seed:int64；仅footer，明确不重hash data pages。未来CPU只需保存当前精确refs/稳定frame/实际schema小receipt，并与既有canonical当前SHA验证及真实source authority绑定。
- 最终Common header须有真实parent/proof/C0、完整90069 completion+outcome refs、roles hash、最终membership/physical identity refs、PM7和普通S′分role计数、exclusion gate含Se例外、未解决数量、orders/map真实freeze状态。不能造未来Common或把source-only N1 receipt升级。
- 最小CPU审计receipt：全Common N1计数及上述分区守恒、原233交集、源/最终baselineID与origin交叉计数、重复mol/key/physicalID/SHA冲突计数；重读每个实际选中baseline/extra的f64 SHA与源ref，native ID→最终int64→order三方一对一；每个owner endpoint/UID/job与真实会计链可追溯。不能在login打开名单DATA或packet来完成它。
- `control/n1_actual32_pilot_science_cost_root_review_v1.json` 4143B SHA `1c19465dcf6a642097c8181e87aa06f3d3b9ced18e1ebb03f35c7c2b629cd2b7`：真实32包/30 unique2+2 fallback、全部SHA读回；本身明确source population不是finalCommon，不能外推剩余源人口。

## 独立发现的未执行 finalizer 技术缺陷

Root刚复制、尚未执行/注册的 `formal_cpu_auto_finalize_mapping_v1/finalize.py:143` 新插入行缺换行，使原`import pyarrow as pa`落入行尾注释，且原`import duckdb`缺失。adapter的理想transform包含这两项import，因此CPU source inverse本应在正文前拒绝实际坏文本；不能声称v1已可运行。此为本child源生成错误。冻结v1保留不用，另新v2从原v3精确派生，显式AST核验实际import绑定及完整inverse，并等待Root8纯CPU测试。该未执行源不影响任何已完成S′/N1 science或独立wave2 close_index结果。旧10/5/3交付字节保持STOPEDIT。
