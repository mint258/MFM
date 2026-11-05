# Three source-bound exact compositions

Metadata preparation for Root's existing actual primary-source review. The native
chemistry evidence is the completed Alpha parent 1885152 and its six passed
fixtures. This package does not repeat chemistry or add another approval step.
It replays only whole-field extraction from the closed transported source files,
checks the actual parent accounting, and binds the three observed exact non-H
compositions to the original physical SQL records.

The original Alpha `secondary_coconut_strict5_day_v1.frozen.decontamination`
consumer already accepts composition-only five-column strict5 records. Its
`identity_keys` function serializes the **exact** composition. Its contamination
lookup compares that serialization for equality. No consumer/schema change is
needed for these three rows; no positive lower-bound constraints are produced.
The original producer's source ID recipe and role are preserved:
`entries:<id>:<copy_block>:<source_row_ordinal>:composition:0` and
`ALL_SOURCE_NATIVE_SPLIT_UNKNOWN`.

The proposed rows are 707929 `[[6,46],[7,7],[8,12]]`, 174911
`[[6,41],[8,27]]`, and 174178 `[[6,21],[8,8]]`. Full formula source fields,
whole representation hashes, source ID association and the original stereo and
technical-grade caveats remain in the separate review ledger. No graph key or
stereo is promoted. The old graph UNKNOWN735 records remain unchanged.

Root deploys this module with the already integrated cached735/primary3 packages.
It has no dependency on `coconut_alpha_primary3_formula_draft_v1` (4b319bb).
Use the actual isolated ENTRY from the new source capsule so the code root is on
`sys.path`, keeping the working directory clean and avoiding `~/string.py`.
The following ENTRY convention is the existing capsule launcher taking module
name followed by its arguments; substitute Root's actual launcher path.

```text
<Alpha-private-python> -I -B <ENTRY> workflows.expansion.coconut_alpha_primary3_exact_v1.test_source -v
<Alpha-private-python> -I -B <ENTRY> workflows.expansion.coconut_alpha_primary3_exact_v1.prepare --output-directory /gfshome/alpha/codex_data_v1_20261026/control/pubchem_expansion_runtime_20261103/primary3_exact_source_review_v1
```

The test module calls standard-library `unittest.main()`; the capsule launcher
can continue to require an explicit `workflows.expansion.*` module. It does not
need to allow `unittest` as an additional launcher target. Both commands use only
standard-library metadata operations and the original
stdlib-only identity consumer. Tests initialize themselves through unittest's
`setUpClass`; no separate chemistry initializer or custom test runner is needed.
Root may run the five tests in its allocated validation job. The prepare command
uses the actual 1885152 receipt and `primary3_root_actual_parent.json` by default;
optional `--primary3-receipt` and `--actual-parent` accept explicitly supplied real
paths. The tests support `PRIMARY3_EXACT_RECEIPT`/`PRIMARY3_EXACT_ACCOUNT` overrides.

The output directory must be new and under Alpha's control tree. It contains
`primary3_exact_composition.PROPOSED.strict5.jsonl` (three original-schema rows)
and `root_source_review.PROPOSED.json` (machine-pinned provenance). Preparation
does not insert an index, run a candidate filter, modify any existing output,
quarantine a source or declare all735/all11 ready. The downstream source-ledger
combiner must bind these three proposals to their exact physical records while
retaining all remaining unresolved scope. The remaining 732 records are outside
this proposal, not newly classified, dropped or accepted.

Actual Alpha validation on 2026-11-03: Root ran all five standard-library
metadata tests successfully and the preparation process exited 0. Evidence is
`control/pubchem_expansion_runtime_20261103/primary3_exact_metadata_tests_actual_v1.json`
and `primary3_exact_source_review_v1/root_source_review.PROPOSED.json` beneath
the actual Alpha root. This metadata process is not a new Slurm C0 or a new
chemistry run; its native evidence remains parent 1885152. The three proposed
rows have not been inserted into a complete735 source ledger or used to filter
candidates. Source scope remains unchanged.
