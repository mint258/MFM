# Optional physical input cache for D7 and later D6

This independent module changes only the LMDB path passed to an existing reader. It does not modify active D7/fill source, scientific functions, logical source rows, RIDs, record ranges, seeds, LMDB options, output/checkpoint bindings or closed results. No source copy or job is started here.

`configs/data_v1/window2_source_cache_plan_template_v1.json` copies the11 path/name/source_size entries from the existing stage61 plan (327409029120 bytes recorded total), proposes node20 /tmp destinations, and starts with an empty `closed_source_path_map`. Root selects actual destinations from actual free space and performs rsync --sparse separately. After one source transfer actually completes, Root adds only that exact original-source:absolute-cache-path entry to a runtime copy of this small plan outside Git. Never put an incomplete transfer in the map. No new hash, QA, numeric reread, benchmark, receipt or benefit/admission threshold is used.

Example runtime map entry, only after that file's rsync has completed:

    "closed_source_path_map": {
      "/share/home/zixiao/dataset/lmdb_new/principal_00000001_00300000.lmdb": "/tmp/window2_native_lmdb_cache_20261105/principal_00000001_00300000.lmdb"
    }

The map is exact-string keyed. It never matches a basename, prefix, symlink or normalized alias. Any uncached source follows the original path. Source rows entering/outside the wrapper keep their original source_path; only a temporary dictionary passed to the native physical reader has a redirected source_path. The original D7 reader still opens readonly LMDB, reads the exact original real_index %09d key and unpickles exactly as before. Its LRU4 policy remains unchanged.

Minimal future runtime hook, once per worker after the original initializer:

    import os
    from workflows.data_v1_final.conformers.window2_source_cache_v1.keep_source_map import install_native_reader
    original.initialize(science_path)
    install_native_reader(original, os.environ.get('DATA_V1_COMPLETED_SOURCE_CACHE_PLAN'))

Root can add these two hook lines to the future runtime initializer alongside the existing RMSD cache hook. Pass the map filename through the environment so the scientific D7 plan/checkpoint stays byte-for-byte logically unchanged; no new key is needed in the scientific plan or its same_inputs comparison. Existing worker processes receive no changes. Each future worker reads the map once. Root decides whether/when the actual closed D7 checkpoint continues with that new reader; this module never stops a running parent.

D6 may reuse `KeepSourceMap.from_plan(path).physical_path(logical_source_path)` at its own physical file-open boundary while retaining its original locator/provenance fields. This does not create a new source identity or alter its geometry/target joins.

Exactly one new pure unit test is prepared for the next actual parent:

    python -B -m unittest workflows.data_v1_final.conformers.window2_source_cache_v1.test_v1

It verifies exact path mapping, unchanged RID/MID/index and original input row, same-basename uncached fallback, prefix/lexical-alias nonmatching and identity mapping with no plan. It performs no LMDB/native/scientific data read.