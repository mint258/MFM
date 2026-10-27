# Saved4550 terminals: one CPU-only replay and representability analysis

DRAFT SOURCE ONLY, not executed by author. Root alone reviews, checks source/syntax and submits one actual16CPU job. No new encoder/head baseline,weight load,native data,SDK,monitor,dispatcher or separate QA parent. Actual4550 remains FAILED1/53s,12P36F,192FP32 forward and2304helper calls. This analysis never changes that verdict.

## Exact scientific question

For every one of48 cases,all13fields and all3 recorded transforms (1872 records), replay the original transform_expected/field_measurement logic against its52 saved actual F32 terminal matrices. Then compute the smallest absolute distance of each original F64 expected component to its nearest representable F32 value, and actual-to-nearest F32 ULP distance/scale.

The crucial original implementation already uses CPU F64 for expected and comparison: original saved F32 -> CPU.double(), invariant identity or @ recordedR64 followed by+t64 for coordinate, then double subtraction/abs. It does not round expected back to F32. We directly reuse those functions via the frozen original projection_adapter.load_equation() and original fixture0c49debe901ee5db79a71fcbc8541d426231c5090eb9740b84649e867d8df0e8. The old numerical_policy context is NOT called. No build_composition,encoder,bank,forward or functional-head operation is called. Importing class definitions is not model construction.

At each component, nearestF32 gap is a conditional representability bound **only for this saved original terminal and this exact expected transform**. Nearest conversion is checked against adjacent lattice neighbors. gap>1e-5 means no F32 transformed terminal can meet the existing absolute criterion at that component under those fixed conditions. It does not establish a universal FP32 floor,necessity of FP64/API changes,or an encoder/head cause. gap<=1e-5 also does not prove the model can produce the required value or satisfy nonzero/edge/domain criteria. No rescaling,fixture/seed/parameter/tolerance change or population selection occurs.

## Inputs and lineage

inputs.json binds the actual RESULT and all48 original caseJSON/NPZ refs. Metadata-only preparation checked all48 JSON raw hashes and physical NPZ stat sizes without reading NPZ bodies. It preserved12P36F and73 failed field-transform records. Archives total10174750B,caseJSON2685387B. Original per-case archive<=512KiB,numeric<=320KiB,and all selected input/source/metadata<=128MiB remain strict. The worker streams SHA before/after actual NPZ reading,requires exact52keys,F32/2D/shape/finite/known ZIP members and no pickle,then frees one case before the next. Original output arrays already select physical native masks; no padded activation population is substituted.

Original input geometry push uses F64 transform then F32 cast. All144 saved vector-edge comparisons are unchanged; the recorded noise-push residual maximum4.6147705909382886e-7Angstrom is reused as metadata only. It is not a terminal error/Lipschitz bound. Saved endpoints alone cannot decompose geometry-input rounding versus encoder/head propagation. Old1838H0 or1561F64encoder is not claimed to be this projection candidate's hidden state and is not loaded.

The actual4550 execution lineage is localf4652e940823141ac376eba5b6b1195f700fa692/publicb2c4c6772d751ba08ac611cbe563ee2e1b40e709/tree411ebc59652f8aecf2d06938842aeca4782a184d. Only source/class definitions from that package are imported; no model/parameters are instantiated. Original helper and adapter rawrefs,standard I/O from counterfactual_common,oldCPU supervisor and its three existing private/process helpers are in dependencies.json. The old functional-H0 consumers are NOT executed.

## Full output and controls

The original case/field/count/components/law/unit,finite/nonzero,pass boolean and tolerance metadata must match the original helper replay. Original maxabs/norm scalars and original saved argmax actual/expected values must replay within predeclared1e-10 diagnostic scalar bound (not a changed1e-5 physical tolerance). Saved argmax coordinates are retained even if CPU tie order differs; both the full new measurement and same-point scalars are saved.

Each case writes all39 records,including failures. The complete1872-row CSV includes saved error,nearestF32 gap/count,actual magnitude/ULP and fixed original-argmax signed tuple. Each caseJSON includes every unattainable row/component coordinate,full ULP histogram,original measurement and replay,and the signed endpoint identity A-E=(A-Q)+(Q-E) at the same component; unrelated maxima are not added or ranked as causal evidence. Signed zeros share one ULP rank.

All48 are attempted before final status. Missing/corrupt/nonfinite/mismatched inputs or scalar controls produce retained per-case errors and HOLD/nonzero,not case selection or altered tolerances. Successful child status is COMPLETE_PENDING_ACTUAL_CPU_OUTER_C0,not physics PASS. Root closes the actual parent separately. Runtime records actual Python,Torch,NumPy and CPU thread settings. No scientific adoption or universal impossibility is inferred.

## Root single CPU invocation

The SB is a thin copy of the actually used counterfactualCPU template:16CPU/16GiB/RSS12GiB,oldrun_cpu_supervised_v3 and unchanged2GiBoutput/private accounting,with800s supervisor/15min Slurm for bounded import+48archive analysis. Output/guard/stdout use fresh job-specific paths under O. Estimated RSS below4GiB,output below16MiB,wall30-90s are unmeasured estimates,not promises.

Root binds MODEL_V3_EXPECTED_NODE to a fresh allowed CPU node,MODEL_V3_TERMINAL_INPUTS_SHA to inputs.json raw SHA,and MODEL_V3_TERMINAL_PINS_SHA to source_pins.json raw SHA. It uses the existing submission/admission flow and the new run_terminal_analysis_CPU.sbatch. CUDA is hidden;oldsupervisor establishes private TMPDIR/identity and exact2GiB budget. Original source guard files and failed4550 artifacts are never changed. No new W&B run or data/NPZ/weight file is written.

Before actual work Root performs its normal source audit/checker/publication as applicable. The author performed no Python,AST,Git,sacct,model,array,SDK,SSH orSlurm operation and did not hash/decode NPZ. These files remain source-only until Root's actual execution.
