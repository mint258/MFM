# Geometry4579: one passive head-internal diagnostic

Design-only stage, no executable/measurement/adoption yet. The geometry model remains local03e26/public498ec, all parameters/initializers and the complete original48 criterion remain unchanged. Use the successful passive-stage-v3 lifetime/finite writer, the geometry complete48 builder and original guard, not a new model/monitor. Head-off GPU4580 is independent; Root alone chooses a future free-card allocation. The worst4579 scalar2.5928020477294922e-5 has tied cases, not a uniquely identified head policy.

## Inputs and complete controls

Baseline is actual geometry4579 RESULT plus all48 case JSON/52-terminal archives, never4550. New capture is new hidden state, and attribution to4579 requires all2496 external terminal arrays, case/config/fixture/view/full seeded parameter identities and passmatrix15/33 to match exactly. Continue all48 even if a capture/control fails, then HOLD rather than accepting a subset. Original physical13fields x3transforms, absolute1e-5/rtol0, nonzero/domain guards and saved failures stay authoritative. Exactly192 actual FP32 encoder forwards,512geometry and2304projection calls, no encoder/local-op replay or FP64model. No new baseline or H64 quantization route.

Keep the v3 existing passive stage/geometry capture and original full88/132/view population maps; add only head ports. The CPU consumer reuses the saved-input/thread/budget machinery but does not rerun the prior1296stage/384geometry statistics or the whole-F64-head matrix.

## Actual ports and observer lifetime

There are two separately parameterized _DipoleHead modules, one per registry field p_dipole and p_dipole_magnitude. They do not share charges or weights. Resolve modules through actual registry/field keys, class and magnitude flag; never infer magnitude by norm of the other head.

Per role store the shared actual PD clean H0 float32[44,512], pos float32[44,3], batch int64[44]. The existing full packedH0[88/132,512], clean_rows, native/view masks remain available; after hooks are removed require actual PD H0/pos/batch to agree bitwise with that current same-forward clean selection. Per head store:
- charges float32[44,1], actual center float32[3,3];
- center[batch], actual relative subtraction and actual charge-times-relative product, each float32[44,3];
- reduced moment float32[3,3];
- original final output float32[3,3] or float32[3,1].
Original native graph counts3/9/32 remain; no row/seed/layer is selected.

Reference-only pre/post hooks on the two heads and their charges MLP retain actual input/output objects. Temporary wrappers of the existing v3_heads aliases compensated_pool/index_add/norm3 call the original function once and return its exact object; only the active head receives records. A TorchFunctionMode scoped to that one original head forward retains only its actual center-index/subtraction/product operation results, calling every func once and returning its original result. No tensor arithmetic/copy/cast/synchronization or numerical validation is introduced during forward. Missing/unexpected ports become post-forward capture errors, not substituted computations or swallowed original model exceptions.

After the full original forward returns, first disarm all original/new handles and restore aliases/method wrappers; only then validate/copy/serialize. The proven outer-finally close covers the original forward, disarm, take, write and normal return; original model exceptions propagate. Before/after state SHA, parameter1492, RNG/backend flags and actual dtype/mode checks remain. No returning hook replaces a tensor. Expected new coverage is384 head/charges/center/product/reduction captures and192 magnitude-norm captures across all192 roles.

Store the two actual charges-MLP typed FP32 state dictionaries once per case (role0 archive), not four times; role1..3 bind the same state. Complete exact names/shapes/dtypes/raw hashes are mandatory. Each head has hidden64: [64,512],[64],[1,64],[1],131588B; both263176B. No full model/bank weights or optimizer payload export.

## Bound before execution

Old4563 Root metadata records192 archive sizes totaling397140992B, maximum2526404B; whole trace412196600B. The additional per-role visible payload estimate is94704B, including actual clean H0/pos/batch plus both heads ports;48 once-per-case state payloads add12632448B. Thus additional numeric total30815616B, expected overall443012216B. A further16MiB allowance for new ZIP headers/metadata gives459789432B, below536870912B. Maximum original-role archive plus ports plus once-per-case state is2884284B before modest new headers, below4MiB.

These are source/old-metadata estimates, not a promise of new data. Retain actual prewrite4MiB role and512MiB trace caps, all trace/terminal/control files and finalization reserve. Whole/private remain2GiB separately; original node21/C35 guard,16CPU32GiB,RSS28GiB,1100s,85%,sole inherited public UUID lock are unchanged. CPU all-selected-input bound is512MiB (not the old128MiB). Before hashing/decode stat/deduplicate every selected trace/control/source; reject if it does not fit. CPU uses existing16CPU16GiB/RSS12GiB,4processes x4BLAS<=16, finite original wall and2GiB whole/private,128MiB bounded output. No separate QA or dispatch parent is added.

## One local numerical accounting, after passive gate

No encoder or head object is loaded/run by the CPU moment consumer. Use saved actual q, positions, center, relative, products and moment. First replay the original FP32 center/subtraction/product/fixed reduction/norm on those identical actual inputs, through the existing frozen numeric primitives, and require exact captured output at each applicable port. A CPU mismatch is an explicit unsupported GPU/CPU-local-replay result/HOLD; do not loosen it or call CPU native arithmetic the GPU path.

The independent real-formula reference promotes only saved FP32 values/weights to FP64 outside the model. The readout reference is just the actual two-layer charges affine/SiLU/affine on the same actual H0, not a full F64 head or encoder. Its q difference includes reference algorithm/backend contrast and is not an instruction-identical dtype proof.

For vector output let q* be that reference, M(q,p)=sum q*(p-mean(p)) evaluated independently, L(v)=v@R. At the same component use:
H=L(M(q*t,p0)-M(q*0,p0));
G=M(q*0,pt)-L(M(q*0,p0));
I=M(q*t,pt)-M(q*0,pt)-H;
Q=[M(qGPUt,pt)-M(q*t,pt)]-L([M(qGPU0,p0)-M(q*0,p0)]);
E=[dGPUt-M(qGPUt,pt)]-L([dGPU0-M(qGPU0,p0)]).
Thus observed D=H+G+I+Q+E with a predeclared1e-10 diagnostic closure only, never a changed physical tolerance. H is H0-linked readout drift, not proven error of a specific encoder op. G retains actual coordinate cast plus original R/real-formula effects; verify original row-R cast provenance/orthogonality without changing R or constructing new model inputs.

Further split each per-frame moment error E using the saved actual intermediate operands in program order:
M0=M(qGPU,p);
M1=sum qGPU*(p-captured_center);
M2=sum qGPU*captured_relative;
M3=sum captured_product;
M4=captured_moment.
The four consecutive differences isolate centroid, relative subtraction, product and reduction residuals at fixed actual operands; transform each base term with the same L. For magnitude use that head's own q and moments, apply norm to the same ordered M0..M4 chain, and add captured_norm-norm(M4). Use the corresponding scalar functional N(q,p)=norm(M(q,p)) in H/G/I/Q. This handles nonlinearity by an explicit fixed program-order telescoping chain, not by summing maxima or treating the two heads as shared.

Retain all48/three transforms/three native graphs, signed terms at the actual saved terminal argmax and each term's own argmax separately, component counts/RMS with exact populations, and all algebra checks. Do not add/difference independent maxima or rank local modules as whole-model causes. This targets51 of56 failed dipole/magnitude observations; the5 extensive failures remain outside this head-internal explanation. No universal floor, necessity of dtype/API change, head-only fix promise or adoption follows.

## Freeze stages and interfaces

Stage1: narrow passive_capture_head.py plus existing run/launch/SB/metadata mechanical adapters, source snapshot and Root AST/publication. Future CLI remains the old guarded Root submit/action pattern; the child is run_head_moment_trace.py --request ACTUAL_REF --request-sha256 ACTUAL_SHA --output-root FRESH. Method/actual binding has no future SHA placeholders accepted.
Stage2: after actual GPU closure, one analyze_head_moments_CPU.py --inputs ACTUAL_INPUTS --inputs-sha256 ACTUAL_SHA --output FRESH using the existing CPU wrapper. No NPZ/model execution by source authors. Root alone validates/executes, with full closed raw refs and fresh resources. This document does not authorize running a DRAFT.
