# PM7 cache32 metadata plan helper

Main **login** only, UID 1278/sonmi, Python standard library only. This helper
imports no project code, opens no scientific task/packet/Parquet/LMDB body,
does no SSH/Slurm action, and cannot approve or submit a stage for Root.
Copy these three files to the same relative directory in Root's repository.

```sh
P=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025
H=$P/repository/workflows/data_v1_final/execution/pm7_cache32_plan_helper_v1/helper.py
PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
$PY -B "$H" candidates --hof-mode CANONICAL_VERIFIED --output "$P/control/pm7_cache32_candidates_v1"
```

Candidates have `ROOT_REVIEW_REQUIRED`/`UNSIGNED` and are rejected as runtime
approvals. Root independently reviews and writes **new** approved HOF, resource,
and plan JSON files, using the candidates' `proposed_runtime_status`. The plan
must then bind the actual approved HOF review's positive bytes/SHA triple;
the helper deliberately leaves this future reference `null`. Geometry-only HOF
mode is available, with energy/diversity remaining pending. The resource
candidate retains the approved S′ reservation of **182 × 8 GiB** and adds
**8 GiB prepare + 8 GiB run**; it grants no full cache execution or publisher
renewal. Expiry/fresh quota and 200 GB headroom remain CPU runtime guards.

Using Root's actual approved files:

```sh
$PY -B "$H" prepare32 --plan /ABS/approved_plan.json --quota-review /ABS/approved_cache_resource.json --stage-output "$P/artifacts/conformers/pm7_independent_cache32_v1/prepared_v1" --output "$P/control/pm7_cache32_prepare_candidate_v1"
```

This writes an unsigned exact scope candidate plus unapproved central inputs.
Root reviews the scope and writes a new approved scope file with an explicit
reason. Repeat the same command with a **new** `--output` directory and
`--approved-scope-review /ABS/actual_approved_scope.json` to generate
`stage_spec.json`. The helper checks all bound fields against that existing
approval. Root can then use unchanged central v2 materialize/submit/activate
steps for **compute-0-13**, analysis/pilot=false/16 CPU/no memory request/8 GiB.
Default wall request is 7200 s; it is an allocation ceiling, not a forecast.

Only after an actual prepare C0 and standard accounting/raw exist:

```sh
$PY -B "$H" run32 --plan /ABS/approved_plan.json --quota-review /ABS/approved_cache_resource.json --prepared "$P/artifacts/conformers/pm7_independent_cache32_v1/prepared_v1/prepared.json" --accounting /ABS/actual_prepare_accounting.json --stage-output "$P/artifacts/conformers/pm7_independent_cache32_v1/run_v1" --output "$P/control/pm7_cache32_run_candidate_v1"
```

Approve the run scope independently and repeat with a new `--output` plus its
actual `--approved-scope-review`, as above. Run inputs bind the real prepared
header, actual C0/raw, 32 task locators, source authority locator and 16 golden
packet locators. Scientific locators are never read or hashed on login.

Every output directory/file is new, exclusive, fsynced and bounded; partial
metadata is preserved on failure. Existing plans/approvals/sources stay
unchanged. Future job IDs, receipts, successful outcomes and hashes are never
generated. No Common, physical ID, P′ or full-cache release is granted. Static
source review only; this child did not execute the helper or project tests.
