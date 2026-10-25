# Isolated nullable/cache replay repair pilot

Actual diagnosis job 4520359 projected every one of the 335 native mismatches
from failed pilot 4520357. All 335 records (136 molecules) have unassigned
membership, failed parsing/sanitization, null graph fragments and geometry
components, false saved X01, false geometry-checked marker, and null X03/X04.
The row file is 223898 B, SHA256
`ad13ee05f2565db3b1d6b0091a1c04cf6c53c42b68a46c846c0a78d88b281ca4`.

The actual historical operations explain these values:

| Source / execution | Exact behavior | Source SHA256 |
| --- | --- | --- |
| Stage61 `scan.py`, receipt 4512136 | Lines 123, 169–180 leave graph flags unknown on parsing failure; 332 writes nulls | `73a4e3e9dbf5722c976bda640474b1778328bd79f9b24b3acf82de3c6617f632` |
| WP0 inventory 4512799 | Lines 352, 357 compute nullable graph/dot X01 and charge/radical flags | `dae1d25ade45719eb8a393dc83daec8853dc85471a3d2d6ead9520cf9b4a60c7` |
| Unassigned parser 4512802 | Lines 147–148, 189–201 preserve unknown no-dot X01 on failure; 216–219 only probe sanitization | `043cc9cd1fac0662c54ac357d682849482831a98aa1297013dd65d7b4dad50e1` |
| Geometry enrichment 4512808 | Lines 24–25 always coalesce raw X01 and component-hit to false independently of checked status | `4fa8a1d6108691eb6b1a0700f7b11e8598737214e78194d94a0f26a020f9a6cd` |
| WP1 quality source | Lines 106–119 combine fixed geometry and final no-positive flags | `c8a5e896bb2560d80ad2bbefb00a36a90b9ace4e4bb69f8b6d4d2083d1114740` |

v1 only restored raw X01 when `X01_geometry_checked=true`, so its cache replay
missed the unassigned unknown case. v2 independently compares raw nullable
flags with native graph/atom replay, then executes the exact historical
enrichment formula and compares all stored enriched flags and the checked
marker. Unknown raw values remain unknown in the raw layer. A parsing failure
does not waive mismatches in any layer.

The immutable v1 evaluator still supplies admission, portable comparisons,
and fixed geometry/identity decisions. Every one of the exact frozen 8741
pilot records must match those previous decisions, identities, portable
comparisons, and geometry augmentations. The newly corrected cohort must be
exactly the 335 IDs proved by the diagnostic job. Any other corrected ID,
changed decision, raw/enriched drift, or incorrect marker stops the pilot.
All raw, enriched, native, and portable layers are saved for every pilot row.

`x_regression_plan_template_v2.json` contains actual small historical source
and execution proof references, frozen v1 decisions, and diagnosis references.
Root fills runtime code pins and freezes a fresh READY control plan. The
runtime code chain includes `regression_x_v2.py`, immutable `regression_x_v1.py`,
`common.py`, `screen.py`, `source.py`, `download_raw_v1.py`,
`data_authority_v1.py`, and package `__init__.py`; pin the wrapper as well.
All plan/code/history/diagnosis and small source-pin receipt references go in
`request.source_references`. Only the three original GB input files go in
`request.data_references`; the runtime still fully hashes those on compute20.

CLI:

```bash
/share/home/zixiao/.conda/envs/chemprop/bin/python -B -m workflows.expansion.regression_x_v2 --plan NEW_V2_READY_PLAN --root-submit-intent REAL_NEW_INTENT
```

The new wrapper exports `EXPANSION_REPO`, `X_REGRESSION_V2_PLAN`, and
`X_REGRESSION_V2_ROOT_INTENT`; the established dependency overlay is explicit.
Budget: compute20 / 16 CPUs / 32 GiB / one hour / total output and spill cap
16 GiB, DuckDB memory 8 GiB and spill at most 8 GiB. Fresh published quota
must be <=300 seconds old at job start. Expected cost is comparable to the
failed 43-second pilot, with additional small proof and per-record layer I/O;
the hard allocation ceiling is 16 core hours. Six new targeted synthetic tests
cover the boundary and non-waiver behavior; no original suites need repetition.

This entry accepts only the isolated repair pilot. It cannot claim full-input
99.9% consistency, downstream decontamination, or authorize source screening.
The v1 source, failed pilot, and diagnosis source/output remain unchanged.
