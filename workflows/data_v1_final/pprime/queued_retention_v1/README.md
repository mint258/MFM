# 原2000 UFF输入的严格 CPU retention 准备

状态：源码交给 Root；本子 agent 未执行 Python、测试、科学计算、SSH、Git 或 Slurm。新工作不重跑 UFF，不调用 QM，不改旧源码/配置/已准备的 pairs 或固定随机顺序。准备 job 可在 frame 实际验收前独立排队；后续2000 QM仍必须等两项真实闭合。

## 精确最小绑定改动

新增 `retention_v1/prepare_cpu_queued_v2.py` 从原 `retention_v1/prepare_v1.py`逐字节复制，唯一改动：

~~~
observed=IO.runtime(prepare=True)
    -> observed=IO.runtime()
~~~

原 `prepare=True`硬限node20；普通 `IO.runtime()`沿旧函数限定14–19，16实际worker。所有 source_audit、stable selector、原20审计与stable hits的union、字段、归档语义和parquet写入都未改。新 wrapper 另外要求真正CPU分区、16CPU/64GiB、当前节点匹配、新鲜执行证明、原全部用户声明85%、foreign0阻止、配额200GB；不继承旧small-memory例外。

Root先运行纯stdlib源码证明（只读小source，无测试/科学）：

~~~
$PY -B $REPO/workflows/data_v1_final/pprime/queued_retention_v1/verify_binding_v1.py \
  --output $RUN/control/<new-retention-source-proof>.json
~~~

证明完整inverse bytes与normalized AST一致，明确新wrapper不是旧prepare AST；wrapper只增加资源/元数据绑定、PROJECT cwd及独立读回。它不伪造已通过实际测试或已准备manifest。

四项新增边界的精确CLI（由Root在新的真实CPU allocation内执行，不借旧fixture结果）：

~~~
$PY -B -m unittest workflows.data_v1_final.pprime.queued_retention_v1.test_v1 -v
~~~

覆盖：仅CPU准入call可改/其它science字节漂移拒绝；严格64G与zero/missing foreign声明拒绝；队列时间旧证明、错误节点与配额拒绝；2000原记录、原20审计、stable union、全12 raw标记及实际engine parquet读回守恒。仅合成metadata，不重跑原selector/数值测试。

## Root注册与排队

~~~
$PY -B $REPO/workflows/data_v1_final/pprime/queued_retention_v1/materialize_v1.py \
  --repository $REPO --run-root $RUN --reviewer root --node compute-0-14 \
  --source-proof $RUN/control/<new-retention-source-proof>.json \
  --execution-intent $RUN/control/<new-retention-execution-intent>.json \
  --plan-output $RUN/control/<new-retention-queue-plan>.json \
  --output-prefix $RUN/artifacts/pprime_retention_v1/<new-prefix>
~~~

metadata helper只在sonmi读≤2MiB的小型源码/authority JSON。它复用已冻结frame materializer的纯small-file函数并pin该依赖，不执行该模块main或frame任务。原 `artifacts/pprime/prepared_v1/prepared.json`仅4012B；19,385,976B的 `pairs.jsonl`、全部parquet（包括1424B原20审计）只登记locator/hash，不在登录节点读取、hash或stat其正文。原prepared必须1000分子/2000构象、audit_records20、QM_started=false且配置pin一致。

输出plan提供 `command_argv`、kind=analysis/pilot、16CPU64GiB、3600秒墙时、原8GiB科学输出上限加64MiB队列预算、小source refs与deferred data refs、源码proof pin。16分配核时只是墙时资源上限，不是预计耗时。Root须把plan自身和wrapper加入实际request.source_references，并提供与 `--execution-intent`完全相同路径的**实际启动时**新鲜proof；排队时间不能代替执行准入。

wrapper在准入后以PROJECT cwd子进程执行原body的CPU variant，随后在同CPU allocation独立读回新engine audit parquet与原20 audit parquet，并核对source audit、stable hits、union及所有原始输入SHA保持。生产的 `prepared/retention_manifest.json`保持原schema=`PPRIME_STABLE_RAW_RETENTION_EXECUTION_BINDING_V1`和status=`PREPARED_NOT_QM_EXECUTED`，可以被原 `retention_v1/run_pilot_v1.py`直接消费。

wrapper的 `queue_execution_receipt.json`仅当原producer C0且完整独立核验通过，才是 `ACTUAL_RETENTION_PREPARATION_COMPLETE_NOT_QM_AUTHORITY`并exit0；失败exit3，原partial不覆盖、不自动重试、不发终止信号。实际source/union数量从本次CPU真实输出读取，未预设stable hit数。原2000 QM science-once ledger不被这个准备步骤创建或修改。

准备和未来QM的全部实际父任务成本均须保留；评估pipeline总成本时包含准备、启动、导出和失败，不能从单个worker秒数扣除retention开销。当前尚无实际retention manifest、实际测试结果或实际科学成功率。

## 后继仍有两道实际依赖

1. frame队列任务真实达到其受限scope的PASS，保留72调用raw及所有负面结果。
2. 本准备任务真实C0并附实际closed manifest/ref；然后Root单独冻结并排队2000构象×12任务pilot，软件/关键词不改、成功率≥99.5%且actual allocated core seconds/conformer≤11.7才允许后继全量。最终共同人群、P′异常扫描、P/P′对比与训练格式交付均不由本准备步骤宣告完成。
