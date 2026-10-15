# Pretraining data-quality protocol v3

Status: frozen before quality-filtered scaling runs  
Policy: `configs/iclr2027/data_quality_policy_v3.json`  
Authoritative generation interface: `/share/home/zixiao/unimol_data/QM_stable_state_parallel.py`

## Scope

This protocol measures and improves fidelity to the stored PM7/structural/RDKit supervision. It does not claim
agreement with high-level quantum chemistry or absolute physical truth, and it does not call MOPAC, PM7, DFT,
Psi4, or any other new QM calculation.

## Generator audit

The authoritative generator stores `FINAL HEAT OF FORMATION` in kcal/mol and the `NET ATOMIC CHARGES` table in
elementary-charge units. Its success check requires only that both section titles occur in the MOPAC output. It
does not check a normal-termination marker or numerical plausibility. If optimized Cartesian coordinates cannot
be fully parsed, the generator writes the original coordinates instead. Consequently, finite tensors and a
correct unit string are necessary but not sufficient data-quality checks.

The pre-quality domain-matched pools contained:

| pool/domain | count | minimum energy | median energy | maximum energy | unit |
|---|---:|---:|---:|---:|---|
| 400k molecule | 200,000 | -948.58545 | -56.489405 | 385.16874 | kcal/mol |
| 400k principal | 200,000 | -46,940.01781 | -162.785415 | 545,243.93981 | kcal/mol |
| old validation molecule | 4,096 | -639.30658 | -53.033045 | 238.26671 | kcal/mol |
| old validation principal | 4,096 | -5,418.78090 | -102.417320 | 93,857.56947 | kcal/mol |

All 408,192 energy labels were finite and labeled `kcal/mol`, so a finite-only loader accepted every extreme.
The 400k pool also contained atomic charges down to -14.998474 e. These tails explain the very large energy RMSE
and the late multi-task validation instability seen in the pre-quality 400k pass-6 run.

RDKit descriptor generation failed for 27,438/400,000 training structures and 643/8,192 old validation
structures. Those molecules are not globally quarantined: the existing masks remove unavailable descriptor
supervision while retaining valid energy, charge, geometry, element, and bond targets. PBF is not treated as a
bounded [0, 1] quantity; RDKit defines it as the plane-of-best-fit descriptor, unlike the normalized principal
moment ratios NPR1/NPR2. See the official [RDKit 3D descriptor documentation](https://www.rdkit.org/new_docs/source/rdkit.Chem.Descriptors3D.html).

## Automatic quarantine policy

The policy is frozen from the 50k nested training prefix before quality-filtered model comparison. For a scalar
target, robust sigma is `1.4826 * median_absolute_deviation`.

1. Reject malformed/non-finite element, coordinate, energy, masked charge, or masked descriptor tensors.
2. Require the stored energy unit to be exactly `kcal/mol`.
3. Apply a domain-specific energy band of `median +/- 12 robust sigma`.
4. Apply a second `energy / atom_count` band of `median +/- 20 robust sigma`, which catches gross failures in
   very small structures without tightening the molecular-energy band.
5. Apply an atomic-charge band of `median +/- 20 robust sigma` to masked stored charges.
6. Do not use charge-sum deviation as a hard filter: legacy `total_charge` provenance is not guaranteed and the
   model has no explicit conservation constraint.
7. Do not reject a whole molecule solely because RDKit targets are unavailable; use the stored masks.

These are data-driven engineering quarantine thresholds, not physical-accuracy or chemical-accuracy thresholds.
The large multipliers deliberately target gross pipeline failures, not legitimate hard molecules or ordinary
PM7 tails.

## Recoverability and split construction

Source LMDBs are immutable. Every rejected record is written to a quarantine ledger containing domain, shard,
real index, sample key, parent identity, reasons, and a recoverability flag. Cleaning is implemented only by new
manifests.

The builder creates nested 50k, 100k, 200k, 400k, and 800k train pools with an exact 50:50 molecule/principal
ratio. Validation is selected after the largest train pool, is also 50:50, and excludes every train parent across
both domains. This prevents a principal structure and a molecule-domain representation of the same parent from
crossing the train/validation boundary.

## Historical disposition

Pre-quality V3 checkpoints are preserved and marked `HISTORICAL_INVALID_FOR_V3_DATA_QUALITY`. They may be used to
diagnose the failure mode, but not for V3 scaling, timing, architecture, downstream, or transfer-ready conclusions.
Changing only the validation set cannot repair gradients already produced by contaminated training labels.
