# Opt-in FP32 compensated arithmetic candidate v1

Status: SOURCE_PREPARED, not tested, not adopted. This is one numerical candidate,
not a search over seeds, weights, fixtures, thresholds or architectures.

## Motivation and scope

Actual CPU job 4521404 completed all 384 encoder forwards (48 unhooked and 48
hooked cases), preserving all 52 output arrays bitwise under observation. None
of the 48 cases met the existing absolute 1e-5 composed criterion. Its first
32-atom clean graph shows FP32 geometry arithmetic residuals of about 2.75e-5
in squared-distance units and approximately 1.97e-6 in H0. A same-weight FP64
head shadow still exceeds 1e-5 for one dipole magnitude: a head-only correction
is not sufficient evidence for a complete fix.

Actual GPU job 4521406 durably completed its OP_REPLAY_DIAGNOSTIC_ONLY capture,
but exited nonzero because its original-policy repeatability control failed.
Ten of eleven fixed-input operations varied across three repeats. H0 sum pooling
varied by up to 2.288818359375e-5; the identical fixed PD bank varied by up to
6.347894668579102e-6. A separate strict-deterministic diagnostic made all eleven
operations repeat bitwise; it did not establish composed equivariance. These
observations motivate explicit fixed-order arithmetic, not a backend flag change.
The authoritative saved inputs are:

- runs/model_v3_20261025/C4_layer_head_v3_output_4521404/diagnostic/DIAGNOSTIC_RESULT.json
- runs/model_v3_20261025/C4_GPU_layer_head_4521406/DIAGNOSTIC_RESULT.json
- runs/model_v3_20261025/C4_GPU_layer_head_4521406/original_policy_SUMMARY.json
- runs/model_v3_20261025/C4_GPU_layer_head_4521406/strict_deterministic_diagnostic_SUMMARY.json
- runs/model_v3_20261025/C4_GPU_layer_head_4521406/CPU1404_firstcase_trace_decoded.json

## Fixed candidate

The sole new mode is `compensated_fp32_v1`; the absent/default mode is `legacy`.
All input, parameter, forward output and arithmetic tensors remain FP32. No
FP64 production arithmetic, initializer changes, new trainable parameters,
state-dict key changes, implicit deterministic/TF32 flags, or changed cutoffs
are permitted. H0 remains the same 512-wide encoder API. Its numerical values
can change through more accurate evaluation of the same mathematical geometry.

Segmented additions sort indices stably, preserving within-segment input order.
A packed CSR balanced tree uses Neumaier two-sum residuals in FP32 and carries
those residuals to the final rounded FP32 value. There is no padded
segment-count x maximum-degree x feature-width tensor and no loop launching once
per edge. Tree work shrinks geometrically and has logarithmically many levels.
The custom linear backward is the exact mathematical gather derivative of
index-add; it does not differentiate the floating-point compensation branches.
Empty segments preserve the base value. All source rows remain in the sum.

This reducer replaces sum/mean graph pooling and centroids, independent dipole
moment sums, and geometry message/noise index-add. Existing pair chunk size and
checkpoint boundaries remain. Compensation is per index-add call (including its
base), not a promise of exact real summation across arbitrary chunk schedules.
Dipole charges, centroid definition and moment expression remain unchanged;
there is no charge demeaning or physical model change.

Three FP32 coordinate squares use compensated two-sums before the final FP32
rounding. The corresponding square root has the ordinary Euclidean derivative
and a zero derivative at coincident coordinates. This same primitive is used for
C1-0 squared distances, C1-a/b direct distances, pair RBF distances and vector-head
distances. Pairwise distances are built in fixed 65536-pair tiles. Geometry edge
screening uses the same compensated direct distance in the candidate, avoiding a
different arithmetic definition for screening and features; existing strict
radius/zero tests remain. No finite cutoff is added to global attention.

Mode selection is explicit via `numeric_stability: {mode:
compensated_fp32_v1}`. The builder records matching `numeric_mode` in its existing
backbone/head config dictionaries. V3HeadBank requires the matching explicit
constructor option; its existing extra-state and C1's existing extra-state bind
that option without adding state keys. Raw tensor state dictionaries alone are
not scientific checkpoints: the existing typed model-config binding, or the new
explicit numeric checkpoint contract, is required to distinguish the modes.
Legacy config identity and extra-state contents remain unchanged when omitted.

## Fixed validation before any adoption

Root first registers the source and this protocol in Git, then executes the
meaningful CPU tests and original complete 48-case matrix: 3 C1 choices x 2 C3
view policies x 4 head policies x 2 predeclared seeds, each with all three
original rigid transforms. Preserve all original weights, fixture/mask/noise,
32-atom graph, terminal nonzero checks, output units, absolute 1e-5 and rtol=0.
Record legacy and candidate separately, with every failure retained. Do not
claim a mathematical all-real-input guarantee. The original legacy path is
checked bitwise against an independent copy of the base source with equal seeds,
and state tensors/keys/RNG against the opt-in candidate.

GPU validation uses the established node21/c35 public lock/UUID, 16 CPU/32 GiB,
28 GiB process bound, 2 GiB whole-output/private limits and <=20 minute allocation.
CPU-only tests use actual CPU nodes. Root owns all execution and submission.
No GPU backend policy is changed. Fixed-input repeatability and meaningful
finite/analytic gradient checks precede interpreting composed error results.
Actual capacity/throughput remain unmeasured; the O(edges x width) temporary tree
and logarithmic synchronization must be measured under the existing bounds.
A failed case is a failed case, not a reason to change seeds or lower output size.
No new D schema, labels, data splits, architecture decision or recipe acceptance
is implied. No formal training is authorized by this candidate.

## Integration boundary

The candidate is FP32-only and explicitly rejects AMP, half parameters or
non-FP32 coordinate inputs at the shared encoder/head-bank entry points.
V3HeadBank remains independently constructed: callers pass its explicit matching
mode. The supplied original-fixture adapter does this for every complete case.
Legacy primary/historical checkpoint admission is not broadened. Candidate
checkpoints use the existing typed model-config binding or
`numeric_checkpoint_contract` plus `load_numeric_bound_state_dict`; a shape-only
raw state load cannot establish scientific mode identity.

The ordinary regression entry contains 47 expected parameterized unit cases
(collection/execution pending Root). It includes independent original attention,
dipole and geometry expressions, equal-seed state/RNG checks for all three C1
choices, cancellation/empty/unordered segments, exact linear gradients,
coincident finite norm gradients, a nonzero Hessian oracle for force losses,
FP32-only dispatch and mode/checkpoint drift rejection. The scientific 48-case
matrix lives under validation/ so ordinary regression does not pretend the new
candidate is already scientifically accepted.
