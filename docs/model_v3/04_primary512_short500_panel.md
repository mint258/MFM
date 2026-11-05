# A00 short500 primary512 TRAIN-only development panel

This is a 512x6 toolchain/timing check from the successful A00 native20/500 diagnostic export486. It is not an architecture selection, sufficiently trained model, formal-pretraining completion, or two-seed scientific acceptance.

Evaluation job 4520544; pretraining seed 0; matched random initialization seed 20261025; readout seed 0.
Only the frozen TRAIN and TRAIN inner-validation panel was used. No final evaluation result is claimed. Seed SD is unavailable from this single pretraining seed.

| Summary | Cells | Mean normalized improvement | Paired molecular bootstrap 95% CI |
|---|---:|---:|---|
| primary_18_cells | 18 | 0.126943 | [0.089920, 0.164969] |
| ridge | 9 | 0.087359 | [0.039849, 0.128133] |
| linear64_relu | 9 | 0.166527 | [0.129039, 0.205271] |

All means use equal task/readout weights. The 1,000 paired bootstrap resamples group native rows/atoms/isoforms by source molecule; the frozen implementation shares each dataset's draw across tasks and readouts. These intervals are read from the bound result, not recomputed from predictions by this report tool.

| Task | Readout | Candidate error | Random error | Improvement | 95% CI | Molecules |
|---|---|---:|---:|---:|---|---:|
| cyp.2D6 | linear64_relu | 0.576923 | 0.730769 | 0.210526 | [-0.050000, 0.428571] | 26 |
| cyp.2D6 | ridge | 0.461538 | 0.615385 | 0.250000 | [-0.058824, 0.500000] | 26 |
| cyp.3A4 | linear64_relu | 0.4 | 0.628571 | 0.363636 | [0.136288, 0.583456] | 35 |
| cyp.3A4 | ridge | 0.457143 | 0.685714 | 0.333333 | [0.110965, 0.545455] | 35 |
| exp.LogD | linear64_relu | 0.633945 | 0.672338 | 0.057104 | [0.030310, 0.084268] | 1009 |
| exp.LogD | ridge | 0.529366 | 0.613902 | 0.137703 | [0.101297, 0.173330] | 1009 |
| exp.LogS | linear64_relu | 0.488736 | 0.510338 | 0.042328 | [0.020276, 0.063203] | 1025 |
| exp.LogS | ridge | 0.412108 | 0.446464 | 0.076950 | [0.039852, 0.109680] | 1025 |
| exp.Log_HLM_CLint | linear64_relu | 0.427192 | 0.443007 | 0.035699 | [0.010667, 0.060302] | 747 |
| exp.Log_HLM_CLint | ridge | 0.385715 | 0.402929 | 0.042722 | [0.005599, 0.080384] | 747 |
| qm9.U0 | linear64_relu | 11.968 | 12.3961 | 0.034533 | [0.017138, 0.052124] | 2048 |
| qm9.U0 | ridge | 10.0054 | 8.70014 | -0.150032 | [-0.198163, -0.106284] | 2048 |
| qm9.alpha | linear64_relu | 2.42349 | 2.88336 | 0.159492 | [0.129927, 0.190926] | 2048 |
| qm9.alpha | ridge | 1.94018 | 1.5633 | -0.241080 | [-0.291554, -0.192649] | 2048 |
| qm9.homo | linear64_relu | 0.0088901 | 0.010775 | 0.174934 | [0.146330, 0.201045] | 2048 |
| qm9.homo | ridge | 0.00773464 | 0.00876333 | 0.117386 | [0.091518, 0.142658] | 2048 |
| qm9.lumo | linear64_relu | 0.0158983 | 0.0274339 | 0.420487 | [0.400045, 0.439100] | 2048 |
| qm9.lumo | ridge | 0.0137483 | 0.017609 | 0.219245 | [0.192972, 0.242456] | 2048 |

Negative cells: qm9.U0@ridge, qm9.alpha@ridge. Both readout means and all cells remain visible; no readout is selected after seeing results.

Regression errors retain source units (Expansion source-label scale, QM9 energy/orbitals Ha, alpha bohr^3). SoM reports 1 minus native hit@1. Observed SoM inner-validation molecule groups: cyp.2D6: 26, cyp.3A4: 35. These small populations limit confidence-interval stability and generalization; atom counts are not independent bootstrap sample counts.

Core elapsed: 503.357s. Guard wall through SDK finish/cleanup: 509.288s. Actual outer Slurm allocation: 512s. Inclusive one-GPU-hour observation (both guard and outer allocation): True. The matched random encoder is also 512-dimensional. This timing applies only to this cold-cache checkpoint/panel run.
Torch allocated-memory high-water counter: 391877632 bytes. Its scope is the evaluator process's PyTorch allocator since its last counter reset; it is not device-global, driver, all-process, or guaranteed H0-phase memory. The report does not infer a whole-run device-memory peak or 85% capacity validation from it.
Independent native SDK verification: VERIFIED. The original core flag is still False; originals are preserved. An independent certificate, when present, is separate evidence.

This report exports only aggregate errors, counts, intervals and run/source identities. It reads no downstream source store, final targets, member-ID list, cached H0 tensor or predictions.

Actual code: `9638f7c461a6a88b6b2469f2c7e9ec8023d276e5`. Published panel/rules preregistration: `39cf4929299cd227a3c361183a4b26c8b1405900`.
