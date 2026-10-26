# Fixed-H0 terminal shadow: source plan v1, not executed

Status: DESIGN_ONLY, no new candidate, source edit or scientific execution.
Production, immutable candidate16 and original48 test/fixtures stay unchanged.
No NPZ was opened to prepare this plan.

## Existing artifact sufficiency

Current1435 RESULT/case JSON catalogs contain only52 arrays:4 states x13
terminal outputs. No actual cleanH0, head input positions/batch or parameter
matrix is archived. H0 is represented only by a max-difference diagnostic;
weight summaries are digests/counts/norms, not recoverable parameters. Therefore
neither JSON alone nor loading current terminal-only NPZ supplies the requested
same1435-H0 replay. Rebuilding the encoder on CPU would change H0 and cannot
establish current GPU head arithmetic versus inherited-H0 attribution.

No existing NPZ is necessary for a source-only plan. A genuine same-H0 shadow
requires a new transparent capture unless another exact H0 artifact is supplied.
Future shadow execution must load that new capture NPZ with allow_pickle=False.
Old1435 terminal NPZ may be read only for an optional honest cross-job output
comparison; they do not retroactively prove the newly captured H0 equals1435.

## Minimal capture, only after Root authorizes it

Use a new external analysis child, original current candidate/source/public tree,
all48 Cases in the original canonical order, original seeds and all3 transforms.
No best-seed/config filtering. Reuse the existing single-GPU guard, not CPU
encoder replay or another resource framework. This needs192 actual encoder
forwards; it is a new capture of the same failed candidate, not a model repair.

A transparent pre/post hook on the actual pd_heads bank retains references to
its actual arguments (H0[44,512], clean pos[44,3], batch[44]) and actual outputs.
It delegates to the original forward unchanged. After the full forward returns,
copy these exact FP32 tensors to CPU. No source arithmetic, dtype, parameter or
random draw is changed before the forward. Save all4 actual states/case and the
three target GPU outputs; retain the other original terminal controls and report
same-job/cross-job reproducibility honestly. Never overwrite1435.

Save the exact PD-bank tensor state once/case, its registry/forms/extra-state in
JSON, tensor names/shapes/dtypes/digests, and whole-bank parameter SHA before/after.
Use NPZ tensor arrays plus JSON metadata, not pickle or guessed reconstruction
from global RNG. Source/factory configuration and actual graph-argument captures
must agree. Capture all actual source heads/controls; shadow evaluation selects
only p_extensive, p_dipole and p_dipole_magnitude by the frozen registry names.
The current protocol has13 terminal fields plus H0 diagnostics, not a newly
invented fourteenth physical label.

Four cleanH0 states per case total16.5MiB (17.3MB) across48. With captured head-bank
states, coordinates, original controls and JSON, declare <=128MiB capture-input
budget before execution (actual census required). Preserve source and parameter
identity before/after. Existing whole/private2GiB bounds remain. Successful
capture is analysis completion, never a claim that FP32 physics passed.

## Minimal CPU shadow child, conditional on that valid capture

Proposed new independent module run_fixed_h0_terminal_shadow_v1.py, small typed
capture manifest, and mathematical oracle tests. No production/model file changes,
no new generic dispatcher, monitor or training path. Root owns freeze and execution.

1. Require complete48 membership/all4 input states, exact source/config/parameter
   and actual capture/supervisor bindings, finite explicitFP32 H0/pos, int64 batch,
   original graph identities, exact tensor shapes and NPZ keys. Unknown/missing
   heads or data fail closed; no regenerated H0 and no fallback from missing rows.
2. Instantiate only the original V3HeadBank (no encoder), load the captured tensor
   state and existing extra-state strictly. Evaluate the original FP32 branch on
   those exact captured H0/coordinates as a CPU backend control. It need not be
   bitwise equal to the GPU readout; that backend discrepancy is reported.
3. Evaluate an explicit functional FP64 mathematical shadow for the same three
   registered heads, same captured FP32 parameter values cast toFP64, same pooling
   (sum/mean/learned), H1/H2/H3 linear/SiLU layout, centroid, charge MLP, moment and
   norm. KeepFP64 across the whole readout chain until analysis. The actual
   compensated_fp32 module rejects double tensors, so calling .double() on that
   production branch is not an implementation. The shadow must reproduce the
   known head topology explicitly and refuse an unknown one.
4. For each transform evaluate the same four H0/pose combinations in each precision:
   F00=f(H0,p0), Ft0=f(Ht,p0), F0t=f(H0,pt), Ftt=f(Ht,pt). Cache F00. Let L apply
   the original row-vector R to vectors and identity to scalar/magnitude outputs.
   Use signed componentwise decomposition:

   D=Ftt-L(F00); H=L(Ft0-F00); G=F0t-L(F00);
   I=Ftt-F0t-L(Ft0-F00); verify D=H+G+I componentwise.

   GPU_FP32_D minus FP64_D is the actual head-arithmetic residual contrast at
   captured inputs. FP64_H is inherited-H0 response; FP64_G includes the already
   rounded coordinate input difference; FP64_I is interaction. Compare same graph
   and component, not sums/differences of unrelated global maxima. Scalar extensive
   heads do not depend on positions, providing a G=I=0 mathematical control.
5. Save per-case/field/transform/graph/component signed terms plus original GPU,
   CPU_FP32 and FP64-shadow error summaries, all48 coverage and source identity.
   Higher-precision shadow is attribution only, not a renamed FP32 pass or proof
   that the real-data/entire-model precision policy should change. Original
   38failures and threshold1e-5 remain. No architecture/C1/seed selection follows.

## Budget and tests

Given complete captures, this is at most10 input combinations x3 fields x48 cases
x2 CPU arithmetic paths=2880 small head evaluations, no encoder. Input arrays are
bounded <=128MiB and decoded one case at a time. Proposed actual CPU-only parent:
16CPU, RSS<=12GiB, wall<=120s, existing whole/private2GiB cap. Use at most4 bounded
case workers with at most4 math threads each, or the existing deterministic
single-process thread policy; no unbounded executor. A <=2min expectation is a
planning estimate, not an observed timing or a promise. Stop/censor honestly if
that fixed cap is insufficient. The needed GPU capture is separate and cannot be
claimed inside a CPU-only2min budget or replaced by already-saved terminals.

Meaningful preflight/oracles: all-head-form functional parity against original
FP32 with fixed tensors; FP64 small dense/manual sum oracle; nonzero vector
row-R four-way identity; extensive zero geometry/interaction; parameter/source
and NPZ key/dtype/shape drift rejection; complete48/4-state failure on missing
entry; explicit CPU/GPU backend distinction; no target/data-label read. No new
model/candidate/array computation has occurred for this plan.
