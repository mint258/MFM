# D-3: direct export from the 171 closed source fragments

This isolated producer exports the existing frozen 50,000 TRAIN and 5,000 ROUTINE VAL molecules under D-1 v3.0. It reuses all 171 source fragments from job 4525670: 7,128,716 source rows and 65,570,829 label pieces. It performs no source projection, QM or UFF calculation.

The node-local SQLite database contains only `(gid, part, source_id)` routes. A merge of the original covering key indexes detects duplicate owners and inserts the keys in order; the 430,926,245,888 source payload bytes stay in their original files. Eight store writers use the routes to read the original payloads and write the existing LMDB and permanent F64 formats. Each writer keeps at most eight source connections open. The original source fragments remain intact through delivery.

The four scientific files `source.py`, `projection.py`, `frame_mapping.py` and `payload_io.py` are copied byte for byte from the existing producer. Field IDs, masks, roles, r73 ordering/F64 authority/one F32 cast and r674 LOSS_DISABLED remain unchanged. Geometry and D-5 exclusions reuse the existing closed D-4 inputs.

The original single final count check and 1,000 original-Parquet field comparisons run once. The existing checksum rsync and 180-second read benchmark run once. The original metadata publisher requires actual parent completion; model loader and head overfit acceptance remain subsequent model work.

The actual prior parent must be terminal before this producer starts, because its old merge path would otherwise delete these source fragments. The prior closed geometry index is copied to node-local scratch. Scratch working forecast is 40 GiB with a 4 GiB free-space reserve; available local disk is measured in the real allocation and shortage waits. This is not a forecasted capacity pass or a wall/RSS limit. The existing Lustre 750 GB forecast and real 100 GB account reserve after all future budgets remain unchanged and are transferred once from the prior job.

Status at installation: source only, not submitted or executed. The old producer has not been edited. Its partial payload merge can be retired only after it has actually exited and the closed source fragments are preserved.
