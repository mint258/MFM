# D7 canonical WP5 HoF来源审计（SOURCEFINAL）

日期2026-10-27。只读冻结源码、原registry和实际小metadata；不读task JSONL、record owners Parquet、LMDB、molecule packet或任何标签payload正文。无Python/AST/测试/SSH/Git/Slurm执行；不新增数值容差、mask或科学规则。精确实际metadata/source引用、19个实际source observation、原始owner/index DATA locator见同名_refs.json。

结论：**可以建立canonical pm7_B registry60 HoF的来源权威，且有真实256分子/1344记录的闭合读取证据。它来自WP5 MOPAC解析叶，不来自LMDB energy_raw。当前新geometry-only cache32的203条记录尚未由本审计实际读取或验证HoF，仍pending。**

## 字段定义与生成链

原label_registry_v2.json（438523 B/SHA b1a74b7a1fc27b0173dc837cb00de568991309b7ed8157e7c354b65df122654e）的registry_id=60精确为：task=pm7_B、source_path=values.heat_of_formation_kcal_mol、method=PM7、charge=0、context=gas、geometry_context=native_original_PM7、unit=kcal/mol、classification=physical_label。非native旧能量别名、非xTB total energy。

冻结wp4_parsers.py:125直接从MOPAC输出的FINAL HEAT OF FORMATION = 数字 KCAL解析该值；wp5_parser.py:14–21固定并校验此legacy parser SHA66938afa8d3d7b7f51e8922c875c0987687a865a97cb1591d6f6c511b38098e0，parse_mopac:58–61直接沿用其数值解析。WP5协议pm7_B使用PM7 1SCF XYZ ... CHARGE=0；expected_versions声明MOPAC23.0.3。具体打印精度不可仅由最终Parquet double推断。

wp5_parquet_v2.py:112–119按registry的source_path从detail/values取值；encode:51–63将原Python float存为CELL.kind=1、f64，逐CELL encode/decode exact校验。该编码是来源链的一部分，不是把energy_raw重新命名成HoF。wp5_engine_v2.py:338把旧native energy放在独立old_energy字段，而任务结果来自NATIVE.invoke；二者不是registry60的同义字段。原XYZ/LMDB energy_raw只保留原来源语义，不能凭名称、单位猜测或数值接近升级为HoF。

## 实际canonical读取链

冻结Root statistics_v1/profile_common.py（7209 B/SHA ae642a210ba23e11125254790569ce308a090f7e872f86b4f7164170819f7039）当前物理bytes/SHA与真实4520383请求登记相同。prepare_profile.py（11261 B/e1175c45d6d25842a4a19fea2c1bb87cfd1288f54e3ef33b29410b4020fbe189）及run_profile.py（13503 B/35a239330bf4378750aa29b1b08ffca8e422c4c4eb4d508571045a97437d8072）也逐SHA匹配其原实际请求，没有重写旧科学版本。

- prepare_profile.py:48–56实际验证latest-owner receipt的30,233,309 B DATA pin及catalog/projection/verification小pin；:69只选state=COMPLETE、receipt_context_consistent、export_published的owner。formal记录与该molecule owner绑定attempt_id/job_id/task_id/lane，形成1344条原record pointers。
- :114按family=pm7_neutral、source_job_id及原file_group筛选producer文件；:119并行调用read_hof_file；:120–125拒绝跨文件重复并要求set(hof)==set(owners)。不会以原native energy补缺。
- profile_common.scalar_columns:91–101精确投影record/molecule/owner五键、lane/natom/calc_type/status/numeric_issues/converged及values.list.element.{registry_id,kind,f64}三个叶；缺叶拒绝，不退回读取整个values，不读array_f64或text列。
- read_hof_file:128–153只允许producer已有inherited_full_readback_verified的pm7_neutral；过滤完整(record_id,molecule_id,attempt_id,job_id,task_id)，另核lane/natom/source_job_id，拒绝重复canonical record，读前/读后核file identity。历史attempt不是当前owner，不能混读。
- decode_hof:104–125要求calc_type=pm7_B、恰好一个registry60、kind1/f64且有限、registry60无numeric_issues；SUCCESS或PROPERTY_FAILED的字段级可用值保留。converged=False无效；converged=NULL保留HoF、convergence_null_review=true，不当作电子失败。NULL值、absent、重复、非float/nonfinite、坏status分别给reason，合法0不冒充缺失。
- run_profile.py:83–85从task.hof[rid]取真实HoF作能量；缺HoF保留几何/random，energy及最低能起点diversity unavailable，绝不回退energy_raw。

SCF元数据本身由wp5_scf_metadata_v2.py:37–103从实际输出电子迭代/终止标记提取，不由进程exit/status成功推断。缺实际电子输出、未明确报告所有stage或计数不可得会留下NULL/missing_reason；scf_iterations=NULL也不自动等于converged=False。D7上述NULL语义与之相容。本次256 profile的NULL-review计数恰为0，只是该实际范围事实，不代表全人口均无NULL。

## 可直接绑定的实际小证据

以下路径相对RUN=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025；本轮对小文件重新读取并核SHA，完整表在_refs.json。

| metadata | bytes / SHA | 事实 |
| --- | --- | --- |
| artifacts/conformers/statistics_v1/prepared_v1/prepared.json | 32876 / 09960a447e2130b48fca6eded17a98b1da0ce5bfc74a922e77db387bb853cca6 | 4520383、256mol/1344records、15实际owner jobs、19 source observations |
| control/d7_profile_preparation_actual_closure_v1.json | 1866 | 父4520383 COMPLETED0、180s/16CPU；原tasks/owner table引用，不把其科学正文在登录重读 |
| artifacts/conformers/statistics_v1/profile_v1/receipt.json | 2149 / 7319dbad1317172ee03f26fd7b5f5721cdbeed0271a57584f4203f408be9009d | 4520390、256complete、errors0、newQM/geometry generation0 |
| control/d7_profile_actual_closure_v1.json | 1645 | 父4520390 COMPLETED0、40s/16CPU、640allocated coreseconds |
| artifacts/conformers/statistics_v1/profile_v1/profile_statistics.json | 2598 / 517e0969088bdfb95a1b1f2cb5d95fab36739d01445876f9debe33e213fc4fae | canonical_hof_complete_molecules256、hof_missing_reason_counts{}、NULL-review0、energy_units kcal/mol |
| control/sb3_catalog_projection_v1/projection_receipt.json | 1189 / 36cd80930322c9629f8687734aa6f918d28063ba825fa300c5eea0c3c197f3f0 | catalog＋D20-aware verification＋source_files的真实小pin；本projection无科学body读取 |
| control/sb3_catalog_projection_v1/source_files.json | 1010451 / 2ace0ded289e1bd63a16ea919cbae777c5bc177df3cc5924c983fb94dbcbeb5d | 2024文件按family/job/group的producer精确locator；HoF取pm7_neutral |
| artifacts/labels/owner_prepared_v1/owner_receipt.json | 9941 / 956515adb25e207540ed5a17d318f1c80ddee565225ab193864302b3eed21c3e | 本轮真实观测latest_molecules DATA pin，非伪造旧catalog已有SHA |

最新owner DATA为原catalog_closed_v2/latest_molecules.parquet，30,233,309 B/SHA c6ea21ab66b62415011fb71f475a803c895418d5a8b69a31302d7ac3805c1d80；formal_record_index为1,242,386,629 B/ef2d99ae1b6c1001f6ffeb979ebafd10b04c13fa4774e52527a90a6276c06276。D7 prepared产物tasks.jsonl为8,630,021 B/d4e057e6971fe4d844fb6cacb51f46147c36b879fc8d32b1d064fd62267895ab，record_owners.parquet为89,697 B/c51da82e20fd8058dac7e194d394cde3492bb91fbd210a6585808db7e5c814a7。这些仅DATA locator，本轮未打开正文。

WP5验收绑定：catalog SHA b5aed096ae0dc4c479a64b9b05e8709205911a0f9a474b71ae1490992ce28765；D20_failure_aware_v2_4515602/verification_report.json 1,442,624 B/ce9b58e988f66f8a402dc93eeb050a8f7b55317cfe37db3c3b1f08dd7b2045e5，status PASS、latest_closed=true、serious_schema_issue_rows0。其文字明确是原完整readback加D20针对性证据继承，不是该v2重新readback全源；957已知D20 QC保留，不放宽unknown失败。不能把这份继承报告说成本轮203 HoF再次读回。

19个实际source observations的producer文件bytes相加是**71,794,931,208 B**，不是实际storage read bytes：当时只投影3个typed scalar叶及必要owner/status列。1344行HoF真实读取/保存与profile闭合可承认；71.8GB整body本轮/当次已读、所有array精度已验或新cache32所需I/O成本已知，都不能由此推出。新32可能涉及不同owner/files，应从真实source_files按其实际owner/group重新选择；不能限用旧256的19文件假装覆盖outside256。

## geometry-only32之后的最小增补

Root已有4521593 prepare C0（32mol/203records，16 golden＋16 outside256），4521602为独立geometry-only run。本报告不越权宣布其terminal或HoF完成。原geometry-only缓存、其原key、random顺序、几何/graph/order bit签名与方向性RMSD矩阵保持原始只读。

已有pm7_independent_cache32_v1.prepare32.canonical_hof:9–60接入CANONICAL_VERIFIED模式：必须有Root独立VERIFIED_FROZEN_PM7_B_SCALAR_READER审查、真实latest-owner DATA、projection_receipt/source_files以及原registry60/unit/no-native-fallback。其实现直接调用未改profile_common.read_hof_file，并为缺owner、坏/重复源、资源STOP保留明确pending。适合新独立augmentation wrapper复用；不得将geometry-only旧review直接改字节成verified。

新wrapper只从实际C0 cache32的source_records取203条原pointer和natom，取真实canonical HoF；读取原cache的pair_rmsd_A＋pair_rmsd_record_ids，直接复用未改geometry_orders计算energy/min-energy diversity（random固定）。core.py:83–97已经保留每个有向pair及真实diagonal，不强制对称／归零；无需再读715GB LMDB、重新构图、重算几何或RMSD。新派生输出须引用原cache SHA与新HoF source/owner refs，保留common/physical/order release=false。16 golden与旧D7相同RID逐HoF bits和energy/diversity order比较；未知/缺失逐项留pending，不发明容差或以native能量顶替。

全值mask、源单位/原始打印precision、全source数值审计和最终common TRAIN D4仍各有独立门槛。此来源审计不替代它们，也不改变原HoF QC或最终导出授权。
