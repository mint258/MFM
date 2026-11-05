# v16：唯一官方三URL有界GET probe

仅 `official_three_get_probe_alpha_v1` / `OFFICIAL_THREE_URL_BOUNDED_GET_ONLY_NO_IDENTITY`，primary `AlphaRoot/code/official_get_probe_v1/run.py`、module `official_get_probe_v1.run`。复用v11 controller原文，只有3种错误标签改名为v16 GET；资源/hold/release/once/freshproof/有限foreground观察/实际parent+steps账务不变。Root可独立逆编辑验证；本交付未运行Python/AST/tests。

`PYTHONPATH=AlphaRoot/code`，现有base queue gate/probe/common、storage_scope7原样，16CPU/no_mem/wall整分钟120<wall≤3600/output256MiB/analysispilotfalse/perffalse。无data input，不能混用旧16QA/其它数据源/full或权限，不能修改旧注册文件。只有Root在Alpha实际allocation启动后，producer先5纯seam再network；登录controller只核小catalog/research/code/authority，不发HEAD或GET。

plan schema `SECONDARY_OFFICIAL_THREE_GET_PROBE_PLAN_V1`，proof `SECONDARY_OFFICIAL_THREE_GET_PROBE_STARTUP_V1`，scope mode `EXACT_OFFICIAL_THREE_URL_GET_PROBE_NO_FULL_RELEASE`，参数字典精确 `official_get_probe_v1.contracts.PARAMETERS`。沿标准readonly字段：

```text
scope_key/producer_key, scope_parameters, stage, endpoint, uid, run_root, node,
python, kind=analysis, pilot=false, cpus=16, memory_policy=SLURM_DEFAULT_UNSPECIFIED,
wall_seconds, output_cap_bytes=268435456, output_directory, startup_proof_path,
execution_argv=[AlphaPY,-B,-m,official_get_probe_v1.run,--plan,ABS,--startup-proof,ABS],
source_references, data_references=[], parent_evidence_references,
scope_mode, performance_profile=false, root_review_reference,
resource_authority_reference, cost_decision_reference,
locator_catalog_reference, origin_locator_catalog_reference,
research_reference, origin_research_reference
```

Rootreview schema/status按既有 `EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1/APPROVED_FOR_EXACT_STAGE`，reviewer=root，严格绑定contracts.REVIEW_FIELDS（含outputdir/kind）和全部approved source set。两个origin refs精确等于contracts的Main原metadata常量，Alpha copy bytes/SHA逐字相同，不重写旧catalog的HEAD字段或pending物理SHA。catalog42335B/SHAac77dff2ceef3d1b177765c7338e29aa094f0e8074c1f58d2249e3f42b5b45dd；研究8668B/SHAec9b9a996b5374fe66f5ba0cee3a6529ebca20b8ebc89c1d1992cbd3b147b745。

SourceRefs包括producer6件、v16全部py/md、base queue全部py、Rootreview/plan由controller纳verified targets、资源/cost authority及catalog/research原字节Alpha copies。后两者同时列ParentEvidence。输出严格新 `AlphaRoot/artifacts/official_get_probe_v1/<tag>`。Root实际source install/currentSHA核完再准备独立新plan/请求，三归档未知bytes/SHA不得补猜成data refs。

实际执行由Root手动调用 `AlphaPY -B -m secondary_cpu_readonly_queue_v16.controller submit --producer readonly --input PLAN --authority ACTUAL_AUTH --storage-review ACTUAL_SCOPE7 --controller-review ACTUAL_BASE_REVIEW --output FRESH_QUEUE_DIR --node ALLOWED_NODE --job-name FRESH_NAME --reviewer root --wall-seconds SECONDS`，其余沿原框架。此文档不是submit授权旁路。

实际receipt区分responseEntity全/partialSHA与TDC archive EOF+CRC SHA，MARCEL永不archivecomplete；403/错误/partial body留存，相关source失败且无重试。没有任何identity/all-split/stereo/训练或后续full GET放行。Root依据真实结果另决定下一步。
