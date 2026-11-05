# MFM project guidance

Read [portable project context](docs/project_context/README.md) first, then the
task-relevant contract, current branch status and original evidence.

- Develop the shared representation under `current/phychem_mfm`. H0 is
  `SharedBackboneMFM.encode_atoms(batch)` before task fusion or gates. Preserve
  source atom order, geometry identity, labels and masks. Model-v3 targets six
  layers and 512-dimensional H0; historical 4x384 checkpoints are distinct.
- Repository skills live under `.agents/skills/`. They do not require a personal
  skills directory, a particular drive letter or an existing local memory.
- Resolve the actual checkout, remote project, logical interpreter, storage and
  authentication from the current environment. Mounted remote files are live
  server files; an unrelated local copy does not synchronize by implication.
  Run server code in its server environment.
- Substantial computation uses compute nodes and the established scheduler.
  Read-only metadata inspection and file editing may use the login node.
  Keep task-specific resource restrictions and explicit exceptions scoped;
  historical node availability is not a current allocation.
- This handoff does not launch, resume, cancel or delete anything. Paid-server
  formal pretraining requires explicit user authorization. Do not interfere
  with other users or unrelated project jobs.
- Original LMDB and authoritative WP5 F64 Parquet remain read-only. Keep real
  data, weights, checkpoints, computed labels, caches, databases and credentials
  outside Git. Run `python tools/check_repository.py` before committing.
- Preserve frozen configurations and scientific source bytes. Record new
  revisions separately from `docs/SOURCE_MANIFEST.json`. Publication commit,
  execution commit, data manifest and actual job result are distinct.
- Fit normalization, anomaly statistics and model selection on the declared
  TRAIN population only. Current model development must not run or inspect
  downstream TEST results; historical benchmark reports are not new selection evidence.
- PM7 energy means FINAL HEAT OF FORMATION in kcal/mol; charge means NET ATOMIC
  CHARGES in e. Other semantics follow the versioned field registry.
- Latest explicit user instructions apply within their stated task scope.
  Dated cleanup permissions, resource exceptions and retry rules do not become
  general authorization. Preserve failed, unknown and unvalidated states.
- The dated handoff records D-3 v3.1 data-side delivery, pending model payload/head
  acceptance, and a user pause on D-6 and later. Recheck current evidence before
  continuation. WP5 and old S/S′/S-repair workflows are closed historical tasks;
  old ACTIVE notes do not authorize restarting them.

For the older exported source tree also read `docs/DEVELOPMENT_HANDOFF.md` and
`docs/DATA_PIPELINE.md`. This bundle is not a merge of model-v3 and data-v1 code.

