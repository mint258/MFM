# SOURCEFINAL: Alpha 单一官方2013 QM7b ZIP 获取/opaque inventory

10件新源：consumer7 `workflows/expansion/secondary_qm7b_official2013_acquisition_v1`；thin3 `workflows/data_v1_final/execution/secondary_cpu_readonly_qm7b2013_v1`。控制器与已冻v13逐字节一致（25237B，机器pin在manifest）。旧11源获取目录及所有科学源码/数据/UNKNOWN均未改。SB4未运行Python/AST/tests/科学DATA/SSH/Slurm/Git，未获取ZIP body；Root独立sourcecheck/部署/实际CPU运行/记账。

复用原 `secondary_external_sources_acquisition_v1.run.NoRedirect/safe_headers` 和原CSV6 Budget/journal函数对象。原 acquire engine不能接受此冻结目录之外的URL，故不调用/改写它；新seam仅一次普通GET和标准ZIP逐成员opaque核验。无新调度算法。

## 实际前置小SOURCE

原字节复制下面两件到 AlphaRoot `/metadata/qm7b_official2013_v1/`（源码包内有原字节副本及manifest）。它们是已SOURCEFINAL的小研究文档/响应头观察，不是科学archive：

- `qm7b_official_graph_rowmap_research_20261027_v1.md`：7303B，SHA取manifest/实际源文件。
- `qm7b_official_candidate_http_metadata_20261027_v1.json`：3752B，SHA取manifest/实际源文件。

新contracts已通过本机源码文件机器SHA转录这两件实际pin，不允许换成未来图/映射结论。原HEAD仅证明原作者2013页面实际href的精确URL可达/长度：`https://www.mrupp.info/Data/2013dsgdb7njp.zip`，HTTP200、application/zip、2671083B。另一个QM/ML候选不会被本job下载、fallback或视同字节。初始archive SHA仍UNKNOWN；请求/plan不带伪初始DATA locator。

## 最少新请求字段

标准Alpha来源authority/base8 review/cost/scope7之外，只需这两件小SOURCE refs和新output/proof，不需要旧科学body/全MAT/XYZ/journal/任何未来account：

```text
schema: ROOT_REQUESTED_ALPHA_QM7B_OFFICIAL2013_OPAQUE_ACQUISITION_V1
status: REQUESTED_FOR_REVIEW
requested_by: root
primary_research_reference: 实际Alpha metadata下原7303B memo triple
official_HEAD_reference: 实际Alpha metadata下原3752B HEAD JSON triple
adapter_source_review_reference: Root独立批准的source-template副本
base_controller_review_reference: 现有真实8-source base review
resource_authority_reference: 现有USER_AUTHORIZED Alpha资源ref
cost_decision_reference: 现有report-and-continue且质量不变ref
storage_review_reference: 实际scope7 triple
python: 实际Alpha Python3.11.14绝对路径
node: 现场可用且属于Alpha现有allowlist的CPU节点
output_directory: NEW AlphaRoot/artifacts/...目录
startup_proof_path: NEW AlphaRoot/control/secondary_startup/...json
```

KEY=`qm7b_official2013_zip_acquisition_alpha_v1`；module=`secondary_qm7b_official2013_acquisition_v1.run`；PLAN=`SECONDARY_QM7B_OFFICIAL2013_ARCHIVE_PLAN_V1`；PROOF=`SECONDARY_QM7B_OFFICIAL2013_ARCHIVE_STARTUP_V1`；stage=`AUTHOR_2013_QM7B_OPAQUE_ZIP_SHA_CRC_INVENTORY`。analysis，pilotfalse/performancefalse，16CPU/no_mem/noexclusive，600s/2GiB/scope7。网络读取进程1，不伪称16下载worker。

## Root最短CLI

`PY/M/D/R/SCOPE7/AUTH/BASE_REVIEW/NODE/QUEUE_NEW` 均由Root取实际路径。所有命令仅为交接，SB4没有执行：

```sh
cd /gfshome/alpha/codex_data_v1_20261026/code
PYTHONPATH="$PWD" "$PY" -B -m secondary_cpu_readonly_qm7b2013_v1.materialize source-template --source-manifest "$M" --output "$D/source_review.template.json"
# Root独立审核，另写APPROVED_FOR_EXACT_METADATA_ADAPTER/reviewer=root的原字段副本；再写实际request R。
PYTHONPATH="$PWD" "$PY" -B -m secondary_cpu_readonly_qm7b2013_v1.materialize draft --request "$R" --output "$D/spec"
# Root独立审核exact scope/URL/limits/source/parents，另写APPROVED_FOR_EXACT_STAGE/reviewer=root的原字段副本。
PYTHONPATH="$PWD" "$PY" -B -m secondary_cpu_readonly_qm7b2013_v1.materialize finalize --draft "$D/spec/draft_receipt.json" --root-review "$D/scope_review.approved.json"
PYTHONPATH="$PWD" "$PY" -B -m secondary_cpu_readonly_qm7b2013_v1.controller submit --producer readonly --input "$D/spec/plan.json" --authority "$AUTH" --storage-review "$SCOPE7" --controller-review "$BASE_REVIEW" --output "$QUEUE_NEW" --node "$NODE" --job-name dv1_qm7b2013 --reviewer root --wall-seconds 600 --max-poll-seconds 90
```

`source-template`与`draft`只产pending模板，不代签Root。`finalize`不submit；`submit`内部复用原prepare/submit_held/observe，resume/account原样。`data_references=[]`，sources为新10+原CSV6全部源+原NoRedirect所在4源+base8+两SOURCE/实际审批/authority/cost/scope/request/manifest，均只有small IO。startup proof诚实标记 `bounded_source_acquisition_scope_only=true`，而非声称网络获取是单纯既有数据读取。

## 实际CPU动作与失败边界

先fresh Alpha UID1264/节点/boot/PID/start/all8argv/当前Slurm16CPU/no_mem/全部注册储存caps+200GB核验；再原allocation内3meaningful pure；再创建原Budget，最后才GET/body。纯测试覆盖固定URL/重定向和HEAD/status失配、bounded完整/截断/不超读、ZIP完整逐成员CRC与声明mass/member限。旧fixtures不重跑。

唯一原URL、最多GET1；正常环境/默认代理/TLS继承，不改网络，不跟重定向、不range/resume、不重试、不镜像/认证绕过。403/429或任何非200/长度失配保留实际头与有界opaque响应然后HOLD。body最多16MiB；必须实际声明长度和完整EOF字节都等原HEAD2671083才能进入ZIP闭合。新job才产生首个producer SHA，并从稳定FD wholeSHA复核再解ZIP。

最多20000物理成员/256MiB总解压；每成员size/EOF/CRC/SHA全部核。原compressed响应完整保留；全部原uncompressed字节（含README/文件头/可能身份字段）保存在单一稳定blob，每成员offset/bytes/SHA在原字节fsync后写durable inventory。保留重名与directory标记，不按原路径extract/follow/import/execute，不丢文档，不解析任何坐标float/SMILES/键/映射。

原CSV6 Budget的1GiB+128MiB drain完整保留在2GiB内；RSS/MemAvailable/时间/储存压力自然STOP，partial文件不删、不信号。600s是上限，不是已测费用。成功也只表示official archive+ZIP结构完整，所有graph/SMILES/SDF/MAT rowmap仍未审查、UNKNOWN；编号或7211不得推MAT对应。Root后续另做有限CPU格式/文档审查，不自动放行原图、fallback policy、去污染或pool。新父实际终态/启动/失败费用全部由Root记账，1.5成本超估报告继续、质量不变。
