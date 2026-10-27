# One encoder-geometry FP32 residual-expansion candidate

Status: SOURCE ONLY. No author Python/AST/tests/model/array/Git/SSH/Slurm execution. No candidate acceptance, capacity claim or new FP32 lower-bound claim. Root performs normal checker, complete CPU regression, exact source/method publication and original48 GPU validation before considering any conclusion.

## Fixed question and lineage

Base is f4652e940823141ac376eba5b6b1195f700fa692 (projection/centered/compensated FP32, not Core64). Actual4550 and bit-transparent4563 remain12 physical passes/36 failures,73 failed field-transform records. Actual4554 replayed all1872 terminal scalars with no mismatch/conditional unattainable-F32 component. Actual4564 analyzed all192 saved roles/1296stage384geometry144coordinate comparisons.

The same-pair geometry contrasts contain more than recorded-coordinate casting: for C1-0 general rotation, D=3.0517578125e-5 Angstrom-squared, A=+3.7315465476694953e-5, C=-6.797887380116663e-6, B=2.8421709430404007e-14. Shared-distance same-D-anchor has D=-1.9073486328125e-6 Angstrom, A=-1.8651179978235177e-6, C=-4.223063854169595e-8, B=3.552713678800501e-15. A compares an independent real-formula reference, so it is algorithm+precision, not isolated dtype or terminal causality. Original sum/moment heads can amplify inherited512-channel/32-atom changes; small H0 drift does not prove head-only error. This candidate changes only the observed encoder distance primitive.

## One explicit configuration

Set backbone.geometry_mode to residual_expansion_fp32_v1. Missing/explicit legacy keeps the old distance expressions and no new key is inserted into an old configuration.

This mode requires the unchanged six-layer512x8 compensated_fp32_v1, centered_fp32_v1 and blocked_k64_compensated_fp32_v1 base with zero dropout. Only DenseGeoSelfAttention's six raw dist-squared ports and SharedGaussianPairEncoder's single shared C1-a/b raw distance are replaced. All six layer mode declarations and the shared encoder must match the model configuration. Runtime/Native/replaced attention modules cannot silently omit the mode: encoder/backbone binding checks reject unsupported replacements. This does not claim that an external Native constructor was executed or ported.

QKV/output projections, RBF center/scale/shift/MLP parameters, LayerNorm, heads/pools, S geometry/epsilon, masks/edges, input rows, weights, initialization/RNG and512-dimensional H0 API are unchanged. No new parameters or buffers exist. Existing COMPENSATED semantics are not repurposed. The only added math identity is the explicit backbone configuration and, for C1 shared standalone state, a conditional geometry_mode extra-state field. C1-0 checkpoint recovery must use the bound full configuration/numeric_checkpoint_contract; bare tensor state alone never establishes a declared arithmetic mode.

## Fixed FP32 operations

1. Supply BOTH raw coordinate triples to the aligned primitive, before a rounded subtraction is discarded. Recover its high/low subtraction parts with the existing FP32 two-sum applied to left and -right.
2. Use per-triple exact power-of-two scaling (frexp/ldexp) to keep the splitter working range finite. These are FP32 mantissa tensors and integer exponents, not FP64 arithmetic or coordinate normalization of the model's input.
3. For scaled h+l, expand each component's square as h*h +2*h*l+l*l. Fixed4097 split-product recovery retains product residual terms. For each of exactly three components, collect six terms (product/residual for h*h,h*l,l*l); sum all18 in a fixed balanced Neumaier tree with high/low parts.
4. Squared output rounds/rescales the expansion once. Norm output uses an FP32 sqrt of the high part and one fixed residual correction using its expanded squared product, then rescales. Return only FP32. Zero distance uses the retained finite zero-gradient convention. There is no epsilon, cutoff, output multiplier, tunable tile or layer/seed selection.
5. Preserve the original65536 ordered-pair tile size. No E-by512 padding, shape sorting or logical-batch/view change.

All floating operands/results, forward and backward, are FP32. No double model, AMP, hidden cast, backend setter or fallback exists. Eager separate operations are required; compile/trace and unsupported devices/dtypes are typed rejections. Nonfinite/overflow or a nonzero difference flushed to zero is rejected rather than labelled successful. Error recovery still has ordinary finite-FP32 underflow/range limitations; this is not a universal error-free/correctly-rounded theorem or an all-real-input guarantee.

## Analytic training derivatives

The real squared function is sum((left-right)^2), with gradients +/-2*(left-right)*upstream. The real norm has gradients +/-(left-right)/norm*upstream away from zero. A custom autograd function uses THESE explicit formulas, not derivatives through split/recovery cancellation expressions. For create_graph, norm is reconnected through the same norm function so complete second cross derivatives/force-style objectives retain their mathematical dependence. At zero norm, the old zero subgradient/zero second convention is retained; the norm is not claimed differentiable there.

Backward arithmetic remains FP32 and therefore rounded, like the retained model. It does not assert exact real derivatives for arbitrary unrepresentable values. The mode is trainable; there is no eval-only exemption.

## Necessary engineering verification (all pending)

The added CPU module has63 manually planned cases; only actual pytest collection/results establish counts. It includes an independent exact raw-subtraction-tail squared oracle, F64 real-formula scaling references, independent input/right/coefficient first and complete second cross derivatives, finite zero-distance convention, noncontiguous ordered pairs spanning65536, empty gradient connections, dtype/AMP/invalid-domain/eager-only rejection and a real floating-port spy through both derivative orders. F64 is used only by test oracles, never candidate model arithmetic.

Three actual6x512 production-S builders exercise all six C1-0 tiled distance MLP inputs or shared C1a/b once, plus real parameter/position gradients. Tensor-state/RNG/default-bitwise and checkpoint/mode drift negative cases preserve old behavior and reject silent substitutions. There is no real CUDA or real D-schema qualification from CPU tests.

Root next runs the full existing CPU suite with this new file and the normal checker, preserving existing optional skips. Root then publishes the exact candidate/method before the original48-case GPU protocol: both original seeds, allC1/two-three views/four heads/three transforms,192 full forwards,52 terminals/case, original1492 parameter SHA, unchanged fixture/nonzero/domain/mask controls and absolute1e-5/rtol0. A bounded spy may verify512 top-level encoder-geometry calls and actual FP32 ports without changing results or adding model replays. New candidate terminal values intentionally differ from4550; only parameter/fixture/old-default controls demand old equality.

Eager residual recovery adds pointwise kernel launches and temporary scalar geometry expansions. Autograd retains both raw coordinate triples rather than only a rounded difference, so training memory can increase even though tiling is bounded. Existing resource/85percent guards remain authoritative; capacity and speed require later actual measurement, with no logical-batch reduction or OOM fallback.

No changed head or QKV method, local causal ranking, tolerance adjustment, output shrinkage, architecture selection or scientific adoption accompanies this source.
