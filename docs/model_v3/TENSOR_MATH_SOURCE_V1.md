# Tensor math candidate v1: source-only boundary

Status: SOURCE_CANDIDATE_NOT_EXECUTED_NOT_R674_ENABLEMENT. Worktree
`MFM_model_v3_tensor_math_candidate_v1`, branch
`model-v3-tensor-math-candidate-20261028-v1`, parent supplied base
`e4b21193be60fcb396ab1d2d56c1cba6736078dd`.

This change adds only the standalone module, its synthetic test source and this
note. It changes no FieldSpec, registry, provider, wire, factory, default model,
training recipe, label, mask, normalization release or running task. No Python,
AST, pytest, Git, SDK, Slurm or scientific data was executed/read for this source
handoff. Actual collection, PASS count and runtime acceptance are unknown.

## Source conditions

The conditions were read from data-line
`runs/data_v1_20261025/repository/docs/interfaces/training_format_v3_draft5_public_head_addendum_v1/ADDENDUM.md`
section 3 and model-line
`MFM_model_v3_reporting_v3/docs/interfaces/training_format_v3_draft4_model_review_20261027_v1.md`
sections 3-4. Both remain conditional designs without joint freeze. The public
model review is associated with commit
`1f7f255fd412cd53ce7f6913ddbb43645d9f9ee7`; this candidate is separate source.

The actual r674 source origin, sign, units, native coordinate transmission,
translation law, coefficient, precision and D4/D5 release are not established by
this module. In particular, no additional xTB 1.5 coefficient is applied.

## Explicit mathematics

Source order is `xx,xy,yy,xz,yz,zz`. All six members, including zz and the supplied
trace, survive conversion. The symmetric matrix mirrors xy/xz/yz; these mirrored
entries are not nine independent source labels. Orthonormal six coordinates
multiply xy/xz/yz by sqrt(2), so Euclidean six norm equals the matrix Frobenius
norm. Matrix-to-source conversion validates symmetry with absolute FP32 tolerance
1e-5 and reads named upper components; it does not average, project or repair.

`rank2_rotation_operator` requires one finite proper rotation [3,3], the literal
`row_XR_plus_t` convention, and FP32. For column six coordinates q it returns
D with q'=Dq, representing Q'=R^T Q R when X'=XR+t. Proper-rotation validation
uses absolute FP32 tolerance 2e-5. For a true observation y=Aq, the operator API
returns A'=A D^T, retaining y and its original source identity. A six-bool mask
is never used as a replacement for this transformed operator.

`StandaloneRank2Head` maps invariant H0 to invariant atom coefficients. With
explicit per-graph origin O, u_i=X_i-O_graph, its two explicit forms are:

- `symmetric`: compensated graph sum of a_i u_i u_i^T + b_i I.
- `traceless`: compensated graph sum of a_i(u_i u_i^T-|u_i|^2 I/3).

The traceless option is a model basis choice, not a projection of source labels.
The origin is never inferred from COM, neutrality, atom count or a registry name.
Callers must explicitly assert `explicit_comoving` and
`caller_consistent_no_conversion`; only O'=OR+t gives the stated mathematical
equivariance. Fixed-native-origin translation rules remain unsupported/unknown.
These assertions do not prove that an actual source origin or units satisfy them.
The output has coefficient times coordinate-squared units (plus the explicitly
learned isotropic term for the symmetric form); no physical unit mapping is
claimed. Coefficients, coordinates, parameters, intermediates and output stay
FP32. Existing compensated graph summation and squared-norm helpers are reused.

## Low-level observation loss, without a population policy

`radial_huber_observation_loss` requires packed q[T,6], A[K,6], y[K], and tensor
IDs[K]. Only real observed rows appear in A/y. Unobserved source components have
no target slot; the implementation does not manufacture zero labels. Arbitrary
partial operators are allowed, including the rotated source selectors above.
The observation metric is Euclidean in the explicitly supplied observation rows;
a non-Euclidean metric would need explicit caller whitening and its own contract.

For each tensor, the exact supplied-parameter formula is
`r = ||(Aq-y)/s||_2 / sqrt(d)` followed by radial Huber
`rho_delta(r) = r^2/2` for r<=delta, otherwise `delta*(r-delta/2)`.
The TRAIN scale s and normalization d must be positive finite FP32 scalar or [T];
delta must remain positive and finite in FP32. All three are mandatory. No d=6,
d=9, m-based denominator, robust statistic, centering cI, axiswise scale or
physical unit conversion is selected by this API. Scale-role `TRAIN` and unit
consistency are mandatory caller assertions, not recovered D4 evidence.

The mandatory policy token is
`caller_eligibility_observation_math_only`. Caller `loss_eligibility[T]` and
`source_component_mask[T,6]` are required and returned as exact independent clones.
The function does not derive eligibility from component coverage or choose the
jointly pending complete-only versus partial-observation population policy.
An otherwise eligible tensor with m=0 is separately excluded. Each active tensor
counts once in `field_count`, regardless of K or matrix mirroring; `total` sums
active tensor losses and `mean=total/max(field_count,1)`. All-empty observations
produce a connected zero loss with zero active fields. Observation count, zero
observation flags and packed normalized residuals remain available independently.

The square-root implementation retains the smooth quadratic Hessian at zero
residual, avoiding an inactive sqrt'(0) branch. The analytic mixed-derivative tests
check this and a nonzero radial linear-branch Hessian. Counts and IDs are int64;
source masks and eligibility are bool; no floating output is promoted to FP64.

## Planned independent checks and outstanding gates

The authored tests cover explicit six order and nonzero trace, Frobenius isometry,
independent Rodrigues rotations with fixed seeds 11/29/83, invariant-H0 heads under
general rotations and comoving translations, empty graphs/cancellation/source and
graph reordering, transformed partial observations, full/partial radial formulas,
field denominator and zero observations, scalar scale broadcasting, invalid
origin/unit/policy/shape/nonfinite/TRAIN scale inputs, analytic first derivatives,
nonzero mixed second derivatives, zero-residual Hessians, and an FP64-production
prohibition. Small FP64 tensors occur only in independent test oracles. Seeds,
output amplitudes, backend settings and physical acceptance thresholds are not
selected or changed to obtain a pass.

These are test sources awaiting Root's authorized CPU execution. There is no
actual collected-test count, PASS result, GPU measurement or new E2E physics
result for these bytes. The earlier complete 48-case physics matrix still failed;
this isolated foundation cannot change that result. Root must review/run the new
source, preserve prior failures, and separately complete the actual D1 physical
definition, population/mask/metric/denominator policy, final D4/D5, real consumer
chain, actual TRAIN/ROUTINE VAL, child H0 and prescribed real-model acceptance.
The current r674 consumer remains unsupported and joint freeze remains false.
