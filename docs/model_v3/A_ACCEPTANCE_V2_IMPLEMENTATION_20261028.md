# A acceptance v2 implementation (source only)

The authority is Root's separately published
docs/model_v3/DECISION_RULES_A_ACCEPTANCE_V2_20261028.md.
This file describes implementation, not authority, publication, QA or a new PASS.
Old A5/4524601 remains FAILED. A models keep every existing bias and Parameter;
the separately owned C bias-free candidate is not part of this change.

## Exact gates and unchanged model path

v1 remains the default paired mode and its original compare_tensors,
a_equivalence_report, trajectory_report and B gate functions remain byte-for-byte
as the original prefix of v3_performance_acceptance.py. New code/source identity
does not rewrite any old receipt. v1 output schemas gain no v2 keys.

Explicit v2 uses all-parameter/all-element abs(candidate-reference) <=
1e-8 + 1e-4*abs(reference), including zero-reference elements. Every violating
element fails its parameter/batch. Names, shapes, finite values and one-sided
None remain strict. Ordinary inactive heads both None remain legal. The verified
ACTIVE analytic-zero six biases must provide actual gradient tensors and both
L2 norms <=1e-8; both None is failure, not a fabricated norm0.

Difference/threshold, both norms, difference norm and counts are audit-only FP64
on detached CPU snapshots. No cast, forward, gradient, Parameter, optimizer,
initialization, view/noise/mask generation, loss, sampler, RNG or GPU backend is
changed. Reports retain shape, finite status, violating count, maximum absolute
error, minimum/maximum combined threshold, maximum error/threshold, both norms
and zero-proof metadata. Forward remains relative L2<=1e-5; each original500 loss
point remains relative<=1e-3. Numeric checks alone do not grant source/resource,
SDK, cross-GPU, R1, B or scientific acceptance.

## Why exactly six active zero-semantic parameters

analytic_zero_gradient_parameters inspects actual reference AND candidate models.
It requires the original six RealCoordTransformerLayer modules, original
DenseGeoSelfAttention or RuntimeDenseAttention, global/use_dist_bias attention,
the original Linear(1,dim)/SiLU/Linear(dim,heads), the actual bias Parameter
identity, requires_grad, FP32 dtype and [actual_heads] shape. It accepts only the
existing nn.Sequential, TiledDistanceMLP and ConfigurableTiledDistanceMLP
containers and the exact backbone/logical-batch wrapper classes. No value/norm
is used to discover this list. All six names must exist, without aliases/extra:
backbone.layers.{0..5}.attn.dist_mlp.2.bias. Actual S is six512/eight heads; tiny
CPU semantics fixtures do not become a scientific population.

The final projection adds one scalar c_h to every valid key's logit for a fixed
query/head. On the valid-key real softmax domain,
exp(z_j+c_h)/sum_k exp(z_k+c_h) = softmax(z)_j, so the real derivative of a
loss depending on the resulting attention is zero. Original finite -1e9 padding
overwrite and padded-query behavior are preserved; this is NOT a proof of
bitwise IEEE zero backward or an arbitrary modified/radius attention. Finite
sentinels are not silently changed to -inf. Roundoff is constrained by the
additional measured double-norm gate. Unregistered semantics are refused.

## Explicit actual publication binding

Only paired_a_acceptance gets local new flags; shared/single tools are unchanged:

    --acceptance-version v2
    --acceptance-rule-document ACTUAL_RULE_MD
    --acceptance-rule-document-sha256 ACTUAL_RAW_SHA256
    --acceptance-prereg-sha ACTUAL_PUBLIC_RULE_COMMIT40
    --acceptance-rule-publication ACTUAL_ROOT_PUBLICATION_JSON
    --acceptance-rule-publication-sha256 ACTUAL_PUBLICATION_RAW_SHA256

The metadata step imports no Torch before the original CUBLAS binding. It reads
owned ordinary bounded files and the actual existing
model_v3_exact_tree_publication_actual_v1 receipt, matches mint258/MFM
(repository_full_name or repository; aliases cannot conflict), public commit,
tree, both actual GitHub readback flags, checker closure rawref and the exact
rule-document Git blob SHA computed from actual raw bytes. A 40hex string is
not publication proof. The child does not query GitHub; Root's actual preflight
must have verified that actual immutable publication. Old v28 receipts lacking
this exact new rule blob cannot pass.

configuration/fixed gate/summary/status conditionally bind the same semantic
v2 contract SHA, actual rule-document rawref, actual publication/checker refs,
public rule commit/tree/blob and both models' six Parameter proofs. This
external-source boundary is explicit. The runner rebinds the metadata even for
a direct run() caller. A source change requires a new code identity; no old
receipt or Root closure is automatically upgraded.

The default full v2 A5 path still runs original20, and only if it passes proceeds
to original500. No smoke, export integration or parameter removal is introduced.
The original guard/supervisor, UUID lock, resources, whole/private budgets and
normal offline W&B finish remain in place. No job/monitor/dispatcher is added.

## Existing PASS cohort recheck, not a new full qualification

--fixed-batch-only is allowed only with v2, original20 and no smoke/export.
Configuration and summary say V2_FIXED20_RECHECK_ONLY, planned trajectory0,
trajectory not run and full_A_numeric_acceptance=false. Real fixed failure or
success is retained; passing fixed-only finishes the original offline trackers
normally. Status separately records actual trajectory start/committed updates.
This flag must NOT shorten the new A5 trial, feed R1 or stand in for all20+500.

Read-only inventory of nine original full-PASS cohorts is delivered separately
with exact original paths: A00/405,411,438; A01/456; A00 export/486; A03/549;
manual/3976, auto/4551, head-off/4580. All saved floating-gradient max_absolute
records are0, but each cohort's120 six-bias records contain NO reference/candidate
norm. Thus no cohort has been granted v2 by this inventory. They need actual
fixed20 zero-norm recheck, and arbitrary old L2 PASS alone is insufficient.

Root may associate unchanged old500 evidence only after proving its actual
complete PASS, same model/configuration/initial state/real inputs/seed/precision/
deterministic controls/GPU scope and semantic model/loss/optimizer/data sources.
Only Host verification rules may differ. Insufficient proof requires a full
rerun; this runner does not manufacture a combined certificate.

A specific existing boundary remains: auto checkpoint profiles bind the complete
current execution source graph, including the paired tool and acceptance module.
This Host source change therefore makes old9e profiles fail the original strict
source check. This change DOES NOT relax checkpoint policy, borrow R2 for R1,
or relabel an old capacity profile. Root must resolve actual compatible capacity/
source evidence before an auto recheck; unknown authority remains refusal.

## Planned CPU checks and resources

One new test module has34 planned cases (not actual collection/PASS). It covers
atol0/zero reference, nonzero rtol and direction, a single bad element hidden by
old L2, exact boundary/nextafter, both zero norms, missing/nonfinite/shape/set
failures, legal inactive heads, v1 exact report shape, real six-layer Parameter
identity, actual publication/raw blob/aliases and explicit fixed-only scope.

Two actual six512 models are constructed for identity/state/RNG checks; four
small six16 models are constructed for refusal cases. No model forward,
training, CUDA, real scientific payload, SDK or checkpoint is used by this test.
Other cases use small tensor snapshots (largest10000 elements) and tiny temporary
publication fixtures marked UNIT ONLY. Mechanism fixture publications are not
actual authority. No weights/SDK/CP/temp scientific artifacts are produced.
Memory/time are unmeasured; two model Parameter sets are about a few hundred
MiB plus existing Torch/PyG libraries, so the prior16CPU/16GiB/RSS12GiB/2GiB
CPU unit budget is a reasonable bounded first run, not a measured guarantee.

Root alone will inspect/AST/check/commit/publicize/test and schedule actual GPU
rechecks. All new actual QA, public implementation and GPU verdicts are pending.

The v2 per-parameter report is larger than v1. The unchanged2GiB whole/private limits remain; future v2 metadata consumers must bind the new schema and an explicit finite exact-file gate bound from actual size, not blindly retain the old4MiB fixed-gate exception. Existing v1 closers/SDK consumers are not modified here.
