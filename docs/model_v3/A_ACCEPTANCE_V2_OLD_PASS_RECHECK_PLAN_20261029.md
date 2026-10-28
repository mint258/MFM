# Old A-PASS cohorts: explicit v2 recheck plan

This is a metadata/source plan, not a new verdict. Authority is the preserved187667-byte A_acceptance_v2_old_PASS_cohort_capability_v2.json (SHAe2e3a374c3bde4600b467a04f5284c4134cfef8a8a15a5a72f7a595efcbb4f64). No old SDK, trajectory journal, fixed-gradient arrays, model checkpoint or data payload was opened. The old records below remain v1 results. A5-v2 job4704 failing does not waive any recheck.

| Old job | Exact old case/options | GPU / UUID suffix | Old code | Evidence root |
|---|---|---|---|---|
|4520405|A00, distance/backbone/head=T/T/T|4090 / ec788ed1…|a6c6203…|O/a_native_control_4520405|
|4520411|A00, T/T/T|5090 /22e21021…|a6c6203…|O/a_native_control_4520411|
|4520438|A00, T/T/T|3090 /a967b766…|6df0aa5…|O/a_native_control_4520438|
|4520456|A01 backbone-off, T/F/T|4090 /ec788ed1…|8ece64c…|O/A_a01_backbone_off_4520456|
|4520486|A00, T/T/T, old non-opt-in path|5090 /c35f2434…|8ece64c…|O/A_a00_control_4520486|
|4520549|A03 head-off, T/T/F|5090 /22e21021…|8ece64c…|O/A_a03_head_off_4520549|
|4523976|A00 manual R2, T/T/T, no packing|5090 /c35f2434…|9e16d4c…|N/performance_manual_R2_v1/child|
|4524551|A00 auto R2: requested T/null/T; actual selected all-on|5090 /c35f2434…|9e16d4c…|N/performance_auto_R2_v1/child|
|4524580|A03 head-off R2, T/T/F, no packing|5090 /c35f2434…|9e16d4c…|N/performance_head_off_R2_v1/child|

O/N are runs/model_v3_20261025 and runs/model_v3_20261026 below /share/home/zixiao/descriptor_analysis. The companion JSON preserves the exact full paths and rawrefs for each configuration, summary, fixed gate,500 gate and supervisor/Root closure; it does not newly hash those server artifacts.

All nine saved cohorts declare the same6x512/8head architecture, NativeS/seed0, P8M, workers8, Adam lr0.0003/weight_decay0.01, fixed-LR numeric trajectory and clip1. Their model, optimizer, schedule, sampler/loader and shard snapshot projections compare equal in this preserved inventory. All nine report20 fixed batches and complete500-point PASS with201216 base records. All have fixed-input receipt SHA38c80a677bae4dc1b057554088c79fb3254347d2e950a177dd14ed02f4c59f46 and original500 gate SHA28c819cbb4dbd813921c6eb4714ec227fc803120c23ab908946f3f2a49459d7a. The latter contains relative comparisons; its identical bytes do not establish cross-run initialized parameters/RNG or absolute loss history.

Each old fixed report saved6580 named-gradient rows,2340 numeric rows, with numeric max-absolute differences zero. Each saved120 analytic-zero rows but neither side's zero-bias norms. Therefore all nine still need actual v2 fixed20, including both active zero norms. No fused/TF32/compile/all-off/failed A5 is part of this old-PASS list.

## Minimal execution path

Use the actual published7ffe8a5557590b1481f4ca74073007f070dc6a50 source/public2b4a4df8636e5d65915d535472ba01084ea72dab and the existing tools/model_v3/paired_a_acceptance.py under the unchanged run_supervised.py. Keep NativeS/seed0/workers8/P8M/snapshot d2e1ace1636485cd3dd0106b1177518dd37eb9741919195a9efcd846c1c2242f, deterministic controls, original reference B1_seed0_v2.json and corresponding candidate JSON:

- A00: current/configs/model_v3/performance/a00_control.json, SHA52ae1dae8ff65229a2b4f26b281a0e488e751e08671dbf953d33601e6c1a6bf0.
- A01: current/configs/model_v3/performance/a01_backbone_off.json, SHAd3bb101a8e5417fcbe998c39f97698e6902a9b06851a343aa0a0e4830ef0e8d4.
- A03: current/configs/model_v3/performance/a03_head_off.json, SHA9e958e8fb4374211f80e2c8ed741266b93f701dbde15f2dd36cb862a9e10723e.
-3976 manual profile observation: add current/configs/model_v3/performance/a1_manual_capacity_observation_v1.json, SHA7cabbd4a0300d551154ffb9bcbed5466fc9886d0eb886a1ae37ee3e7f70db46e, no padding.
-4580 head-off retains its original explicit85-byte a1_manual_capacity_observation_v1.json (same7cabbd4… SHA): manual, padding=null, capacity_profile=null, resident_models=2, P8M, workload67d3c18442811509529be54fc9d77da02297a2f70b9db91fd1d288e697743080. Do not remove its opt-in or add the A5 packing JSON.
-The first six old non-opt-in cohorts stay non-opt-in: do not silently add a new execution request to re-label their scope.

Every child adds the six already public v2 rule flags from the actual5747-byte rule Doc and2608-byte receipt. A fresh separate output/family/hold and original16CPU64GiB/RSS56GiB/6900s/2h/whole-private2GiB/85%/strict UUID lock and resource admission are required. Preserve historical UUID/environment when trying to associate an old500. A changed physical card needs an explicit new applicable full20+500 scope; it cannot borrow an old capacity profile or ABBA identity. Do not interfere with Native4706, old1338/4558 or other processes.

The A5-v2 driver is not a generic old-cohort launcher: its preflight deliberately fixes the A5 JSON, and the posthoc reader fixes job4704. Reuse the existing generic paired/supervisor body and each corresponding old family thin adapter, replacing only current tested/public/ref/actual rule/source authority, case options and fresh outputs. Do not monkeypatch that A5-only validator.

## Order and the auto dependency

Prioritize current-9e lineage on C35:3976 manual all-on,4551 auto after its new same-source observation, then4580 head-off. Next cover486 legacy control,4090 control/backbone-off405/456,3090 control438, and22e control/head-off411/549 when their applicable resources are genuinely available. This is an operational ordering, never case selection; all nine remain on the matrix until individually closed. Identical-looking controls from different original code/producer paths are not automatically coalesced.

For auto4551, the old9e profile is rejected by the unchanged complete mandatory-source gate because the two Host verifier sources changed. Its existing options JSON N/performance_R2_capacity_consumer_v1_source/auto_R2_options_DRAFT_v1.json (SHAa618f741e42c681e735c13b837d9d72ea3381e2ccbfc6240f6e2eaaea6c13d64) remains a valid options shape; it does not grant capacity. First obtain an actual C0 manual all-on R2 observation on the new source with complete20+500. Reuse the existing six-ref profile format schema=model_v3_closed_checkpoint_capacity_profiles_v1, observations=[{configuration,summary,run_status,supervisor,parent_sacct,steps}], with actual new rawrefs only. The existing consumer is v3_checkpoint_policy.load_closed_observation(item,requested,configuration,options,sources). It requires the real same-source complete paired gates, no packing, resident_models2, same workload/budget and actual provenance; the subsequent real GPU performs environment selection. Keep checkpoint_policy=auto_closed_profile_v1 and backbone_checkpointing=null in the actual auto execution, with a new execution JSON/rawSHA binding that genuine profile. Neither a CPU synthetic table nor a manual run relabels the auto verdict. A failed new baseline supplies no profile and does not waive other rechecks.

## Keeping old500 without inventing a full PASS

The already public --fixed-batch-only option is v2-only original20 and explicitly0 trajectory; it never emits full_A_numeric_acceptance. It may avoid an unnecessary new500 only after Root independently establishes the predeclared old500 reuse conditions: actual complete original500 C0/PASS, unchanged declared and actual initial parameters/RNG, actual input/reset/seed/precision/determinism, GPU applicability, model/loss/optimizer/data semantics, with only the Host acceptance rule changed. Associate both raw proofs explicitly; do not rewrite either job.

This inventory itself records no cross-run initial-parameter/RNG raw hash, and the oldest six have only54/61 saved source-map entries versus305 in the recent three. Their common model/options/input hashes alone are insufficient to fill that gap. Root can examine existing immutable source/launch and configuration provenance to prove comparability; if insufficient, use the existing complete20->500 path rather than invent a certificate. For the new current manual capacity anchor, the unchanged capacity consumer itself requires a same-run full20+500, so a fixed-only/old500 composite is not a substitute for a new profile. Keep forward1e-5, v2 all-element1e-8+1e-4|reference| plus six dualnorm1e-8, and original each-point500 loss1e-3 unchanged.

No operation, verification, actual resource, new GPU result or v2 PASS was executed or inferred by this plan.
