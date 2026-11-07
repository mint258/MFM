# Original S240k P/D shared-D6 binding

Run `python -B -m workflows.data_v1_final.export.s240k_pd_binding_v1.run --plan configs/data_v1/S240k_PD_shared_binding_20261108_v1.json` on Root's actual compute allocation. Only the original subset MID column and final Common MID/role/common columns are read; the closed S record index is referenced, not reopened or reused as D6 row indices. Every original MID/order is retained with explicit gap reasons. No population intersection, new LMDB, labels, coordinates or model-window edit.

Output `membership_binding.parquet` is built once. `manifest.json` exposes identical P/D input paths and stays NOT_READY/root=null until all original MIDs bind to final Common TRAIN and the final producer-published D6 manifest exists. After D6 closes, rerun the same CLI: it reuses the closed membership table and updates only the JSON root binding. It never substitutes the newer D5 240k list. NFS admission reuses the existing Guard/quota snapshot; the config reserves the already-planned85GB final-ID/metadata growth, window3 16GiB and other6GB.

Only the new synthetic `test_binding.S240kPDBindingCheck.test_identity_only_binding_preserves_order_gaps_and_late_d6_root` is pending Root's first execution. No existing tests or scientific QA are repeated.
