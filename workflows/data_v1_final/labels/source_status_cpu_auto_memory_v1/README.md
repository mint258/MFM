# source-status：CPU自动内存资源适配 v1（未执行草案）

按最新skill1.0.120及`configs/data_v1/user_cpu_auto_memory_20261026_v1.json`：CPU分析节点实际cpu2/8–19含11–13，16CPU；不申请Slurm内存、不exclusive，不以64GiB/声明85%准入。记录实际RSS/MemAvailable，软STOP只停止新派发、在跑工作自然完成，无信号/自动重投。Root统一检查、提交、监控；本代理仅写新源码，未执行Python/SSH/Git/Slurm或科学正文。

旧source_status_v1七文件、config5355B及旧held prepare4521023保持原字节。原8科学semantic fixtures已由Root实际bootstrap4521065 CPU12 C0/28s（与原22合计30）通过，本目录不克隆或重复执行它们。此处3项增量资源fixture尚未运行；新增source的实际完整性/性能尚未验收。

## 精确变更与证明

- prepare.py、reduce.py与旧Root版本**完整字节相同**，相对`.support`自动落到新namespace。
- support.py只替换guard、rss两个资源函数。guard使用`execution.cpu_auto_memory_queue_v2.runtime.require_startup`，绑定新authority/current main/全部argv/真实16CPU/新proof/全部旧新source与原config；不伪称获配64GiB，不调用旧64GiB guard。中央v2 API与v1一致，v2修正Slurm真实AllocNode:Sid解析，绝不回退v1。
- scan.py只增加resource_runtime导入、将run中的原全部提交Executor控制块替换为16个inflight有界dispatcher。行筛选、canonical owner、14task、字段/shape/precision计数、复核位、覆盖ledger、batch/限额和所有其他函数原字节/AST不变。实际scan.run AST确有此调度差异，不声称全部AST天然相同。
- verify_equivalence.py纯stdlib读取小source，逆回两个资源函数、一个import/控制块后，检查四文件全文bytes及AST精确等于旧Root；并直接比较所有非资源函数AST。它不导入producer、不读科学数据。

Root整合后运行metadata证明（本代理未运行）：

```bash
python -B -m workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.verify_equivalence \
  --repository /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository \
  --output /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/source_status_auto_memory_equivalence_v1.json
```

## 资源观测与自然drain

producer startup后，独立线程每1s读取本node `/proc/meminfo`，以及自身PID/start_ticks/UID绑定的子树RSS；不读其他用户进程正文、不发信号。4GiB绝对MemAvailable软floor由Root已明确同意，只记录并锁定STOP；它不是sbatch或启动内存准入。任何实际memory观测失效也停止后续文件派发。原scan worker的3GiB软件线仍使用ru_maxrss，超过只写STOP/保留currentRSS/HWM，不打断当前file。它不套给prepare/reduce主进程。

scan首16任务原barrier作为同一wave派发（避免少于16导致barrier死等）。后续最多16个inflight；STOP后不提交更多file，已经开始的file自然读完并关闭其唯一ParquetFile。随后抛明确SourceStatusSoftStop，旧外层保留partial receipts，不发布完整shard/全人口结论。真正source异常仍走原peer-failure路径；不把资源紧张写成新科学mask。

prepare/reduce是单个inflight stage，DuckDB12GiB、spill8GiB及stage输出24/2/4GiB等全部原软件预算保留；4GiB floor不会伪装成3GiB主进程限制，也不杀正在索引/归约的stage。Root根据输出的STOP和closure决定后续，不自动推进下一stage。

观测/STOP先存node-local `/tmp`，进程正常退出时atexit停止监测并逐文件SHA核对导出到新tag旁resource_observation目录；即使源码因异常退出也保留能导出的证据。单stage local和durable各64MiB，额外整阶段18×128MiB保守计入whole预算（旧科学60GiB不变），另保留quota200GB。closure记录真实SLURM_MEM*环境作为观测，绝不当作本任务请求内存。若无法正常关闭/导出，不能声称资源证据闭合；Slurm终态仍由Root实际记账。

## metadata helper与入口

materialize.py纯stdlib，仅小source/metadata≤2MiB SHA；不读/stat大科学文件，不计算索引，不提交。接受旧**request或spec**及原source/data refs，实际核对旧小pin；原科学config只引用、不复制、不改字节。只允许三处argv变化：主模块namespace、新output tag、freshproof占位符；逆回后必须逐项等于旧argv。

Root先审阅本源码并整合实际v2中央模块，再生成等价proof。明确Root review后，调用以下helper（例子路径仅新metadata；现有同名即拒绝）：

```bash
PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
R=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025
$PY -B -m workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.materialize \
  --legacy-input "$R/control/requests/dv1_q_source_status_prepare_20261026_v1.json" \
  --new-output "$R/artifacts/labels/source_status_v1/auto_memory_v1/prepared" \
  --output-directory "$R/control/source_status_auto_memory_prepare_v1" \
  --equivalence-proof "$R/control/source_status_auto_memory_equivalence_v1.json" \
  --parent-evidence ACTUAL_SMALL_BOOTSTRAP_CLOSURE \
  --root-reviewed --root-review-reason 'Root reviewed exact scientific inheritance and latest user resource authority'
```

helper生成resource_binding/scope_review/stage_spec/receipt。Root实际执行helper前的明确审阅才授权这些review，代理没有提前写APPROVED产物。所有old/new/central v2 source pins绑定实际Root路径，不能用child同SHA代替Root路径；只读父证据必须是Root实际closed receipt，不能把候选脚本充当结果。

prepare使用BOUNDED_METADATA_PREPARATION；首次scan可用BOUNDED_PERFORMANCE_BATCH、pilot=false，继承实际preparation证据。剩余full scan/reduce传`--parent-profile`真实首片结果后使用FULL_SOURCE_AFTER_PROFILE；>500coreh和全部原科学预算门槛不变。不因默认内存改变宣称既有560coreh ceiling成为实际成本。

生成stage_spec后交Root `execution.cpu_auto_memory_queue_v2.materialize --spec ... --authority ... --node ACTUAL_CPU_NODE --job-name FRESH`，再由Root真实提交与observer承接。这里不生成sbatch、不释放旧held任务、不终止任何running任务。

新增3项纯资源fixture入口：

```bash
python -B -m unittest workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.test_resources -v
```

覆盖16个在跑文件自然drain/不派发后32个、无压力完整文件集和inflight上界、3GiB worker软线及argv仅资源位点逆等。所有全人口源状态、shape/precision未观测项目、>1%新mask硬停、z>20只review、common/D4/P′独立来源要求全部沿旧计划；不新增成功率例外或最终科学结论。