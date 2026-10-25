# 两个缺包的恢复提案：未授权、未运行

本目录新增源码，不修改任何旧科学源码、配置、批准、任务、包、原closure或历史验收。
没有提交器、Slurm模板、后台协调器、自动续跑或正式人群放行。
`recovery_v1.template.json` 与 `recovery_approval_v1.template.json` 均为待决模板；
直接运行 generator 会在读任务正文、导入化学代码和启动worker之前拒绝。

## 已观察到的事实与输入

Root只读审计4520527在compute-0-17实际C0/2s/16CPU，报告为：

- 原336试点4520364为TIMEOUT，parent14425s×16=230800核秒=64.111111核时。
  Exit0:0不改变TIMEOUT，batch/extern不重复记账。
- 334个包完整可复用，2缺包、0损坏、0意外目录条目。334个完整包不是334个科学成功：
  SUCCESS102、EMBED_FAILED41、INSUFFICIENT_CONVERGED_CANDIDATES42、
  PM7_STEREO_UNRESOLVED25、SOURCE_CONFORMER_GRAPH_OR_ATOM_ORDER_MISMATCH33、
  SOURCE_SMILES_ATOM_MAPPING_FAILED41、SOURCE_SMILES_GRAPH_MISMATCH50。
- 缺包为principal_01112964/N7、principal_00509656/N10，原cohort均retry_once、原状态EMBED_FAILED。
  候选级嵌入/优化状态只在RAM中，没有可恢复checkpoint；只能按同一原任务/输入/seed重新执行整个分子。

模板绑定实际Root路径/bytes/SHA：
`artifacts/conformers/partial_pilot_audit_v1/audit_v1/audit_report.json`
37509B / 9fb99edd7fb447949be3d2e7e113c30d4fc8e5529ab83864aa79f4934cdf21a2；
`artifacts/cpu_analysis_guards/dv1_partial_sprime_audit_cpu_v3/closure.json`
1991B / f62a895c00a202533de69af35377c8b9f8c60baa7c8853f76c29d09791477437。
前者的outputs继续绑定991378B的complete_packages、missing、原tasks等引用。
原prepared54827B/74b1cda8…、原recipe3629B/cfd153fb…、
原tasks4912072B/d10c0984…保留；tasks只在实际CPU准入后完整核SHA和读取。

## 科学与执行范围

`run_recovery.py`直接调用原`run_pilot.run_one`，继而原`science.process_task`与统计；
原recipe/config字节、同一原task字典、所有PM7指针/旧accepted几何、seed、10N/300、
ETKDGv3、UFF参数、0.5Å/固定重原子proper-Kabsch与选择逻辑都不改。
新增的是物理执行，不是第二次logical retry；不创建formal once key、不换seed。

334个旧包只保留原路径与SHA引用，不复制、不覆盖、不以新计算替代其科学人口。
额外14个控制来自334中SUCCESS且new_real_accepted_count>0的分子，按MID字典序取前14，
模板冻结清单，运行时从原audit重新核对。原审计有86个合格控制；不以失败或空几何充数。
控制用于同种子复现，结果单独写`controls/reproduction`，不加入336人口，也不替换旧控制包。
比较整个原结果（坐标、能量、原子序列、候选身份、seed、orders、统计、raw审计候选），
只移除`summary.elapsed_seconds`；其余任何bit可见差异均失败，不扩大数值容差。

16spawn worker各进入同一个屏障（120s启动超时），16个不同PID都到达后才调用原run_one。
总执行16项=2missing+14控制；记录PID/start_ticks/job/UID、taskSHA与结果SHA。
若初始化/屏障失败，科学函数尚未开始；没有额外重试。正常科学失败仍原样保存，
IMPLEMENTATION_ERROR或身份错误不能伪装完成。所有已经运行的分子自然结束，不发信号。

原包中的sprime_conf_idx是原producer行rank，原original_sprime_conf_idx和全部几何身份保留。
恢复联合产物明确命名package_*，不是formal physicalID导出。
正式旧ID保留/新ID追加仍必须走独立formal_v2；本目录不重新编号、创建来源或N1第二候选。

## 资源、预算与审批仍待Root

generator只接受新的kind=conformer/pilot=true、16CPU64GiB、cpu分区、节点14–19的Root请求。
沿原submit_reviewed.py与common.require_preflight，全部用户声明合计≤85%；任何别的作业
MinMemoryNode/CPU=0仍为无明确上限，阻止本恢复。无CPU-analysis scope或旧memory_basis替代。
正式生成原64GiB/all-user85规则完全不变。这里没有创建32GiB恢复例外。

运行期复用原32G模块的owned-process采样与MemoryMonitor类，**不调用其旧批准验证入口**，
不借用旧336批准。新包装器更严格地另核：实测used+全部已知正声明+完整64GiB请求≤85%，
并保留原24GiB自有RSS守卫作为额外保守限制；1s采样/2s新鲜度不放宽。
内存紧张只阻止新派发并自然drain，结束后保存全部memory证据。只有16项启动批次，无后续追加。
实际首次运行是否通过这些守卫尚无证据，不能声称已验证。

原64核时是旧声明估计，实际已64.111111；原1.5倍门槛为96核时，
剩余31.888889核时，按16核仅7175秒=1h59m35s。
两个missing在原4h仍未完成，不能据此假称剩余额度足够或给出可靠点预测。
模板wall_seconds与additional_allocated_core_seconds_cap为null；Root必须取得新的具体预算/资源决定，
冻结新plan与独立decision。allocation ceiling不是成功耗时预测，任何48h上限也不是预计运行时。
新decision必须精确绑定plan、费用ceiling与实际用户答复，且original_336_approval_reused=false。
原TIMEOUT、重复物理执行、控制、失败与scheduler实际费用全保留。

运行中以本段已观察elapsed给出保守下界；达到原1.5倍门槛时写
COST_GATE_STOP_NEW_DISPATCH.json，Root须立即报告用户并停止后续提交，
已运行分子依指南自然结束。最终以实际sacct parent计算是否越限，不能用worker秒或step代替。
本目录不放行后续full，不自动把新预算决定解释成已通过科学/费用门槛。

## Root审核与未来精确CLI

先Root纯静态/AST/check_repository，再在真实CPU allocation内运行六个新边界：

    "$PY" -B "$REPO/workflows/data_v1_final/conformers/recovery_v1/test_recovery.py" \
      --root-preflight "$NEW_ANALYSIS_INTENT"

该测试入口接受已授权、无新UFF/QM的分析监控；不运行原producer/旧科学测试。
6项为334+2守恒、拒绝控制混入/路径复用、只排除elapsed的精确比较、task输入变化、
TIMEOUT+Exit0不升级且steps不重复计费、待决plan不得启动。
Root应把新四个py与原九个依赖、recipe、partial audit/monitor等small refs全部pin。
模板required_additional_source_relative_paths列出代码；原tasks为data ref，不在登录节点hash大正文。

取得新预算/资源决定并冻结新的Root plan/decision后，未来generator CLI：

    "$PY" -B "$REPO/workflows/data_v1_final/conformers/recovery_v1/run_recovery.py" \
      --plan "$NEW_ROOT_APPROVED_PLAN" --approval "$NEW_INDEPENDENT_DECISION" \
      --root-preflight "$NEW_GENERATION_INTENT" --output "$RUN/artifacts/conformers/recovery_v1/run_v1"

本目录没有生成这些获批文件或提交。不要对模板改status后直接借旧intent运行。

新恢复真实C0后，Root新query必须含4520364、4520527、新recovery父，
可附同批其它真实terminal父；raw请求集合必须守恒。Root再备独立只读CPU closure：

    "$PY" -B "$REPO/workflows/data_v1_final/conformers/recovery_v1/close_recovered.py" \
      --plan "$NEW_ROOT_APPROVED_PLAN" --recovery-receipt "$RECOVERY/recovery_receipt.json" \
      --recovery-submission "$NEW_ACTUAL_SUBMISSION_RECEIPT" --sacct-evidence "$NEW_REAL_QUERY_EVIDENCE" \
      --root-preflight "$NEW_ANALYSIS_INTENT" --output "$RUN/artifacts/conformers/recovery_v1/closure_v1"

closure分析可使用原sprime_pilot_closure_336（336/原job4520364/newUFFQM0）有限scope，
但**generator绝不能使用该分析scope**。closure cap1GiB/1h/16CPU，中央runtime_v2保持；
新plan、receipt、submission、query/raw、原输入、所有new/old代码都须按实际Root路径pin。
它用最多16个在途IO任务重新核334旧包+2新包CRC/SHA/身份，并独立重核14控制。
旧334的fstat/device/inode/mtime/UID与原audit须相同；跨节点若设备身份不同须Root先建立
独立观测证据，不能静默删掉该校验。原目录334条目变化也要求重新审计。

联合包清单恰336且原334路径逐字节引用，控制只在独立证据里。
产出package_molecules/package_conformers float64 parquet、SHA读回、package_orders、
cohort报告、试点descriptive统计与真实parent accounting。原PM7 native-anchor顺序仍仅诊断，
不能替代canonical WP5 HOF。worker秒只统计已封包部分，丢失原尝试不推测，控制另列。

新schema为RECOVERED_SPRIME336_PILOT_CLOSURE_V1；原TIMEOUT仍TIMEOUT，
只有新恢复parent可C0。旧strict336/C0 closure与planner不会自动接受此新schema。
pilot_accepted_for_planning/root_review_granted/formal_generation_authorized/common_frozen始终false。
费用越限只报告新status，不能称试点已过关；Root仍须单独审阅科学失败/成本，并为后续planning
另作显式兼容审查。没有最终共同人群、最终D7或正式ID/全量完成声明。

## 本次交接限制

本子agent仅通过X写新源码/metadata与人工读取核对；没有Python运行、AST验证、测试、
科学计算、SSH、Git或Slurm。所有执行、合并、实际授权与费用核验由Root完成。