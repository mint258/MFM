# Downstream benchmark execution

Authority: `docs/benchmark/USER_DIRECTIVE_20261119.md` and unchanged requirements of the 2026-11-18 directive and BENCHMARK_PLAN. Current work covers B1, C1, and B2 environment/fixed100 acceptance only.

Data enter through `configs/benchmark_data/B0.DELIVERY.json`. Shared geometry/labels use `SharedB0Reader`; P′ uses `PprimeReader` only after the corresponding source is sealed. No database copies are made. The complete five-deferred-endpoint inventory was verified before fits; its anonymous identities are never published here.

The server worktree remains based on B0 commit `6d056a41f379b921d31017ecfed9ce84d1a5c71a`. GitHub publication uses the connector; the equivalent scripts were submitted inline to Slurm because X: source editing is unavailable. These files archive the submitted logic; they have not yet been merged/deployed into that server worktree. Output paths contain native job IDs. For later fresh submissions, update an input job path only to the corresponding closed producer, preserve the frozen science, and retain the original artifacts.

| Scripts / logic | Current native execution |
|---|---|
| endpoint_catalog.sbatch | 4536889: 96 active candidate endpoints across 11 source groups; no decisions |
| b1_molecular_features.sbatch | 4536908: MoleculeACE and PharmaBench closed |
| b1_more_molecular_features.sbatch | 4536920: five additional source groups closed |
| b1_rf_lightgbm_official.sbatch | 4536910: 80/80 task-model pairs closed, no failures |
| b1_chemprop_official.sbatch | 4536913: fixed-default final-epoch fits in progress |
| c1_d_features.sbatch | 4536892: native D20 + six global D3 fields for eight tabular groups |
| c1_d_lightgbm_moleculeace.sbatch / c1_d_tabpfn_moleculeace.sbatch | 4536894 / 4536899: 30/30 each |
| c1_d_lightgbm_pharmabench.sbatch / c1_d_tabpfn_pharmabench.sbatch | 4536912: 10/10; 4536921 in progress |
| c1_d_lightgbm_tdc_asap.sbatch | 4536929: 23/23, original endpoint masks and split metadata |
| pka_macro_binding.sbatch | 4536926: frozen macro labels, dataset+rawdataID SAMPL join, full-key TRAIN exclusions |
| c1_d_lightgbm_pka.sbatch | 4536951 continues pre-import I/O failure 4536932; native logs retain both job identities |
| b1_rf_lightgbm_tdc_asap.sbatch / b1_chemprop_tdc_asap.sbatch | 4536953/4536954 continue pre-import I/O failures 4536935/4536937; no prior fit was restarted |
| reference_source_schema.sbatch | 4536945: original NMR label/atom interface and reference/PPE/Biogen source metadata for consumers |
| selection.py / test_selection.py | 4536943: 14 new-logic tests passed; no produced model result was replayed |
| B2 scripts | Native acceptance and unresolved attempts indexed in BASELINE_AVAILABILITY.md |

Primary official-split fits use the original TRAIN/TEST population, seed 20261025, default RF/LightGBM settings, 1000 whole-molecule paired bootstrap draws, and a TRAIN-mean reference. Binary tasks predict class-1 probabilities; their RAE uses absolute probability error against TRAIN prevalence. Filter-impact diagnostics fit on the full processable TRAIN and report full/retained/excluded TEST populations separately. Blind ASAP/ExpansionRx main predictions retain all official evaluable TEST rows and use the registered TRAIN-mean fallback outside the domain.

Chemprop uses the default graph architecture and learning-rate schedule, batch64, 50 epochs, and final-epoch weights; no validation or TEST checkpoint selection or parameter search. Regression scaling is fitted on TRAIN only and inverted in prediction. Every completed epoch has a last checkpoint, and completed task fits write closed prediction/result files.

The selection module refuses missing baselines or different evaluation IDs, original labels, molecular groups, or TRAIN references. Its official-split statistics resample the same whole molecules in all models, using 1000 draws. The discrimination SE is for the observed worst-minus-best RAE pair. The <30 rule takes the total labeled points in the filtered endpoint, explicitly supplied by the task binding. For tasks lacking an official split, five repetitions of five scaffold-group folds are mandatory; optical folds group by chromophore scaffolds across every solvent observation. Tukey HSD requires the same complete 25 fold scores for all three baselines. The final B1 roster is not yet produced or frozen.

P′ and P′+D remain conditional on B0 sealing; atom-site pKa labels are not inferred from predicted microspecies. Standard NMR uses the original Jonas release, not a DFT-only substitution. No B2 full extraction, B3/B4, pretraining, paid school-server work, or PM7 geometry reconstruction has been launched.
