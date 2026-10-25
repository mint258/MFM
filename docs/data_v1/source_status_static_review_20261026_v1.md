# source-status 与恢复后 planning 的静态审查

2026-10-26。SB2仅通过X读取新源码和小型权威metadata，未运行Python、AST、测试、SSH、Git、Slurm，未读真实标签、LMDB、Parquet、reproduction package或其他科学数据正文。下述判断是静态源审，不是首片实测通过。原source_status_v1七文件与既有conformer源码未改。

## 当前结论和真正的接入阻塞

全原人口census可按现有边界先做prepare与首片；静态审查未发现其ordinal×task覆盖设计把影子物理行静默删除，也未发现NULL收敛被升级为mask。真实文件schema、总RSS、SQLite/spill大小、全量时间及输出高基数只能由第一次实际任务证明，不能由本报告补齐。

1. source_status_v1/support.py的guard明确只接kind=analysis/pilot=false；原queue_v1.materialize仍是pilot-only。运行此pass必须使用新的nonpilot materializer，保持严格16CPU64GiB及队列新鲜proof；不得伪标pilot借用旧入口。Root已知并负责这个适配。
2. conformers/formal_v1/full_common.py的review（106–122行）只接受旧PILOT_COMPLETED_REQUIRES_ROOT_REVIEW、expected/completed=336及parquet_readback，且require_actual_accounting要求pilot.runtime.job_id为C0。恢复closure是RECOVERED_SPRIME336_PILOT_CLOSURE_V1，原4520364必须保持TIMEOUT。直接传旧review必然拒绝；不得伪造旧receipt或把TIMEOUT改为C0。
3. 旧formal_v1/plan_batches.py直接调用旧review，并用package summary.elapsed拟合分组max、以actual allocation/已封包worker秒校准overhead。恢复前缺包attempt秒未知，14controls又不属于336人口；新的planning adapter必须显式保留这项右删失与所有相关parent成本，不能只改schema字符串后复用为可靠耗时预测。
4. 旧full_common.runtime(science=false)写死compute-0-20。新CPU分析与规划应使用新namespace/queued guard，不能在20或GPU节点运行来迎合旧代码。

## source-status 已有的覆盖和资源约束

- prepare先对population/latest实际SHA，在同一CPU allocation内用DuckDB核全部record/molecule/role数量与精确physical ordinal 0..N-1，再分批4096写SQLite。角色分片16份必须齐。索引是磁盘SQLite，每worker仅16MiB page cache；没有把全人口owner复制16遍的Python字典。
- TASKS来自14个固定task；source projection的latest_rows总量必须为14×N。扫描逐文件要求physical=canonical+shadow，canonical与closed latest_rows一致。reduce对每个ordinal/task唯一槽去重并按effective role核对，最后每个task必须恰N；输入声称的11231854记录/157245956 canonical槽与8694 shadow均有独立守恒检查。这里没有重新测出这些总体数字。
- 16个spawn worker的首16文件barrier保证实际PID；一worker只打开一个ParquetFile并跨batch复用，关闭后接下一文件。Arrow CPU/IO各1、batch256、worker峰值RSS3GiB硬拒绝，16worker上限理论合48GiB，尚须首片实测父进程/库缓存/全树峰值。
- prepare的DuckDB12GiB、spill8GiB与prepare24GiB输出cap是配置上限，未证明SQLite实际大小或2h足够。SQLite每4096行commit在共享FS上的成本尚未测；超时或cap拒绝时应保留partial，以新目录和新请求处理，不能直接写成prepare完成。
- 每file预留64×canonical_rows+4MiB；每shard reserve在materializer核到2GiB内，reduce两个uint8 ledger为14N+N字节，约160.7MiB（N取11231854时168477810字节），不是14N个Python对象。全pipeline申请总cap60GiB并留200GB quota，符合把partial/spill/ledger计入的方向。
- NULL convergence、NULL/nonpositive SCF、source_status不一致、numeric_issues、cell重复/unknown/declared-shape异常均为review-only标志，未生新mask。JSON/数值array payload明确未投影，因此不得称已经完成真实shape、finite、物理阈值、打印精度、单位或frame审计。

## 条件性 safe-fail 风险，不是已证实的真实数据失败

1. precision_metadata（scan.py 36–43行）用默认json.loads，允许NaN/Infinity；随后dump允许allow_nan=true，并把解析dict放入precision_examples。文件报告的dump及support.save采用allow_nan=false。若实际来源precision JSON含这些非有限数，会在报告序列化前安全拒绝，而不是正常归类为malformed metadata。源码中可构造，未检查真实来源有无此值。若首片触发，建议在新版本中用parse_constant拒绝或递归finite检查，返回单独NONFINITE_PRECISION_METADATA状态且不保存该dict；补一项针对nonfinite声明的增量fixture，保持原值不改。
2. precision_variants_per_file=64且单precision JSON允许65536字符，理论声明样例可超过4MiB，而文件报告显式限3MiB；即使没有实际数值payload，也可能因合法高基数metadata而安全失败。当前不推测实际签名数量。首片应核precision变体、单report大小和worker RSS；必要时新版本把每例按字节预算保存/外置字典并保留overflow计数，不能静默丢声明。
3. support.save只有传root/cap才prewrite预算；reduce.py112–128行几个输出save不传cap，只在最终audit前做总量检查。prepare每批SQLite commit后才查cap，scanner在报告写后查per-file cap。正常受控基数预计小于固定cap，但静态代码不能支持“任何异常输入均不可瞬间越cap”的强声明。建议新版本在每次实际写前使用root/cap，并对聚合JSON先计编码长度；SQLite按剩余空间/PRAGMA max_page_count或保守批次预留保护。不能因这个未触发限制把当前首片虚报已越限。
4. declared_shape把任何等于natom的维度记N，natom恰3或6时可能与固定向量/对称tensor轴重合。此pass只统计声明且payload未观测，现有边界不据此验证物理shape；后续payload pass宜保存原shape或标AMBIGUOUS_N_EQUALS_FIXED_AXIS，避免把观察类别当物理轴证明。

新输出若没有全部片真实闭合及精确ledger通过，只能保留partial/FAILED；不得发布全人口完成、D2/D4或指南1.5完成。

## 恢复 planning 新namespace方案

recovered_planning_v1直接验证真实新closure及其所有引用，不转换为旧receipt。新Root decision必须显式接受科学失败披露、全部相关实际parent费用和右删失限制。核336=334旧路径+2新路径，14controls只作复现且不进入union，核float64读回、原task/seed/源hash、原TIMEOUT和新C0。把相关owned-submission集合与raw sacct唯一parent集合逐项守恒，FAILED/TIMEOUT、复执行、控制、cleanup均留成本，不重复加step；拒绝遗漏/负成本/状态伪升。输出仅为新planner的typed recovered planning input authority，formal/common/D7/pilot_accepted原closure字段仍false，满批和>500预算仍需后续真实测量及Root审阅。

不能把未保留的旧missing attempt worker秒从新package elapsed推出来；可报告全部parent分配总成本作为已知下界/overhead证据，不能把右删失消失包装成精确forecast。

## N=1 的第二个UFF候选：只读源码结论和方案

原factory runs/sprime_s_convergence_20261013/scripts/sprime_v6.py：n=len(PM7 rows)，218/224行请求3*n候选，242–246行按0.5Å选择并在len(selected)==n时停止，248–258行只返回selected输出；main只写molecules/conformers parquet及receipt。对n=1虽然曾生成最多3个候选，当前factory保存路径只留下一个selected；本次未发现把第二个未选候选持久化的分支，也未检查所有历史产物，不能宣称任何地方绝无额外几何。

新conformers/science.py只在原缺口len(existing)<target时请求min(10*target,300)，末尾仅失败或确定性1%审计保留全部candidate archive。不能假设原5040个PM7-N1母人口都有现成第二UFF；5040也不是已冻结common数量，本次没有重计该人群。

建议先在metadata确认可追溯审计候选是否实际可用，再为剩余N1建立独立pprime_second_uff_v1任务域。保留PM7原N=1、其唯一PM7记录、旧UFF物理ID/坐标不变；不复制几何，不把PM7坐标换成第二UFF。新adapter明确分离source_pm7_count=1、candidate_pool_base_N=1及uff_select_target=2。现有kernel把target同时用作pointer数量/最低能range/candidate数/selection数，直接把expected_conformers改2会触发ACTUAL_RECORD_MANIFEST_MISMATCH且可能越PM7数组界，不能这样用。

候选生成保持原ETKDGv3/UFF版本、seed、图/立体/原子顺序检查、10N/300参数：对N1仍用10个真实优化候选（10×source N），已有UFF1作accepted baseline，选出另一个真实candidate；优先0.5Å，不足时按原max-min RMSD补足且标below_dedup_threshold。不得为凑数复制旧geometry；如全部有效候选与旧geometry完全相同或不足，记录SECOND_REAL_UFF_UNAVAILABLE并如实报告，不把它伪装为两不重复构象或悄悄删common。新任务域有独立once ledger，不能消耗/复用原fill retry；追加ID仍遵守formal_v2在所有旧attempt最大idx之后追加，保存candidate/seed/optimizer及geometry hash。仅有真实第二候选后才能供P′两构象选择；common仍由原定义与最终资格独立冻结。

## 只读审查来源快照

| 文件 | 字节 | SHA256 |
|---|---:|---|
| support.py | 7994 | 5b2d7cff71a755cac595d7769cd0e9c48514b3f9daa8326af17586d2040b4194 |
| prepare.py | 8573 | 0b2dbeaf4525ffe6738fa1acc96783ec15d7bfd9a2932a2dc332e53f0087a0cc |
| scan.py | 17994 | eeffa7639ffbe0df3ba8fabc46526bb862696edb2aba7dc58c773c55f0f54fa7 |
| reduce.py | 11563 | a5159ead489521736c56d3f5dc79378fcf429a1bcc9914ab5724236d533df865 |
| materialize.py | 12182 | 368d13e5c6cb32b506c16f6f97fa68c44fc6b1b971694909f05d6353d6bd3ce0 |
| test_semantics.py | 8125 | 5b4b5c855cb6436e0facf49cb9fc892d2f260ae9584fb50231d216a8854f571e |
| README.md | 10738 | 831721ed73e3b377f8b2e667434853e6cafca6dadb71cd5d9ca8c8ba0a2f10a9 |
