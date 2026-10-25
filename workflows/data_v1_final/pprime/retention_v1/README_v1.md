# Stable raw retention execution adapter

Root accepted seed20261010 / threshold100 of10000 on 2026-10-25. This directory
implements that new retention version; it has not executed QM. The original
15 pilot sources, pilot config, prepared345 and frozen20 audit remain unchanged.
New work uses `configs/data_v1/pprime/stable_raw_retention_v1.json`, separate
manifests, output directories and a science-once ledger. Root alone submits.

`source_shard_id` comes from the frozen eleven-LMDB source_plan and exact source
path, not source file position, output batch/rank or molecule-index file_group.
The observed pilot example molecule_01200493 has shard6 and old row file_group5.
Both remain explicit: stable sampling uses6; old engine membership guard uses5.
The legacy group is checked against frozen20 entries and never overwrites the
source row. Size strata are the original heavy-atom bins <=20, <=40, <=75, >75.
Missing source identity/heavy count/path or a mismatching bin is rejected.

The hash input and original/fill physical namespaces are defined by the pinned
pure selector in `../raw_policy_proposal_v1/policy_v1.py`. Original S-prime IDs
are actual source IDs, not a new rank. Full/fill sampling requires explicit
frozen physical identity; unknown or N1 namespaces are rejected. The stable
threshold produces approximately1% per stratum. Actual counts/rates are
reported; neither an exact1% count nor old WP5 audit identity is claimed.

Preparation reads the original2000 pairs, computes stable hits in16 threads,
and creates:

- source_audit.json: every original physical identity, source_shard_id,
  legacy_engine_file_group, bin, key SHA/bucket/selected flag and source SHA;
- stable_full_hits.json and pilot_retention_union.json: original frozen20 union
  stable hits. Old20-only rows are marked extra_reproduction_retention;
- new audit_selected.parquet/audit_membership.json using unchanged legacy
  engine group values; all union records require all12 raw calls;
- retention_manifest.json binding the exact original prepared/pairs/20/config,
  source plan, new policy and all new output hashes.

Run entry calls the pinned original `run_pilot.run_lane` unchanged. It passes
the original pair objects, original config, same record IDs, 12 tasks, keywords,
binary/library pins, perturbation seed/sigma, geometry adapter, QC and exporter.
Only the independent engine audit membership selects more raw to retain.
Input hashes in parsed and durable raw call metadata are compared after closure.
The output-only archive still forbids input bodies. All ordinary failed-call
raw is retained independent of audit selection. No scientific rerun is created
to acquire missing raw. The once ledger includes original pair SHA and protocol
SHA; changing output path or retention version cannot repeat a started pilot.

stable_raw_all12_proof.json independently reads SQLite/gzip output bundles and
records each required call's task/execution ID, input hashes, keyword SHA,
output member manifest and pinned container. It checks the full12 union plus
every completed scientific-failure call. Partial/missing calls remain failures.
The result cannot pass pilot gates when this proof is incomplete.

Root uses ordinary16CPU64GiB on compute14-19 for actual QM, max2h. The336 UFF
32GiB exception cannot be used. Every one of16 original lane processes must
exit and be joined. New policy/retention work is included in actual parent
AllocCPUS*ElapsedRaw; do not subtract it to pass the11.7 allocation-second gate.
The original8GiB output cap, per-worker raw/staging caps and200GB quota reserve
remain. There is no submitter, automatic retry, automatic full launch or GPU.

Use the actual Root-integrated absolute paths and freshly pinned requests:

    PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
    REPO=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository
    BASE=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025
    "$PY" -B "$REPO/workflows/data_v1_final/pprime/retention_v1/prepare_v1.py" \
      --config "$REPO/configs/data_v1/pprime/stable_raw_retention_v1.json" \
      --original-prepared "$BASE/artifacts/pprime/prepared_v1" \
      --original-prepared-sha256 3fd2feb6adf9bc125c81fb8be07f97bdbe5737d7bb09f4690da115a8468dcfca \
      --root-preflight "$NEW_PREPARE_INTENT" \
      --output "$BASE/artifacts/pprime_retention_v1/prepared_v1"

The preparation is an analysis job on compute20. After actual metadata closure,
Root may independently review a future ordinary QM request:

    "$PY" -B "$REPO/workflows/data_v1_final/pprime/retention_v1/run_pilot_v1.py" \
      --execute --config "$REPO/configs/data_v1/pprime/stable_raw_retention_v1.json" \
      --retention "$BASE/artifacts/pprime_retention_v1/prepared_v1" \
      --retention-sha256 "$ACTUAL_RETENTION_MANIFEST_SHA" \
      --root-preflight "$QM_INTENT" --output "$NEW_PILOT_OUTPUT"

Close with the unchanged `pprime/close_pilot.py --config <original pilot_v1.json>
--result <new result.json> --sacct <Root actual parent sacct raw> --output <new
gate report>`. The new result also lists every actual conformer elapsed time.
Formal reuse requires this policy and all12 proof, as well as actual pilot
gates; scientific failure values/statuses are reused as failures, never filled P.

Tests: `python -B retention_v1/test_v1.py` has3 controlled fixtures, including a
real bounded SQLite/gzip roundtrip. `../raw_policy_proposal_v1/test_v1.py` has4
hash/union/identity fixtures. These do not run QM, UFF, LMDB, GPU or Slurm.
