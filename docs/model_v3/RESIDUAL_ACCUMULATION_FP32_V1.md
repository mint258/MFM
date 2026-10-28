# Fixed three-term residual accumulation in FP32

This isolated, unadopted candidate starts from FFN candidate local commit `e4b21193be60fcb396ab1d2d56c1cba6736078dd`. That candidate's complete GPU job 4524610 measured 14 passing and 34 failing cases, with 56 failing field/transform observations. The geometry predecessor had 15 passing and 33 failing cases and also 56 failing observations. These results do not identify residual addition as a cause. This is one fixed, falsifiable numerical intervention; there is no layer, seed, block-size, fixture, or output-scale selection.

## Exact scope

The sole new option is `backbone.residual_accumulation_mode='two_sum_three_term_fp32_v1'`. Absence means `legacy`, and the missing key is not inserted into old configurations. The option requires all six 512-dimensional, eight-head layers, FFN multiplier two, zero dropout, and the existing compensated FP32, centered attention, K64 attention/FFN projections, and residual-expansion geometry modes. Both C1-0 and C1-a/b use the same finalizer.

For each layer, retain the original program through the FFN:

```
a = attention(norm1(x), ...)
u = x + a                         # original rounded FP32 addition
b = ffn(norm2(u))                  # exactly once, using original u
```

Only the final `u + b` becomes a fixed three-input sum. Reuse the existing `_two_sum` routine, which selects a Neumaier correction by operand magnitude; it is not an unconditional FastTwoSum. Compute `(s1,e1)=_two_sum(x,a)`, `(s2,e2)=_two_sum(s1,b)`, then `s2+(e1+e2)` in FP32. No correction is injected into `u`, norm2, or the FFN. Mask multiplication retains its original place. Changed outputs can propagate to later layers, so preserving this local `u` construction does not assert unchanged downstream tensors.

All floating model operands, results, parameters, and H0 remain FP32. There is no FP64 model path, rescaling, quantization, changed epsilon, new parameter/buffer, or RNG call. Attention, geometry, projections, SiLU, LayerNorm, softmax, heads, pooling, and their existing implementations are otherwise unchanged. The old residual branch directly executes its original two additions. Existing Parameter objects and state-dict tensor keys are retained. The option is recorded through the complete model configuration/numeric checkpoint contract; SharedPair standalone extra state adds it only when enabled. Cache identity must continue to consume the complete configuration rather than treating equal tensor bytes as equal execution modes.

## Derivative and supported domain

The custom primitive represents the real linear function `x+a+b`, with VJP `(g,g,g)` for its three connected inputs. The nonlinear graph producing `b(u)` remains outside the primitive. There is no extra gradient for `u`, detachment, in-place update, or first-order-only decorator. This is the usual model derivative that ignores rounding, not a derivative of discrete floating-point rounding decisions.

Inputs must be same-shaped FP32 tensors on one CPU/CUDA device. Broadcasting, active autocast/AMP, TF32 or non-highest matmul policy, compiled/traced execution, replaced layers/FFNs, Native/performance builders, and unsupported layouts are rejected explicitly. The candidate does not silently fall back to legacy. Six-layer mode/configuration consistency is checked at the model/backbone boundary, including real C1 SharedPair modules.

Finite operands alone are insufficient: the rounded high sums, selected correction terms, combined tail, and final result must also be finite. Otherwise a typed error is raised, without repair or an alternate algorithm. Zero/empty inputs and smallest-normal operands have explicit controls. There is no general claim about subnormal/FTZ equivalence across backends, no global flush-mode change, and no correctly-rounded or monotonic-improvement claim. Improving a sum of the actual three operands does not prove that the nonlinear full-model real-arithmetic error decreases.

## Source tests and future validation

`current/tests/test_model_v3_residual_accumulation.py` contains 73 planned parameter-expanded CPU cases; only actual collection can establish that count. Independent controls include large cancellation, a noncontiguous dyadic reference, three-input mixed Hessian/HVP, and nonlinear branches. For `a=x^2`, `u=x+a`, `b=u^2`, `x=1/2`, the independent expectations are `y=21/16`, `dy/dx=5`, and `d2y/dx2=13`. Another two-variable branch checks a nonzero mixed Hessian. Tests also check original rounded-u identity, all six C1-0/a/b layer calls and connected parameter gradients, state restoration/Parameter identity, absent/explicit legacy bitwise behavior, RNG preservation, unsupported configurations, overflow, dtype/AMP/precision, and a mocked compilation-state rejection without invoking a compiler. Test-only high-precision reference arithmetic is outside the model.

Nothing has been executed as part of this source handoff. Root must run the ordinary checker and the complete CPU suite, including unchanged legacy/numeric/projection/geometry/FFN tests, before exact candidate publication and any GPU use. No historical CPU or GPU result qualifies these new bytes.

The subsequent GPU experiment must retain all original 48 cases, two fixed seeds, three transforms, 192 FP32 encoder forwards, 13 fields per transform, 52 saved terminals per case, original 1492 parameter identities, nonzero controls, physical units, domain checks, and absolute `atol=1e-5, rtol=0`. Every failure must remain durable. A narrow spy can wrap the actual `residual_accumulation(layer,x,a,b)` aliases in attention and SharedPair: call the original once, return the same result object, verify six sites per forward (1152 total), and record actual FP32 operands/results. Existing QKV/FFN/geometry counts remain separate. No new baseline or extra encoder forward is required. New outputs are intentionally not required to equal older terminal arrays. Original resource, UUID-lock, source-before/after, private-storage, and cleanup guards stay unchanged. Even a passing diagnostic does not by itself merge or adopt the candidate.
