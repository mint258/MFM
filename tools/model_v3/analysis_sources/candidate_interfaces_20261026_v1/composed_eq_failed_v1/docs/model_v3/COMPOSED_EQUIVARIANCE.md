# Composed FP32 rigid-motion validation

Status: implementation frozen for Root's first CPU/GPU execution; **no PASS or
scientific architecture-selection claim**. Initial source base:
`e47d066e53f000d71c05bf1c772597f2a5c42c30`. Only four new helper/test/CLI/document
files are added. Old model implementations, defaults, tests, frozen experiments
and historical evidence are unchanged.

The earlier head-only absolute check and small C1 encoder relative check do
not establish a composed six-layer/512-dimensional output error bound. This
new check measures the actual production composition. It opens no native
dataset, data-line delivery, checkpoint or TRAIN/VAL record. Its registry is
explicitly a synthetic model-owned fixture, not a D-1/D-2 schema or D-5 subset.

## Frozen matrix and actual forward path

The matrix has **48 actual model cases**:

| Axis | Values |
| --- | --- |
| Distance bias | C1-0, C1-a, C1-b |
| Physical views | two: clean/both; three: clean/geom/topo |
| Scalar head/pooling | H1 fixed sum/mean; H1 learned; H2 fixed; H3 fixed |
| CPU weight seed | 20261026, 20261027 |

Every model is built with `build_source_s_architecture_model`: real six layers,
512 H0 dimensions, eight attention heads, FF multiplier two, 119 atom types,
zero dropout, the original Phase1/A4 heads and the actual measured tiled65536
C1-0 production builder. C1-a/b use their actual shared Gaussian encoders.
Attention is the current **global** implementation: cutoff=None. Its unused
radius8 is not silently enabled as a hard cutoff. This first matrix does not
claim coverage of an opt-in finite-attention-radius configuration.

Each case composes that encoder with `V3MultiViewModel` or `V3TwoViewModel` and
the real `V3HeadBank`. All S/D/P fields execute. A forward hook requires exactly
four full backbone passes: original plus the three declared transforms.
Packed sizes must be 88 atoms for two views or 132 atoms for three views, all
with output width512. The PD bank receives the clean H0 rows from that same
encoder pass. Original positive native bond predictions must be nonempty,
cover all three clean graphs and use only clean views.

The 13 measured terminals per transform are:

| Terminal | Rigid-motion law | Raw output units |
| --- | --- | --- |
| PD/p_extensive, PD/p_intensive | invariant | synthetic energy |
| PD/d_intensive, PD/d_atom, PD/p_pair | invariant | synthetic scalar |
| PD/d_binary | invariant | raw binary logit |
| PD/p_gradient | vector, v@R | synthetic energy/Angstrom |
| PD/p_dipole | vector, v@R | synthetic charge*Angstrom |
| PD/p_dipole_magnitude | invariant | synthetic charge*Angstrom |
| S/noise | displacement vector, v@R | Angstrom |
| S/coordinate | position, x@R+t | Angstrom |
| S/element_logits, S/clean_bond_logits | invariant | raw class logits |

The units describe the unnormalized head outputs in this synthetic contract.
There is no D-4 normalization, rescaling, division by sigma, loss averaging or
relative-error denominator. H2 has two scalar fields in P, exercising its
shared group projector. Fixed pooling includes both sum and mean. Only H1
adds the guide's learned sum/mean pooling comparison. Atom-vector, dipole and
pair heads execute for every H policy rather than only for one scalar form.

## Fixed geometry, physical views and transforms

The single packed base batch contains 3-atom water-like, 9-atom ethanol-like
and 32-atom decane-like synthetic geometries in Angstrom. The first two use
literal coordinates; the last has a fixed ten-carbon zigzag, two hydrogens per
carbon and two terminal hydrogens, centered once. All formulas and bonds are
in `fixture_batch`. These approximate fixtures are not optimized PM7 structures
or evidence of chemical stability. There is no geometry/seed search or retry.

The 32-atom graph deliberately exceeds the default Euclidean `cdist` MM size
threshold of25 in the original A4 neighbor construction, including its padded
batches. C1-a/b retain their existing explicit direct-distance path. This is
a test of their actual existing difference, not a silent change of either
distance implementation. See the primary
[PyTorch cdist documentation](https://docs.pytorch.org/docs/2.9/generated/torch.cdist.html).

The real view builder runs **once** per case with seed271828, epoch2, ordinals
700/701/702, default topology level0.3 and geometry level0.2 (additive
sigma0.1 Angstrom). The moved views are clones of those already generated
physical views. Both noisy/current `pos` and clean `target_pos` receive the
same rigid transformation. Elements, target elements, actual-change masks,
view IDs, source row maps, eligibility and native bond facts retain the exact
same byte digests. An explicit displacement push-forward check allows only
2e-6 Angstrom of input float32 rounding; it is separate from the terminal
1e-5 limit. No rotated view is regenerated from independent noise.

Using row-vector convention x@R+t, three transforms are fixed before running:

| Name | Axis before normalization | Angle (radians) | Translation (Angstrom) |
| --- | --- | --- | --- |
| general_rotation | (1,2,-1) | 0.713 | (0,0,0) |
| translation_only | (1,0,0) | 0 | (1.25,-0.75,2) |
| other_rotation_and_translation | (-2,1,3) | -1.137 | (-2,0.5,1.25) |

Rodrigues rotations are formed in float64 and checked for determinant+1 and
orthogonality within1e-12. Input positions are rounded to float32 before any
model call. The model, geometry, heads and all actual terminal outputs remain
float32 under explicitly disabled autocast, TF32 matmul and TF32 cuDNN, with
matmul precision `highest`. Float64 is used only for constructing the rigid
transform and measuring the mathematical expected output/error from the
actual FP32 tensors. It is not a double-precision encoder or head.

Before accepting a case, report the actual minimum distinct-atom distance,
maximum within-graph distance and distance to the A4 hard5-Angstrom boundary.
The declared domain requires distinct distances above0.05 Angstrom and a
minimum hard-boundary margin of1e-4 Angstrom. The actual original and moved
neighbor edge counts/digests must also match exactly. A domain or edge failure
is retained as a failure, not excluded or replaced by a new geometry. The
explicit scalar-pair head has an8-Angstrom smooth envelope and fixed native
pair indices; global attention has no hard8 boundary.

## Parameter and nonzero safeguards

Factory initialization uses each predeclared CPU seed. The existing A4
`normal(std=1e-3)` final matrix and all other default head initializers remain
unchanged. No head is zeroed, shrunk or reinitialized after seeing an error.
Two deterministic test-only assignments avoid degenerate candidate states:

- C1-b scale is `1+0.1*sin(0.37*ordered_pair_code)` and shift is
  `0.03*cos(0.11*ordered_pair_code)`, so it exercises element-dependent affine
  transforms instead of C1-a's common initial state.
- Every H1 learned mixer uses fixed logits `[-0.7,0.4]`, exercising a nonuniform
  sum/mean mixture.

Each case records a digest of **all named parameter bytes** plus parameter
count and per-vector/dipole/pooling/pair-module digests and squared norms.
There is no error-dependent weight selection. Every vector/noise/dipole/
magnitude/coordinate terminal must have a row norm above1e-8 both before and
after transformation; the count of such rows and maximum row norm are recorded.
An all-zero output cannot pass merely because it transforms to zero.

For every field and transform, preserve count, component width, finite check,
maximum absolute error, argmax row/component with actual/expected scalar,
nonzero diagnostics and pass/fail. The single acceptance condition is
`max(abs(actual-expected)) <= 1e-5`, with **rtol=0**. Padding is removed using
the actual node mask before vector/coordinate comparison. H0 maxabs is also
recorded as a latent diagnostic; it is not relabeled as a raw-unit terminal.

This is evidence for these finite declared fixtures, parameter states and
observed runtime. It is not a theorem for every real coordinate, weight or
hardware. Floating-point operations and batched kernels can differ across
platforms; disabling TF32 removes that additional reduced-mantissa option,
without claiming bitwise universal results. See the primary
[PyTorch numerical-accuracy notes](https://docs.pytorch.org/docs/2.7/notes/numerical_accuracy.html).

## Automated checks and Root execution interface

`current/tests/test_model_v3_composed_equivariance.py` is expected to collect
**57 cases: 48 complete model combinations plus nine control cases**. Controls
prove that missing/inverse vector rotation, wrong coordinate-versus-displacement
law, absolute error hidden by a large relative scale, all-zero vectors and
nonfinite outputs fail. They also check mask/noise preservation, complete
matrix coverage and request/source/tolerance/case drift rejection. Requests
can be prepared without CUDA initialization; that is not execution authority.

Root runs the CPU tests in an admitted CPU allocation, preserving basetemp:

```text
PYTHONPATH=current MODEL_V3_EQ_TEST_DEVICE=cpu MODEL_V3_EQ_TEST_THREADS=1 python -B -m pytest -q -p no:cacheprovider current/tests/test_model_v3_composed_equivariance.py --basetemp /external/new_eq_cpu_pytest
```

The full CLI additionally produces persistent per-case receipts. Prepare a
new external request with exact source-byte inventory and its raw SHA:

```text
python -B tools/model_v3/check_composed_equivariance.py prepare-request --device cpu --expected-node compute-0-12 --threads 1 --output /external/eq_cpu_request.json
python -B tools/model_v3/check_composed_equivariance.py prepare-request --device cuda:0 --expected-node <actual-GPU-node> --gpu-uuid <actual-full-UUID> --threads 1 --output /external/eq_gpu_request.json
```

The CPU node shown is an example, not a reservation or claim of availability.
Root chooses currently available resources, verifies at least16 requested CPUs,
all-user memory below85%, actual available memory/quota, and the owned GPU UUID
lock/protection for a GPU request. Root uses the corresponding actual Python/
Torch/CUDA environment and existing bounded supervisor. This tool never sets
CUDA visibility, submits Slurm, claims a GRES reservation or starts training.

Within the corresponding allocated node, use the machine-returned request SHA:

```text
python -B tools/model_v3/check_composed_equivariance.py run --request /external/eq_cpu_request.json --request-sha256 <raw-SHA> --output-root /external/new_eq_cpu_result
python -B tools/model_v3/check_composed_equivariance.py run --request /external/eq_gpu_request.json --request-sha256 <raw-SHA> --output-root /external/new_eq_gpu_result
```

The request binds all current package `.py` files, the fixed original S memory
builder, these four new files, `conftest.py` and the two old CUDA test files.
It includes the complete case list, protocol, node/device/UUID/thread policy
and32MiB whole-output budget. Root must create another request after any
source/merge drift; old receipts are not rewritten. Runtime requires the actual
Slurm node/job, at least16 CPUs and explicit CPU visibility or the exact actual
single CUDA UUID. This binding supplements Root's resource/identity supervision.

The GPU CLI runs all48 models on the actual CUDA device and then executes both
previously skipped nodes unchanged:

```text
current/tests/test_model_v3_transfer.py::test_custom_batch_pin_protocol_and_nonblocking_cuda_transfer
current/tests/test_model_v3_native_bond_transport.py::test_pinned_bond_arrays_and_nonblocking_cuda_transfer
```

It retains their raw stdout/stderr and JUnit XML and requires exactly two actual
PASS cases, with zero skips/failures/errors. A missing GPU is a failure, not a
skip. This GPU job contains real model forward operations, not a CPU-only
task assigned to a GPU node. The CPU CLI explicitly leaves those tests unrun;
it cannot claim their CUDA acceptance.

The CLI continues through the frozen48-case list even after a model failure,
preserving every completed field measurement and case exception externally.
`RESULT.json` distinguishes `PASS_DECLARED_DOMAIN` from `FAILED_PRESERVED`.
It checks source inventories before/after and writes `COMPLETE.json` only
when all required cases pass. Each case also preserves its original plus
three moved **actual FP32 terminal tensors** in an external compressed NPZ,
including partial outputs if an exception occurs after a forward. The recorded
R/t reconstructs expected outputs without rerunning a model. Exact keys,
shapes/dtypes, bytes and raw SHA accompany the NPZ. The declared per-case raw
numeric bound is320KiB (the actual frozen matrix's maximum is below that),
compressed-file bound512KiB; the forecast for all48 cases is about11MiB of raw
terminal values before compression. These are only public synthetic fixture
predictions, never native data or parameter weights, and are not put in Git.
No weights, checkpoint, native coordinates or member IDs are saved. Peak
output including pending NPZ/JSON, legacy test logs/XML/temp and failure
records is capped at32MiB. Root's actual
Slurm/supervisor termination is still needed to close the job.

If CPU or GPU fails, retain the exact case, initialized parameter digest,
geometry/view digest, field/argmax and source/runtime evidence. Investigate the
actual implementation (distance arithmetic, scalar amplification, reduction or
centering) before proposing a minimal new opt-in numeric configuration. Do not
relax1e-5, change fixtures/seeds to remove failures, change a cutoff secretly,
normalize away a raw-unit discrepancy or overwrite the failed version. Tensor
physical semantics remain pending authoritative data; this check selects no
tensor algorithm or architecture.
