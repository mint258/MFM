# Full physical source index — taskbook v2 entry

Run directly inside a Main Slurm CPU allocation, from the source worktree:

```bash
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
/share/home/zixiao/.conda/envs/chemprop/bin/python -B -m unittest workflows.data_v1_final.export.full_physical_index_v3.test_index
/share/home/zixiao/.conda/envs/chemprop/bin/python -B -m workflows.data_v1_final.export.full_physical_index_v3.build_index --plan workflows/data_v1_final/export/full_physical_index_v3/source_plan.json --output /lfshome/zixiao/data_v1_20261025/D6_full_physical_index_20261105_v3
```

Root submits this one producer; no startup proof, resource wrapper, SHA calculation,
receipt or independent reread is used. Existing source references are copied only.
`source_plan.json` binds the already closed full WP5 and frozen-ready Pprime files.
It does not invent missing Pprime results; appended B3 results can be indexed
separately once their producer closes. The output forecast is descriptive only.

The builder writes the original exact record/MID/family/task physical locations,
using the same canonical-owner selection as v2. It reads identity columns, never
numerical targets or geometry arrays. The final JSON is its producer manifest.
No final Common, D4, D5 or Model acknowledgement is needed to build this index.
Final training export must join the actual completed Common and D5 selection.

Numerical consumers import
`workflows.data_v1_final.export.full_physical_index_v3.read_index.locators_for_mids`
and pass `(manifest_path, whole_molecule_ids)`. Each returned locator contains
source_domain, molecule_id, record_id, source_reference, family, row_group,
row_within_group, physical_row_ordinal, task_code, original_native_pointer and
canonical_or_QC_identity. Use `read_index.iter_source_rows()` to read only those
physical rows and selected scientific columns once, grouped by source row group.
The locator's native_key/input_view retain the original stored identity.

This replaces the failed source-before-DATA wrapper, not its original history.
