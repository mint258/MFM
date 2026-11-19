# Authorized downstream execution

Authority: [2026-11-19 directive](../../docs/benchmark/USER_DIRECTIVE_20261119.md). This directory records the actual self-contained Slurm producers used for the initial B1/C1 and B2 preparation work. No databases, computed labels, predictions, weights or caches are packaged in Git.

| Script | Actual run | Result at publication |
|---|---|---|
| endpoint_catalog.sbatch | 4536889 | 8 logic tests passed; full five-marker deferred-policy coverage; 96 candidate endpoints across all 11 source groups |
| c1_d_features.sbatch | 4536892 | 6 interface tests passed; eight tabular source groups closed; reference-group bindings pending |
| c1_d_lightgbm_moleculeace.sbatch | 4536894 | 4 statistical tests passed; 30 of 30 MoleculeACE LightGBM-D fits closed |
| c1_d_tabpfn_moleculeace.sbatch | 4536899 | Running with the same official rows, D features, train-only mean and clustered bootstrap |
| b2_mace_off100.sbatch | 4536880 | 100 shared UFF conformers; 192-dimensional invariant atom descriptors |
| b2_cpu_interface_repair.sbatch | 4536890 | Monroe CPU inference passed; Uni-Mol atomic-interface mismatch remains UNRESOLVED |

The scripts retain the actual remote input/output bindings and model environments used by these jobs. Their first line is a Slurm shell header, so they can be submitted with sbatch after reviewing those bindings. Existing jobs and results are retained; publishing these sources does not resubmit anything.

Molecular C1-D inputs are the 20 unchanged B0 global D fields plus PMI1/2/3, PBF, volume and total SASA from the first accepted shared UFF conformer. Raw F64 values and explicit masks are preserved; unavailable fields remain missing. Atom-wise SASA remains an atom-level field. The derived feature cache is outside Git and references B0.DELIVERY.json and the full-inventory scope proof.

C1 fits use official source TRAIN/TEST membership, default model settings, seed 20261025 and no hyperparameter search. RAE denominators use the applicable TRAIN mean. The 1,000 bootstrap draws resample molecules, keeping repeated/atom rows together. TabPFN uses the public V2 checkpoint; the official per-estimator 10,000-row subsampling ensemble applies only if its training context limit is exceeded.

The candidate catalog is not B1_task_screen.csv and is not a final task selection. No B1 screen decision or completed all-task C1 result table is claimed. Full B1 fitting, remaining C1 models/tasks, pKa macro/single-site binding, complete NMR label binding and the recommended B2 environment matrix remain in progress. B2 full-population extraction, B3, B4 and pretraining remain outside the current authorization.
