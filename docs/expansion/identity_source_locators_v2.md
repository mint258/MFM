# Identity-only all-source input preparation

New directory/version only; registered source, config, common population, and
old test-only embargo artifacts remain untouched. The new source locator
catalog contains76 physical locators and8 small source/metadata authorities.
Every locator is historical or stat-only metadata until a new compute job
verifies its current bytes, SHA and independent physical record count.

The decisive locator is
`docs/phase1/evidence/stage43_downstream_membership/run_4511949/membership_manifest.json`.
Its all-member source counts are CYP2003, AZ109-fold, QM77165, QM9133885 and
ExpansionRx5326train+2282test. Its `target_values_decoded=false` and original
raw/fold references locate inputs; it is not a new all-source identity proof.

| Dataset | Required scope and existing physical source |
| --- | --- |
| v1 | Whole formal Parquet11231854 records plus excluded-unassigned Parquet4900; all members later excluded by common still included |
| v1 roles | Effective TRAIN11104772, VAL=ROUTINE11322, FULL excluding VAL115760, EMBARGO4900; each physical record exported once; retain membership flags for provenance |
| ExpansionRx | `data/OpenADMET_ExpansionRx_MLQSAR_paper_reproduction/log_train_data.csv`738171B/history SHA2bb87a…5326 records and `official_test.csv`338634B/history SHAec4831…2282 records |
| CYP | `/share/home/zixiao/benchmark_dataset/cyp_isoform/raw/` nine original SDFs,2003 molecule–isoform instances; all10 original fold CSVs and assignment; preserve raw records even for repeated chemical identities |
| AZ | `/share/home/zixiao/benchmark_dataset/az_exactsom/raw/az_120_compounds.csv` all120 raw; all10 original fold CSVs cover109; extra11 raw remain in conservative exclusion scope |
| QM7 | `/share/home/zixiao/benchmark_dataset/qm7/raw/qm7.mat`17884280B/history SHAfd6c26…7165 original Z rows; original full graph/charge/stereo remains UNPROVEN, so Z-only non-H composition exclusion; no coordinate-based key fabrication |
| QM9 | Original `benchmark_dataset/qm9/raw/dsgdb9nsd.xyz.tar.bz2` locator comes from frozen original downloader; current existence/size/SHA still pending; original ID universe1..133885, including later loader exclusions |

The catalog preserves the full original/fold identity ledgers: source QM
`source_records.jsonl`266807412B/history SHAe6081f…141050 combined QM rows;
CYP raw4376790B/SHA33bdc2…2003, CYP folds4702487B/SHAae3fd6…2003,
AZ raw259136B/SHA62eca7…120, AZ folds242735B/SHA7c8e5c…109. No ledger body
was scanned during this preparation. Current full hashes/counts require the
new allocation; original paths outside X are not asserted currently present.

The first executable step is compute20/16CPU/4GiB/<=1h, output<=32MiB:

```bash
python -B -m workflows.expansion.identity_v2.pin_inputs_v1 --plan NEW_READY_PIN_PLAN --root-submit-intent ACTUAL_ROOT_INTENT
```

Root binds the new plan, catalog, runtime code and catalog's8 small metadata
authorities in `source_references`. Literal large input paths are authorized
by the bound catalog; this producer creates their first current pins and must
not put large file bodies in login-side `source_references`. The plan has no
false precomputed current SHA. Runtime pins include the new producer, common,
download_raw_v1, source, both package init files and wrapper. Wrapper exports
`EXPANSION_REPO`, `IDENTITY_INPUT_PIN_PLAN`, `IDENTITY_INPUT_PIN_ROOT_INTENT`.
Root alone submits. Published quota must be fresh<=300s.

The producer hashes opaque full-file bytes in16 bounded I/O tasks; CSV reading
materializes only ID/SMILES/InChIKey/role columns, without labels, features,
label filtering or target-based ordering. Parquet only reads physical row
footer/schema metadata. SDF/JSONL are only counted by record/line boundaries;
SDF properties and JSONL value objects are not decoded. QM7 only inspects MAT
variable/shape metadata, not numeric X/T/R/Z values at this stage. QM9 tar only
walks member headers/IDs, not molecular target lines. Missing optional locators
stay PENDING; changed historical hashes/counts or missing required inputs stop.
The new receipt is explicit about not being an identity export or all-source
decontamination acceptance. Follow-up extraction will bind these measured
references and only project identity fields into a new versioned manifest.

Three new synthetic checks:
`python -B -m unittest workflows.expansion.identity_v2.test_pin_inputs_v1 -v`.
They check CSV multi-line rows/identity-only projection and count mismatch,
opaque SDF/JSONL counting, and MAT metadata without numeric array loading.

External scope stays PENDING. The [official TDC overview](https://tdcommons.ai/benchmark/admet_group/overview/)
confirms22 endpoints with separate train_val/test. The [official DeepChem docs](https://deepchem.readthedocs.io/en/latest/api_reference/moleculenet.html)
are recorded, and all17 proposed molecular datasets remain required; six local
CSVs do not close that union. [ATTNSOM](https://github.com/dmis-lab/ATTNSOM)
documents the9 CYP source files and AZ raw120; the used historical commit
remains0faa38bbd1665262efb3642a2a3ae0f83c928a49.

The [official COCONUT download page](https://coconut.naturalproducts.net/download)
currently lists October2026 CSV191/207.9MB and a31.91GB SQL dump explicitly
including active/inactive records. CSV inactive coverage is unproven; do not
substitute a smaller scope. Current physical SHA/all-source proof remains
pending. Official Dataverse/MARCEL/Figshare metadata fetches were inaccessible
or restricted in the web tool; no proxies, alternate mirrors, login bypass,
or large download was attempted. The catalog retains their registered official
URLs, historical version hints and PENDING state, without claiming fresh bytes.
