# 全原人口 source-status 审计 v1（待真实执行）

本轮可以独立于尚未冻结的common推进：原population、latest COMPLETE且receipt_context_consistent/export_published的owner、ROUTINE角色已闭合。仅观测原始来源，不过滤label失败、不依赖S′资格、不改变标签或新增mask、不拟合TRAIN尺度，不发布最终D2/D4。

本目录6个Python文件和本文均为新文件；既有streaming、EA、normalization和queue源码/config保持原字节。当前尚未执行本目录的AST、8项fixture、metadata materializer或任何真实源扫描；以下是可审阅入口及预算，不能写成PASS或全人口已完成。

## 人口、源与14个任务

权威均由materializer实际读取小metadata并核pin生成config，不用下文口述数字重建source refs：

- `configs/data_v1/labels/streaming_v1.json`只提供既有闭合authority pins；不继承其mask或统计结果作为新结论。
- catalog最终D20 failure-aware verification → `control/sb3_catalog_projection_v1/source_files.json`及projection_receipt，约1MB/2024文件；catalog3.5MB、formal_record_index1.24GB、latest_molecules30MB仅作为locator，metadata helper不读/不stat正文。
- `roles/routine_v1_job4520334/manifest.json`及16个molecule_roles分片：TRAIN1206608mol/11104772records，VAL7610mol/72525records，FULL6248mol/54557records。共1220466mol/11231854records。VAL是原ROUTINE；原TRAIN不重切。source_role与effective_role按冻结角色分别核验。
- canonical身份完整绑定record_id、molecule_id、attempt_id、job_id、task_id，量化行额外核lane/natom。ordinal是formal_record_index精确物理行号0..11231853，不是过滤后编号。
- 原registry_v2的756条物理/QC/metadata定义全部留inventory，包括故意未序列化/不在14任务scope的字段；registry_v3的264组件保留146enabled、103NA组件（63个原字段）、10原常数删除、5legacy inactive四类，均不重新分类。

| 家族（每家族184文件） | task | canonical行数 | 压缩源文件字节总量 |
|---|---|---:|---:|
| D20 | D20 |11231854|405034471|
| D3 | D3 |11231854|5618600593|
| pm7_neutral | pm7_B |11231854|375922258533|
| pm7_ions | pm7_anion、pm7_cation |22463708|35103382571|
| pm7_solvents | pm7_octanol、pm7_water |22463708|35103584001|
| xtb_singlepoint | xtb_singlepoint |11231854|22392882314|
| xtb_vipea | xtb_vipea |11231854|5502349100|
| xtb_vfukui | xtb_vfukui |11231854|6513351238|
| xtb_alpb | xtb_ALPB_octanol、xtb_ALPB_water |22463708|8291212077|
| xtb_fod | xtb_fod |11231854|10294753268|
| perturbed | xtb_perturbed_gradient |11231854|58384422831|

共171个source job、184个(job,file-group)、2024个文件。原文件物理行157254650，canonical157245956=14×11231854；其中12量化槽134782248，D20/D3槽22463708。8694个非canonical物理行另列RID不在authority或非latest owner等原因，另保留status/SCF计数，绝不静默丢弃。任何canonical重复槽/缺槽/role不符/物理行总量不符均不能接受全覆盖结果。

563531830997B是全部压缩源文件大小上界；首轮仅投影量化CELL metadata，不能把这个大小称作实际读取量或据此宣称运行时间已测。

## 实现与输出契约

`prepare`在真实64GiB/16CPU严格队列中校验population/latest SHA，DuckDB12GiB＋spill8GiB构造canonical索引，4096条一批写单个只读SQLite，保存原role/natom/owner。每worker只读16MiB SQLite page cache，256条RID批量查，不把整owner或全人口变成16份Python字典。不读取原LMDB/SQLite scientific store或base_geometry。

按每物理source file派发，LPT平衡原行数和压缩源大小到16片；各片至少16个真实文件任务。每个worker只打开一个ParquetFile并跨所有batch复用，try/finally关闭，Arrow CPU/IO各1，3GiB worker RSS止步。每片首16任务barrier保证16个实际source worker，失败只停止下一batch/file、不强杀、不自动重投，partial证据保留。此处避免EA旧版逐row-group重新开footer导致的真实内存增长。

量化首轮只读CELL registry_id/kind/declared-shape，明确禁止投影f64/array_f64/text正文。D20/D3读取其原生小布局，仅观测已有NULL/列表长度/源valid_mask，不计算新物理值。逐file报告：

- role/task/status/source_status/converged三态/SCF NULL、正、零、负、非整数/failure/software_version以及raw选择/locator存在性的交叉精确计数；raw locator存在不等于archive实际读回。
- 全原registry CELL的NULL/ABSENT/kind、声明shape、numeric_issues已有标记、precision metadata声明。数组的实际payload长度与JSON内部布局仍UNOBSERVED；声明shape中其他变化维度聚为OTHER，保持rank/常见轴观测，不能称完全物理shape验证。
- storage Arrow schema及Parquet每leaf物理/logical dtype；double载体不证明原生float64，更不证明原程序打印精度。precision_by_field_json只是来源声明；缺raw、未映射/格式错误/变体超64均显式留出，绝不反推打印小数位。
- ordinal/task/role/review_flags紧凑coverage ledger，正常numeric原值不复制。NULL收敛、z规则和已有source numeric_issues不升级成新失效；这里没有新物理阈值、没有mask。duplicate CELL、unknown registry、声明shape非法仅列结构性review，canonical覆盖重复则硬失败。

`reduce`独立读取原角色索引，对14×N的uint8磁盘ledger逐batch去重/核role，要求每槽恰好一次；聚合全部源和非canonical行。输出raw_registry_inventory、264component_observations、field_declaration_map、全覆盖ledger和audit。NA/常数/legacy是旧声明，常数零及NA值未重算。只有全部片闭合后才能标`SOURCE_METADATA_CENSUS_COMPLETE_PAYLOAD_AUDIT_PENDING`；`guide_1_5_completed=false`始终保留。

## 实测依据与资源预算

旧4520374实际C0/34s、16worker、512mol/4251records；对应209个源文件/200998物理任务行/970140107B，真正用于统计的canonical记录只是4251。峰值RSS16worker之和4408647680B、最大347058176B，输出11620283B。这个优先低I/O的选样不能代表全人口或本新pass。旧4520344逐叶复制40记录输出1604722B也不能全量外推。

EA IO v4实际4520570 C0/20s、7cases/14contexts/16worker，maxRSS385368064B，96opens=96closes/5560reuses/max1handle。它验证一次开文件的实际内存收益，不是本pass的全源性能测量。

新pass实测成本仍UNMEASURED。每个真实stage均16CPU/64GiB、普通全用户声明85%、exclusive=user、CPU允许节点2/8–19，guide/site严格wall≤4h；默认prepare2h、每scan2h、reduce1h。16片的allocation上限560coreh（不是预测）；超过500须先真实第一片闭合，Root根据新pass实际IO/RSS/时长/output接受整批预算，再排剩余片。fixture不是该真实证据，不自动批量提交。

输出硬cap：prepare24GiB（包含SQLite/spill/partial）、每scan2GiB×16、reduce4GiB，共60GiB；每file预分配64×canonical_rows＋4MiB，第一轮metadata materializer根据真实清单给每片精确reserve。每份stage request保守声明整个60GiB，另至少留200GB账户quota；不是整磁盘df。scanner只允许新目录，不删除或覆盖partial。SQLite/coverage/scratch均计unique inode，不隐藏临时开销。更多时长/内存只能由实际测量后新受审请求，不改旧配置。

## Root实际入口（本代理未执行）

先拷贝/整合这7个文件到实际Root repository，再由Root做AST/source checker及8个增量fixture：

```bash
/share/home/zixiao/.conda/envs/chemprop/bin/python -B -m unittest \
  workflows.data_v1_final.labels.source_status_v1.test_semantics
```

materializer纯stdlib，小pin≤2MiB，仅读小JSON/code，所有大数据只继承exact locator；不提交任何作业。运行于Root实际路径、PYTHONPATH包含Root repo:deps：

```bash
PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
REPO=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository
RUN=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025
$PY -B -m workflows.data_v1_final.labels.source_status_v1.materialize initial \
  --repository "$REPO" --output-directory "$RUN/control/source_status_v1_initial" \
  --artifacts-root "$RUN/artifacts/labels/source_status_v1/full_v1"
```

得到config、真实source/task/shard成本计划及prepare_spec；需Root新nonpilot队列materializer。冻结queue_v1.materialize明确只接受pilot=true，**不能伪标pilot借用**。科学CLI由spec完整列出，实际startup proof占位符仍沿Root现有机制，生产guard再次核实际16CPU64GiB/current job/源pins/freshproof。

prepare真实C0并核manifest后，只先物化第一片：

```bash
$PY -B -m workflows.data_v1_final.labels.source_status_v1.materialize scan \
  --repository "$REPO" --config "$RUN/control/source_status_v1_initial/config.json" \
  --prepared "$RUN/artifacts/labels/source_status_v1/full_v1/prepared/manifest.json" \
  --only-shard 0 --output-directory "$RUN/control/source_status_v1_shard00"
```

第一片接受后，Root可用`--only-shard N`逐片物化，其SCI argv为`...source_status_v1.scan --config CFG --plan PREPARED --shard-id N --output NEW --startup-proof PROOF`。省略only-shard仅生成全部spec，不提交。16个actual shard manifests全部C0/closure后，materializer reduce重复传16个`--shard-manifest PATH`，生成独立reduce_spec。新nonpilot observer要覆盖所有新job的身份和freshproof，不借旧4-job观察列表声称已监控。

## 尚需真正完成的1.5与单位/frame审计

后续独立受预算payload解析pass必须读原数值array/text，验证声明shape与实际数组长度、atom/pair index和compound组件布局，重核10常数现值/63NA原字段可观察状态，完成每field SUCCESS但缺失/shape/finite的真实联合数值审计及物理/交叉/同分子异常复核。原值、mask和统计population仍分别绑定；新增异常mask>1%规则保持硬停，z>20只review。真实raw保留部分可做程序原生precision/parser读回；未留raw的来源不得写“已证明未收敛/程序失效”。EA8791的既有7case诊断未提供此因果证明，SCF NULL不是失败阈值，GFN1 VIPEA与GFN2 SP不能当同Hamiltonian能差。

MolMR最终数值单位/原RDKit19项生成runtime、Fukui单位convention、原生F32量化、AO sigma/pi basis、dipole/quadrupole原点和实际输出frame仍未冻结，保留既有D2 proposal及pending证据。最终common+effectiveTRAIN+精确PM7/S′诊断geometry_map/order未齐以前，原TRAIN median/MAD/size试点不冒充最终D4。P′仍是独立来源、独立统计，不用P值代填。