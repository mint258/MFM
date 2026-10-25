# 严格 CPU 队列中的真实 frame 审计

这组新源码由 Root 集成后使用。子 agent 没有执行 Python、测试、QM、Slurm、Git 或 SSH，未改旧源码、配置、输入和结果；不把4520552输入准备当QM验收。

## 可以立即交给 Root 的任务

`materialize_frame_v1.py` 只在 sonmi 读取≤2MiB的小型源码/authority JSON，登记已完成准备包 `artifacts/vector_frame_audit/prepared_cpu_v4/prepared.json`，验证4分子、72输入、QM_started=false。4,427,609B cases正文、parquet和程序二进制只保留原 locator/pin，登录节点不读、不hash、不stat。元数据 helper 不提交作业。

Root CLI（所有参数是新位置）：

~~~
$PY -B $REPO/workflows/data_v1_final/pprime/queued_v1/materialize_frame_v1.py \
  --repository $REPO --run-root $RUN --reviewer root --node compute-0-14 \
  --execution-intent $RUN/control/<new-fresh-execution-intent>.json \
  --plan-output $RUN/control/<new-frame-queue-plan>.json \
  --output-prefix $RUN/artifacts/vector_frame_audit/<new-frame-run-prefix>
~~~

输出 plan 给出 `command_argv`、kind=qm/pilot=true/16CPU/64GiB/7200秒、2GiB原科学输出上限加64MiB整个队列预算、全部小source refs、延迟至CPU核验的大数据refs、固定软件与执行/评估源码refs。32分配核时是墙时上限，不是耗时预测。允许节点14–19；所给node是Root选定的入队节点，实际启动必须由新Root证明绑定。排队本身不是科学准入；所有其他用户的零/缺失内存声明仍阻止执行。

`run_frame_v1.py` 需要 plan pin、自身pin、全部plan source pins都出现在**执行时的新鲜** Root request中。这个request必须kind=qm、16CPU/64GiB、7200秒、node匹配实际CPU节点；不得使用旧small-memory policy。全部用户声明85%、配额余200GB以及实际Slurm内存由新proof与环境复核。

wrapper只增加严格绑定、PROJECT cwd 和闭合gate，原 `vector_audit/run_v1.py`、`evaluate_v1.py`、NATIVE invoke、协议、关键词、软件、扰动和数值参数完全复用原文件。两个子进程依次执行原72 QM调用与原离线评估；72个控制并非2000构象×12任务pilot。全部实际调用输出按原RawSink持久保存，审计输入另存复现材料；失败scratch保持，不发信号、无自动重算。

只有实际72调用、72 durable raw、72独立解析、16实际工作PID、原worker全关闭、无执行错误，且原 evaluator 的 `INPUT_FRAME_SUPPORTED_ON_TESTED_CONTROLS_WITH_LIMITS` 才exit0。其余exit3并保留原raw与闭合receipt；run_closed本身不代替帧验收。`queue_execution_receipt.json`记录真实计数和两个returncode。此审计只支持选定PM7 B/GFN2 SP/gradient及noisy/translation控制，不认证全语料或PM7离子/溶剂矢量。

## 程序与后续2000 pilot

权威WP5 reproduction manifest固定MOPAC23.0.3（software_version_id1）与xTB6.7.1（id2），binary SHA由旧engine在CPU初始化实际核验。原协议12任务与seed20261010、perturb_sigma_A0.1保持；72frame审计只调用其中B、SP、perturbed_gradient及附加同几何SP控制，不冒称全部12任务已验收。

真正2000 pilot必须另行满足：

1. 真实frame gate通过；原1000分子×2UFF准备包SHA仍一致。
2. `retention_v1/prepare_v1.py` 为原20审计加stable source-shard hit union创建新的 `retention_manifest.json`。当前尚无此真实manifest；旧prepare的 `IO.runtime(prepare=True)`硬限node20，应由Root另建只改CPU绑定的新variant，在实际CPU分区完成准备，不能直接在CPU14上用旧入口。
3. 使用 `retention_v1/run_pilot_v1.py --execute --config configs/data_v1/pprime/stable_raw_retention_v1.json --retention <closed-retention-dir> --retention-sha256 <actual-manifest-SHA> --root-preflight <fresh-proof> --output <new-output>`，仍16CPU64GiB≤2h，原science-once ledger绑定原pairs+protocol，不以新目录允许重算。
4. 原 `close_pilot.py`附实际terminal父sacct，包括启动/导出/归档和失败；成功率≥99.5%、分配核秒/构象≤11.7后才讨论全量。P′ outlier scan、P/P′比较、最终共同人群仍未完成。

本提交件只令下一步72个**真实** QM控制可审阅、可排队，不放行2000 pilot或全量。
