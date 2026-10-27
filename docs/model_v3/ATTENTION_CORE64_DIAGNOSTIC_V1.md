# Uniform six-layer attention-core FP64 diagnostic

SOURCE_ONLY. Root created the isolated model-v3-attention-core64-diagnostic-20261027-v1 worktree from centered candidate cf8ce66d97cd518ebf279b40ee20294919bb95e1 / tree2389ab046ee23f2ba92fcb61179d853dfdee8357. No Python/AST, tests, Git, model, scientific payload, network or Slurm work has been executed by the source author.

This is explicitly a mixed-internal-precision diagnostic, not a formal model-freeze candidate. The guide's all-FP32 equivariance requirement at absolute1e-5 is unchanged. An FP32 parameter/I/O model containing an FP64 attention core cannot replace that requirement, including if every diagnostic case passes.

## One fixed change

The default remains legacy; the existing centered_fp32_v1 path remains. The sole new opt-in value is backbone.attention_aggregation_mode="centered_core64_diagnostic_v1". It applies uniformly to all six coupled DenseGeo/SharedPair attention layers. There is no per-layer selector, seed selector, precision grid, implicit fallback or new parameter/buffer.

- Original FP32 QKV, geometry, compensated norm/distance, C1-0 distance MLP or C1-a/b pair projection remain. Only actual Q32/K32 operands are losslessly promoted for FP64 QK and scale. The computed FP32 bias is promoted at logits addition; native masks, original finite -1e9 fill and radius predicates stay unchanged.
- Softmax inherits the actual FP64 logits dtype. The actual P64 is retained through centered AV: first-valid anchor64 + P64 @ (V32-promoted-anchor64). No renormalization, detached anchor, probability rounding or changed backend policy is introduced.
- Context is cast to FP32 once before the original FP32 output projection. DenseGeo's auxiliary public weights are cast to FP32 only when returned, after AV. SharedPair's output and packed H0 remain FP32; H0 shape/API/atom ordering are unchanged.
- Model parameters, persistent floating buffers, initialization, state tensor keys and RNG remain FP32/unchanged. The existing complete model config/numeric checkpoint contract and SharedPair extra_state bind the new explicit mode. A checkpoint declaring another arithmetic mode is not silently accepted.
- This mode is eval-only. The outer shared model, backbone and attention guards reject training; even outer-model train with an eval backbone refuses. Eval-mode gradient QA is permitted to verify differentiability, not to authorize optimization. Unsupported performance/RuntimeDense/Native/bf16/AMP, effective attention dropout, unknown or mixed layer implementations, non-FP32 externals, empty/all-masked graphs and nonfinite helper operands refuse. Exactly six uniform layers are required at the whole-backbone entry.

The five modified model files are v3_attention_numerics.py, attention.py, backbone.py, shared.py and v3_architecture.py. The original backbone UTF-8 BOM is preserved. Old heads, numeric-stability implementation, geometry functions, factory, config resolver, trainer, old tests and old worktrees are untouched.

## Evidence and limited inference

The3505 source-stable all48/192-forward local study retains21PASS/27FAIL physical cases. Derived3706 scalar postprocessing contains546 groups/4368 observations. A local attention-block algorithm+FP64 contrast can motivate this single placement test but cannot locate the contribution within QKV/QK/bias/softmax/AV/projection or prove whole-model causality. Local blocks overlap; their maxima/residuals cannot be added or causally ranked.

Old1641 evaluated local AV controls from captured p32/V32 or already-rounded logits32, without QK64 or injection into the complete model. The3505 independent reference promoted complete modules and mapped numeric/centered algorithms to legacy. Neither is this mixed-core forward. This diagnostic preserves all old records and does not assert a universal FP32 floor, necessary API change, physical-model improvement or adoption.

## Planned CPU checks, not executed

The new test file has36 planned parametrized cases: four analytic QK/softmax/anchor/value gradient controls; two real-module dtype/gradient traces; two external Q/K dtype refusals; ten invalid AV operand/population cases; two training/dropout/autocast module refusals; three complete six-layer configuration/state/checkpoint checks; three outer-training/mixed-layer refusals; five scope/precision/backend refusals; two performance-backend refusals; and three old-mode no-FP64/default-preservation checks.

Small algebra controls use explicitly nonzero, representable values. A nonunit-probability-mass primitive control exposes a detached-anchor gradient error; production always uses the unchanged actual softmax. Tests trace actual original functions once and do not replace returned tensors. Small six-layer mechanism fixtures have dim16 and are not the actual6x512 C4 population.

Root must run ordinary checker and the new36 plus existing73 centering tests,47 numeric-stability tests and appropriate existing model/architecture/checkpoint/default regression. All counts are planned until real collection/execution. New source-only tests do not reuse historical C0 as a new pass.

## Required future preregistration and GPU scope

After independent source review, Root CPU QA, normal checker and public exact-source registration, Root may run the diagnostic only:

1. Use the original actual6x512 complete48 population:3 C1 variants x2 view policies x4 head policies x2 weight seeds20261026/20261027. All six attention layers must report this same explicit mode, original compensated numeric mode and FP32 parameters/external tensors. These are fixture weight seeds, not independent pretraining seeds/seed SD.
2. Preserve all original fixtures, masks, noise, packed88/132 physical views, first-valid anchors, four frame order, proper rotations/translations, head initialization and weights. Match named-parameter rawSHA/names/classes/shapes/dtypes and fixture/input digests. No idealized coordinates, new sampling or hidden geometry changes.
3. Execute all48 x4=192 actual encoder forwards. Reuse the original frozen13-field/three-transform, original H0 and physical-unit comparisons with absolute1e-5/rtol0, finite and nonzero diagnostics. Save all52 terminal arrays and case JSON before assertions; run every case, preserve every failure, no fail-fast/xfail/filtering/seed or layer choice. Do not substitute a FP64 inverse-transform scoring convention.
4. Add only bounded inline tiny checks for actual QKV/bias/projection FP32, internal QK/logits/softmax/AV FP64 and returned weights/context/H0 FP32. These controls are separate from scientific cases. Do not import the old FP32-only AV interception as if it supported this mode.
5. Root retains actual UUID/public lock,16CPU/32GiB, RSS28GiB,1100s, whole/private2GiB and live85percent safeguards. No fallback to FP32, alternate backend or smaller population after OOM/timeout. Original old-source capacity/speed profiles do not qualify this changed source.

FP64 QKV temporaries scale with B*N*512; logits/probabilities with B*heads*N^2. Original FP32 operands, FP64 copies/workspace and casts can coexist, so peak need not be merely2x. The registered small B<=9,N<=32 fixture is not a real-training memory bound. Autograd/training capacity and FP64 throughput are unqualified; formal training is rejected here.

A fully passing diagnostic would only establish this mixed arithmetic result on the fixed numerical cohort. It is not the all-FP32 guide gate and does not freeze a model, architecture, recipe or source for production. All prior21/27 results and failed candidates remain. No subsequent intervention is automatically selected.
