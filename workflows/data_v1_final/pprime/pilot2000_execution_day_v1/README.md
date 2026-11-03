# P′ 原2000构象×12 baseline：单日执行器

Source-only，尚未运行Python/AST/import/tests/DATA/Native/SSH/Slurm。Root统一Source审阅、资源review、安装和运行。这个包接续SB4暂停的4个未完成Source，完整提供metadata→Root review→Generic16→CPU source3→原计算→原F64导出/全部读回→实际父会计closure；没有submitter、Native替身、自动retry或full启动。

## 人口与科学边界

唯一输入是原4520345固定1000MIDs×2个完整S′的2000几何，经新的 `pilot2000_prepare_day_v1` 实际零invoke准备闭合。它不是NEW20/strict15/1200/Native30，也不等最终Common、不重新随机选分子、不加入≤80原子过滤。原selection/order seed、12 tasks、perturb seed20261010、sigma0.1 Å、原版本/程序/900秒/全部parser、atomic-array/nonfinite/scope/Q02及保留协议不变。真正调用直接原 `engine_adapter.compute_pair`，内部为原 `NATIVE.invoke`；原 `RawSink`、`export_families.export`、`retention_policy_v1.prove_raw`、`close_pilot.assess` 均使用原函数/类对象。`source_origin.json` 对这些模块及几何/序列化依赖固定完整Source bytes/SHA；新Source不复制科学函数、公式或codec，也不改原模块。

每个构象仅一个baseline×12，无旋转臂/参考臂/companion/新QA。结构上最多24000次；原invoke自己异常而没到原raw sink的实际attempt保持UNKNOWN，不能以dispatch或返回观察数伪造实际调用数。完整成功时24000原raw-sink return均逐record可审。所有partial/error/raw/scratch和未闭状态保留；无重试，不因输出目录、mode或精度改变重开once。

原全2000 pilot once key字节表达式与旧retention runner一致：`['original2000-pilot-science-once-v1',originalPairsSHA,originalProtocolSHA]`。仍使用原 `artifacts/pprime_retention_v1/pilot_once`。新增物理record key只细化原全局保护，绑定MID/原conf_idx/坐标SHA/原protocolSHA，故不能绕过全局已消费claim。旧全局claim一旦存在即拒绝；不代Root清理或恢复它。O_EXCL+fsync先claim再派发，claim不是已返回/成功证明。

## 精度两模式

- `ORIGINAL_WP5`：原协议，Root exact2000 scope据指南授权；user_precision_decision_reference必须为null。
- `TIGHTER_ONLY_THREE_FIELDS`：固定候选三差异（pm7_B `SCFCRT=1.D-9`、xtb_singlepoint和xtb_perturbed_gradient `--acc 0.01`），原其余9task/900秒/seed/sigma/质量不变。但必须有新的真实 `USER_AUTHORIZED_PPRIME2000_TIGHTER_PILOT_V1/USER_AUTHORIZED` 正ref，精确绑定本实际prepared2000、两协议、2000/24000/16CPU/86400秒/32GiB与禁止自动retry/full。Root scope还须引用同一用户ref。

当前没有tight2000用户授权。缺ref时draft产生NONEXECUTABLE、无plan；runtime在DATA、claim、engine initialize/invoke前也拒绝。15、1200、Native30的授权和PASS从不满足这个门。源里定义这个schema不构成授权；Root应在准备真实C0与完整执行Source审查后给用户具体提案。

## 准备header与科学DATA分离

metadata只读Root新增的纯producer header：

`PPRIME_ORIGINAL2000_ZERO_INVOKE_PURE_CLOSURE_HEADER_V1 / ACTUAL_PREPARED_OUTPUT_CLOSED_ACCOUNTING_PENDING_NOT_NATIVE_AUTHORITY`。

它只有counts/locators、plan/proof/source3/两protocol refs和init1/invoke0/oncefalse，无MID/坐标/数值。其pending accounting**不算C0**；必须另以实际account/raw验证准备Parent真实COMPLETED0:0/16CPU/原node，proof/Source3与header同job。实际header尚未产生或account缺失时context只能NONEXEC，不造futureSHA。

`prepared2000.json`即使目前为JSON仍列DATA；同样原19MB pairs、record_input_hashes、orders_and_lineage、stable_source_audit、audit-selected Parquet及原大来源/软件refs均按positive/non-bool/64hex大locator声明，不套small-source2MiB规则。实际CPU source3后wholeFD-SHA/当前frame读prepared正文，再与纯header精确核对。随后原pairs reader与原Native payload/atomorder验证及每record12个预渲染input-file hashes闭合；原选中输入/返回hash都核对，不靠新名字制造child几何。

446 execution assets在CPU验证：432普通project DATA沿原Body，14个原外部软件路径沿准备R2的literal exact14 registration+同一软件only reader，包含真实alias链、owner/mode/完整SHA/同FD前后稳定。没有放宽普通Body根/UID/正数约束。原initialize可唯一写入本worker实际scratch_base；新IO校验只排除这个明确scratch上下文字段比较，原其余整个protocol必须相等，不能笼统忽略资源/数值字段。

## 一个真实Parent与预算

Generic `execution.cpu_auto_memory_queue_v2` 原机制，exact module
`workflows.data_v1_final.pprime.pilot2000_execution_day_v1.run`，scope
`pprime_original2000_formal_pilot_day_v1`。真实16CPU、86400秒、无mem/exclusive/GPU，node只能当前已复用storage/resource路径的13/14/18，由Root现场选择。不借在跑S′/labels的quota身份或旧lease。新的实际有限25h provider要覆盖实际剩余wall+300秒，维持0..120秒、200GB与全部future exactonce；资源小未来时钟分支只用已冻结共享guard，不改原provider/expiry。

资源request `pilot=False`，`scope_parameters.scientific_pilot_2000=True/resource_pilot_relaxation=False`。它是科学试点但没有放宽资源。Scope mode沿原 `BOUNDED_PERFORMANCE_BATCH`，必须Root实际 `bounded_batch_limits_reviewed=true`，`parent_profile=None`；该validator只在FULL_SOURCE_AFTER_PROFILE要求profile，不伪造本阶段科学profile或PASS。

固定persistent16 spawn workers、最多16 pending physical records，每个worker只初始化一次，复用原engine并逐record调用。Native原900秒不缩短，不把resource event传入Native lifecycle；停止派发后自然完成已入场record。每record可能12个顺序900秒调用，故最坏12×900+120秒才允许领取新record；一天不足时保留游标/once/partial，不承诺强行完成2000或自动下一天重开全局once。

共享32GiB为Root待实际review的proposal，不是已获配或最大输入等于最大输出。角色预算为8GiB parent+16×1GiB active/UNKNOWN+实际closed records，动态不得超过32GiB。每record原RawSink cap768MiB含原SQLite journal判定、F64解析record128MiB、终态metadata及保守余量。Parent8GiB包含原F64 family export重复副本、retention proof、所有metadata/worker闭合/guard。原exporter只是传入更窄whole-output cap，算法/codec不改；实际family bytes从parent剩余空间扣除并保留512MiB管理/收尾。不足即停止/失败保留，不截断label/raw或挪费用。

Parent借原observer的check和原quota/guard方法；唯一used() IO seam改为预付active/UNKNOWN/private+parent roles，避免父进程stat正在原子rename的活输出树。它是保守预留量，report不冒称实际used。closed record结算才做quiescent统计。原RSS观察为parent+直接children，report不冒全部Native descendants峰值；真实MemAvailable继续检查。`/tmp`每worker沿原Scratch软观察2GiB及原per-file128MiB，不声称2GiB是整个Parent的硬scratch总上限，不强发signal。

## Source3与输出

同一个正式Parent内在科学DATA/claim/initialize前恰3个meaningful methods：

1. 未授权tight/旧诊断schema/错误prepared/数值更改拒绝；仅真实owned scratch差异可接受。
2. mode/output不能改原once身份，真实exclusive claim第二次拒绝，原staging保存None/-0/NaN F64位；直接原函数对象路径核验，无Native initialize。
3. UNKNOWN不释放private保留额，16active上界；已返回raw packet与durable sink失败分开记录，不填成功/重试。

fixture生成成功不说明实际Native/2000/物理轴已PASS。Root统一实际Source检查；作者只做Source/小JSON字节打包。

每record独立原RawSink容器、原F64 staging、全部task/输入SHA、call观察、failure/UNKNOWN及终态。父进程等全部16真实process退出/close后才能原F64 family export及全字段bits/type读回；原union1%分层+原20审计全12及每个失败raw走原prove_raw。原compute_pair对unfinished异常不返回完整record时不拼造record，已durable raw和不完整attempt如实保留并使技术闭合失败。

`per_record_cost_observations.DATA.json` 保存原scientific elapsed与worker wall、失败/UNKNOWN；不伪分配父allocation到每一record。实际费用最终只用Parent `AllocCPUS*ElapsedRaw/2000`，包括启动/失败/timeout/导出/保留/检查；准备C0及其他历史费用另引真实account不删除。两项费用规则严格分开：generic allocated core-hours超过pilot估算1.5倍的授权是报告后继续已授权工作；它不豁免P′正式试点的WP5基线7.8×1.5=11.7核秒/请求记录门。原assess的`allocated_seconds_within_1_5x_wp5`与所有其它门完整保留；实测>11.7必须报告且HOLD全量，不签scientific PASS。≥99.5% record全12成功、原1%质量mask/Se/原raw/其他科学门保持。P′全人口异常/与P对比分布尚需其原科学路径实际完成，报告明确pending，执行闭合不冒scientific PASS/full许可。

## Root实际CLI

本包旁 `context.DRAFT.json` 全部未来ref为null，不是Root签名。Root填已有真实header/准备DATA/account与父链、实际资源/新provider/identity/carveout/cost决定，另存真正request并审阅。没有prepared/Common未来hash自动填充。

```bash
"$PY" -B -m workflows.data_v1_final.pprime.pilot2000_execution_day_v1.metadata draft \
  --request "$ACTUAL_ROOT_REQUEST" --output "$FRESH_METADATA_DIR"
# Root独立签署 root_review.template.json 的精确副本为APPROVED_FOR_EXACT_STAGE/reviewer=root。
"$PY" -B -m workflows.data_v1_final.pprime.pilot2000_execution_day_v1.metadata finalize \
  --draft "$FRESH_METADATA_DIR/draft_receipt.json" --root-review "$ACTUAL_ROOT_REVIEW"
# Root用原Generic16 materialize/held/activate/fresh proof流程；作者不提交。
"$PY" -B -m workflows.data_v1_final.pprime.pilot2000_execution_day_v1.run \
  --plan "$FRESH_METADATA_DIR/plan.json" --startup-proof "$ACTUAL_STARTUP_PROOF"
"$PY" -B -m workflows.data_v1_final.pprime.pilot2000_execution_day_v1.metadata close \
  --plan "$FRESH_METADATA_DIR/plan.json" --startup-proof "$ACTUAL_STARTUP_PROOF" \
  --accounting "$ACTUAL_PARENT_ACCOUNT_JSON" --result "$ACTUAL_OUTPUT/result.json" \
  --output "$FRESH_ACTUAL_CLOSURE"
```

如果Parent失败且没有result，close可省--result，只记录真实terminal accounting/UNKNOWN，无伪造2000结果。closure保留原assess所有逐门结论，包括独立11.7核秒/记录门；generic allocated-hours继续授权与该门没有覆盖关系，超门仍HOLD全量。当前准备实际C0、tight授权、资源、CPU tests/Native运行均未由作者声明存在。

## R3 inactive-executor compatibility with actual prepared03_cpu19_r3

The original Source9 R2 executor had not been installed or run. This revision does not claim an executor path failure or change any installed preparation. Actual zero-invoke preparation4524807 onCPU19 already closed all446 assets, including14 software originals, with the installed preparation R3 reader and schema.

The original executor run.py:41–48 already calls that very same Preparation.hash_software_original for the exact14 C.P.software_original_specs entries; it never sends those conda/system files through the ordinary Body. XTB installation and original configuration files are already inside the ordinary reader's existing /share/home/zixiao/descriptor_analysis/runs domain and remain exact frozen execution_asset_references. No global path guard, software reader, source UID/mode/alias chain, wholeSHA, software version, original protocol, prepared2000 body, input selection, once, timeout or threshold is changed.

The only executable delta is the same explicit CPU19 quota Client branch already present in the successfully used preparation R3. Without it, the inactive R2 Budget would incorrectly routeCPU19 to the14/18 Client. CPU13 and14/18 paths remain byte-for-byte unchanged. contract.sources already inherits the cpu_analysis_cpu19_v1 Source closure from the actual preparation contract, so no invented or missing resource Source is added.

Read-only software paths are descriptive below, not new arbitrary-root permission: /share/home/zixiao/.conda/envs/chemprop/bin/python; /share/home/zixiao/.conda/envs/mopac/bin/mopac and the six exact frozen libraries under its lib directory; the six exact frozen loader/C-library aliases under /usr/lib64. The existing project-contained XTB prefix is /share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010/software/xtb/conda_env (bin/xtb, producer-pinned lib and share/xtb files). The original native MOPAC reference files are under the same run's software/mopac_reference/native_v2. Original WP5 configs are /share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/configs; current pilot recipes/protocol authorities are exact refs under repository/configs/data_v1. Directory names confer no read authority alone: only the unchanged producer-pinned446 references and exact14 whitelist are read.

Original source3 runs in the one real execution Parent before DATA/claims/initialize; no separate preflight or new diagnostic is introduced. Original WP5 production precision,900s per call,no retry,99.5% success and11.7 allocated-core-seconds/requested-record gate remain intact. No tighter diagnostic precision is promoted. The actual prepared03 positive pure header is used; no scientific prepared body or new selection is read on login. Root alone reviews/installs/submits the one original2000 pilot. Source author executed no Python/AST/test/SCI/SSH/Slurm and did not inspect software files or alter live Source.
