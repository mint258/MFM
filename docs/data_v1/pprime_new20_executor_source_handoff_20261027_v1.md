# NEW20 执行器与一次性具体审批交接

新包 `workflows/data_v1_final/pprime/strict_numerics20_qa_v1` 共10件：完整 runtime、actual-parent contracts、metadata draft/finalize、3项合成fixture和README。旧 prepare9、strict15、协议、原Scientific函数及结果均未改。SB4未执行Python/AST/tests/DATA/SSH/Slurm/QM，未向Root或Alpha安装。此交付是可审源码，不是用户批准、测试PASS或任何科学放行。

执行上限为实际只读 prepared20 的20个唯一MID×原12任务×B1/B2/R1/P1/P2=1200；仍原1..80原子边界、原rank0独立target-independent seed20261010抽样、原atom order和精确P90坐标轴变换。仅固定候选协议原三字段差：pm7_B SCFCRT=1.D-9、xtb_singlepoint/xtb_perturbed_gradient --acc0.01，其它9任务与原900s/method/version/seed完全不改。不新UFF，不以旧20条审计记录冒20MID，不使用最终Common人口声明。

Root已报告实际只读准备4523779 C0/60s/16CPU13/960coresec，prepared20.json450663B/SHA914396b240ccadc0cef4d37ec80c4fe511f1b47f36b2bb8499fd282077f774800；780 eligible、220>80 QA-unavailable、invalid0。这里只20个≤80atom有限诊断，对220大分子不得外推。实际Parent account control/accounting/pprime_new20_zero_invoke_prepare_4523779_actual_C0_v1.json1054B/SHA3383202c551421cec63bbcf99c3699dccf3b6419f1333c70816d03917e6850c8。原prepare声明463 DATA=17核心(1pair+5S′+11LMDB)+446executionassets，不误写16核心；执行meta/runtime仍须CPU实际producer链核验，不因本memo数字绕门。

Root实际准备独立验收记录是 control/root_actual_pprime_new20_zero_invoke_preparation_review_v1.json4091B/SHA7aa9b91cfef8844f2f5955c294597909d7ddff5f6ab7d4ccd761bee6bbb8d7c49。新executor的Source3与具体执行预算仍待Root实际验证/审查，用户新1200授权仍不存在。

硬门顺序是新 USER_AUTHORIZED_PPRIME_NEW20_ALL12_STRICT_QA_V1 决定→实际prepareC0/account/raw/3pure/source/proof及1200 cell→fresh central-v2 exactQM proof/Rootreview→新3pure→实际quota/RSS/storage→DATA/候选initialize/原Native.invoke。旧15批准与成本报告继续权限不能替代新决定；runtime在父件遍历前即拒缺批准。新决定必须绑定实际prepared20/protocol，并明确1200/20/12/5、16CPU/86400s/900s、combined32GiB/prep1GiB/exec31GiB/closed25MiB/UNKNOWN112MiB/max16及unknown/scratch软限边界。只提供批准模板不能生成可运行stage；用户真实答复后需fresh request/新Rootscope审查。

Root最短元数据流程：request schema ROOT_REQUESTED_PPRIME_NEW20_USER_REVIEW_OR_EXECUTE_V1，status REQUESTED_FOR_REVIEW、requested_by root；字段 prepared20_reference、prepare_accounting_reference、original_protocol_reference、candidate_protocol_reference、quota_reuse_reference、resource_authority_reference、cost_decision_reference、fresh output_directory、user_decision_reference（先null）。output在 RUN/artifacts/pprime_strict20_all12_qa_v1 下、避开 independent_once_ledger。

```
python -B -m workflows.data_v1_final.pprime.strict_numerics20_qa_v1.metadata draft --request ACTUAL_REQUEST --output FRESH_CONTROL
```

这只在实际prepared20 C0之后生成具体用户提案/未授权决定模板；不读1200科学task或input正文、不造未来hash。准备阶段真实Parent费用、source/prepared refs和实际排除计数附提案。用户新答复前没有Rootscope template/可运行spec。真实决定后用fresh request再次draft，再由Root独立批准 exact template，运行：

```
python -B -m workflows.data_v1_final.pprime.strict_numerics20_qa_v1.metadata finalize --draft NEW_CONTROL/draft_receipt.json --root-review ACTUAL_ROOT_REVIEW
```

之后Root才可沿原central queue提交 Main Python -B -m workflows.data_v1_final.pprime.strict_numerics20_qa_v1.run --plan ACTUAL_PLAN --startup-proof ACTUAL_PROOF。本包无submitter/新队列算法，无Alpha接入。当前实际quota mapping仅CPU13，固定16/no_mem/noexclusive/24h，QoS按原central不改。实际有限account Client、共享physical与whole-wave+ownremaining+200GB两轴复用；provider不续约，成本超估报告继续、质量不改。

一次性键为已冻new20 domain + candidate triple + actualprepared20 triple + qa20cell；ledger原子O_EXCL/fsync先于submit，至多16 pending。碰到任何旧new20已消费claim即HOLD，不清旧once、不自动重试/替补/换namespace。新的resourceEvent仅用于派发，**绝不传**原NATIVE.STOP_EVENT；在跑程序沿原900s/原deadline规则自然收尾。新源无替换NATIVE函数，只有一次直接原invoke位置，原函数源码identity由冻结原例程核对。

每call所有raw审计留存，原RawSink之后再closed wholeSHA+BoundedRawReader(gzip EOF/CRC)+原unbundle/memberSHA+inputBundle核验，独立vector parser取该closed readback bytes。实际postcall inputs另存并逐字等于prepared candidate。原native返回、WP5status、SCF与各未知状态分开原样存，不用metadata伪补成功。scratch只有durable raw readback完成后才原cleanup；不明/live进程及错误scratch保留。

parent不扫描active输出树。每active/不明call预留112MiB，原Store预付SQLite journal；worker关闭全部写者后精确quiescent文件字节（含terminal）≤25MiB且原defined QC有效才结closed。超额或unknown保留112MiB并停新派发，不截断/删raw为凑PASS。parent256MiB，不把1200个≤8MiB科学结果常驻内存，五臂分组durable后释放。上界角色公式 prep1024MiB+parent256MiB+1184×25MiB+16×112MiB=32672MiB，距32GiB余96MiB；前提是角色关闭/stop机制，非每call成功/小体积承诺。

node scratch另轴观测：每worker2GiB soft threshold、tmp-free4GiB floor，原RLIMIT_FSIZE128MiB是单文件；不宣称总scratch硬上限。实际递归RSS16GiB和MemAvailable max(4GiB,15%)为软件停派阈值，不是内存申请/保证。观察异常/provider expiry/墙钟不足900+180秒自然停新派发，无新强制信号。即便保留原capture有大缓冲，soft监测也不虚假保证无OOM；失败费用与原始证据均保留。

科学判定不扩大：原定义可判定的input/raw/native WP5status/array QC或四种vector门FAIL/UNKNOWN即停止新派发并收尾。五关系B1/B2、B1/R1、B1/P1、P1/P2、B1/P2用原covariance/print半宽/四对象tol；完全收集期望500项vector检查，PM7B和xTBgrad仍需自身坐标/原子序证据、xTBgrad原force关系。其它9 task basis/tensor/axes及SP没有独立output坐标必须UNKNOWN，不冒PASS；这些共享语义缺口阻止科学放行，但不把第一16调用因同一约定未知而全部停掉。没有新tensor门或extra companion，更不从不同几何旧15数值伪造同输入baseline。

新3pure（待Root真实CPU）：①旧15/缺决定/模板/错prepared20或资源拒绝；②原子once互斥、1184closed+16active预算、25M→112M UNKNOWN停新派与自然drain；③20MID×12×5范围与原子轴约定、共享解释UNKNOWN不假axisPASS且真实原任务失败仍拒。均无真实DATA/initialize/invoke，不重复旧3。

建议最后一次具体问用户：是否批准“对已实际冻结的20个MID执行最多1200次有限严格数值QA，只有已测三参数变化，16CPU≤24h，准备+执行共享32GiB，单次原900s、不重试、全raw保留；失败或资源压力停新派发并收尾，原15FAIL及2000/full HOLD不变”？旁附真实prepared20/account/protocol refs、程序/fixture实测和资源/UNKNOWN说明。384核时仅24h最大分配ceil，不是预测或实际费用。Root实际准备与新pure证据闭合后才问；本交付未声称已经问或批准。
