# Centered fixed-H01838 / CPU1842: read-only analysis

**C4 remains HOLD:21PASS/27FAIL; no adoption.** GPU4521838 closed C0/66s:
48 fresh cases,192 FP32 encoder forwards,zero FP64encoder forwards,all2496
external1776 terminal arrays bitwise equal,and the same21/27 passmatrix.
CPU4521842 closed C0/32s on16CPU,node17,with48cases/432observations and unchanged
sources. Root independently bound successful supervisors,raw accounting,
complete/result and1290 current source refs. New H0 is from1838; it is not
claimed to be unsaved1776 hidden H0. This analysis reads closed JSON only,
no NPZ/SDK/model tensor or scientific script. The scalar companion binds
both Rootclosures,complete/result,old1503 and the retained1776 analysis.

## Head precision alone does not clear the residual

Each field has144 observations; parentheses are counts above1e-5:

|Field|captured GPU FP32 D|CPU FP32 D|functional FP64 D|H|head arithmetic delta|
|---|---:|---:|---:|---:|---:|
|extensive|1.52587890625e-5(10)|1.1444091796875e-5(11)|1.1082818222263313e-5(2)|1.1082818222263313e-5(2)|1.2076356391332865e-5(9)|
|dipole|2.7487121196890715e-5(36)|3.4153461456298828e-5(51)|3.0803788369837548e-5(28)|3.0804355181324183e-5(28)|2.01979887526349e-5(5)|
|magnitude|1.761317253112793e-5(25)|2.8699636459350586e-5(25)|1.8458790521092006e-5(20)|1.8640782338402717e-5(20)|1.675806967676996e-5(2)|

FP64 D still exceeds1e-5 in50/432 observations across30/48 cases. G is zero
for extensive and at most2.5509768741827088e-7 otherwise; I is zero for
extensive and at most3.38053751658407e-11 otherwise. Neither exceeds1e-5.
At each of the50 F64-D worst components,H is the largest of H/G/I. This is
an observed attribution in this cohort,not an assumption from F64failure.
It does not locate a particular encoder operation or establish an FP32 bound.

At the *captured GPU's own argmax*,H is the largest of H/G/I/head-delta in
52 of its71 failing observations,and head-delta in19. Broken down by field,
H/head-delta counts are extensive1/9,dipole30/6,magnitude21/4. The arithmetic
delta is a residual difference,not a per-forward absolute error bound.

The largest captured GPU error is C1-0/two/H1/seed20261027 general_rotation,
row2/component0. At that single component:
GPU D=+2.7487121196890715e-5,
H=+1.507847714673025e-5,G=+3.2284751603876838e-8,
I=-3.4091149804656943e-13,head-delta=+1.2376359639468086e-5.
The largest F64 D is a different point:C1-0/two/H3/seed20261026 translation,
row2/component0:D=-3.0803788369837548e-5,
H=-3.0804355181324183e-5,G=+5.6677240678482121e-10,
I=+3.907985046680551e-14. Here head-delta=+1.0836232370081689e-5 partially
cancels H,leaving captured GPU D=-1.9967555999755859e-5. Maxima from different
components are never summed. All50 F64failing argmax rows are the32-atom graph.

FP64head arithmetic moves42 original GPU-failing observations below1e-5,but
moves21 original GPU-passing observations above it;29 fail both. Thus the count
falls71->50 while affected cases grow27->30 because cancellation changes.
CPU FP32 gives87 failing observations/37 cases,and its largest single moved
output difference from captured GPU is3.8921833038330078e-5. It is an actual
CPU evaluation,not a reproduction of the GPU rounding path or an acceptance
oracle. GPU_FP32_D uses the fixed FP64 row-R transform; the original13-field
physical test remains the authoritative21/27 result.

## Controls and distinct old cohort

The original small-tensor parity/row-R/decomposition/metadata selfchecks pass.
Largest recorded CPU-FP32 four-way closure is1.0587911840678754e-22,and FP64
closure is1.3234889800848443e-23; the executed source separately requires the
full GPU=H+G+I+head-delta residual closure within1e-10. The actual CPU reports
Torch2.10.0+cu128,NumPy2.2.6,intraop4 with4 workers and BLAS environment4;
its recorded interop thread setting is96,not an assertion that96 workers ran.
Old1503 environment equivalence is explicitly not asserted.

Old1492/1503 used different,uncentered H0. Its same mathematical functional
implementation gave65 F64-D failures/31cases/max3.8905694872831686e-5 versus
50/30/max3.0803788369837548e-5 now. Old H had63 failures/31cases versus50/30;
G/I remain small in both cohorts. Head-delta exceeds1e-5 in16 observations
now versus12 before. These are descriptive different-H0 cohorts,not repeated
samples,an architecture comparison,or permission to select layers/seeds.
The scalar report preserves all48 case summaries and full C1/views/head/seed
groups without selecting a favorable subset.

## One conditional next measurement

The results warrant checking where precision is required,but do not establish
LayerNorm,GEMM,softmax or RBF as the cause. Do not start another broad encoder
candidate from these aggregates. A smaller reusable CPU-only counterfactual
can test the final FP32 H0 interface separately from internal encoder arithmetic.
The closed1561 analysis already saved four44x512 FP64 reference H0 arrays per
case. This is an explicitly different mathematical reference,not a replacement
for current1838 H0 or supposed1776 hidden state.

Only after strict all48 parameter/case/source/actual-input lineage checks,
including exact stored1492-versus1838 position,batch and role-transform checks,
compare three fixed routes on the same actual positions and current bank state:
A:cached reference H64 -> unchanged functional64 heads;
B:H64 rounded once toFP32 -> the same functional64 heads;
C:that same once-roundedFP32 H0 -> the actual ordinaryFP32 bank.
Use all48/the same three fields/three transforms/two seeds; no ideal coordinates,
newencoder,GPUrun,parameter change or selection. A->B isolates final512D-FP32
interface rounding;B->C isolates head arithmetic at that controlled reference.
A->B quantifies rounding only on the historical1561 reference; even a B failure
cannot prove a universal FP32 floor or a need to change the512D FP32 API.
B->C is a head implementation/dtype contrast on this CPU backend,not solely a
precision contrast. This cannot identify a unique internal encoder operation.
If any required identity fails,reject reuse rather than call oldH0 currentH0.
This is one conditional preregistered measurement proposal only,no new code,
execution,production precision change,H0 API change or scientific adoption.
