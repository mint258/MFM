# PhyChem-MFM Pretraining Target Accuracy Standard (Protocol v3.1)

Status: **PROVISIONAL-FROZEN FOR V3 RE-EVALUATION**  
Threshold registry: `configs/iclr2027/target_fidelity_registry_v3.json`  
Evaluator: `tools/evaluate_target_adequacy.py`

## Scope and terminology

This standard measures **fidelity to the stored pretraining targets**. It does not measure agreement with an
independent high-level quantum-chemistry calculation or experiment. In particular, `1 kcal/mol` is not called
“chemical accuracy” here. All numeric acceptance bands below are explicitly project-defined engineering
thresholds frozen before v3 architecture comparison.

The server data generator uses MOPAC PM7. The PM7 documentation says its parameters reproduce reference
geometries and heats of formation ([MOPAC PM7 manual](https://openmopac.net/Manual/pm7.html)). RDKit graph and
node descriptors are cheminformatics labels; its 3D descriptors require a conformer
([RDKit descriptor documentation](https://www.rdkit.org/docs/GettingStartedInPython.html#list-of-available-3d-descriptors)).

## Audited transformation semantics

All current regression heads emit values directly in the stored target space. The loss implementation is:

```text
Huber((prediction - target) / training_std)
```

Although it is written as two z-scored terms, the training mean cancels algebraically. There is no target
clipping and no nonlinear target transformation. Consequently `inverse_transform_prediction()` is an audited
identity transform for the current checkpoints. Applying `prediction * std + mean` would corrupt the result.

| Target | Stored definition | Original unit | Mask | Loss scaling |
|---|---|---:|---|---|
| energy | MOPAC `FINAL HEAT OF FORMATION` after PM7 processing | kcal/mol | clean graphs | residual / `stdE` |
| charge | MOPAC `NET ATOMIC CHARGES` column | elementary charge `e` | `charge_mask`, clean atoms | residual / `stdQ` |
| geometry | pair distances derived from reconstructed and target Cartesian coordinates | Å | valid clean/geom/both atoms | Morse-shaped all-pairs loss |
| graph descriptors | 31 stored RDKit descriptors | descriptor-specific | per-descriptor mask, clean graphs | residual / descriptor std |
| formal charge, E-state index | stored RDKit node descriptors | `e` / descriptor-specific | RDKit node mask | residual / descriptor std |
| element, bond, categorical node descriptors | stored class IDs | none | task-specific masks | CE/BCE; no inverse transform |

## Energy target fidelity

The field named `energy` is not a generic SCF electronic energy. The server script parses `FINAL HEAT OF
FORMATION`, writes `SCF Energy: ... kcal/mol (PM7 optimized)`, and the LMDB parser stores that scalar unchanged.
The MOPAC accuracy tables likewise report heat-of-formation errors in kcal/mol
([MOPAC heat-of-formation table](https://openmopac.net/PM7_and_PM6-D3H4_accuracy/table_of_heats.html)).

Required metrics are molecular MAE, RMSE, median absolute error, P90 and P95 absolute error. Absolute error per
atom is diagnostic only and never replaces molecular MAE.

| Molecular MAE | V3 interpretation |
|---:|---|
| ≤0.5 kcal/mol | exceptionally faithful reproduction of this stored PM7 label |
| ≤1 kcal/mol | **HIGH_FIDELITY** engineering band |
| 1–2 kcal/mol | strong label fidelity, below the high-fidelity gate |
| 2–5 kcal/mol | **USABLE** PM7-surrogate fidelity |
| 5–10 kcal/mol | weak; reportable but not adequate for transfer-ready |
| >10 kcal/mol | **INADEQUATE** |

These bands do not quantify PM7 error relative to experiment.

## Stored atomic-charge fidelity

The current label must not be called “Mulliken charge” without qualification. The server job uses `PM7`/`PM7
AUX` and does not request `MULLIK`; it parses `NET ATOMIC CHARGES`. MOPAC documents default net atomic charges as
Coulson-type and says a Mulliken population analysis requires `MULLIK`
([MOPAC derived properties](https://openmopac.net/Manual/features.html),
[MULLIK keyword](https://openmopac.net/Manual/mullik.html)). The value is still expressed in elementary-charge
units; MOPAC states that Mulliken populations also use the electron as unit
([MOPAC populations](https://openmopac.net/Manual/mulliken_populations.html)).

Required metrics are atom MAE/RMSE/median/P90/P95 and per-element MAE for present H, C, N, O, F, P, S, Cl, Br,
and I. Molecular `sum(predicted atom charges) - formal charge` is diagnostic because the architecture does not
enforce charge conservation.

| Atom MAE | V3 interpretation |
|---:|---|
| ≤0.01 e | exceptionally faithful |
| ≤0.02 e | **HIGH_FIDELITY** |
| 0.02–0.05 e | **USABLE** for reproducing the stored local-charge pattern |
| 0.05–0.10 e | coarse |
| >0.10 e | **INADEQUATE** for reliable local-charge description |

## Geometry/distance fidelity

The coordinate head predicts Cartesian coordinates; the training objective compares all valid pair distances
using a Morse-shaped error and a per-atom `log1p` aggregation. It is not coordinate RMSD and it is not restricted
to bonded pairs. Protocol v3 therefore recomputes raw Å errors and reports separately:

- bonded pairs from stored RDKit bonds;
- local nonbonded pairs with target distance ≤2 Å;
- longer-range nonbonded pairs;
- all pairs as a diagnostic.

The hard-gate metric is the worse MAE of bonded and local-nonbonded strata. This prevents numerous long-range
pairs from diluting local failures. Distance-based molecular models explicitly motivate preserving local atomic
neighbourhood geometry ([Simm & Hernández-Lobato, ICML 2020](https://proceedings.mlr.press/v119/simm20a.html)).

| Local-pair MAE | V3 interpretation |
|---:|---|
| ≤0.01 Å | exceptionally faithful local distance reconstruction |
| ≤0.03 Å | **HIGH_FIDELITY** |
| 0.03–0.05 Å | strong |
| 0.05–0.10 Å | **USABLE** |
| 0.10–0.20 Å | weak/coarse |
| >0.20 Å | **INADEQUATE** |

## Element and bond fidelity

Element corruption recovery reports accuracy, macro-F1, per-element recall and a confusion matrix. Macro-F1 is
the gate because overall accuracy can be dominated by H/C/O. `HIGH_FIDELITY` is macro-F1 ≥0.95 and `USABLE` is
≥0.85.

Bond existence reports precision, recall, F1 and AUPRC over the project’s stored positive bonds and sampled
negative pairs. Existence F1 thresholds are 0.95/0.85. Bond order reports accuracy, macro-F1 and per-class recall
for none, single, double, triple, aromatic and other; positive bonds are used for the order metric, with
macro-F1 thresholds 0.90/0.80.

## Descriptor fidelity

Every graph descriptor is reported separately in raw descriptor space with MAE/RMSE and in training-standard-
deviation units with normalized MAE/RMSE. RDKit documents NPR1/NPR2 as normalized principal-moment ratios and
lists Eccentricity, Asphericity, PBF and Radius of Gyration as conformer-dependent 3D descriptors
([RDKit 3D descriptors](https://www.rdkit.org/docs/GettingStartedInPython.html#list-of-available-3d-descriptors)).

The only category aggregation allowed is the existing schema’s `geometry`, `extensive`, and remaining chemical
descriptor partition. The graph-descriptor hard gate uses mean normalized MAE: ≤0.10 high fidelity, ≤0.25 usable.
Raw per-descriptor results remain authoritative, especially for NPR2/Eccentricity and long-tailed Kappa3.

Node regression descriptors use normalized MAE; binary/multiclass descriptors use macro-F1. For each node
descriptor family, the worst group error is gated at ≤0.10/≤0.25 so an easy frequent label cannot hide a weak
rare class.

## Task-aware transfer-ready policy

`TransferReady = OptimizationMature AND TargetAdequate`.

Only active objectives are gated. Every active core objective must reach at least `USABLE`; any `INADEQUATE`
objective makes `TargetAdequate=false`. Diagnostic metrics never independently fail the gate. `HIGH_FIDELITY`
is reported as a stronger level for architecture analysis, not required universally.

The threshold file is versioned. Changing a number, source, metric direction or hard/diagnostic status requires
a new registry version and re-evaluation; old results must retain their original protocol version.
