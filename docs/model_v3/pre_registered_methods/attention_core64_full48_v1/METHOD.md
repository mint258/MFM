# Core64 complete48 diagnostic: preregistered method v1

This diagnostic uses the already published model branch
model-v3-attention-core64-diagnostic-20261027-v1
(local 0f1cfb725dfe97a183ab5173fc5e4d0347228e41,
public b88f07d1628e53d7f78e1232397fab0568ffd823,
exact tree b94944d57a3751ccde9d89bbf4a8a747c1d69539).
The eight archived source leaves are byte-exact copies of the server's frozen
attention_core64_diagnostic_e2e_v1_source science and metadata leaves.
Original paths and raw source inventories remain in the independent run folder.

## Question and immutable comparison

Test whether FP64 QK/softmax and centered value aggregation, with FP32 QKV,
parameters, public context and outputs, reduce the original complete-encoder
equivariance error. This is mixed internal arithmetic, not the guide's formal
all-FP32 acceptance. formal_FP32_gate_satisfied and model_freeze_candidate remain
false for every possible outcome, including 48/48 diagnostic passes.

Use the original 6x512 model, original initialized parameter identities, fixture,
physical units and nonzero/finite checks. Preserve all 3 C1 variants x 2 view
variants x 4 heads x 2 weight seeds = 48 cases, four frames per case = 192
encoder forwards, 13 fields and three transforms. Original 52 terminal arrays
per case and the absolute 1e-5, rtol=0 criterion remain. Run every case and
persist each terminal array/JSON before the original assertions; no case
filter, early physics stop, new full-FP64 encoder baseline or threshold change.

Only the declared centered_core64_diagnostic_v1 aggregation mode changes.
All six layers use the same mode. The real helper tiny controls observe
operand/return dtypes and analytic gradients, call the original helper once,
restore temporary spies in finally, and do not instrument the full48 run.
They do not claim hardware accumulator introspection or causal attribution.

## Source and resource gates

The related CPU job4524049 passed156 tests. The exact model subsequently passed
the full115-module CPU job4524207:2745 passed,3 optional skips,0 failures/errors.
Both actual Root closures and the exact-tree publication are verified by the
archived metadata module. CPU skips do not authorize CUDA or actual D3 data.

Use the existing node21/physical c35 GPU workflow, 16CPU/32GiB, RSS28GiB,
1100-second guard, 20-minute Slurm ceiling, whole output2GiB and private2GiB,
existing process-identity/private-storage helpers and one inherited public UUID
lock. Before the sole explicit Root submission, require fresh real allocation,
all-user CPU/memory/quota and empty selected-GPU admission. No foreign process
is signalled. Preserve all partial/failed artifacts.

The current source-bound request/pins are DRAFT metadata, not admission.
Root must bind this published source receipt into fresh final runtime metadata,
then obtain fresh resource admission. Original model/source/evidence and failed
CPU4186 remain unchanged. No GPU execution result is claimed in this method.
