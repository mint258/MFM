# Centered-attention complete48 GPU1776: read-only analysis

**Not accepted.** Actual job4521776 ran the complete original matrix in42s:
48 cases /192 recorded encoder forwards /1872 field observations,21PASS and
27FAIL,0error/0skip. The original absolute FP32 limit1e-5 and rtol0 remain.
Root closed this as `ACTUAL_COMPLETE48_SCIENTIFIC_GATE_FAIL_RETAINED_NOT_ADOPTED`.
Candidate localcf8ce66d/publicf8417157/tree2389ab04 remains an independent
experiment branch. Sourcebeforeafter is unchanged; no production adoption.

This report only groups/counts/maximizes scalars in the closed JSONs. All48
case raw bytes/SHA match RESULT and Rootclosure. It reads no NPZ/SDK/model
tensor and runs no scientific Python,model,SSH or Slurm. The companion scalar
JSON binds Rootclosure,both RESULTs,all96 paired case JSONs,all71 failed
observations and all five common identity hashes percase.

## Residual errors

Each field has144 observations(48cases x3transforms). Only three fields fail:

|Field|1776 failing obs|1776 max absolute error|1435 failing obs|1435 max absolute error|
|---|---:|---:|---:|---:|
|PD/p_extensive|10|1.52587890625e-5|14|1.5497207641601563e-5|
|PD/p_dipole|36|2.7487121196890715e-5|35|2.1939841282838865e-5|
|PD/p_dipole_magnitude|25|1.761317253112793e-5|32|5.6512653827667236e-5|

All71 failures have argmax graphrow2,the32-atom graph. The other10 fields all
pass: p_intensive/d_intensive maxima5.7220458984375e-6,d_binary3.814697265625e-6,
d_atom2.0265579223632813e-6,p_pair4.4107437133789063e-6,p_gradient4.43416205003766e-8,
S/noise3.2528114576879652e-8,S/coordinate6.4869180604887333e-7,
S/element_logits2.86102294921875e-6,S/clean_bond_logits2.1457672119140625e-6.
All recorded domain and neighbor-identity gates pass. The unchanged original
measurement retains its finite/nonzero checks and fixture/transform laws.

Failure observations by transform: general_rotation27(16cases),translation20
(18cases),other_rotation_and_translation24(21cases); case sets overlap.
The worst is C1-0/two/seed20261027,shared by H1fixed/H1learned dipole:
general_rotation,row2,component0,actual0.00761973112821579 versus expected
0.007592244007018899,absolute error2.7487121196890715e-5. Its recorded H0max
is1.5497207641601563e-6; these different maxima are not a sensitivity ratio.

## Paired comparison and complete cohort

Versus1435's10PASS/38FAIL,15 old failures now pass and4 old passes now fail;
6 cases pass both and23 fail both. This is not a monotonic improvement.
All48 pairs preserve named-parameterSHA,fixture geometrySHA,discrete viewSHA,
physical view geometrySHA and registrySHA. Global H0max is unchanged at
1.9073486328125e-6. Dipole's worst error grows as overall casepasscount improves.

|Grouping|1776 passing cases|1435 passing cases|
|---|---:|---:|
|C1-0|6/16|1/16|
|C1-a|9/16|2/16|
|C1-b|6/16|7/16|
|two views|11/24|5/24|
|three views|10/24|5/24|
|seed20261026|11/24|7/24|
|seed20261027|10/24|3/24|
|H1fixed|5/12|1/12|
|H1learned|6/12|4/12|
|H2fixed|5/12|2/12|
|H3fixed|5/12|3/12|

The four regressions are C1-a/three/H2fixed/seed20261026(dipole+extensive),
C1-b/two/H1learned/seed20261026(magnitude),
C1-b/three/H3fixed/seed20261026(dipole+magnitude),and
C1-b/three/H3fixed/seed20261027(dipole). All are retained. These comparisons
cannot select C1,seed,headpolicy or layers; unchanged tolerances apply to all48.

## One next discriminating measurement, no broad candidate

The JSONs do not localize a full-H0 drift mechanism. A scalar maximum lacks
atom/channel/common-mode structure and a matching downstream derivative.
Dipole/magnitude account for61/71 failures,but that alone does not separate
head cancellation from inherited H0 error. Nor does the32-atom pattern identify
a unique arithmetic cause. A head-only charge rewrite leaves the10 extensive
failures structurally unaddressed. CompensatedLayerNorm/GEMM or another AV
variant is not established as causal here. The earlier FP64encoder reference
is analysis only,not a production precision proposal or an FP32 lower bound.

The one warranted next measurement reuses the accepted transparent fixed-H0
capture + CPU functional-head decomposition on the current all-six-layer
centered candidate,over all48 cases and original three transforms. Capture
actual bankH0/pos/batch/typed bankstate and raw terminal controls from the same
fresh forward; retain original parameters,fixture,seeds,mask,backend and1e-5.
Compare the actual FP32 bank to independent functional FP64 arithmetic for the
fixed extensive/dipole/magnitude fields,including F00/Ft0/F0t/Ftt,H/G/I and
arithmetic delta at the *same* failing component,with closure. Maxima from
different rows/components cannot be added. Reuse existing tools and bounds;
no new monitoring framework is needed.

1776 did not store bankH0: its52-array NPZ is terminal output. The new capture
must have fresh lineage and same-forward controls; it cannot claim1776 internal
tensors or overwrite its21/27. The1492/1503 head shadow used different encoderH0
and cannot answer this current question. If functional-F64 heads remove a
residual while FP32 does not,that supports researching head arithmetic. If the
same-H0 F64 residual stillfails,a head-arithmetic-only precision improvement is
insufficient to remove that residual. Inspect same-component H/G/I before
choosing a representation,geometry or interaction intervention. Neither outcome
alone identifies LayerNorm vs GEMM.
No new precision candidate,tolerance relaxation or layer/seed selection follows
from this report. Root must preregister before any new GPU measurement.

Audit note: one Root message duplicated a character in its textual closure SHA.
The unchanged file's actual64-character machine reference is bound in the scalar
JSON and confirmed by Root. This is not a scientific or source discrepancy.
