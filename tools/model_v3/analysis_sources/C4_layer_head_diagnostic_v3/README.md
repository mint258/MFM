# Revision v3: original weight validation retains inference mode

Actual4521181 completed all48 unhooked exact-baseline replays, then failed at the first hooked weight check: measure_case creates inference parameters, and the original torch.isfinite checksum was called after its inference context had exited. No complete attribution or new model acceptance was obtained.

This revision runs the exact original equation.weight_summary inside torch.inference_mode at both existing hard gates. It changes neither that checksum nor any model, forward, terminal, parameter, data, numerical tolerance, bitwise control, case membership, budget or shadow formula. Ordinary and inference-created tiny real-source parameter checks, ambient grad-mode restoration, unchanged parameter flags/bytes and a modified-inference-weight negative add3 CPU cases. Expected27 remains pending actual Root QA. Oldv2, its24-case QA, publicf96 registration and failed4521181 artifacts are preserved.

The following sections describe the inherited design/history; the v3 context repair supersedes the earlier byte-identical instrument statement. A new publication must precede any new full diagnostic.

# C4 read-only layer/head attribution implementation v1

Prepared, not executed. Root approved the fixed PLAN5f7c802... and draft7139b0...
in the separate eq_layer_head_diagnostic_v1 directory. Its original3 files are
unchanged. This new source directory implements that design, not a model fix,
architecture choice or new numerical acceptance rule. No Python/test/SSH/Slurm
or scientific measurement has run during source preparation.

## Exact controls and interpretation

The runner first runs all48 original unhooked cases, then all48 instrumented
cases:384 complete encoder forwards with original6x512, weights, views/masks/
noise, seed/geometry, proper3 rigid transforms and raw-unit abs1e-5/rtol0.
Every full result must replay the original baseline JSON measurements/domain/
edges and weight/input/config identities exactly. Every one of52 FP32 terminal
arrays per case must be bitwise equal between two newly generated control and
hooked archives. Old NPZs are never read. A mismatch stops attribution, preserves
partial output and writes no completion marker.

All hooks copy tensors and return None. A temporary _pool wrapper calls only
the exact original function, then captures input/output. Factory/pool identities
restore and hooks remove in finally, including failure paths. Actual parameter
digests must match before/after hooks and before/after head/shadow replay.
No production forward, pool, parameters, cutoff or fixture is rewritten.

Trace stages include all6 norm1/attention/norm2/FFN/layer outputs, initial atom
embedding, pre/post final norm, C1-0 literal squared-distance inputs/bias outputs,
C1-a/b shared pair features/distances and per-layer projections, actual PD
pool/input/mixer/projector/linear/activation, clean H0 and own charge heads.
Summaries compare only valid physical graph rows/pairs. Position/centroid pool
traces use the coordinate law; other scalar features use invariance. Input
coordinate casting/noise transport and exact-distance-on-actual-input reference
errors are split from FP32 distance arithmetic residuals.

Each target head runs all4 original same-weight full-batch FP32 crosses H0/P0,
H1/P0,H0/P1,H1/P1.00 and11 must bitwise match actual full-forward outputs.
Vector row convention is x@R. Signed full small cross values and H0/position/
interaction decomposition are retained. Magnitude uses its own independent
charge MLP and reconstructed own vector, not the other dipole's charges.
Functional FP64 same-parameter shadows and H1/dipole algebra checks are solely
numerical references. Original model parameters remain FP32 and unchanged.
A completed diagnostic C0 does not mean any original1e-5 case passed; original
raw failures/pass count and is_FP32_acceptance_evidence=false remain explicit.

## Source and result boundaries

Execution_protocol_v1.json fixes384 forwards, all48 membership, controls,
functional-shadow scope and budgets. Source preparation stays independent of
old math/defaults. The new request binds the original full source inventory,
immutable prior attribution helper, its complete baseline/control refs, all3
reviewed design files and this implementation/test/README/protocol. Request
rawSHA and complete runtime source hashes revalidate before/after. Prior1066
aggregate rawSHA6b24cb45... is bound through the unchanged design draft.

Do not freeze only the unit test's obvious imports: Root should snapshot the
complete source_files(support,equation,repository) map and original execution
inventory, including conftest, both legacyCUDA test sources and s_model_memory,
plus all pinned control metadata. All are hashed; the CPU runner does not
execute those two CUDA tests. No labels, native geometry or checkpoints enter.

## Root CPU verification —24 expected cases, pending

Tests use analytic scalar/vector4cross oracles, wrong row-rotation detection,
same-weight dense FP64 MLP/H1/H2/H3 pooling and dipole references, independent
magnitude charge parameters, dtype/unknown-module rejection, unchanged hooks,
planted layer drift,52-terminal bitwise mismatch (even one ULP), incomplete48
membership, gzip budget/overwrite and factory/pool/hook restoration on failure.
The two real-source head tests use only3 synthetic atoms and2-dimensional head
inputs; they are not an execution of any full48 scientific case or acceptance
measurement. No test skips actual required evidence.

```bash
B=/share/home/zixiao/descriptor_analysis
SRC=$B/runs/model_v3_20261026/eq_layer_head_diagnostic_v2_source
EQ=$B/MFM_model_v3_composed_equivariance
PY=$B/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' PYTHONPATH="$EQ/current" \
 "$PY" -B -m pytest -q -p no:cacheprovider "$SRC/test_layer_head_attribution.py" \
 --basetemp "$FRESH_SHARED_UNIT_ROOT"
```

Root runs this on an available siteCPU node with16CPUs, bounded guard, exact
source before/after snapshots and actual terminal C0. That closure is pending.

## Root prepare/public binding/run interface

After source tests, Root alone freezes the metadata request on a siteCPU node.
Preparation imports frozen source and hashes metadata but performs no full model
forwards. Root must publish/bind the exact implementation/protocol/source tree
before the actual diagnostic. The source preparer has not done that work.

```bash
"$PY" -B "$SRC/instrument_layer_heads.py" prepare-request --eq-repository "$EQ" \
 --aggregate "$B/runs/model_v3_20261026/eq_diagnostic_v1/baseline_aggregate.json" \
 --expected-node "$AVAILABLE_CPU_NODE" --output "$FRESH_REQUEST_JSON"
"$PY" -B "$SRC/instrument_layer_heads.py" run --request "$FRESH_REQUEST_JSON" \
 --request-sha256 "$RAW_REQUEST_SHA256" --output-root "$FRESH_EXTERNAL_OUTPUT"
```

Actual run requires owned CPU Slurm job, siteCPU2/8-19, at least16CPUs and CUDA
hidden. Use the original5090venv CPU runtime as baseline1006 to retain exact
backend replay; no GPU node is used. Proposed16GiB allocation/12GiB RSS,
Torch+BLAS threads1,600s child/660s outer,64MiB child total and existing2GiB
outer/private caps remain. Root retains its quota/global-memory guard.

Only one hooked case's intermediate tensors stay in memory. Disk has two new
terminal NPZ sets, per-case JSON and deterministic gzip trace JSON. Per trace
rawJSON<=8MiB/compressed<=512KiB, total child<=64MiB; no deletion, truncation,
case exclusion or cap expansion. Source/native weights are not archived.
Failure outputs preserve FAILED.json and partial archives; result remains
incomplete. Successful close requires both48 matrices, all bitwise controls,
source stability and all trace/head gates. COMPLETE.json additionally binds
DIAGNOSTIC_RESULT.json; original raw1e-5 failures are still present.

## Independent test-dtype repair, preserved1121 failure

This v2 package retains the production instrument_layer_heads.py and execution
protocol byte-for-byte from v1 (source6f15397d.../protocolca9cc753...). The separate
reviewed design3 files are unchanged. Actual1121 collected23,22PASS/1FAIL with
stable sources. Its vector oracle reconstructed FP64 JSON values through a
new default-FP32 tensor before calling double, introducing quantization in the
test itself. Original source four_way values were FP64 and correct.

Only the test reconstruction now specifies dtype=torch.float64 immediately.
All4 vector components of the decomposition (total/H0/coordinate/interaction)
are checked with the same original atol1e-8/rtol0, and a dedicated JSON FP64
roundtrip positive/explicit-FP32-loss negative is added. Production formulas,
scientific1e-5/rtol0, all existing tolerances, data, fixtures and parameters stay.
Expected24 CPU cases are pending Root execution. Original v1/1121 log and
failure evidence are preserved. No actual diagnostic has been run here.
