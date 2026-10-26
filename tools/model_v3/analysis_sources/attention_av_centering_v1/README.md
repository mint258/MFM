# Full48 local attention AV centering diagnostic

Source-only draft until Root freezes, reviews/checks and publishes this protocol.
The author has not run Python, a model, an SDK reader, SSH or Slurm. Production,
numeric candidate, original1492 capture and1561 evidence are unchanged.

The experiment tests a local numerical hypothesis; it never runs a centered model,
never changes the six-layer/512 H0 API, and cannot accept an architecture, Native-S,
bf16, training dropout, a recipe or the original48 FP32 physics gate.

## One bounded experiment

The original complete48 case order, parameter seeds, four forwards/case and actual
1492 capture request are retained byte-for-byte. Only original coupled
DenseGeoSelfAttention and SharedPairAttention are supported. Actual global/eval,
FP32, dropout-disabled paths are required. RuntimeDenseAttention is refused.

1. Same-GPU tiny controls precede the scientific cases: both real attention
   classes each do one original forward, one AV replay, one centered control and
   separate FP64 Rraw/Rnorm/Cexact. A third returned tiny forward observes the
   original all-masked finite--1e9 behavior then refuses it. An effective-dropout
   negative control is refused by the pre-hook before its attention executes.
   Counts are separate; fixed tiny initialization runs in a CPU RNG fork.
2. Run all48 x4 original complete model forwards. Scoped module hooks plus a
   TorchFunctionMode delegate each original operation once, keep actual
   softmax-input logits, post-dropout p, V and pre-projection AV references, and
   return the original outputs. There is no global torch-function monkeypatch.
   All copies, hashes and finite/mask checks occur after the entire model forward
   has returned. Compare actual bank H0/pos/batch bits against1492; preserve full
   physical input88/132 and clean44 population. Gate all192 before scientific AV
   controls. Original measured physics failures remain failures.
3. Cache only exact CPU contiguous values plus original dtype, shape, strides,
   storage offset and CUDA device metadata. The predeclared payload cap is2GiB;
   expected payload is about1.70GB for p/V/logits/output, plus small masks. No
   operands/weights are written to disk. The cache is not claimed to preserve a
   GPU allocation address. One operation at a time is restored into a bounded
   GPU storage/view with the original strides and storage offset, then byte/hash
   checked. Recreated unreferenced storage holes are never read or serialized.
4. For every one of1152 AVs, replay the original matmul exactly once under the
   original flags and require output bitwise equality. A mismatch is
   OP_REPLAY_MISMATCH, not evidence about centering or the old network.
5. For every admitted AV perform exactly one FP32 control
   C32 = v0 + p32 @ (V32-v0), with v0 from the first valid native key of that graph,
   per head. No layer/case/anchor selection by error, new weight scaling,
   normalization, mask change, epsilon or safe-softmax is allowed. Center every
   original V key including padded keys; only analysis statistics exclude padded
   queries, whose original output is masked later by the unchanged model.

Two different FP64 references are required:

- Rraw = p32.double() @ V32.double(), the stored-operand product.
- Rnorm = softmax(masked_logits32.double()) @ V32.double(), normalized from the
  same stored masked logits, not a rerun of upstream QK or a full FP64 encoder.

Independently compute Cexact64 = v0_64 + p32_64 @ (V32_64-v0_64), then compare
Cexact64-Rraw to (1-sum(p32_64))*v0_64. The former is not defined from the latter.
The conservative128*eps64*scale closure bound is a floating arithmetic audit,
not a change to the original1e-5 physics tolerance. C32 may be farther from Rraw
yet closer to Rnorm; those findings must not be conflated.

The v0 formula relies on real softmax row sum1. Active training dropout violates
that assumption. A general weighted identity would need sum(w)*v0; it is a
different hypothesis, is not implemented here, and would need its original RNG
mask/gradient semantics preserved. Nonempty global graphs are checked. Empty
graphs/all-masked rows are refused, not repaired or silently dropped. Padding,
dropout mode and actual arithmetic flags are recorded.

## Evidence and outputs

Original1492 H0 is the comparison authority. Original1435 H0 is not reconstructed.
Actual1561 all-encoder FP64 results are prior side evidence only; no192 FP64
encoder forwards are repeated or claimed by this experiment. Current encoder
and bank state/source checks reuse1561's helpers and original builders.

Outputs contain192 role replay records,48 original measurement metadata files,
the global replay gate,48 AV case reports (24 operations each), one complete
AV_metrics.csv, tiny controls, result/closure and source before/after snapshots.
Every metric summarizes the complete valid population; each AV also records all
signed comparisons at the same original-minus-Rnorm argmax component. No sampled
cases, activations, raw operands, weights or NPZ output. Scalar1e-5 counts are
descriptive local error counts; no centered-model physics PASS is produced.

The whole output remains2GiB including external Root/stdio/control files; private
storage independently remains2GiB. The inherited child ceiling is outer-96MiB
and is never raised. Compact diagnostic output has a further128MiB bound. The
CPU cache2GiB payload cap is not a disk allowance or an exact RSS peak. Root
retains16CPU/32GiB, RSS28GiB, original1100s supervisor,20min allocation, c35 on
node21, fd9 shared UUID lock, quota/headroom, fresh max(queue,AllocMem)85% and
actual MemAvailable/NVML guards. No new monitor, dispatcher or automatic retry.

Scientific forward counts:192 original FP32, zero FP64 encoder. Scientific local
counts:1152 original AV replays,1152 centered controls,1152 each Rraw/Rnorm/Cexact.
Tiny controls add3 returned attention forwards,2 each local replay/control/oracle,
and one active-dropout pre-hook rejection. All actual counts must match.

## Root entry points after actual checker/publication

Use the existing fixed GPU guard and the new independent output/attempt names.
First AST/source review and ordinary repository checker; Root must publish these
new rules/sources before submission. No prepublication scientific use is allowed.
Audit only imports stdlib metadata helpers, not torch or a model.

```bash
P=/share/home/zixiao/descriptor_analysis
S=$P/runs/model_v3_20261026/attention_av_centering_v1_source
PY=$P/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
PIN=$(sha256sum "$S/source_pins_v1.json" | cut -d' ' -f1)
"$PY" -B "$S/launch_av_diagnostic_GPU_v1.py" audit --source-pins-sha "$PIN"
"$PY" -B "$S/launch_av_diagnostic_GPU_v1.py" submit --source-pins-sha "$PIN" \
  --submission-receipt "$P/runs/model_v3_20261025/attention_AV_centering_GPU_v1_attempt1.json"
```

The source author has not executed these commands. Root chooses whether the
diagnostic falsifies the hypothesis; no result is promised and no production
centered path is implemented.
