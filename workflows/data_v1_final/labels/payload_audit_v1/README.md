# 原人口payload审计 v1：最小试点及同入口全量（待执行）

承接实际4521201全人口source-status归约C0/397s，不重扫纯status、不重建registry/roles/canonical index。本目录6文件均为新源码/说明；未运行Python、科学数据、AST、fixture、Slurm或SSH。旧源、旧数据、Model树不修改。

## 已知输入与待完成项

实际`auto_memory_v1/reduction/audit.json`为1038256B，状态SOURCE_METADATA_CENSUS_COMPLETE_PAYLOAD_AUDIT_PENDING；11231854records/1220466mol/2024files/157245956canonical任务槽，2024opens=closes，max worker466694144B。prepared manifest1182503B，canonical.sqlite1733042176B，均只继承实际pin。TRAIN/ROUTINE-VAL/FULL全部保留，common/diagnostic未冻结不阻碍本原人口审计，但不能据此发布最终D4。

当前metadata中SUCCESS且converged=NULL的task rows为xtb_vipea11228110、xtb_vfukui11226671（全role、不同任务，不相加当独立records）。NULL不等于失败，不能把这两个全量值和指南旧“约390”直接混同。8791eV既有案例未建立parser/程序失败因果，本轮高数值仅进可追溯extreme/review列表，不自造EA阈值。

下一最小真实CPU阶段直接使用既有`streaming_v1/prepared_pilot_v1/group_plan.json`：16owner/512完整分子/4251records，TRAIN4211+VAL20+FULL20，209files/970140107B/200998物理任务行。原选样未重新做、不按label/S′过滤；每条记录仍与新full canonical.sqlite核五键、lane、natom及角色。原试点偏低I/O，不能代表全人口。

## 复用与观测

- 冻结`common.decode_cell/component_values`：每原CELL只decode一次，严格prod(shape)=实际数组长度，JSON真实解析；实际原子/分子vector、Fukui、shell、compound和sparse载荷提取沿原函数。
- 冻结`pilot_masks.source_value_mask/add_cross_field_checks`：全部原物理范围、同PM7 context的IP−EA/gap sign、中性电荷source precision容差不改。GFN1 VIPEA不与GFN2 SP强作同Hamiltonian能差。NULL/z>20只review。
- enabled146沿同一field_key排序分配原field IDs，复用compact.encode/schema，不新增原因码到旧mask schema。264组件（146enabled/103NA组件/10deleted常数/5legacy）逐一只观测既存值、NULL/缺失/布局/zero，旧NA/常数/legacy声明不重分类、不重算QM。
- 追加观察compound重复atom ID、ENPART one-center全原子覆盖、sparse atom ID范围及重复/冲突key。basis pair key沿既验size_cpu_v2.aggregate.pair_keys。追加项是单独structural review，不偷偷改旧mask或把ENPART存储项和当总能量。
- 所有原CELL含QC/metadata的array长度和JSON语法都decode计数；非物理JSON没有权威结构定义的项不伪称完整语义通过。SUPER完整heavy-atom拥有范围及真正atom order仍需base geometry/atomic_numbers独立证据，当前只核既有range/uniqueness，不猜Nheavy。
- 既有pilot精确TRAIN median/MAD仅在完全同mode/fingerprint的4251-record选择使用；保留其源TRAIN4211范围和pre-common定义。full没有matched fullTRAIN calibration时明确PENDING，不借pilot尺度。z/MAD=0规则只review，不改训练标签。
- 每owner的磁盘scalar extrema只保存mol/field min_abs/max_abs及定位ordinal/sign/count，复用原非零同号且max/min>1000的数量级跳变复核；不把这些当新mask或最终归一化。每field按原值绝对值保存最严重20个scalar定位，便于全量定位已知EA高值；没有因高值判定程序失败。

## 文件与执行资源

payload.py为小的只读解析/观察kernel；run.py为pilot/full owner完整流式driver；reduce.py独立归约；materialize.py纯stdlib新metadata helper；test_payload.py为6项增量synthetic测试；本文为交接。

直接复用已有CPU auto-memory resource observer/drain与中央v2：16CPU、无SBATCH内存/no exclusive、分析cpu2/8–19含11–13、≤48h、quota200GB、4GiB MemAvailable软STOP、3GiB仅scan worker软件线、自然drain/no signals。每文件ParquetFile仅开一次跨batch复用并try/finally关闭，Arrow CPU/IO各1。source batch沿已实测旧stream config的16，不借metadata 256-row批量读大payload。canonical索引每worker只读16MiB SQLite page cache/256RID批查；pilot选样ID集合很小，full不复制全人口到Python。

full同一driver把171owner分为8片（每片≥16真实worker任务），每分子的构象与其owner同片；SQL磁盘scalar extrema避免全mol×field Python字典膨胀。正常原子/原子对数组不复制，mask和coverage不存正常原值；只有bounded worst20/previews、来源已有1% raw选择的后续候选和标量min/max统计保存数值。

pilot软件预算group64MiB/shard2GiB/reduce4GiB，whole8GiB；full group2GiB/shard12GiB/reduce4GiB，whole128GiB（含软件观测/partial余量）。运行时观察unique inode、每1024 canonical任务行留512MiB shard写入余量，超过保存partial并停止。SQLite/输出软件限额不冒充Slurm内存申请；第一轮实测必须核准实际临时/最终大小及峰值，不自动全量。默认pilot2h、full每片8h、reduce2h，都是allocation ceiling、不是已测时长。full超过500coreh由Root接受本次真实payload试点后提交。

成本授权`user_allocation_overrun_report_continue_20261026_v1.json`只把1.5倍核时超标改为报告后继续；质量阈值、source immutable、200GB、原配方/precision/frame等不变。全部失败/启动/partial仍计实际会计。

## Root入口（本代理未执行）

Root先拷贝整合并运行AST/source checker。原test_payload.py的6方法已嵌入实际scan primary：fresh中央v2 admission与全部源pins核验后、任何真实payload/SQLite/data正文打开前执行；严格发现6/run6，fail/error/skip/expected-failure/unexpected-success全0且来源SHA不变才继续。实际stdout打印完整unittest transcript与计数，外部stage目录保存pre_scan_fixture_gate.json；scan manifest引用该receipt及实际6项通过数。门禁失败保留receipt/failure并停止，绝不进入16owner扫描。不另建runner或独立排队父任务，不改原6测试body，不重旧19/24/8套：

```bash
PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
R=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025
$PY -B -m workflows.data_v1_final.labels.payload_audit_v1.materialize initial \
  --mode pilot --output-directory "$R/control/payload_audit_v1_pilot_metadata" \
  --artifacts-root "$R/artifacts/labels/source_status_v1/payload_auto_memory_v1/pilot"
```

helper只读小code/JSON并hash≤2MiB，Parquet/SQLite/role ledger只继承locator，不在login做索引/数据计算。初始输出plan/config/receipt实际绑定Root source与已闭合population。然后Root明确审阅生成新scope（替换ACTUAL闭合证据）：

```bash
$PY -B -m workflows.data_v1_final.labels.payload_audit_v1.materialize scan \
  --config "$R/control/payload_audit_v1_pilot_metadata/config.json" --shard-id 0 \
  --output "$R/artifacts/labels/source_status_v1/payload_auto_memory_v1/pilot/shard00" \
  --output-directory "$R/control/payload_audit_v1_pilot_scan_scope" \
  --parent-evidence ACTUAL_FULL_SOURCE_STATUS_CLOSURE --root-reviewed
```

新stage_spec交Root中央v2 materialize/submit/observer，不自动调用Slurm。scan实际C0+resource closure后，helper `reduce --config CFG --shard-manifest SHARD/manifest.json --output NEW_REDUCTION --output-directory NEW_SCOPE --parent-evidence ACTUAL_SCAN_CLOSURE --root-reviewed`生成归约spec；pilot保持BOUNDED_PERFORMANCE_BATCH，真实full须`--parent-profile`指向被Root接受的实际payload试点，FULL_SOURCE_AFTER_PROFILE；full initial只改mode/新tag，不拿pilot calibration入full。

reduce读取所有组coverage，复用已验consume_coverage去重并核新closed role ledger；每槽恰好一次、每146/264字段分母一致、整mol质量守恒。候选mask文件hash重新核对。任一enabled field新增mask率或新发现的实际结构失败率>1%先保留证据、退出2并报告；旧缺失/NA不拿来触发这个新异常阈值。mask candidates始终未freeze，不能因退出0就说guide1.5或D4已完成。

## 剩余真实证据

本轮将按task最多4、每owner最多64条保存**来源已标raw_audit_selected且有raw locator**的候选，带record/task/source/input hashes/program ID/precision声明；不打开大archive、不重新跑QM。下一独立有界CPU raw probe按候选archive/member逐字读回，核原程序打印精度、parser数值和actual geometry/frame证据。raw缺失就是缺证据，不由f64、SCF NULL、合成旋转或无日志断言失败。

MolMR原数值单位/19项继承RDKit生成版本、Fukui单位convention、native F32出处、AO basis、dipole/quadrupole原点、perturbed gradient与坐标实际frame均继续pending。现P′协变矛盾不能用此payload结构pass放行；P′独立来源/统计仍不能复用P。最终共同人群+effectiveTRAIN+精确diagnostic geometry/order冻结后才可运行最终D4。