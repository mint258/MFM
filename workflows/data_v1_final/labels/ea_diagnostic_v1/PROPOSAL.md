# EA8791 的有界只读诊断提案

状态：新诊断尚未执行，不提出新 mask，不改 parser、任务状态、值或旧证据。旧 probe 已实证的事实与本轮待证假设分开记录。

## 已有实际证据

旧摘录 `runs/pretraining_readonly_audit_20261023_v1/reports/xtb_EA_actual_probe_closed_excerpt_v1.json` 和原 probe `reports/xtb_EA_sample_outliers_v1_4520167/EA_sample_outlier_report.json` 已定位以下七条固定样本。没有重新抽样，七条来自六个分子；不能外推全人口异常比例。

| record_id | molecule_id | attempt/job/task | EA / IP，eV |
| --- | --- | --- | --- |
| principal_01200001_01500000.lmdb:401413 | principal_01308749 | 0/4513984/25 | 8791.0184 / 6.817 |
| principal_01200001_01500000.lmdb:411535 | principal_01308749 | 0/4513984/25 | 8791.0184 / 6.817 |
| principal_00000001_00300000.lmdb:94634 | principal_00014116 | 0/4515374/10 | 5737.3021 / 9.5536 |
| principal_00600001_00900000.lmdb:1070786 | principal_00671474 | 0/4514439/11 | 5633.8674 / 9.0408 |
| principal_00000001_00300000.lmdb:25895 | principal_00004385 | 0/4514439/11 | 5545.9323 / 10.0017 |
| principal_01200001_01500000.lmdb:236073 | principal_01252963 | 0/4514439/11 | 5457.6039 / 8.7776 |
| principal_00000001_00300000.lmdb:12191 | principal_00002427 | 0/4514439/11 | 3308.3762 / 10.635 |

旧 probe 只为前三条补读了正式 family 上下文。前三条都是 SUCCESS/source_status SUCCESS、numeric_issues=[]、failure_code=NULL、SCF iterations/converged=NULL；两条8791的lane为18，5737的lane为11。原值与 sample/全TRAIN max一致，故不是仅 CSV 展示或统计汇总伪影。其余四条不能冒称已经核过这些正式状态。

前三条 `raw_audit_selected=false`、`raw_output_locator_json=NULL`。原实际 job 的 `run.json` 绑定 `wp5_engine_v3.py`、`wp5_archive_v5.py`，归档政策是 `FAILURES_PLUS_STRATIFIED_RECORD_AUDIT_NO_INPUT`。archive_v5.py:15–19,78–85 明确普通 SUCCESS 不插入 shared raw；engine_v3.py:375–385 在保留决策持久闭合后清理 scratch。因此空 locator 与当时保留政策一致，不能当作 SCF 未收敛证据。也不能把代码政策当作已经查询过这七条的 archive 主键；新 probe 将实际查证。

指南“约390条 SUCCESS+收敛为空”的确切总体、任务及去历史口径，目前没有在已定位的小闭合报告中重新建立。本轮七例诊断不会宣称重新统计390，也不能替代后续 canonical 全人群逐字段状态扫描。

## 方法、单位与可见性边界

冻结 protocol（SHA `3e831aa57d4d90376c6107e309484e231038a3536ed0f28371d2f8554149a6bc`）中，SP为 `--gfn 2 --chrg 0 --uhf 0`，VIPEA为 `--gfn 1 --vipea --chrg 0 --uhf 0`。两者 Hamiltonian 不同；不能用 SP 总能量严格代替 VIPEA 的中性态能量，不能将 SP gap 与 VIPEA 的 IP−EA 不同号单独升级成确定失败规则。

现有 physical registry 的 VIPEA 恰为751(EA/eV)和752(IP/eV)，没有导出任何中性/阴离子/阳离子总能量或电荷。SP有668(charges/e)、670(total energy/Eh)、671(HOMO/eV)、672(LUMO/eV)。新诊断读取 VIPEA 所有实际 typed numeric cells，并明确未登记的状态能量不是 NULL→0。原始 `process.out`、`xtbout.json` 若实际保留，才可进一步分离电子态；最后一个 TOTAL ENERGY 打印不默认视为中性态。

EA/IP冻结 parser 链为 parser_v2 → parser → wp4_parsers，取最后一个 `delta SCC ... (eV)` token，D指数转E并检查有限，没有额外能量单位变换或范围裁剪。新脚本保留 `precision_by_field_json`；float64容器不证明原打印精度或排除程序失效。D20原LMDB的f32源精度问题与这条EA解析链不同，不互相充当生成证据。

## 官方6.7.1源码提供的独立机制证据

以下是发布源码的只读核对，不等于已经证明冻结 conda 二进制由这些字节构建，更不证明本例触发了某分支：

- [main.F90](https://raw.githubusercontent.com/grimme-lab/xtb/v6.7.1/src/prog/main.F90)：526–535默认按GFN级别选参数；811–834分别调用带电态单点并计算IP/EA，EA采用 `Eneutral−Eanion−shift`；907执行错误checkpoint。不能仅凭`--vipea`名称把实际参数文件改称IPEA；实际raw参数头仍待证。
- [calculator.f90](https://raw.githubusercontent.com/grimme-lab/xtb/v6.7.1/src/xtb/calculator.f90)：231初始化energy为0；257–260遇环境错误返回。这只说明零值可能出现在某些失败路径，不证明任意极值来自它。
- [scf_module.F90](https://raw.githubusercontent.com/grimme-lab/xtb/v6.7.1/src/scf_module.F90)：607–611传播SCC错误，765–768为明确不收敛登记错误。
- [environment.f90](https://raw.githubusercontent.com/grimme-lab/xtb/v6.7.1/src/type/environment.f90)：checkpoint检查错误；fatal默认退出码1。

符号检验也约束假设：若中性能量为负且阴离子能量为0，按上述公式应得到大负EA。因此正8791不能直接归因为“anion能量为零”。“极端EA接近某一绝对总能量”仅供实际诊断比较，不触发mask；须先明确同方法、电子态、shift及实际失败证据。

冻结复现包给出的xTB executable SHA为 `271dd6cdd5da127a8e39919e7e32d924790fb346f0057b4183769ba8b3411887`，版本6.7.1，software_version_id=2；另绑定libxtb SHA `c405797f34ed96470f23158406e6d8a8e102681d3c3cbbaea16692f514f22853`。存在GFN1/GFN2/IPEA参数资产不表示本case实际加载了其中哪一个；实际raw和构建血缘仍有证明边界。

## Root 待提交的有界入口

`bounded_probe.py --config <新绑定配置> --root-preflight <Root新鲜intent> --output <新外部子目录>`。

配置 `configs/data_v1/labels/ea_diagnostic_v1.json` 绑定七个既有RID、六个确切 owner/family 文件，共737,661,761B的物理容器上界；不扫20万样本表、不扫原LMDB、不扫全WP5。先SHA核验小metadata与30,233,309B latest-owner metadata，只接受 latest COMPLETE/receipt_context_consistent/export_published 与原case owner一致。owner改变即停止要求重绑定，不静默切历史attempt。

六文件仅投影ID、状态/SCF、precision/source_evidence/raw locator以及CELL registry_id/kind/f64/array_f64物理叶；每批16记录，先Arrow筛七个RID才转Python，不转无关巨型CELL。按真实Parquet row group分为16个非空worker分区；不足16个分区在读正文前拒绝，不用空任务伪装并行。输出14个精确同record上下文及实际worker PIDs/源身份前后一致性；原科学文件SHA继承已闭合verification，不冒称本轮重新全文件hash。

随后只读打开三个已经闭合的原 archive，`mode=ro/query_only`，每RID/task按索引查元数据。以 completion receipt 的显式execution和owner context定位canonical调用，历史部分attempt单列，不用其raw替代canonical。只有匹配调用确实存在才使用冻结archive reader实际解压，核验raw SHA、input_bundle SHA、molecule及输出manifest，重提取实际SCF和原parser EA/IP，保存process.out/xtbout.json及有序energy/SCC打印证据。没有对应raw则报告证据缺口；不补造输出、不重跑QM。

普通node20 CPU分析：16CPU、32GiB、1h；每worker RSS观察停止1GiB、报告上限4MiB；source容器上限1GiB；raw单调用4MiB/总计16MiB；输出unique-inode上限64MiB，SQLite只读cache8MiB。新鲜quota和全用户声明内存85%守卫沿用冻结support。此预算是新小诊断的配置与推断，不是本诊断实测RSS，不影响size/full/final的64GiB要求。

新文件尚未进行静态检查或真实诊断，Root统一检查、源SHA登记和Slurm执行；不需要重复旧19/24/13套fixtures。完成后先检查projection/归档查找coverage与实际日志，再判断是否有可复现parser差异或明确程序失败。当前不提出任何新mask阈值。即使将来证明某条属性无效，也仅变更独立规则版本与逐字段mask，不删除record，且新增mask>1%硬停规则继续适用。
