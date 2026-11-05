# Native S operational v7: plain-text failure-log binding

SOURCE ONLY, prepared in local Windows Temp. Not server-installed; no Python/AST/tests/Git/SSH/Slurm/model/CP/SDK execution or payload reads. Root alone transfers the19 source leaves plus pins, checks raw bytes, reviews, runs same-source QA and explicitly adopts/submits. v4/v5/v6 sources and all actual QA, adoption, logs, leases and failures stay unchanged.

## Exact observed defect and fix

Root actually installed/reviewed v6, checked the current24-row quota projection (including the new residual2GiB hold), ran CPU4524703 with30/30 metadata tests and adopted it. The next coordinator PID3204269 then failed before new lease/intent/script/slot/SBATCH: long_operations.py sent failed_v5_coordinator_stdout to common.read_ref, whose contract JSON-decodes its bound file. That reference is a plain-text traceback, so JSONDecodeError was an operational failure, not a quota/science failure.

v7 replaces that one log read with require(binding(log_ref['path'])==log_ref). A bound plain-text log remains a raw-byte identity check, never a JSON document. The new failed-v6 log uses the same raw binding. No old evidence is rewritten and no model is rerun by this fix.

The submit-next read-only preconditions now distinguish formats explicitly:

- original_failed_closure, prior_operational_adoption, failed_v5_operational_adoption, failed_v5_package_manifest, failed_v6_operational_adoption and failed_v6_package_manifest: bound JSON, original read_ref.
- failed_v5_coordinator_stdout and failed_v6_coordinator_stdout: plain-text traceback, binding(path)==rawref, no read_ref/json.loads.
- actual_CPU_QA summary and unit_result: bound JSON. Descriptor identity is a rawref; the quota publisher reads its actual JSON descriptor separately under the unchanged original protocol.

Adoption still uses the original v4 main chain, VALIDATED/principal/config/profile/initial roots/runtime/registry, original failed1411 closure and exact orphan019 lease/PID3190990 failure. It separately retains v5 adoption/23QA/PID3201293 log and v6 adoption/actualCPU4703 thirty-test QA/PID3204269 log. The exact v6 failure path is control/Root_slot019_coordinator_v6_20261029_v1.stdout.log; it must contain the actual JSONDecodeError/long_operations.py/common.py/read_ref traceback. Both later coordinator PIDs must be gone. The original18 attempts/17 successful segments/safe17000, next019 seed0/fp32 to18000 and original checkpoint are mandatory. No019 intent/submitted/script/slot or v5/v6 fresh lease is permitted.

## Version binding and unchanged guards

New source namespace, manifest, adoption, descriptor/feed and fresh-lease suffix are v7. The v5 and v6 manifests are separately pinned historical dependencies; all their19 source leaves are verified during adoption. Current v7 has31 protected dependency refs. The original v4 main-chain ref is not replaced with a fabricated success. New descriptors still use the original v1 external schema and actual v7 publisher SHA. The original orphan lease can only be reused by exact ref while it covers7200s, otherwise a distinct operational_v7 lease has the original9000s duration; no automatic retry/renewal or overwrite.

The v6 typed registry projection algorithm is unchanged. Standard ONE_JOB gates remain; the sole historical panel alias must have exact key/phase, zero remaining, both old standard fields absent, typed2GiB caps/flags and finite positive time. All live rows/holds, including newly registered positive holds, are kept; no fixed23 population is imposed on live quota. The synthetic regression fixture remains the original23-holder population, with pending4090 positive2GiB and17 zero phase entries. Original canonical registry digest/rawref and projection digest remain separate. No foreign phase is made a Native ledger. Lock, fresh actual quota/inodes,64GiB headroom and90s freshness stay unchanged.

Eleven worker/science/policy/repair/test leaves are byte-identical to v6/v5/v4. Science3d9 and4x20k members/config/data/seed/precision/checkpoint/source rules remain. GPU UUID22e/node21/16CPU32GiB/RSS28GiB/85%,7200/7100/6900s, whole/private2GiB, child outer-minus96MiB,128GiB durable/512MiB metadata/32768 records/512 roots/inode100000/384MiB safeCP and108/96/12/216 counters are unchanged. No dispatcher, monitor, quota-age widening, science/adoption result, D5/B acceptance or final recipe is introduced.

## Actual CPU and adoption interface

The same three complete metadata modules and30 planned cases are retained (4+4+22). test_quota_publish.py differs only in FRESH_V7 operational labels; fixture scientific/historical identities remain exact. Inline GPU metadata QA is the original8 cases.30 is not a new actual v7 PASS claim; CPU4703 belongs to v6.

Root mechanically rebinds the existing frozen-units request to the new source/test paths and all19 leaves+pins+31 dependencies, fresh task/request/output, unchanged runtime cwd and original runner. CUDA_VISIBLE_DEVICES is empty; PYTHONPATH starts with the new directory and retains V8/V2/runtime/tests/tools/deps; PYTEST_ADDOPTS=-o tmp_path_retention_policy=failed. Software working16GiB/RSS12GiB/800s/15min/whole-private2GiB and Root's authorized automatic CPU scheduler-memory policy remain. No extra QA parent is added.

After actual same-source C0, the new input schema native_S_long_v7_adoption_inputs_v1 takes exact rawrefs unit_request, summary, unit_result, JUnit, supervisor, actual_sacct; unit_name; orphan_lease; failed_coordinator_stdout; coordinator_pid3190990; failed_v5_adoption/failed_v5_coordinator_stdout/failed_v5_coordinator_pid3201293; and failed_v6_adoption/failed_v6_coordinator_stdout/failed_v6_coordinator_pid3204269. Logs are text, all other listed refs JSON except JUnit XML. Root supplies actual machine refs, not future placeholders. The actual QA gate still checks owned16CPU C0, task environment/requested_cpus string, all current before/after sources, exact full three modules/JUnit30/0/0/0 and supervisor/private cleanup.

```text
PY -B NEW/adopt_operational.py --phase N/native_S_B20k_v3 --pins-sha256 ACTUAL_V7_PIN --inputs ACTUAL_POST_QA_INPUTS --inputs-sha256 ACTUAL_INPUT_SHA
PY -B NEW/long_operations.py submit-next --phase N/native_S_B20k_v3 --pins-sha256 ACTUAL_V7_PIN
```

Root must first validate each actual new adoption precondition according to its raw/JSON/XML format. No new adoption/submission/QA job is generated by this transport. Old4703 and all previous evidence remain attributed to their real versions.
