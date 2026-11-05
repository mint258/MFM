# D3 local store staging and closed-output continuation

The original frozen55k science, training codec, ordered F64 authority and one final1000-Parquet sample are unchanged. Each future store may use private node-local storage; after its original finish and close, files are copied once to the original Lustre output root. Insufficient cache capacity uses the original shared writer. Existing closed stores and metadata are resumed without rewriting their headers.

One checksum rsync places training LMDB and manifests on the GPU node. Permanent F64 sidecars stay in Lustre under their unchanged references; consumers must use those shared authority paths rather than inventing node-local sidecar paths. Actual delivery and Model acceptance come from the original real completion/publisher artifacts, not code presence.
