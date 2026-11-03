# D3 single-job provisional export

Fixed cohort: 50,000 TRAIN molecules and 5,000 ROUTINE VAL molecules, using the already closed complete-S′ pilot and D-1 v3.0. Geometry, native atom order, original source masks and held-out exclusions are preserved; r674 remains LOSS_DISABLED. No new UFF or QM calculations run here.

The producer reads the closed D4 geometry SQLite without rebuilding its F64 BLOBs, creates only a narrow geometry/order index, and projects labels with 16 workers. After these workers exit, eight independent store writers run inside the same parent allocation. Closed source groups are reused across their recorded predecessor roots and retained until every group has merged successfully. Internal label payloads, source locators and permanent F64 sidecars use lossless compression. The training LMDB keeps the original MFM3 float32 wire format. The compressed authority reader is `payload_io.Reader.get_f64` and accepts both old raw and new compressed authorities.

One export job performs the final checks once: counts against the fixed cohort and exported records, 1,000 deterministic random label records compared field by field with original Parquet, and one export-manifest SHA. There is no production Source3 suite, 10,000-record gate, independent replay, 16-reader acceptance pass or full F64 second scan.

The same job copies the training files using one `rsync --checksum` invocation and performs one bounded random-read throughput measurement on the destination GPU node. It does not request or use a GPU. Model loader and per-head overfit tests provide acceptance after delivery.

The version is `v1-pilot-provisional`. Only fixed-random conformer order is currently released; energy/diversity ordering, D6 and the final common population are not claimed by this export.
Full geometry audit provenance, original field locators and source missing-position lists remain in permanent F64 metadata. The training header refers to that same authority instead of duplicating this trace in both LMDB records and masks. All original IDs, hashes, values, masks, reasons and ordered entries remain recoverable through Reader.get_f64; numerical training fields and the MFM3 codec are unchanged.
