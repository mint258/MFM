# Model v3 preregistration

Authority: the user's 2026-10-24 model-line work guide, supplied on 2026-10-25.
Baseline: `mint258/MFM@037546cd7f07b32dbb46bc21a69109dfd273f8da`.
No architecture/precision/recipe experiment has been run under this protocol.
The commit containing this file is the preregistration reference; every run
must record that immutable commit before starting.

## Scientific boundaries

- Develop on `model-v3` under `current/phychem_mfm`; preserve historical paths,
  configurations, source manifests and results. H0 API and 512-dimensional
  output remain unchanged for the new 6-layer model.
- Only downstream TRAIN populations and molecular inner cross-validation may
  influence any decision. Do not run historical formal readout entry points
  that also evaluate outer held-out populations. No downstream final scores.
- Raw LMDB stays read-only. New labels and their semantics come from data-line
  D-1/D-2; do not synthesize an authoritative interface or normalization.
- All training uses one GPU and persistent W&B records, with configuration
  hash, actual code SHA, data version, seed, GPU UUID/model and actual costs.
- No paid school-server use, formal pretraining, conformation grid, S/S-prime
  or P/P-prime decision study, family factorial study or complete fine-tuning.
- A stage becomes usable only after its acceptance evidence and report have
  been committed. Prepared code is not experimental acceptance.

## Stage 2: speed and precision

Implement optional checkpoint selection, compile, fused AdamW, TF32, sparse
radius attention and smaller atom buckets/local sorting. Preserve original
paths. Measure each item separately and cumulatively on 3090/4090/5090.

For each A-class candidate use the same fixed 20 batches: forward relative
error <=1e-5 and gradient relative error <=1e-4. Relative error is the L2 norm
of the difference divided by max(reference L2 norm, 1e-12), separately for
each floating output/parameter gradient; report maxima and missing gradients.
Both sides use fp32. Train paired same-seed runs for 500 updates; relative
loss-trajectory difference at every step must be <=1e-3. Preserve failed
comparisons and causes. Reordering/grouping is not automatically equivalent.
TF32 is not assumed to pass a floating-point equivalence threshold.

For B-class compare fp32 and bf16 S runs, 20,000 steps each, two seeds per
precision. Backbone matrix multiplication may autocast; coordinates, distance,
RBF inputs, geometry-head arithmetic, losses and normalization stay fp32.
Each bf16 validation curve must stay within the fp32 two-seed envelope;
denoising RMSE difference must be <=2%. No premature precision adoption.

## Stage 3: data, heads and losses

Uniform molecule selection then uniform allowed conformation is the default.
Conformation selection and PM7/S-prime/mixed geometry follow explicit manifests.
Honor molecule group/family masks and per-field validity. No inferred field
meaning or missing-label zero imputation.

Use TRAIN-only D-4 normalization then masked Huber delta=1 unless the registry
specifies otherwise. Average observed fields within a label group; average
enabled S/D/P groups equally, independent of their field counts. Log every
field's effective label count on every step. Define progress in consumed base
samples; save at 1/2/4/8/16/32/64 million samples and for recovery. Evaluate
unseen molecules and seen-molecule unseen conformations separately. Log field
loss, R-squared and raw-unit MAE; shared-backbone gradient norms every 500 steps.

Acceptance: every field R-squared >=0.95 on 1,000-molecule overfit tests;
disabled heads have no loss/gradient; synthetic masks pass; resume is bitwise
identical; H0 APIs/signatures and dimension 512 preserved; rotated vectors and
invariant scalars agree within 1e-5 in fp32; uniform molecule frequencies pass
a preregistered chi-square test (alpha=0.01, fixed seed, no resampling).

## Stages 4-5: development panel and architecture

Freeze 8-10 tasks covering ExpansionRx regression/classification, atom SoM,
QM9 energy/HOMO/LUMO, size-related and intensive targets, using only training
populations and inner folds. Freeze `configs/dev_panel_v1.json` before stage 5.
Cache H0 once; evaluate ridge with inner-CV alpha plus source-aligned
Linear64/ReLU, 20 epochs/B32. Report per-task relative error improvement over
same-architecture random initialization, task mean and molecule-bootstrap CI.
Reference the old S B3 endpoint only as a sanity check. Evaluation target is
less than 1 GPU-hour per checkpoint. Seed SD is the sample SD (ddof=1) of two
pretraining seeds of the same configuration, without mixing architectures.

Before stage 5: all existing/new tests pass; actual D-3 SDP 2,000-step smoke
test on each GPU model; one complete checkpoint evaluation; actual throughput
and memory recorded. Synthetic substitutes do not satisfy real-data gates.

Proxy: D-5 nested 240,000 TRAIN molecules, all conformations, PM7, 6x512.
Provisional AdamW lr=3e-4/betas=(0.9,0.95), clip=1, 2% warmup/cosine,
6M consumed samples. Check development plateau on one curve first; any budget
change is documented and committed before candidate comparisons. One seed
initially; add a second seed for the two leading configurations per decision.

- C1: compare original per-layer distance MLP, shared K64 Gaussian RBF/pair
  embedding with per-layer projections, and element-pair-conditioned kernels,
  on S and P (six runs). Among candidates within 1 SD of the best development
  score and within 1 SD of C1-0 separately on S and P, choose fastest. Retain
  C1-0 when both alternatives are worse than it by >1 SD.
- C2: use A4 equivariant denoising; coordinate lookup baseline is descriptive
  analysis and does not add an acceptance threshold.
- C3: compare two/three views on S and SDP (four runs). Use two only if both
  development scores are within 1 SD of three, with no clear masked-element
  or bond-metric regression. Quantify the latter before executing comparisons.
- C4: equivariant vector-label heads are required, with symmetry/overfit tests.
- H1/H2/H3: compare on P/D/SDP (nine runs), plus learned-vs-registry pooling
  on P. Choose simplest within 1 SD of best, seeking one form across groups.
  If a group's H1 R-squared <0.5 and H3 >0.9, use H2 for that group as directed
  by the guide. A field uses the same head in every label combination.
- Pooling: registry defaults; use learned pooling only if it improves P by
  more than 1 SD. Approximately six additional seed repeats; preserve all runs.

## Stage 6: recipe and budget

Set per-GPU atom capacity from measured peak memory <=85% of actual capacity.
On the proxy, scan S/P lr in {1e-4,3e-4,6e-4,1e-3,2e-3} at B0 (10 runs);
best two rates at 2B0 on both tasks (four runs); cosine vs WSD on S/P (four
runs), with WSD final 10-20% decay fixed before that comparison. Prefer WSD
within 1 SD. Choose smaller lr and larger batch within 1 SD; retain B0 if 2B0
regresses. If no rate is within 1 SD of each of the S/P optima, report to user.
Exclude divergent/spiking rates. Derive clip from training gradient-norm p99;
confirm SDP once. Pretraining losses alone do not decide the recipe.

With D-6, run S and P once each to <=64M samples or development plateau.
Plateau is the earliest doubling with improvement <1 seed SD. B-star is the
larger S/P budget; >2x difference requires user decision. Present concrete
results for user confirmation before freezing model/recipe or tagging v3.0.
Then smoke one 120k-molecule/k=2 grid cell for 1M samples through evaluation,
prepare HANDOFF and a PR to main for the user to merge.

## Immediate stop/report conditions

Stop and report unexplained A-equivalence failure; a sub-0.95 overfit field
whose cause may be labels/data; a necessary change to H0 definition/dimension/
export; a need to inspect downstream final scores; stage GPU use >2x estimate
(stage 5 estimate 100-150 GPU-h, stage 6 150-250); required school-server use;
or any required deletion of existing files. Do not change rules after results.
Maintain shared STATUS with dated D-item/status/path and stage milestones;
report elapsed-stage overruns >50%. Preserve negative and abandoned results.
