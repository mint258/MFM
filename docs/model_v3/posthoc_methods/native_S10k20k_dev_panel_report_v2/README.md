# Native S 10k/20k development-panel report (posthoc source only)

This single CPU driver reads only the two actual Root-closed metadata chains: Native seed0 FP32 at 10,000 updates (GPU4524476) and 20,000 updates (GPU4525060). It does not modify either run. The input request binds their actual closure bytes/SHA; each closure binds the original result, request and six manifest JSON files. No tensor, checkpoint, target record, SDK or resource/history journal is opened. Existing closed population/resource facts are consumed as evidence, not rerun.

## Reused implementation and narrow gap

The mature `MFM_model_v3_native_checkpoint_bridge_v1/tools/model_v3/analysis_sources/primary512_verification_v1/make_primary512_report.py` already exports the same 18 task/readout rows and saved 1,000-draw bootstrap intervals. It is a single-run CSV/Markdown reporter and its admission explicitly requires the older `source_training_checkpoint_v1`; importing it as a Native validator would incorrectly reject these actual Native checkpoints. This new one-file driver reuses its scalar projection and original normalized-improvement/equal-weight consistency expressions, with the existing Native Root closures supplying endpoint admission. The added work is the two-point join and ordinary matplotlib plots. No new scientific gate, fit, resampling routine or model implementation is introduced.

## Exact comparison population

Both endpoints must retain the same frozen nine tasks, `ridge` and `linear64_relu`, TRAIN-only inner-validation protocol, original preregistration39cf4929..., 512-dimensional architecture, pretraining seed0 FP32, random initialization seed20261025, readout seed0, evaluator code, data version, native membership, packing plan/budget and effective H0 runtime. The six actual manifests must match their six common fields in the result. Cache keys are independently checked against the original canonical binding encoding and `cache_root/key/manifest.json`; endpoint checkpoint-dependent keys are expected to differ, not forced equal.

Candidate/reference geometry population must match within each endpoint, and the effective population must match across endpoints. Source-unavailable geometry remains reported and excluded under the already frozen rule; it is not changed to zero or silently treated as complete source coverage. Observed task label and molecule counts must match across the endpoints.

## Outputs and reading the uncertainty

- `task_metrics.csv`: all36 endpoint/task/readout rows, source-unit candidate and matched-random errors, normalized improvement, observed labels/molecules and copied original endpoint CI.
- `task_changes.csv`:18 descriptive 20k-minus-10k differences. Negative raw-error change means lower error. There is no CI or significance claim for endpoint differences.
- `aggregate_metrics.csv`: both actual endpoints' original18-cell, ridge and linear64 summaries with their saved CIs.
- `raw_error.png/.pdf`: nine separate task axes, both fixed readouts, actual source-unit candidate errors. The saved results contain no raw-error confidence intervals, so none are invented.
- `normalized_improvement.png/.pdf`: nine task axes, both readouts, the original endpoint-specific paired-molecule95% intervals from1000 resamples. These are intervals against each endpoint's matched random evaluation, not CIs for10k-to20k change.
- `summary.json`: the compact scalar tables, input metadata before/after refs, report source before/after equality and generated artifact refs. No native IDs, predictions, labels or packing lists are copied to the public tables/figures.

The random encoder state is matched, but actual saved reference errors differ for seven `linear64_relu` cells. The report preserves both reference errors and adds no independent0-update random anchor or falsely identical reference curve. Ridge/readout choices remain the original fixed ones; there is no post-selection.

This is a descriptive two-endpoint development panel for one Native seed/precision. It provides no second seed SD, bf16 curve, final TEST, formal D5/proxy authority, B* selection, final training recipe or whole-guide acceptance. Root-closed GPU facts and SDK-audit/sync facts retain their separate scopes; this report does not infer W&B completion from the old result flag or old closure's SDK_PENDING status.

## Root invocation and bounded CPU resources

Use the existing approved CPU auto-memory submission and supervision, at least16CPU, actual fresh CPU node/MemAvailable/quota and original identity/private/output accounting. No new submission framework is included. Suggested report allocation is5min with180s software wall,16GiB software working budget/RSS12GiB, whole output/private each2GiB. The report additionally bounds unique metadata input16MiB (each JSON<=2MiB) and its own output64MiB. Automatic Slurm default memory observations are actual values, never a claimed16GiB allocation.

`PY -B S/report_saved_panel.py --inputs S/inputs.json --output N/native_S10k20k_dev_panel_report_v2`

`PY` is the existing frozen Python environment; `S` is this source directory. Root must choose a fresh output path. This package contains only source and bound metadata request; no report/plot execution, model fit, bootstrap, Slurm submission, Git/publication, hold release or ledger mutation has occurred. Root may execute once and inspect the ordinary PNG/PDF/CSV artifacts before publishing them.

## Layout revision v2

The v1 report completed on CPU4525083 and its original source/artifacts are retained. This revision changes only the plotting function: disable constrained layout, reserve the lower8.5% and upper9% with tight_layout(rect=(0,.085,1,.91)), and place the global legend at figure y=.01. All input bytes, metrics, populations, CSV writing and CI calculations are unchanged. The two original endpoint results are read again as metadata to redraw; no model/readout fit or bootstrap is repeated. The new report output is a fresh v2 directory, not an overwrite of v1. Actual v2 figure readability and output/CSV equality remain for Root's single CPU run and visual check.
