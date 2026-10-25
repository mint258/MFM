# Original CPU composed equivariance failures

This is a read-only aggregation of the original job4521006. Root reported FAILED1:0/48s,57collected=9PASS/48FAIL,0errors/0skips and identical source bytes before/after. This process did not query Slurm or rerun any model.

Exactly48 unique original case JSON files are bound in baseline_aggregate.json by original physical path, byte length and rawSHA256. Original NPZ references, weight digests and fixture/view digests are copied from those bound JSONs. NPZ bytes were not opened.

Algorithm: read each complete case JSON once; take its three stored transform measurements and13 stored field measurements (1872observations total); group by field, C1/head/transform, take maximum stored maxabs and count failed observations/unique case IDs. No relative normalization, fresh scientific calculation, filtering or re-evaluation is performed.

| Field | Observations | Failed observations | Failed cases | Maximum raw absolute error |
| --- | --- | --- | --- | --- |
| PD/p_extensive | 144 | 20 | 14 | 2.288818359375E-05 |
| PD/p_intensive | 144 | 0 | 0 | 5.7220458984375E-06 |
| PD/d_intensive | 144 | 0 | 0 | 4.0531158447265625E-06 |
| PD/d_binary | 144 | 0 | 0 | 3.0994415283203125E-06 |
| PD/d_atom | 144 | 0 | 0 | 2.6226043701171875E-06 |
| PD/p_pair | 144 | 0 | 0 | 3.4570693969726563E-06 |
| PD/p_gradient | 144 | 0 | 0 | 6.5071375038305845E-08 |
| PD/p_dipole | 144 | 82 | 42 | 5.14984130859375E-05 |
| PD/p_dipole_magnitude | 144 | 50 | 28 | 3.0875205993652344E-05 |
| S/noise | 144 | 0 | 0 | 3.5746961956489853E-08 |
| S/coordinate | 144 | 0 | 0 | 6.4869180604887333E-07 |
| S/element_logits | 144 | 0 | 0 | 3.5762786865234375E-06 |
| S/clean_bond_logits | 144 | 0 | 0 | 2.3245811462402344E-06 |

All48 cases failed. Every failed field argmax is graph row2, the32atom synthetic decane-like fixture. All domains and neighbor identities passed; minimum hard5 boundary margin is0.001345363382833753Angstrom and maximum H0 discrepancy is2.2649765014648438e-6. Nonfinite, empty and nonzero-check failures are0.

The correct dipole rule is vector@R and magnitude invariant. The vector field and magnitude field have independent _DipoleHead instances/charge MLPs, so passing one does not establish the other. Current evidence is compatible with FP32 centered-coordinate/charge aggregation and extensive scalar sum amplification, but does not identify a causal operator yet.

The next external diagnostic must retain all48 fixed cases, seeds, views, weights and1e-5/rtol0. It may compare only predeclared temporary interventions; original failure/source/fixture/threshold records are immutable. A FP64 accumulation comparison is an attribution reference, not acceptance under the FP32 protocol or authorization to adopt it.

No original source, JSON, NPZ, geometry, parameter, threshold or existing result was modified. This record establishes a failed finite-domain acceptance check and makes no architecture selection or formal training claim.
