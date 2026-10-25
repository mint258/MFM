# Full X-rule common-pending proof permits only a bounded raw prefix

These new v2 files supersede the uncommitted, untested bounded-screen v1 draft;
the old five files remain unchanged and are not needed by this entry.

The new gate accepts only a separately Root-reviewed READY prefix plan and the
actual successful full v3 proof: small receipt, Root actual Slurm closure,
executed READY plan, and frozen runner source. All four references must be
bound by Root `source_references`, <=8MiB each and SHA-verified. Full large
Parquet outputs and original GB datasets are not opened by this gate. Required
original-source refs are compared as metadata with the completed full plan.

Expected Root closure shape:

```json
{
  "status": "ROOT_X_FULL_V3_ACTUAL_COMPLETED_COMMON_SCOPE_PENDING",
  "receipt": {"path": "ACTUAL_FULL_RECEIPT", "bytes": 0, "sha256": "ACTUAL_SHA"},
  "actual_parent": {
    "JobIDRaw": "EXACT_FULL_JOB_ID", "State": "COMPLETED", "ExitCode": "0:0",
    "AllocCPUS": "16", "NodeList": "compute-0-20"
  }
}
```

Root fills real bytes/SHA/job metadata after full completion; no placeholders
can authorize a run. The full receipt must prove all15,879,477 unique source IDs,
zero raw/native/enriched/metadata/unexplained drift, >=99.9% selection agreements,
complete mismatch detail, actual16-worker coverage, and unchanged v1/v2 closed
pilot/335-cohort checks. Common scope and final training/expansion gates must
explicitly remain false.

Only source ordinals1–10000 are permitted, with 16CPUs/16GiB/<=1h and <=512MiB
new output. Full source screening, released candidate pools, all-source
decontamination acceptance, UFF/D-family export, and training switches must
all be false. The result is always
`BOUNDED_INPUT_PREFIX_PILOT_NOT_DECONTAMINATED`, stored under a fresh isolated
screening directory. Prefix composition/throughput cannot be claimed as a
representative PubChem sample or a full expansion acceptance.

The producer raw receipt is exact4520348 with all16 complete official ranges
and gzip EOF/CRC proof. Only its1.49GB raw file appears in
`request.data_references`; all other bindings are small code/plan/proof refs.
The consumer fully hashes raw on compute20 and checks stable physical identity
before/after prefix processing. It preserves RDKit2025.09.5 and the frozen
chemical/feature functions, isotope/stereo state, exact full-InChIKey dedup,
CID aliases and source ordinals, with no heavy-atom upper bound.

The new coordinator uses a spawn16 barrier and records every actual worker's
input contribution, requiring all16 to process records and exactly10000 source
ordinals with no gaps/reordering. Every rejected prefix record is stored.
Candidates are explicitly named `unreleased_prefix_candidates.sqlite` and
carry no downstream-decontamination or UFF claim. Published quota is pinned to
Root's actual publisher source and must be <=300s old at start.

CLI:

```bash
/share/home/zixiao/.conda/envs/chemprop/bin/python -B -m workflows.expansion.bounded_prefix_pilot_v2 --plan NEW_READY_PLAN --root-submit-intent ACTUAL_NEW_INTENT
```

Wrapper exports `EXPANSION_REPO`, `BOUNDED_PREFIX_V2_PLAN`, and
`BOUNDED_PREFIX_V2_ROOT_INTENT`. Root alone submits. Three new metadata-only
tests: `python -B -m unittest workflows.expansion.test_bounded_prefix_gate_v2 -v`.
No real screening runs until full completion and a new reviewed prefix request.
