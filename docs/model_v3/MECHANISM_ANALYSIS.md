# Functional-group mechanism analysis (taskbook v3)

Status: IMPLEMENTED_AWAITING_CANONICAL_INPUTS.
This is a report-only T1 analysis. It cannot change module adoption, the
development panel, enabled pretraining fields or D4.

The producer is `tools/model_v3/v3_mechanism.py`, dispatched by
`v2_run_development.sbatch mechanism CONFIG CPU PYTHON`. It runs on compute-0-20
with the existing 16-CPU request, actual disk/inode/quota admission and continuous
disk guard. GPU visibility is empty. A real output root must first be registered
in the same global model output forecast. No job has yet been submitted.

Required configuration keys:
`output`, `store`, `selection_use=false`, `smarts_definitions`,
`structure_map`, `A0_evaluation_output`, `A3_evaluation_output`.
The last two paths must identify the completed original T1 P evaluations.
X and z come from those evaluations' existing feature caches; no checkpoint is
encoded again. A0 provides mean(H); its z cell is explicitly not applicable.
A3 provides mean(H) and z.

The SMARTS input is a JSON object with `source` naming the existing data-line
definition and `groups` containing exactly 28 distinct `id`/`smarts` pairs in
their canonical order. This interface supplies no replacement definitions.
The structure-map JSON declares `source_population="TRAIN"`, `source` and
`records`; each record carries `dataset_id`, `member_index`, `member_uid`,
`full_inchikey`, `role` and `smiles`. The role must be the original selected
panel's `train` or `train_inner_validation` role. An adapter may project a
delivered canonical source to this interface without changing structures or
SMARTS. RDKit checks bonded-structure identity against the full native InChIKey
when producing presence labels. No bond inference from coordinates is used.

For each panel dataset, the original member cap, optimization split,
inner-validation split and full-molecule grouping are reused. Datasets remain
separate so that different original inner splits are not pooled. All geometry
records present in the existing cache retain their original role; duplicate
records share a molecular CV fold, as in R1. One binary presence label per
canonical SMARTS and the heavy-atom count are computed from the bonded
structure. No downstream task target is decoded.

Each group/representation has an L2-regularized binary logistic probe.
Five-fold regularization selection uses exactly R1's molecule-fold assignment
and seed 20261025 and alpha grid [1e-6, 1e-4, 1e-2, 1, 100].
Features are standardized using each optimization fold alone. The selected alpha
minimizes the mean of five errors (1-AUROC); the smaller alpha resolves exact
ties. The final fit standardizes using all optimization records and predicts
only the original TRAIN inner-validation population. No class weighting or
size-specific hyperparameter selection is introduced.

The solver is deterministic liblinear, C=1/alpha, seed 0, tolerance 1e-4,
maximum 1000 iterations, with its regularized synthetic-intercept convention.
Thus the equivalent objective is summed binary log loss plus alpha/2 times
the squared coefficient norm, including that synthetic intercept.
A single-class optimization/held-out fold, nonfinite prediction or
unconverged fit makes the affected metric unavailable; folds are never
silently omitted. No additional solver scan or diagnostic retry is introduced.

Held-out AUROC is reported separately for <=20, 21-35 and >35 heavy atoms, with
record/group counts and positive/negative counts. A single-class or empty
stratum has null AUROC and an explicit reason. No bootstrap or hypothesis
test is added to this report-only analysis.

Canonical groups run independently using at most the allocated 16 CPU threads;
BLAS/OpenMP stay at one thread per fit. Cell outputs permit continuation
without refitting completed cells. The configuration and full canonical group
definitions bind a continuation to its inputs. Native offline W&B records
the actual producer; full SDK files are archived only after closure.

Only Python AST and shell syntax were checked for this new entry. Actual first
use is acceptance; no smoke run, extra data audit or repeated regression was
added. The mandated single full regression remains reserved for final merge.
No mechanism scores or complete-input delivery are claimed by this document.

2026-11-13: the original A0/P evaluation4530187 and A3/P evaluation4530204 are both complete0:0. The producer will use their existing cache/configuration entries. Canonical28 SMARTS and the source-bound TRAIN bonded-structure map remain pending; no substitute definitions, bond inference, encoder rerun or mechanism job was introduced.
