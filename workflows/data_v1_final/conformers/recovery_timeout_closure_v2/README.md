# S-prime timeout closure v2: frozen cost snapshot

Source-only replacement for the registered v1 whose job 4521315 was still PENDING/zero elapsed when Root authorized preparing this variant. This source neither queries Slurm nor cancels a job. Root alone verifies that status remains pending with no proof/output, then replaces it. Running jobs are never cancelled. The v1 directory and every old scientific package/source/report remain unchanged.

The only behavioral change is the accounting snapshot. The v1 dynamic scan of all later submissions is not called. Root's previously approved point-in-time Master20 and cost selection are replayed from their exact pins. New N1, QA or other conformer submissions after this cutoff do not become prerequisites of this original pilot closure. Their actual costs still belong in subsequent Root accounting. An as-of subtotal is never represented as a final full-line total or scientific PASS.

## Concrete interface

Run the new primary script in an actual CPU16 allocation, analysis/pilot=false, no memory/exclusive request, maximum wall300 s, output1 GiB and effective-free200 GB reserve. The existing RSS8 GiB/MemAvailable4 GiB software STOP and natural drain remain unchanged. Use a new actual central v2 startup proof, new scope review/spec/request and new output directory.

```sh
/share/home/zixiao/.conda/envs/chemprop/bin/python -B <ROOT_REPOSITORY>/workflows/data_v1_final/conformers/recovery_timeout_closure_v2/run_v1.py \
 --plan /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/requests/dv1_q_sprime_recovery_20261026_v1.plan.json \
 --resource-binding /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/sprime_auto_memory_recovery_binding_20261026_v2/resource_binding.json \
 --stage-evidence <ACTUAL_PINNED_STAGE_EVIDENCE_FOR4521110> \
 --whole-owned-accounting /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/owned_accounting_checkpoint20_cpu_auto_memory_20261026_v1.json \
 --prior-related-cost-selection /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/sprime_timeout_closure_stage_v1/prior_related_actual_cost_selection.json \
 --legacy-scope-classification /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/sprime_timeout_closure_stage_v1/legacy_scope_classification.json \
 --root-preflight <NEW_ACTUAL_CENTRAL_V2_STARTUP_PROOF> \
 --output <NEW_CHILD_UNDER_RUN/artifacts/conformers/recovery_timeout_closure_v2>
```

Keep that exact option order, which is bound to the admitted primary argv. The scope key is `sprime_timeout_closure334plus2_snapshot_v2`, with exact parameters:

```json
{"original_job_id":"4520364","recovery_job_id":"4521110","original_tasks":336,"original_packages":334,"independent_same_seed_controls":14,"unresolved_after_timeout":2,"new_UFF_QM_calls":0,"new_seeds":0,"new_logical_retries":0,"test_methods":3,"fixtures_before_packet_bodies":true,"cost_basis":"ROOT_APPROVED_POINT_IN_TIME_SNAPSHOT","future_registry_scan":false}
```

Fresh startup required refs add the exact prior-related selection to all the v1 authority inputs: historical plan, actual resource binding, stage evidence, original Master20, legacy classification, actual recovery submission/startup proof, stage identity evidence refs and actual user cost decision. Root includes all new/imported source refs as usual. Both actual primary module and argv0 are bound. There is no reuse of a historical memory admission claim.

## What snapshot_costs.py verifies

Only rows already contained in the pinned Master20 are considered. The actual observed cutoff is read from its timezone-aware observed_at. It had 121 actual parent receipts and the frozen selection had 22 related parents; the Root-observed selected subtotal was338400 core-seconds. These numbers are replayed from real pinned rows by the CPU job, not asserted as an executed result by this source delivery.

The validator verifies the Master20/raw reference binding, actual sacct command parent set, unique raw parent IDs, and every captured parent's State/ExitCode/ElapsedRaw/AllocCPUS/cost. It loads each exact receipt in the frozen121-reference set, verifies its path/bytes/SHA, actual submission return code, job ID, UID and request. It uses the unchanged `_related` scope function and `_legacy_scope_review` exact receipt/evidence classification, then requires every recomputed scope decision, reason, selected ID/receipt/cost row and legacy evidence ref to match the Root-approved frozen selection. It retains captured rejected submissions and failed/cancelled/TIMEOUT actual parents. No step is charged twice.

This validator never globs the current submissions directory and never loads a future receipt. It requires terminal state only for selected related parents as captured in this snapshot. It does not require later unrelated, unclassified, N1 or QA jobs to terminate. The current new closure job must lie outside the prior snapshot. Original preparation4520335/606 s, original pilot4520364/TIMEOUT14425 s, partial audit4520527 and recovery4521110/TIMEOUT5409 s cannot disappear. All other known related failures in the frozen selection are revalidated too.

`approved_point_in_time_cost_snapshot.json` records the exact Master/selection/raw/classification refs, observed cutoff, verified parent counts, selected subtotal and historical64h/96h comparisons. User authority REPORT_AND_CONTINUE remains binding; an overrun is reported, never a cost-only STOP or scientific PASS. The current closure and all subsequent task costs remain pending Root append from later actual terminal Masters. The new report explicitly says not_final_data_line_total=true, future_registry_scanned=false and future_parent_states_not_required_for_this_snapshot=true.

## Scientific work is unchanged

`model.py` and `test_v1.py` are copied byte-for-byte from the registered v1. The original three synthetic methods run after fresh central admission/source-pin validation and before any334/14 package body, using the exact same strict count3/no failure/error/skip/expected-failure/unexpected-success rule. No additional fixture matrix or generic framework is introduced.

All package read/validation code and original validators remain unchanged:334 original packages and14 control packages undergo complete SHA/fstat/gzip EOF-CRC/task/seed/native pointer/atom/geometry checks. Controls must reproduce the original packet scienceSHA after excluding only summary.elapsed_seconds; they never add population members. Float64 audit parquet/readback, success and scientific failure lists, stratified description and right-censored uncertainty remain unchanged.

Two missing original tasks remain only UNRESOLVED_AFTER_PARENT_TIMEOUT: principal_01112964/N7 and principal_00509656/N10. Scientific stage/status and worker PID are unknown/null, package_reference is null; the original fixed2+14 scope minus14 verified controls supplies the identity set, not a durable PID/phase map. Both historical TIMEOUT parents, absent producer final receipt and absent monitor closure remain explicit. No new package, scientific outcome, seed, logical retry, attempt key, common population or full release is fabricated.

The report schema becomes SPRIME336_PACKAGE_OR_TIMEOUT_OUTCOME_AUDIT_V2, retaining CLOSED_WITH_TWO_EXECUTION_UNRESOLVED_REQUIRES_ROOT_REVIEW. It leaves planning acceptance/full release/common freeze false. Root reviews this actual read-only C0 and its honest as-of cost evidence, appends this and later actual costs, and independently reviews a full model/budget with all quality thresholds unchanged.

No Python, synthetic test, package read, science, SSH, Slurm or Git command was run by the child. This five-file source delivery is unexecuted.