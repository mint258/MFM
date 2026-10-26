# P′实际 frame 与2000 retention：新 CPU 自动内存适配

来源：用户2026-10-26的明确授权，Root `configs/data_v1/user_cpu_auto_memory_20261026_v1.json` / HPC skill1.0.120。新科学CPU节点11–19、每任务16CPU；一般analysis按central实际CPU名单。SBATCH不申请内存、不exclusive、不再用64GiB或声明85%准入；实际默认内存环境值仅记录。原PENDING4520961/962及其注册源码、请求和未运行记录保留，不复用其输出。旧科学配方、程序、种子、输入、原始输出保留及科学成本/成功率阈值不变。

本目录源码由子agent准备，未运行Python、测试、科学、SSH、Git或Slurm。Root必须整合、检查、运行源码proof和实际新边界，再使用新的central v2登记和提交；不能借Bootstrap4521065或旧严格队列的结果充当新central验收。

## 实际 primary 与科学等价边界

- `run_frame_v1.py`从原`vector_audit/run_v1.py`复制；`execute_case`整函数bytes与AST保持，原72输入、4分子、三类原任务及旋转/noisy/translation控制、NATIVE调用、MOPAC23.0.3/xTB6.7.1、raw持久化和节点scratch处理不改。只替换资源startup/import/CLI、父进程bounded16补派和最终受限frame gate。原`evaluate_v1.py`复用，不扩容差。
- `prepare_retention_v1.py`从原`retention_v1/prepare_v1.py`复制；source_audit、stable selector、原20+stable hits union、字段、parquet和原random顺序不改。只替换startup、sibling import/CLI、16-thread bounded map及资源闭合。成功时严格按原input index恢复结果顺序。
- `source_edits_v1.json`逐项记录精确old/new text。`verify_source_v1.py`将每个新文件完整反向恢复原文件并比bytes/normalized AST，另外比对`execute_case`全文和AST，记录未改retention policy/selector/evaluator的完整refs。新资源wrapper不被假称为旧main的相同AST。

新primary直接调用`cpu_auto_memory_queue_v2.runtime.require_startup`，验证真正新schema/proof、kind、全CLI、scope key/parameters、primary代码和输入/plan refs。没有把旧wrapper的64G proof伪装成新proof，也没有子进程冒充primary。

## 真实观察、软件soft限与自然drain

`memory.py`每秒只读取自身/proc thread children树，以PID/start_ticks/real UID/boot身份验证实际后代，汇总RSS并读取MemAvailable。共享页可能重复计入RSSsum，明确记录；不枚举他人PID，不发信号，不引入声明内存85%判断。

Root新scope显式审阅的软件限额：frame own RSSsum32GiB、retention8GiB；实际MemAvailable低于4GiB、观察不可用/过期、显式本stage STOP文件或dispatch deadline触发时，停止新增派发。它们是算法soft预算，**不是Slurm申请或保障**。每次只有16个在途任务；已提交工作全部自然等待完成，无cancel/terminate/kill。观察样本compact payload最多32MiB、finite samples，另外保留最后一条实际观测，达到证据限额也停止新派发，保留丢弃计数与最后真实观测。

frame所有已完成case raw仍由原函数持久化。partial时保存完成refs和未派发case IDs，不能把partial重复当完整72或自动重算已完成QM。全部72闭合且内存observer仍可派发时，才在同CPU allocation调用原offline evaluator；若72已算完但内存STOP，评估明确DEFERRED，Root后续只评估保存输出，不能重跑QM。

retention在softSTOP时自然drain后保存按原index排序的partial source_audit，状态不是ready manifest；它没有QM/新UFF或science-once ledger改动。完整时CPU独立读回原20审计与新engine audit parquet，复用既有纯closed validator，核对原2000身份、union/stable/full12 flags与原SHA。

## Root精确CLI与独立review

先Root source proof（只读小源码，不执行测试/科学）：

~~~
$PY -B $REPO/workflows/data_v1_final/pprime/cpu_auto_memory_v1/verify_source_v1.py \
 --output $RUN/control/<new-pprime-auto-source-proof>.json
~~~

新增4项边界（在真实CPU allocation运行）：

~~~
$PY -B -m unittest workflows.data_v1_final.pprime.cpu_auto_memory_v1.test_v1 -v
~~~

覆盖declared edit/额外science改动拒绝、实际soft限无Slurm申请假设、bounded map原顺序、停止新派发并自然drain。没有重跑旧selector/数值测试。

frame和retention各用一次新metadata helper；`--old-plan`只是固定科学输入/配置和小authority refs的lineage，不继承其资源字段。Root已注册的旧strict frame52500B plan及旧retention scientific plan均保持。

~~~
$PY -B $REPO/workflows/data_v1_final/pprime/cpu_auto_memory_v1/materialize_v1.py \
 --stage frame --reviewer root --old-plan $OLD_FRAME_SCIENTIFIC_PLAN \
 --authority $REPO/configs/data_v1/user_cpu_auto_memory_20261026_v1.json \
 --source-proof $RUN/control/<new-pprime-auto-source-proof>.json \
 --plan-output $RUN/control/<new-frame-auto-plan>.json \
 --review-output $RUN/control/<new-frame-auto-review>.json \
 --spec-output $RUN/control/<new-frame-auto-spec>.json \
 --output-prefix $RUN/artifacts/vector_frame_audit/<new-frame-auto-prefix>
~~~

retention把stage改retention、old-plan改其原scientific plan，并使用新的plan/review/spec路径和`$RUN/artifacts/pprime_retention_v1/<new-retention-auto-prefix>`。helper只读小source/metadata；已具triples的大正文保留locators；缺bytes的.sbatch仅按小代码SHA核验补实际bytes，未知大小dict完整保留在deferred authority，不在login读/hash/stat字典或科学正文。

helper输出新independent `EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1`与`ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1`，由Root个人实际invocation冻结：frame mode=BOUNDED_PERFORMANCE_BATCH/pilot=true/kind=qm，retention mode=BOUNDED_METADATA_PREPARATION/pilot=false/kind=analysis。墙时仍分别7200/3600秒，stage输出仍2GiB/8GiB，whole额外64MiB；只继承科学上限而不继承旧memory_gib/85/exclusive。primary argv含`__ROOT_STARTUP_PROOF__`供central v2替换，完整参数参与新review绑定。

然后按central v2的materialize/submit/registry/activate/observe流程实际入队。新request不能含memory_gib等旧字段，不能在sbatch或环境隐式指定内存。运行时truthful记录默认`SLURM_MEM_PER_*`，不称其为64GiB。

## 未完成依赖

72控制并非2000构象×12任务pilot；frame PASS也仅覆盖选定控制的PM7 B/GFN2范围。2000QM仍需actual frame PASS、actual retention manifest与独立新请求/原science-once ledger保护；≥99.5%和≤11.7 actual allocated core seconds/conformer的科学门槛未改。全部新旧父任务（含失败、资源停派、准备和评估）成本保留；最终共同人群、异常扫描/P-P′比较、导出和全量验收仍由Root实际完成。
