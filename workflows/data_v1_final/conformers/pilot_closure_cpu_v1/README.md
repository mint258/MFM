# CPU分区小分析专用的闭合入口

独立新源码与metadata runconfig，不修改原closure/config/science/prepared/源结果。
新 close_pilot_cpu.py 是完整可读执行字节，保留原所有source/config/receipt/
accounting/old-vs-new/float64SHA验证；只改运行守卫、有限16任务IO池/checkpoint、
新增CPU proof字段。**没有运行时ASTexec/隐藏改写**，不生成/优化/复制构象。

中央Root接口来自canonical repository的
workflows/data_v1_final/execution/cpu_analysis_v1/{policy,runtime,probe_memory,
launch,submit_cpu_pilot_v1}.py。新runtime_adapter只读已pin文件并调用
root_guard(intent,actual_entry,cap_bytes,wall_limit_seconds)及checkpoint()；
不自行实现或放宽CPU/内存准入。request须为
kind=analysis,pilot=true,partition=cpu,
resource_policy=CPU_BOUNDED_TEST_LIVE_MEMORY_V1，确切scope：

- sprime_closure_fixtures_6：16CPU8GiB/10min，原6fixture+2个最少新boundary。
- sprime_pilot_closure_336：16CPU32GiB/1h，仅完整336最终只读闭合。

只选Root已核cpu分区节点2、8–19；不选GPU节点20/21。
正式/full仍原16CPU64GiB、声明内存85%，没有把当前小analysis例外扩展。
中央launch负责实际资源监测/heartbeat/STOP；新入口在派发/读新批次前检查，
IO池最多16个in-flight，等待timeout0.5s持续checkpoint，停止派发后已在读的
任务自然结束。不发信号、不杀进程、不重试，不声称已经运行。

## 原配置与新配置

原 configs/data_v1/conformers/pilot_closure_v1.json 原946B/SHA
d68f0ca9bfbe851d5331ab8f6e0950201a4486c85ed55cd193aa1acbb7d144d5 保持。
新 configs/data_v1/conformers/pilot_closure_cpu_v1.json 是metadata执行runconfig，
绑定原配置和两个有限scope，不改科学或input authority。
actual输出使用原external_output_root下全新child，例如 cpu_closed_v1。

## 精确Root物化CLI

materialize.py只用标准库及原纯metadata helper；不会SSH/提交/重试。
需Root中央5文件/decision_v4/scope policy/base原request都真实落地且闭合，
文件未齐立即拒绝，不编造pins。request默认ROOT_REVIEW_PENDING；
Root唯一后续审批/提交。--root-review可附Root另写的实际analysis批准，
须statusAPPROVED/reviewerroot/mode/job_name/repository精确一致。

    BASE=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025
    REPO=$BASE/worktrees/sb2
    PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
    MAT=$REPO/workflows/data_v1_final/conformers/pilot_closure_cpu_v1/materialize.py

Root手工选现场可用CPU节点，例如compute-0-8（例子不代表当前准入）：

    "$PY" -B "$MAT" --mode fixtures --repository "$REPO" --node compute-0-8 \
      --job-name dv1_sb2_cpu_closure_fixtures_v1 \
      --bundle-output "$BASE/control/materialized/sb2_cpu_closure_fixtures_v1"

实际336仍需原最终receipt、Root新raw sacct query evidence及父C0才能物化：

    "$PY" -B "$MAT" --mode closure --repository "$REPO" --node compute-0-8 \
      --job-name dv1_sb2_cpu_closure_actual_v1 \
      --pilot-receipt "$BASE/artifacts/conformers/pilot_32g_v1/receipt.json" \
      --sacct-evidence "$ROOT_NEW_ACTUAL_SACCT_EVIDENCE" \
      --application-output "$BASE/artifacts/conformers/pilot_closure_v1/cpu_closed_v1" \
      --bundle-output "$BASE/control/materialized/sb2_cpu_closure_actual_v1"

旧metadata helper的完整336/C0/新鲜sacct/唯一terminal父集合闸门全部保留。
script为SBATCH partitioncpu+中央受控launch：

    "$PY" -B -m workflows.data_v1_final.execution.cpu_analysis_v1.launch --intent ABSINTENT -- "$PY" -B NEW_ENTRY ARGS

runtime绑定DATA_V1_CPU_INTENT和DATA_V1_CPU_GUARD_DIR的真实monitor，
不能直接绕launch运行CPU入口。source refs含base原全部small refs及script、
新variant/runconfig、中央5+__init__、两个policyconfigs、旧submit_reviewed.py；
peak=scope.output_cap_bytes+32MiB，与中央scope原样一致。
既有同名intent/receipt/verification或输出bundle不覆盖、不自动换名重投。

## 入口与验证

fixture CPU入口 test_cpu_entry.py先中央root_guard准入，再把原6fixture的
from close_pilot import显式绑定到新close_pilot_cpu导出函数；旧测试源SHA
4b2817d082fc7831f618d74dfec3ad01f3a6c2f202ee900256f425bf3901b60f固定。
没有执行旧main/旧node20守卫。新增2个boundary验证：
拒绝conformer/错scope资源、中央checkpoint拒绝时任何新IO提交都不发生。
这些fixture仍无真实UFF/QM/LMDB或大数据；8case完成情况由Root实际Slurm确认。

Root可在login只做纯AST静态delta证明（不execAST/不importentry/不读数据）：

    "$PY" -B workflows/data_v1_final/conformers/pilot_closure_cpu_v1/check_source_delta.py

证明原6个数据校验函数AST完全一致；将CPU main中显式列出的guard/pool/
checkpoint/proof增量逆规范化后，main AST与原e7c8992...完全相等。
Root另跑tools/check_repository.py；不以静态证明冒充运行结果。

本次精确stage新增7文件：

    configs/data_v1/conformers/pilot_closure_cpu_v1.json
    workflows/data_v1_final/conformers/pilot_closure_cpu_v1/README.md
    workflows/data_v1_final/conformers/pilot_closure_cpu_v1/close_pilot_cpu.py
    workflows/data_v1_final/conformers/pilot_closure_cpu_v1/runtime_adapter.py
    workflows/data_v1_final/conformers/pilot_closure_cpu_v1/test_cpu_entry.py
    workflows/data_v1_final/conformers/pilot_closure_cpu_v1/materialize.py
    workflows/data_v1_final/conformers/pilot_closure_cpu_v1/check_source_delta.py

没有修改原formal_v2五文件、closure四文件或前一metadata materializer两文件。
readonly P′vector prepare CPU入口未在本目录实现，交Root/SB4另行绑定中央runtime，
不碰其科学/QM源或跨越SB2责任路径。
