# Recovery under CPU auto-memory policy — DRAFT

未冻结、未运行Python/AST/测试/SSH/Slurm/Git，未读取真实tasks/package/LMDB/Parquet正文。此目录只为Root审查后生成新request准备源码，旧registered job/request/script/proof和原科学源码全部不改。

最新用户资源规则取代旧内存准入：16CPU，conformer/UFF/QM节点11–19；sbatch不指定任何memory选项，由Slurm默认处理。新request/proof为central `cpu_auto_memory_queue_v2`协议，memory_policy=`SLURM_DEFAULT_UNSPECIFIED`，没有memory_gib或声明85%准入。优先17以复用原共享文件device/inode身份；代码允许11–19，但不会静默放宽旧334逐文件身份检查。

原approved recovery plan及其64GiB字段原样保留，属于历史资源决定与科学/预算证据。新的resource_binding.json明确historical64GiB_is_not_new_request=true、slurm_memory_requested=false，并引用新USER_AUTHORIZED_CPU_AUTO_MEMORY_DECISION_V1；它绝不声称新allocation已申请或获得64GiB。原32GiB小试点豁免没有复用。

## Producer与最小资源适配

run_recovery_auto.py是原recovery_v1/run_recovery.py全文副本。source_edits_v1.json存原/新实际pin及11项精确文本修改：新资源runtime import/path、新--resource-binding参数与调用、移出旧RecoverySampler、all-related成本下界而非仅原generation pair、memory evidence与receipt新policy来源、当前docstring与soft guard拒绝原因文字。PowerShell文本核对已证按声明依次替换原全文得到新全文；未运行Python或AST。

原init_worker、one、原task内容/seed/recipe、spawn16与16PID barrier、2missing+14control items、old334只读复用、原control精确SHA、persist_result、read_packet、状态闭合与无signals自然drain保留。不新增逻辑retry或seed；原TIMEOUT不改C0，未保存的原missing耗时仍不可推断。

resource_runtime.generation_admit调用central runtime.require_startup，固定expected_kind=conformer、scope/params、实际primary producer、完整有序argv及plan/approval/resource-binding/newauthority/原pending替换审计/全owned总账pins。所有新文件与原科学源必须实际pin。它绕过旧IO.runtime_guard（原14–19）及旧IO.require_preflight（原声明85/64GiB），保留真实UID/job/node/16CPU、CPU-only、线程1、fresh120sec proof、recipe/全部来源、整阶段输出预算与200GB quota reserve。

严格primary/options：

`PY -B -m workflows.data_v1_final.conformers.recovery_auto_memory_v1.run_recovery_auto --plan ORIGINAL_PLAN --approval ORIGINAL_APPROVAL --resource-binding NEW_BINDING --root-preflight FRESH_PROOF --output NEW_OUTPUT`

不通过wrapper普通--producer或任意位置-m冒充实际执行者。该链由central对实际__main__/sys.argv核查；本draft尚未实际运行，不能称真实链已PASS。

## Pending替换与完整成本

Root必须先审计并仅处理自己的旧pending任务，确认无worker实际执行、无对应recovery输出，取得真实终态CANCELLED/ElapsedRaw=0的费用证据后才能建立新的binding。若旧任务已执行或产物存在，不可按“pending平替”再次执行16分子。新名、新request、新输出；旧registered文件不改。

独立审计小JSON schema=`SPRIME_PENDING_ONLY_RESOURCE_REPLACEMENT_ROOT_REVIEW_V1`，status=`APPROVED_NO_PRIOR_PHYSICAL_EXECUTION`、reviewer=root，包含historical_plan_reference/historical_approval_reference、no_prior_worker_execution_verified=true、no_recovery_output_directory_verified=true、replaced_parent_job_ids及非空evidence_references（实际旧receipt、状态查询、输出存在性审计等）。每个被替换parent还必须在完整相关实际成本中为CANCELLED/0秒/0coresec，不能把未知执行记0。

owned_costs.py只复制closing draft的资源无关small-source reader及完整owned选择函数，未复制strict64G guard。它核完整ownedV2/raw/全部actual receipts；无primary/无法确定的wrapper返回三态None，所有未知均拒绝。Root分类小pin只可解决exact旧receipt，并附实际source/sbatch evidence；不能凭准备任务/D7名字默认排除。startup重新扫全部实际receipts，除本allocation自身待终态外，新增相关parent要求新总账，新增unknown也拒绝。

科学费用门槛保持all-related实际≤345600coresec（96核时），含准备/对照/失败重复/审计/cleanup等实际相关parent。原S′ prepare4520335的9696coresec必须纳入实际相关费用；仅原230800+9696再申请6900×16已超过345600，不能机械沿用历史wall。新的独立资源binding要求0<newwall≤原plan.wall，Root用完整最新实际prefix选择较小墙钟，并显式预留read-only closure与readback validation的有限16CPU申请预算；当前实际prefix+16×newwall+两项后继reserve必须≤345600。D7仍须Root依据真实脚本明确分类，名字不能推断无关。申请ceiling/后继reserve不是forecast或最终计费上限：actual超过wall的差额仍全计、原因不推断为cleanup；最终自己的实际费用必须由Root真实terminal sacct闭合，不能用ceiling代替actual或在运行中记0。

## Soft guard与自然结束

旧ProcSampler仅复用稳定的本UID/job进程树/身份/RSS与实际MemAvailable读数；其32GiB+85% admission flags全部丢弃。新RecoverySampler不读取其它作业内存声明，不加虚拟64GiB，也不查SLURM_MEM65536。24GiB是原算法进程RSS soft dispatch阈值，非申请/预留内存；实际MemAvailable默认不足2GiB也停止新dispatch，指标无效则拒绝新dispatch。MemoryMonitor保持sticky拒绝、自然drain与无signals。16分子仍原样作为一次已审查的16worker batch启动，不引入额外分子或自动重试。

## Root metadata入口

Root集成审查后、真实pending替换审计与完整总账齐备后，可在sonmi用小metadata helper：

~~~bash
/share/home/zixiao/.conda/envs/chemprop/bin/python -B -m workflows.data_v1_final.conformers.recovery_auto_memory_v1.materialize_binding \
  --reviewer root \
  --historical-plan <ACTUAL_ORIGINAL_APPROVED_PLAN> \
  --historical-approval <ACTUAL_ORIGINAL_APPROVAL> \
  --new-authority <ACTUAL_NEW_USER_AUTO_MEMORY_AUTHORITY> \
  --pending-only-replacement-review <ACTUAL_ROOT_PENDING_ONLY_REVIEW> \
  --whole-owned-accounting <ACTUAL_FRESH_WHOLE_OWNED_V2> \
  --legacy-scope-classification <ACTUAL_ROOT_LEGACY_CLASSIFICATION_IF_NEEDED> \
  --wall-seconds <ROOT_SMALLER_NEW_RESOURCE_WALL> \
  --closure-wall-reserve-seconds <FINITE_FUTURE_CLOSURE_CEILING> \
  --validation-wall-reserve-seconds <FINITE_FUTURE_VALIDATION_CEILING> \
  --output-directory <NEW_CONTROL_CHILD> \
  --artifacts-output <NEW_CHILD_UNDER_ORIGINAL_RECOVERY_EXTERNAL_ROOT>
~~~

可选legacy分类参数不需要时省略。helper只核小JSON/code与旧输出locator，不读/hash科学数据体，不预建科学输出目录，不调scheduler。输出resource_binding.json、execution_manifest.json、stage_spec_unreviewed.json、materialization_receipt.json。已静态读取SB1实际central源码，采用其ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1与BOUNDED_PERFORMANCE_BATCH；raw spec的review=None不能直接排队。Root须另建EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1（含bounded_batch_limits_reviewed=true、真实newauthority/parents和exact字段）及一个新的reviewed spec，再由新central materializer产生新队列文件。

execution_manifest是未提交的真实候选argv/source/data refs，并非未来job/receipt/output成功证据。仍需Root源审查与合法allocation内验证、actual16/2+14闭合，以及后继在新resource policy下的独立read-only closure；旧strict64G closing draft不会接受新无memory request，不能为兼容而伪造64GiB proof。

test_resource_binding.py另有4个未运行的合成methods：更小newwall与后继reserve、机械沿用6900/漏reserve拒绝、prepare成本漏项/unknown/已执行旧job拒绝、丢旧32G85 flags并只按实际RSS/MemAvailable作soft STOP。它们隔离小metadata与sampler，不调用科学或Slurm，不代表actual admission已经PASS。Root可将以下argv放在新的合法CPU fixture allocation中（实际parent成本再进入完整总账）：

~~~bash
/share/home/zixiao/.conda/envs/chemprop/bin/python -B -m unittest workflows.data_v1_final.conformers.recovery_auto_memory_v1.test_resource_binding -v
~~~
