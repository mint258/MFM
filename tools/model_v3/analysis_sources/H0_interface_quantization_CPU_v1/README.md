# Fixed historical-H64 interface quantization — CPU diagnostic DRAFT

This is one counterfactual measurement on already saved historical1561 values. It does not run or choose an encoder, change FP32/512 H0, or create a production candidate. Current1838 captured H0 is not substituted for historical1561 H64, and historical1561 H64 is not described as current all-six-layer centered internal H0. Original1561/1492/1838/1842 data, sources, thresholds and closures stay unchanged.

The complete original48 cases, seeds, head policies, two/three views, four roles, three transforms and three P fields are retained. Per arm there are192 CPU head calls and432 field/transform observations, zero encoder forwards and zero GPU work. The three routes share the exact original FP32 head bank state and actual FP32 geometry/index values:

* A: historical1561 H64 directly to frozen1503 `functional64`.
* B: that same H64 cast to FP32 once, then losslessly promoted to FP64, through the same `functional64`.
* C: the same once-rounded FP32 tensor through the original FP32 `V3HeadBank` on CPU.

No head formula, pooling, dipole or transform math is rewritten. The original1503 tiny controls run inline. No new suite, dispatcher, monitor, CPU QA parent, layer selection or seed selection is introduced. The actual CPU environment and imported project source identities are recorded.

## Comparability gates

1561 first replayed all192 original1492 FP32 H0/position/batch roles before its different numerical algorithm produced H64. Its functional64 head used each original1492 role's actual FP32 bank position/batch (source `analyze_encoder_precision_v1.py:285–287`). The new input contract connects those saved values to actual1838 only through full case/seed, full original named-parameter SHA, typed bank state keys/extras/identity/tensor headers, registry/forms/constructor, fixture/view/transform and per-role position/batch/pair typed-header equality. At actual execution the1838 typed arrays are decoded with the existing strict codec and actual position/batch bytes are independently hashed against1492 headers. Original1492 NPZ need not be opened. All48 must agree.

A is checked against all432 saved1561 scalar controls: maximum absolute D, signed D at the saved reference argmax, and signed D at the fixed old GPU argmax. Predeclared diagnostic absolute bound is1e-10. The historical head calculations ran on CUDA and this replay runs on CPU; there is no bitwise backend-equivalence assertion. The old full functional-head output arrays were not saved, so these are scalar controls, not full terminal replay. Every A failure is retained; the job still completes all48 numerical observations, then returns nonzero/HOLD and does not admit attribution. Corrupt input/state or resource failure is a separate execution failure.

Every arm retains complete signed D and paired differences B−A and C−B, along with same-component tuples at each arm's own argmax. Physical threshold reporting remains absolute1e-5 and relative0, without changing the original acceptance rule. A→B isolates one final quantization on these fixed historical values. It cannot prove a universal FP32 floor or that an API change is necessary. B→C includes head dtype, implementation and CPU backend effects; it is not a production CUDA comparison. No result adopts FP64 production, a new representation or this candidate.

## Finite input and output scope

The selected source-only stat review found48 historical H64 NPZ=34,653,984 bytes;48 current1838 packed bank NPZ=74,718,432;144 selected case JSON=13,285,890. Their subtotal is122,658,306, leaving11,559,422 within128MiB for all additional actually read control/source/new metadata. Root independently recorded this in `Root_H64_counterfactual_selected_input_stat_actual_v1.json`. These numbers do not assert the final combined scope fits. Metadata assembly and the actual CPU job count physical unique identities for every payload and all metadata/source/inputs/pins they actually read; any total above134,217,728 fails with no waiver. The source facade's fixed metadata import is bound in the same source graph.

Unused1492 NPZ,1838/1776 terminal NPZ, encoder weights and SDKs are excluded because this measurement never reads them. This is an explicit selected-input scope, not a claim that the complete1838 output directory fits together with the historical reference. Metadata prepare never opens or hashes NPZ payloads. Actual CPU execution verifies each raw payload SHA and all H64 value hashes/shapes/dtypes with `allow_pickle=False`.

The copied old CPU guard and wrapper retain16CPU16GiB, RSS12GiB,120s child /3min allocation and the original2GiB output/private guard. No budget is enlarged. Input/case result JSON is bounded; each case is saved separately, plus compact result and CSV. Actual times, RSS and total output remain unmeasured. The earlier32s1842 result is a precedent for a related workload, not a timing guarantee for these new routes.

## Root-only next steps

This draft was written with source/closed-JSON reads and NPZ stat calls only. No Python/AST, model, NPZ read, network, SDK, submission or test has been executed by the author. `DRAFT_SOURCE_INVENTORY.json` describes bytes, not QA. Root/SA4 review and normal source/checker/preregistration procedures precede actual execution. Root may create the CPU bindings after review/preregistration:

```bash
B=/share/home/zixiao/descriptor_analysis
S=$B/runs/model_v3_20261026/H0_interface_quantization_CPU_v1_source
PY=$B/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
"$PY" -B "$S/prepare_metadata.py" --assemble
```

This fresh-only command emits `inputs_v1.json` and `source_pins_v1.json`; it performs no model/array work or submission. Root then uses the established CPU-only admission/helper to submit `run_counterfactual_CPU_v1.sbatch`, setting `MODEL_V3_EXPECTED_NODE`, `MODEL_V3_H0_QUANT_INPUTS_SHA`, and `MODEL_V3_H0_QUANT_PINS_SHA` from the actual new files. No old resource snapshot is borrowed and no automatic retry is added. Actual outputs use the new `O/H0_interface_quantization_CPU_v1_JOB` basename. Parent C0/source/guard/result closure is future work, never prefilled here.