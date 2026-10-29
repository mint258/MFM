# Current R1 typed run CSV v2

Exactly the same eight already closed original R1 runs are represented, four A00
and four HeadOff. This is a schema projection of the immutable v1 rich source,
the original ORIGINAL_A_SPEED_REPORT files and actual Root closures. No metric,
ratio, peak, evaluation or scientific result is recomputed. The rich v1 stays
only at its original N source namespace and is not packaged as a CSV.

Publish runs.csv as a direct child of docs/model_v3/results/, for example
docs/model_v3/results/performance_R1_20261029.csv. Do not place any CSV beneath
a subdirectory, rename the rejected rich CSV to bypass checks, alter the checker,
or overwrite original historical results. README/bindings are ordinary source
documentation; they contain the full nonnumeric per-run identities and references.

Required typed-column mapping:

- run_id: actual tracking_run_id; stage:2; config_sha256: actual configuration
  raw bytes SHA256. The distinct original canonical configuration_sha256 remains
  explicitly named in bindings.json and is not substituted for the raw SHA.
- code_sha: actual7ffe runtime; seed: original0; gpu_model/gpu_uuid: actual C35
  RTX5090. data_version is a descriptive original Native S snapshot SHA identity,
  explicitly not D5 and not an invented Data-release version. Manifest/snapshot
  paths and hashes, original input receipt identity and D_version NA are in bindings.
- elapsed_seconds: actual sacct ElapsedRaw of that single member GPU parent,
  including setup/cleanup. It is not the reported timing window or pure training
  time. status COMPLETED reports only its actual owned C0 parent state.
- preregistration_sha: original R1 method public7f790e9363a5f7ec4b10d475bbabdb2e6969bd5d,
  verified against the actual current_A_performance_methods publication rawref.

All extra CSV columns are finite numeric metric__ fields. Each value is copied
unchanged as the original report token: ABBA position,2warmup/20measured/22SDK rows,
reported timing-window seconds, base-record/native-atom/molecule-presentation
rates, allocated/reserved peak bytes and the original pooled pair ratio.
The pair ratio0.9918131766322366 (A00) or1.0584113049897554 (HeadOff) is repeated on
its four actual member rows; it is a four-member pooled original-tool result,
not a new per-member computation. Finite-number parsing checks syntax only and
does not replace the original decimal tokens or recalculate values.

case, role, series, raw-vs-canonical hashes, actual parent job/node/elapsed scope,
original source identity, all report/numeric-gate/full-native-SDK+official-sync+
cloud-readback Root refs, and both Root recipe_adopted=false decisions remain
complete in bindings.json per run. Numerical20+500 qualification is a separate
existing bound Root result; these R1 runs themselves are2+20 timing runs.
No final recipe adoption, D5/noise-seed experiment, new pretraining, scientific
success or full-guide completion is granted. No cost/weekly ledger or per-job
report is produced. Old v1 artifacts, reports, source/model/data/results and
running jobs are unchanged; no project, Slurm, Git, SDK, steps, weights or arrays
were executed/read. Root performs the actual checker/publication after copying
the typed CSV bytes to the allowed direct-child destination.
