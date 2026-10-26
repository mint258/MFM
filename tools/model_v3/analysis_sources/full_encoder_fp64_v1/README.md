# Full encoder actual-input FP64 reference v1 — analysis only

This source-only package follows Root's latest fixed scope, replacing the larger
counterfactual idea in the earlier feasibility note. No ideal positions, polar/SVD,
new rotations, new weights or production dtype change are implemented.

One original-guard GPU job performs192 original full six-layer/512 forwards first.
Its actual bank H0/pos/batch must match all48 actual1492 cases/4roles bitwise; all old
named-parameter SHA and source/config/fixture identities must match. Stage hooks
retain references only; copying occurs after the complete original forward returns.
All192 controls must pass before any scientific FP64 reference forward. Failure
keeps the new evidence and stops, never passing by tolerance or dropping cases.
Old1492,1435,10physical passes/38failures and all original sources remain unchanged.

1492 did NOT save a separate full-encoder buffer hash or encoder checkpoint. Bank
state is fully captured, but encoder proof uses frozen source, old complete named
parameter SHA, original full-view input digests and the192 actual H0 bitwise gate.
The current replayed encoder→strict independent copy closes all state keys and
buffers, then every floating FP32 state tensor promotes losslessly to FP64 with
per-tensor cast-back rawSHA. This is not a historical1492 encoder-buffer hash claim.

Only the independent copy gets explicit legacy numeric attributes, dtype-preserving
packing forward and Gaussian forward. apply_numeric_mode(legacy) is a no-op in the
old source, so existing attributes on the copy are explicitly reset and verified.
Original parameters/config/checkpoint objects are not rewritten. All previous
original extra-state is compared before this declared analysis mapping. The original
six layers/MLP/attention/LayerNorm and parameter topology are retained. No Flash,
performance, new initializer or new centering formula is selected. Forward overrides
and capture hooks are removed from the analysis copy in finally.

The same actual FP32 view input values are promoted; source positions are not
recomputed at higher precision. F64 does192 canonical full-view encoder calls and
extracts the same clean44x512 after final packed H0. Both all88/132 physical rows
and clean44 are reported for embedding,6layers,out_norm and packed H0. Actual
per-layer masks are captured and checked against batch layout. Real attention
use_radius_mask/cutoff policy is recorded from objects, not assumed from radius8.

The original1503 functional64 function body is imported unchanged from its bound
public module. Original PD bank state remains FP32; the function casts parameters
inside arithmetic and is device-generic. It receives the F64 encoder H0 and actual
1492 positions/batch and computes only p_extensive,p_dipole,p_dipole_magnitude.
The original R is placed on the correct device as F64 with its orthogonality residual
recorded. This covers neither the5A S geometry head nor8A pair envelope in F64.

Counts are separate:384 full512 encoder returns=192FP32+192F64;192 scientific
functional64 bank calls=576 field outputs. Inline post-replay controls perform12 tiny
dim4/one-layer encoder forwards, plus4 CPU and4 CUDA tiny functional64 bank calls.
These are fixed formula/device oracles, not new scientific cases/seeds. Tiny legacy
F32 parity is bitwise; F64 same-input repeat is bitwise; unchanged head CPU/CUDA
parity maxabs<=1e-10. There is no new CPU parent or2639 regression repeat requested.

Reference H0, stage drift, F32-minus-F64 drift and final3field D are analysis. H0 is
scalar/invariant (no3D R on512 channels). GPU terminal D uses F64 L, so it cannot
replace the original FP32 C4 acceptance. F64 remaining drift can include FP32
coordinate quantization, originalR nonorthogonality and finite reference arithmetic;
it is not a proved coordinate-only cause or FP32 lower bound. Signed terms are
compared at the same component; unrelated maxima are never added. F64 finite/nonzero
outputs and typed H0 NPZ allow_pickleFalse roundtrips are checked.

Resource/admission is the already exercisedv2 capture launcher algorithm, unchanged
apart from this source/child/output naming. It imports the pinned d3cba6 original
resource helper, uses the same Root fresh receipt/frame and compute allocation/
fd9/full c35 UUID checks, then the original supervisor. No extra monitor/queue.
Node21/c35,16CPU/32GiB/RSS28GiB/1100s/20min,whole/private2GiB remain. Old87.7MB input
is read-only and checked under128MiB; NPZ/weights are not copied into this package.
Single-case model copies are released; all48 model states are never retained or
persisted. Only necessary reference H0 (34,603,008 numeric bytes), statistics and
SHA/mapping metadata are saved. Actual time is unknown; censor/failure never expands
limits or adopts the original model.

Root must AST/source-audit, normal-check and publicly preregister before the single
actual submission. No Python, tests, models, SSH or Slurm were run by this package's
author. ROOT_GPU_INVOCATIONS_v1.json gives exact audit/submit argv after freeze.
