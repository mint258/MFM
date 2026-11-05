# C4 layer/head attribution plan v1

Design frozen for Root review; implementation and execution are not started.
This is an analysis plan, not a changed model, acceptance rule or adopted fix.
Original Eq48 cases, weights, seeds,32atom fixture, physical views, three rigid
transforms, original units, abs1e-5/rtol0 and failure evidence remain unchanged.
No native geometry/labels/checkpoints are read; no old NPZ is read.

## What actual closed evidence establishes

Root actualCPU1049 completed the7x48 attribution matrix; reporting job1066
closed its aggregate. Original exact replay is true. All7 variants still have
zero fully passing48case combinations. Direct-cdist changed no terminal values.
Charge centering changed dipole82 failed measurements to54 (max5.14984e-5 to
4.75347e-5) but magnitude50 to52 (max3.08752e-5 to2.05934e-5). FP64 graph-feature
pooling reduced extensive20 to14 failures (max2.28882e-5 to1.52588e-5), not zero.
The source-bound aggregate, not these rounded prose numbers, is authoritative.
No intervention is adopted and the FP64 reference is not FP32 acceptance.

C1-0 attention computes explicit coordinate differences and squared-distance
sums, not cdist. C1-a/b already use direct cdist. The remaining default-cdist
calls select vector edges; far-from-cutoff unchanged edges explain why forcing
their distance kernel can leave outputs identical. Size32 alone does not prove
an attention MM-cdist path ran. That old domain flag is a size predicate, not
an observed operator-mode counter; preserve it but do not infer causality.

The graph scalar path pools512wide H0 via FP32 index_add before H1/H2/H3.
Learned pooling combines sum and mean through independently learned logits.
FP64 pooling still leaves upstream H0 error, projections/activations and final
FP32 rounding. Dipole uses q(H0) and FP32 centroid, then sum q_i(r_i-center).
Removing mean charge only suppresses one cancellation term: upstream charge
changes and coordinate errors remain. Magnitude has its own charge MLP; it is
not the norm of the independently parameterized p_dipole output.

The largest baseline dipole discrepancy is at a component around-0.0158,
and magnitude around0.1468. Those are far more than one output ULP, so final
representability alone is not an established explanation. Scalar27.47 errors
of2.29e-5 are about12 ULP and still may reflect accumulated upstream errors.
No currently observed result proves that this fixed48case domain is impossible
for a same-weight FP32 implementation, nor that a head-only rewrite will fix it.

## One predeclared experiment; all48 cases, no search

Run two original full matrices, one fresh unhooked control and one read-only
instrumented replay. Each case executes original plus the same three moved
views through actual6x512 encoder:384 actual encoder forwards total. No
intervention or new initialization is used. Hooks must return None. Require
weights/input/view/config digests identical, original JSON measurement/domain/
edge replay exact, and all13 current terminal arrays bitwise equal between the
fresh control and hooked replay. Read only these newly produced control NPZs
(allow_pickle=False), never old archives. Hook perturbation/drift rejects the
attribution output while preserving every partial measurement.

For each physical graph and each transform, capture these fixed stages:

- Input: actual FP32 original/moved pos and targets, R/t, cast residual
  pos_moved-(pos_original@R+t) in FP64, noise-pushforward residual, pair-distance
  perturbation computed from actual FP32 inputs in FP64, and unchanged edges.
- Encoder: identical initial embeddings; each of6 norm1, attention return,
  norm2, FFN return and layer return; pre/post final out_norm; clean H0. For
  C1-0, each existing dist_mlp input/output; for C1-a/b, shared pair-encoder
  distances/features and per-layer pair_projection output. No local attention
  reimplementation is substituted. Capture masks/IDs to compare valid rows.
- Head: all graph pooling inputs/results, learned mixer probabilities and
  outputs, H2 shared projector/each linear and activation output, individual
  charge MLP outputs, center, centered-coordinate sum, per-atom q*r terms and
  their sum. The magnitude head's own pre-norm vector is reconstructed by
  replaying its original formula and must bitwise match the actual norm output.

Summaries retain dtype/shape/digest, maxabs/argmax, signed error at argmax,
mean-square error and per-graph counts. Distance summaries separately report
input-rounding perturbation (FP64 distance on the two actual input sets) and
FP32 arithmetic residual relative to those references. This identifies the
first actual deviation and its growth, not a correlation-only final maximum.

## Head cross replay and exact bookkeeping

Use captured cleanH0 H0,H1 and clean positions P0,P1 with original same-weight
heads. For every transform and each of the3 failing field families, run all4
crosses Y00=head(H0,P0), Y10=head(H1,P0), Y01=head(H0,P1), Y11=head(H1,P1).
Use the unchanged full-batch head shapes and dtype; do not slice32atoms out for
production arithmetic. No encoder is rerun for these crosses. Y00/Y11 must
match actual full-forward outputs bitwise. Graph-scalar Y01=Y00 is a control.
For vector L=right-multiplyR; for scalar/magnitude L=identity. In FP64 report:

    total = Y11 - L(Y00)
    H_effect = L(Y10-Y00)
    coordinate_effect = Y01-L(Y00)
    interaction = total-H_effect-coordinate_effect

All values are retained, including signs; these identities do not assert that
components are independent. Report a FP64 bookkeeping residual. Magnitude
uses its own vector/norm, not another head's charges. Original raw-unit maxabs
threshold results remain alongside the decomposition without replacement.

Also evaluate declared functional FP64 shadows of these same heads and all4
crosses using the captured FP32 inputs and same parameters converted read-only
to FP64. This is a numerical reference, not a mathematical proof or FP32 run.
Do not call model.double(): current head forwards explicitly cast to FP32.
For H1, separately report W64*sum64(deltaH) and each pool/linear arithmetic
residual; for H2/H3 report pool/projector/nonlinear drift. For dipoles split
fixed-q geometry and changed-q effects before norm. All nonlinear shadows
follow the exact registered head structure; unknown structure must reject.

If the idealized same-weight FP64 head on captured H0 already breaches1e-5,
fixing only head FP32 reductions is insufficient to eliminate that upstream
contribution. If original head arithmetic dominates instead, a future declared
balanced/compensated FP32 reduction can be tested on the full48 matrix. This
plan does not scan reductions or pick the most favorable case/algorithm.

## Absolute tolerance and input rounding

The actual transformed input is round32(P0R+t), not the exact real rigid image.
For a smooth invariant exact-real function f, f(P0R+t+delta)-f(P0) includes
sensitivity J*delta. Size, geometry, parameter norms, cancellations and output
units can amplify it. A universal absolute1e-5 guarantee for all weights, graph
sizes, units and translations does not follow from equivariant real algebra.
This does not change the existing required finite-domain absolute test, excuse
its failures or justify switching to relative error. This experiment estimates
actual sources; it does not declare input quantization unavoidable for these
specific weights without evidence. FP64 shadow arithmetic is not certified
exact-real or an adopted precision policy.

[PyTorch2.10 numerical accuracy guidance](https://docs.pytorch.org/docs/2.10/notes/numerical_accuracy.html)
explains finite precision, operation-order effects and differing batched/sliced
kernels. That supports preserving full-batch replay shapes and distinguishing
algebraic identity from numerical equality; it supplies no waiver of1e-5.

## Frozen execution request and output budget

The accompanying protocol_draft_v1.json fixes scientific identities and the
analysis above. It is not executable: Root reviews design, then new external
runner/test sources and a complete runtime inventory must be CPU-tested and
publicly bound before any actual run. No future jobID or success is invented.
Root alone supplies a currently available siteCPU node2/8-19 and schedules.

Proposed16CPU/16GiB allocation, one Torch/BLAS thread,600s child wall/660s outer,
12GiB RSS,64MiB total child outputs, existing2GiB outer/private caps. No GPU
is visible. These are declared ceilings, not permission to use a GPU node.
Full-layer tensors are retained only for one case in memory; disk contains
bounded per-case summaries and the two newly generated terminal archives.
No unbounded attention/qkv dumps or weights are persisted. Budget overflow is
an explicit failed/censored run; no selective deletion or cap enlargement.
All48 cases and all transforms must close or aggregate remains incomplete.

Suggested tests for the future source: hooks preserve raw full-forward tensors;
negative output-changing hook rejected; planted layer drift is located; analytic
linear scalar4cross oracle; nonzero vector rotation+translation decomposition;
independent magnitude charges; true FP64 shadow matches small dense formula;
unknown module/dtype/source and byte-budget rejection; complete48 membership.
No source/test has yet been implemented or executed for this plan.
