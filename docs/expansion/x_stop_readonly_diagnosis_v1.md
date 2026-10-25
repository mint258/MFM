# Frozen 4520357 STOP diagnosis

This new helper reads the exact 489-row mismatch file and projects only the 335
unique X01 native-mismatch IDs from the original index. It does no chemistry,
no screening, no full regression, and makes no gate decision or explanation
label. Historical registered sources and outputs remain unchanged.

Root copies the template to a new control plan, hashes the small STOP receipt,
fills `code_sources` for the actual helper, `common.py`, `data_authority_v1.py`,
`__init__.py`, and optionally the wrapper, then freezes `status=READY`.
The plan and every code/receipt/mismatch reference belong to the Root request's
`source_references`. Include the frozen STOP's `root_submission` intent reference
as another small source reference. Only `original_index` belongs to
`data_references`; the two other files present in the pin receipt are never read.

The helper requires actual zixiao Slurm compute-0-20, 16 CPUs, 4 GiB, at most
one hour, and exactly 32 MiB output declaration. It verifies same-node source
stat, full original-index SHA on compute, and final stable stat. DuckDB uses
16 threads, 2 GiB memory, and at most 16 MiB spill. Expected runtime is a few
minutes, dominated by the 2 GB sequential SHA; the hard cap is 16 core hours.

CLI under the frozen repository and established deps overlay:

```bash
/share/home/zixiao/.conda/envs/chemprop/bin/python -B -m workflows.expansion.diagnose_x_stop_v1 --plan NEW_READY_PLAN --root-submit-intent REAL_NEW_INTENT
```

Slurm wrapper exports: `EXPANSION_REPO`, `X_STOP_DIAGNOSIS_PLAN`,
`X_STOP_DIAGNOSIS_ROOT_INTENT`. Root supplies unique log paths.

The helper first reads the actual source schema. Missing requested columns are
reported in `missing_requested_columns` and omitted from rows and combinations;
it never fabricates null values. The exact source schema, 335 projected rows,
observed field combinations, input references, and actual job ID are preserved
under the new output directory. These observations determine whether the old
geometry-cache `coalesce` transformation explains X01 false versus unknown.
