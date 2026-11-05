# 去污染输入接口盘点（Source / 小 metadata）

当前 `configs/data_v1/decontamination_sources.json` 的11个来源仍全为 PENDING；这不是各源实际计算均未完成的声明。严格消费器 `workflows/expansion/decontamination.py` 只接受 `source_id, role, subdataset, inchikeys, non_h_composition`；READY 还要求版本、raw/identity producer refs 与 coverage 完全绑定、全部声明角色/子集、独立全源行数及 unresolved-without-key-or-composition=0。单源READY也不能放行全11来源索引或候选池。

| 来源 | 已核实际证据 / Source | 到严格消费格式仍缺什么 |
| --- | --- | --- |
| Kraken | Root 给定 `control/kraken_decontamination_projection_actual_acceptance_v1/kraken_READY_source_candidate.json`：4524517实际C0后1552行 strict identities/coverage 与独立Root接受 refs 已齐，保留原22839关系和全部差异/多键 | 只需Root在适当的全来源配置版本中采用该现成candidate；不重做原图、union或Kraken consumer。全来源配置目前仍PENDING。 |
| Drugs | `control/root_actual_drugs558002_native_union_acceptance_v1.json` 明确接受4523818 C0/1579s/16CPU14、全部558002 native（1000采用+557002新），633101上下文、75099名称、290多SMILES；unknown0，126差异/31名称全并集保留。现有87MB name union有完整producer triple | 现有 `native_graph_full_v1.cache.FullNames`/profile `reader.export_names` 输出原生/来源union与原名/计数，不是strict5field。已查Source索引/确切源文件未找到Drugs合法strict导出器；需独立只读投影、CPU全读回、coverage、真实C0+Root接受candidate。此项可直接推进。 |
| TDC | 真实1757小receipt：44成员/22endpoint、81809物理行，81807 FULL_KEYS_DERIVED+2 ORIGINAL_SMILES_UNRESOLVED；journal114667955B。1907诊断及独立 `secondary_tdc_exact2_composition_v1` 已有源码；Root历史报告exact2实际C0 | 不能把2 UNKNOWN改成已解析图。需要实际exact2 composition小父件/明确Root采用与81809 journal的精确member+ordinal连接，再做train_val/test、全22endpoint strict导出与coverage。当前未获得最新Alpha接受refs，不能据Main顶层无文件推断未执行；不重写原诊断或再跑key。 |
| MoleculeNet | `csv6_full1884803_actual_closed_summary_v1.json`：六源1162144物理行、technicalerror0、旧blank/invalid/duplicate/zero IDs均保留。既有 `secondary_csv6_newline_diagnosis_v1` 已专门解决字节观察入口，不能重复新造。已有native4 full/27 index extractor、QM7b composition Source；Root报告57480原生上下文、27PDB、QM7b2013证据在Alpha | 六CSV不是全17子集；其 `ALLSPLITS`/观测字段也不是strict5field。需要最新Alpha实际newline/native4/27/QM7b父refs与Root采用、全17版本/子集映射和完整身份/保守组成导出。早期六CSV观察中572146短行不证明原因或有效分子数，不能自动丢掉、补key或用technicalerror0冒identity READY。QM7b V3作者同集合组成与2013原件不能冒精确MAT行映射。 |

Drugs 最窄桥接已由Root在本轮授权实施为新 `workflows/expansion/marcel_drugs_decontamination_main_v1`，不改旧源：

* 唯一CPU DATA：`artifacts/expansion/marcel_drugs_native_graph_full_v1/full_v1/all_CSV_names_all_source_and_native_full_key_unions.jsonl`，87064062B，SHA256 `3741dbb7c169e4c05b98b19137118de8c63dd8f9a888495a6f4ed0b988e52bc0`。继承实际Root接受、full receipt12854B SHA `d5bb5dcc832926579c1f8ed36ad52b8e2fb2aecee1c9c77a6c758b5d1e7b56a2`、account1049B SHA `285071983af324f2eddfc5ec28787928674fa344c216f12a9ede0729e44cde41`、原plan/proof/来源父链。3.48GB journal、1.69GB raw blob、259MB ZIP不需重新图解析。
* 保留全部source/native full-key union，用原 `identity_v2.projection_v2.full_keys`、`decontamination.identity_keys` 和 `common.wp5_key` 复核；不得挑代表、折叠差异或重建图。source_id明确为archive SHA+原CSV物理序号定位；原名字段/原native关系由原union DATA行段定位保留。role=`all` 是消费范围，native split仍未知。
* CPU完整same-FD SHA/EOF/frame核验，75099序号与严格identity读回、558002 conformer求和、unknown0/126差异31名称/290多SMILES守恒；新provenance/coverage与READY candidate只经真实C0及独立Root审阅产生。
* 直接复用已实际C0 Kraken consumer的严格JSONL IO、闭合API模式、原Writer/Budget对象；新1800s以内/16CPU/no_mem/512MiB/200GB+future reservations，3个有意义合成IO/守卫方法。无下载、图/SDF重解析、QM/UFF、新队列或自动提交。

此盘点仅读Source与明确小metadata；Source索引查询按Root明确指示使用Git ls-files，未运行AST/Python/测试/科学DATA/SSH/Slurm。两条过宽的Source/control检索已仅终止自有进程，未动挂载/他人；其部分结果不作为全树“没有实现”的证明。TDC/MoleculeNet最新Alpha小父refs待Root回补，绝不以未定位冒称未完成。
