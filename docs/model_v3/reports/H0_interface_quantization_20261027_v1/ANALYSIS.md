# Historical H0 interface quantization1917: read-only analysis

**All three diagnostic routes pass; current C4 remains HOLD21PASS/27FAIL.**
ActualCPU4521917 closed C0/11s,16CPU,node15,after preregistration
7dd1cfc09b6c85cd683ae30fb271a71cb00c3be3. Each route evaluated48 cases,
192 head calls and432 three-field/transform observations. There were zero
encoder forwards and no GPU work. Root closed actual source/supervisor/raw
accounting/result evidence;all48 case rawSHA and references agree. This report
reads only closed JSON scalars,not NPZ/model tensors or scientific scripts.

A uses historical1561 H64 with the unchanged functional64 head. B rounds those
same historical values once toFP32,promotes them losslessly and uses the same
functional64. C sends that same once-roundedFP32 tensor to the actual FP32 bank
on CPU. H64 is neither current1838 H0 nor unsaved1776 hidden H0.

## Complete cohort results

Max absolute drift D; all entries have0/144 observations above1e-5:

|Field|A|B|C|
|---|---:|---:|---:|
|extensive|8.449005584054703e-7|8.978458900799069e-7|7.62939453125e-6|
|dipole|1.2230009710928469e-6|2.0317572508865567e-6|6.369844893966414e-6|
|magnitude|7.935851844068087e-7|1.5237927805944462e-6|7.897615432739258e-6|

Thus every arm has0/432 failing observations and0/48 failing cases. All C1-0/a/b,
two/three-view,H1fixed/H1learned/H2/H3 and both seed groups pass these three-field
diagnostic counts. None is selected. This does not certify the original13-field
CUDA test or its full finite/nonzero/domain conditions.

The three A replay error maxima(maximumD,signedD at savedreferenceargmax,
signedD at fixedoldGPUargmax) are each9.2370555648813024e-14,below the fixed
1e-10 diagnostic bound. All1296 scalar controls pass. These are saved scalar
checks,not full historical F64 terminal-bitwise replay.

B-A maxima are extensive3.518618711950694e-7,dipole1.4151571376963545e-6,
magnitude1.0661133635625486e-6. C-B maxima are extensive7.76482831810199e-6,
dipole6.082801043250097e-6,magnitude8.18786855044662e-6. No paired-effect
observation exceeds1e-5. These maxima are not added across different rows.

At C's worst magnitude point(C1-b/three/H1fixed/seed20261027,generalrotation,
row2/component0),the signed tuple is A=-2.960164266208043e-7,
B=-2.9025311770736195e-7,B-A=+5.763308913442344e-9,
C=+7.897615432739258e-6,C-B=+8.18786855044662e-6.
All1296 recorded A/B/C argmax locations and same-component tuples match the
saved scalar tables. A/B have no maximum ties. C/extensive has16 exact ties,
maximum multiplicity3;10 are entirely zero drift. Each uses the first flattened
maximizer. These zero *residuals* do not imply a zero model output. The actual
terminal norms were not exported,so this diagnostic adds no terminal-norm-floor
claim. A/B residuals are nonzero in all432 observations;C in422.

All192 role quantizations are nonzero;the largest recorded H64-to-FP32 difference
is1.1920607123627747e-7. Actual combined selected inputs125739933 bytes remain
below134217728,with8477795 bytes headroom. Actual CPU metadata records
Torch2.10.0+cu128,NumPy2.2.6,intraop4 and BLAS environment4;no CUDA backend
rounding equivalence is asserted. The original tiny controls pass.

## What follows,and what does not

For these fixed historical H64 values,the final512-dimensional FP32 quantization
alone did not block the three-field threshold. The original CPU FP32 bank also
meets it on that controlled representation. This is finite-cohort evidence,
not a universal FP32 floor theorem,not proof that every representation behaves
this way,and not permission to change the512D FP32 API. C versus B includes
implementation/dtype/CPU-backend differences. No current CUDA candidate passes
by this counterfactual. In particular,current1838 H0 withF64heads still produced
50 failing observations/30cases in1842,with H dominant. The model and retained
1776/1838 C4 result remain21PASS/27FAIL,without adoption.

The one approved next preparation is an internal-operation study on the actual
current encoder,not another quantization/head counterfactual or a broad guessed
precision candidate. Reuse existing hooks/StageReferences and the guarded GPU
runner,all48 cases and all six layers uniformly. Retain existing module input/
output references only;after the full original forward returns and hooks are
disarmed,check nativeFP32 same-input replay bitwise,then evaluate an independent
F64 real-formula reference at those identical inputs. Compare within each module
its native rigid drift,reference same-input drift and local arithmetic delta at
one common component,covering the existing LayerNorm,coupledattention,DenseFFN
and sharedgeometry boundaries. Full192 current bankH0 must match1838 and full52
external terminal controls before attribution. Preserve batch88/132,masks,roles,
parameters and original policies;no output is injected into the model.

Current centered helpers rejectF64,and the old1561 legacy shadow uses a different
numerical algorithm. The reference must state its precision/algorithm contrast;
it cannot be called an instruction-identical dtype substitution. Local module
maxima have different populations/scales and cannot establish whole-model cause
by a cross-module ranking. This is preparation only:source freeze and public
preregistration precede execution. No production file,candidate,threshold,layer,
seed,H0 API or representation was changed by this report.
