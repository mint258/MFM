# All-six-layer centered FP32 attention candidate v1

Status: **SOURCE PREPARED; CPU QA AND FULL C4 CANDIDATE MEASUREMENT PENDING**.
This is one experimental candidate on `model-v3-attention-centering-20261027-v1`,
based on local `4068623cc455915a34a4aacae4f0df5c56f691b7` (published numeric
candidate `5cdb2772dfa51e1cc72098c659fb741440219772`, exact tree
`b2b53cde6a099bf4b4d1686bec8823bc0b30bc8e`). It is not adopted or merged into
the production `model-v3` runtime. Earlier numeric GPU job 4521435 remains
10 passing / 38 failing cases at the original absolute FP32 tolerance 1e-5.

The new explicit configuration is:

```yaml
backbone:
  attention_aggregation_mode: centered_fp32_v1
numeric_stability:
  mode: compensated_fp32_v1
```

The two modes are independent. `numeric_stability` and all its existing enum
comparisons, compensated pooling/geometry/head arithmetic, H0 definition, and
512-dimensional production representation retain their existing meaning.
The newly added attention key defaults to `legacy`. Missing keys are not
inserted into old model configurations; explicit legacy is also supported.
Legacy attention retains its original direct `torch.matmul(p, v)` path.

## Fixed candidate

Every coupled DenseGeo/SharedPair attention layer uses the same expression:

`anchor + p @ (V - anchor)`

`anchor` is the first valid native key value for each graph and head, gathered
without detaching autograd. This candidate applies to all six layers of C1-0,
C1-a and C1-b; it contains no layer/seed selection or fitted coefficients.
Inputs, parameters, buffers, softmax, operands, output and backward arithmetic
remain FP32. No parameter tensor, tensor-state key, initializer, random draw,
backend policy, attention radius, RBF, head, pooling or mask formula is changed.
The existing projection and padded-query mask remain after AV.

`p` is the original already-computed softmax. It is not cast or renormalized.
In exact real arithmetic a normalized row makes the two AV expressions
identical. Finite FP32 rows need not sum to exactly one; the candidate therefore
has a real floating-point expression change and keeps the anchor derivative.
It makes no promise that every original C4 case will satisfy 1e-5.

Evidence motivating this one candidate comprises closed CPU layer/head job
4521404, fixed-operation GPU job 4521406, full-encoder FP64 analysis job
4521561, and local AV diagnostic job 4521641. These are analysis evidence,
not candidate acceptance. In particular, FP64 reference errors do not prove
an FP32 lower bound or identify one exclusive causal operation. Centered AV
also allocates a new value-difference tensor; local AV comparisons cannot
isolate common-component cancellation from operand-layout/kernel effects.

## Explicit supported scope

The opt-in entrypoints reject empty packed coordinates before PyG packing,
empty/all-masked dense graphs, effective attention dropout, autocast, and
non-FP32 input/parameters/floating buffers. Eval-mode dropout is effectively
disabled and allowed; active attention dropout is rejected before QKV/dropout
and consumes no rejected-forward dropout RNG. Legacy packing/dropout/dtype
behavior is unchanged. Unsupported mode strings are rejected.

The actual supported classes are `DenseGeoSelfAttention` and
`SharedPairAttention`. `build_performance_model` rejects the new mode before
building a model; the actual available `RuntimeDenseAttention` constructor
also rejects a centered source attention. Centered `encode_atoms` and both
backbone forwards check actual layer classes/modes before execution. This
catches later replacement by runtime/native/bf16 attention which would
otherwise silently retain centered configuration and execute another AV.
No external NativeRuntimeDense constructor absent from this source base is
claimed to have been tested or ported. Native/selective-bf16 execution is
unsupported in this revision.

## Configuration and checkpoint identity

The complete backbone configuration retains the explicit key, so
`numeric_checkpoint_contract(model)` and `load_numeric_bound_state_dict`
reject a legacy/centered configuration mismatch. Tensor parameter/state keys
remain unchanged. For C1-a/b, the existing SharedPairBackbone extra-state
schema conditionally includes `attention_aggregation_mode` only for the new
mode and rejects standalone cross-mode state loading. Legacy extra-state is
unchanged. C1-0 bare tensor state does not encode the mode: recovery of a
declared numerical model must use the full configuration and existing
numeric checkpoint contract, not claim a bare state dict proves its mode.

## Validation boundary

`current/tests/test_model_v3_attention_centering.py` has a planned 73
parameterized cases (actual collection and outcomes pending). It exercises:

- Nonzero analytical softmax/V gradients with exact dyadic oracles; a
  nonnormalized expression unit separately detects an incorrectly detached
  anchor. This algebra unit is not an alternative production population.
- First valid key versus padded key zero, nonzero constant values, a
  representable common component, and actual FP32 forward/backward only.
- Dropout/AMP/non-FP32/empty/all-masked/invalid population refusal and
  before-QKV refusal without RNG consumption.
- Six-layer 16-dimensional small C1-0/a/b models, all-layer mode propagation,
  finite nonzero gradients, parameter/state tensor/RNG equality, absent and
  explicit legacy bitwise compatibility, and checkpoint configuration binding.
- Empty `encode_atoms`, `encode_graph`, direct backbone and pretraining
  entrypoints; actual RuntimeDense construction and replacement refusal.

Run the unchanged `current/tests/test_model_v3_numeric_stability.py` alongside
these tests. Its independent original-attention expression and earlier legacy
head/geometry/mode cases protect the existing numeric mode/default path.
No unit result, source preparation or small-model oracle substitutes for
Root's unchanged actual 6x512 full 48-case / three-transform / two-seed matrix
with its original absolute 1e-5 threshold, nonzero terminals, saved failures,
and source/parameter/bank-state identity checks. There are no claimed test
passes or scientific results in this source-only snapshot. Root performs
normal checker, CPU QA, source freezing, preregistration, public readback and
GPU execution in that order, and retains failed cases without adoption.
