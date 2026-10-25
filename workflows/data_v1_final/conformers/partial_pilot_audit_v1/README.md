# TIMEOUT 试点的纯只读 CPU partial audit

这是独立审计，不是恢复生成器；原6fixture、336/C0 closure、CPU runtime/guard、
science/config/prepared/原结果不改。Root报告原父4520364已TIMEOUT、Exit0:0、
ElapsedRaw14425、AllocCPUS16，batch CANCELLED0:15/14429。
parent实际费用=230800core-seconds=64.1111111111coreh；步骤保留证据不双计。
程序仍要求实际raw sacct证据，不能用本文数字代替查询，更不把Exit0:0当C0。

固定输出status/schema：

    schema=PARTIAL_SPRIME_PILOT_READONLY_AUDIT_V1
    status=PARTIAL_PILOT_NOT_ACCEPTED_FOR_FORMAL

审计子作业C0只说明审计执行成功，不改变原父TIMEOUT或授予正式planning。
即使目录334包都有效，仍不能声称原336 pilot完整；没有伪造final receipt、
reproduction_manifest或RootReview。没有新UFF/QM、oncekey或恢复提交。

## Root CPU scope

沿现有中央CPU：

    scope_key=sprime_pilot_closure_336
    scope_parameters={"expected_molecules":336,"original_pilot_job":"4520364","new_UFF_QM_calls":0}
    kind=analysis / pilot=true / partition=cpu
    resource_policy=CPU_BOUNDED_TEST_LIVE_MEMORY_V1
    cpus16 / memory32GiB / wall3600s

Root现场选cpu节点2或8–19，中央launch/root_guard/checkpoint全部照旧。
新entry调用本目录runtime_adapter_v2.admit(...,"closure")。该新adapter仅将
旧adapter的动态import从runtime改为runtime_v2，其他字节相同；原adapter不改。
新metadata runconfig partial_pilot_cpu_runconfig_v2.json仅把旧runconfig的
central_runtime_path改为runtime_v2.py，原配置与资源字段完全相同。
中央runtime_v2/launch_v2用node-local /tmp的boot-monotonic heartbeat/STOP/
samples，1s/5s等原边界保持，child自然结束后完整SHA导出global closure。
原closure config保持原pin；新增audit-config只控制独立审计输出根，不改科学。
应用cap1GiB/配额余量200GB；
request estimatedpeak=中央scope.output_cap_bytes+32MiB。
Root应使用实际已核submit_cpu_pilot_v2及prepare_request_v2/launch_v2，
保留旧v1/中央guard字节不动。

**不要调用旧metadata materialize.py --mode closure 来物化本审计**，
旧入口会正确拒绝TIMEOUT。Root用自己的独立metadata builder添加下述定位授权，
修改entry argv；Root唯一审批/Git/Slurm主体，不自动提交或重试。

## data_locator_authorization

Root在新request顶层放入以下对象；不是source_references内的大文件hash动作：

    {
      "schema":"PARTIAL_SPRIME_PILOT_AUDIT_DATA_LOCATORS_V1",
      "read_only":true,
      "expected_molecules":336,
      "original_pilot_job":"4520364",
      "pilot_output_directory":"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/conformers/pilot_32g_v1",
      "prepared_reference":{"path":".../prepared_v1/prepared.json","bytes":54827,"sha256":"74b1cda893683e070097d1784b557c6600cdf088a77a077f3026ab9d34b72d34"},
      "pilot_config_reference":{"path":"ROOT/repository/configs/data_v1/conformers/pilot_v1.json","bytes":3629,"sha256":"cfd153fb524ad823d3903b0ff7d78e402bbbcb74e124136b4bfeb3035279407a"},
      "selected_molecules_reference":{"path":".../prepared_v1/selected_molecules.parquet","bytes":13698,"sha256":"08c4a13c6ff852c4aa9bbf34d5981977d2eaa77a54751287b8abb6f74c194907"},
      "tasks_reference":{"path":".../prepared_v1/tasks.jsonl","bytes":4912072,"sha256":"d10c09845799fa1d54945e93f6b22458030d7c45303adb59305b0ef2174d8917"},
      "original_submission_reference":{"path":".../control/submissions/dv1_sb2_fill_32g_v1.json","bytes":"真实bytes","sha256":"真实SHA"},
      "sacct_evidence_reference":{"path":"Root新实际sacct query evidence JSON","bytes":"真实bytes","sha256":"真实SHA"},
      "allow_tasks_body_only_in_actual_cpu_allocation":true,
      "new_UFF_QM_calls":0,
      "formal_acceptance_allowed":false
    }

所有path用精确Linux绝对值，省略号/ROOT/真实bytes是待填示例；
prepared/selected/tasks引用直接从已pin prepared.outputs取，不自行改写。
新程序逐字段核对定位授权，没有授权就拒绝读取tasks正文。
原source metadata/hash函数仅在真实CPU进程内对4.9MB tasks及334gz做完整读取，
登录builder只hash小config/prepared/selected/query/submission/source，不hash大tasks/gz。

## source_references 与 CLI

Root builder保持中央scope要求的base原全部small refs及script、
authority_references、decision_v4/scope policy、中央5+__init__、旧submitter；
实际submitter_v2及新runtime_v2.py/launch_v2.py/prepare_request_v2.py也必须pin。
后者使用node-local实时心跳，不能让入口仍import旧sharedFS runtime。再加入：

- 本新audit_partial.py、audit config、如运行则test_partial.py；
- 原pilot_closure_v1/close_pilot.py（SHA e7c8992c...，复用read_package/distribution）；
- 本目录runtime_adapter_v2.py与新partial_pilot_cpu_runconfig_v2.json；
- 原common.py、formal_v1/full_common.py；
- 原closure config（946B/d68f0ca9...）、原prepared小JSON、原pilot config；
- 原Root submission小receipt、Root新sacct query evidence及raw stdout。

tasks/gz不放source_references（中央guard的small limit2MiB）；通过上面小authority
链和显式data_locator_authorization绑定，CPU审计现场全SHA/大小/身份再核。
selected13.7KB为纯metadata，读取columns/meta，不读原LMDB/PM7完整库。
原submission的script/source refs和原pilot config.science_source_pins都在CPU核原SHA。

Root生成的script通过中央launch执行：

    "$PY" -B -m workflows.data_v1_final.execution.cpu_analysis_v1.launch_v2 --intent "$INTENT" -- \
      "$PY" -B "$REPO/workflows/data_v1_final/conformers/partial_pilot_audit_v1/audit_partial.py" \
      --config "$CANON/configs/data_v1/conformers/pilot_closure_v1.json" \
      --cpu-runconfig "$REPO/configs/data_v1/conformers/partial_pilot_cpu_runconfig_v2.json" \
      --audit-config "$REPO/configs/data_v1/conformers/partial_pilot_audit_v1.json" \
      --root-preflight "$INTENT" --sacct-evidence "$ROOT_ACTUAL_SACCT_EVIDENCE" \
      --original-submission "$BASE/control/submissions/dv1_sb2_fill_32g_v1.json" \
      --output "$BASE/artifacts/conformers/partial_pilot_audit_v1/audit_v1"

CANON=$BASE/repository，REPO可为已整合canonical或sb2 worktree；
所有源码必须按实际路径pin。源目录不复制、不补写manifest/receipt。

## 审计内容与产物

按selected336唯一MID构建SHA256(UTF8 mid).json.gz文件名表；
目录出现意外文件/子目录/符号链接记录但不读取。原tasks只在CPU按prepared pin
读一次，核MID集合/cohort/status/N/已有accepted数/完整PM7 pointer数。
最多16个包in-flight、0.5s checkpoint等待：
整包full SHA、gzip CRC/JSON、fstat前后、元信息/N/source anchor、
原oldidx/seed/坐标SHA、new候选身份、shape/finite、原子整数序列/原native atom数、
固定seed元数据规则、严格converged/status/能量/原source refs均核验。
复用旧read_package，不重实现UFF/RMSD/科学选择，不打开LMDB。

输出：

- complete_packages.json：完整通过且可原字节复用的包、fullSHA/fstat、实际summary/
  worker seconds/old-new计数；不代表所有科学状态SUCCESS，科学失败照实保留。
- missing_tasks.json：精确缺包MID/预期filename/cohort/status/N。
- invalid_packages.json：存在但CRC/JSON/身份/校验失败的MID与异常；不删除/自动重算。
- unexpected_entries.json：母表外目录条目，保留证据但不扩大读取人群。
- cohort_report.json：只统计验证通过完整包；失败来源与耗时仍保留。
- actual_accounting_evidence.json：原TIMEOUT、step明细、raw query pin与实际父coreh。
- audit_report.json：complete+missing+invalid=336守恒、目录包总bytes、
  complete包bytes/科学worker秒、全部定位/来源pin和中央proof，status始终NOT_ACCEPTED。

未保存的missing/invalid分子worker秒不推测，不能用闭合包worker秒冒充总科学费用。
实际审计自身CPU费用由Root随后加全局账本；不混进原父64.1111coreh。
输入目录/每包fstat前后若变化则停止，不冻结活跃或变动snapshot。

## 最少新增验证与stage

4个新boundary测试：TIMEOUT+Exit0不变C0/steps不双费，拒绝RUNNING/C0伪partial，
336唯一metadata filename约束、tasks正文必须显式只读定位授权。
test_partial.py也须由中央launch/CPU guard启动（同32G analysis scope），参数
--config/--cpu-runconfig/--root-preflight；不运行producer重复科学测试。

Root可先运行纯metadata差异证明（不import/execute运行入口，不读数据）：

    "$PY" -B workflows/data_v1_final/conformers/partial_pilot_audit_v1/check_runtime_delta_v2.py

它逐字节证明新adapter仅替换一次runtime动态import、新runconfig仅替换一次
central_runtime_path，并核旧e7c8992...包验证器未变；输出双方完整bytes/SHA pins。

本次首冻新增7文件（原4文件尚未登记，入口已首冻前切到v2）：

    configs/data_v1/conformers/partial_pilot_audit_v1.json
    configs/data_v1/conformers/partial_pilot_cpu_runconfig_v2.json
    workflows/data_v1_final/conformers/partial_pilot_audit_v1/audit_partial.py
    workflows/data_v1_final/conformers/partial_pilot_audit_v1/test_partial.py
    workflows/data_v1_final/conformers/partial_pilot_audit_v1/runtime_adapter_v2.py
    workflows/data_v1_final/conformers/partial_pilot_audit_v1/check_runtime_delta_v2.py
    workflows/data_v1_final/conformers/partial_pilot_audit_v1/README.md

Root代静态检查/测试/Git/物化/提交。此交接没有实际跑审计，没有新增SSH或恢复生成。
