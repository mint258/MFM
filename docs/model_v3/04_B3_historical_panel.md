# Historical B3 TRAIN-only development panel

This is a descriptive 384-dimensional historical sanity check. It does not select or validate the 512-dimensional model-v3 architecture.

Evaluation job 4520437; pretraining seed 0; matched random initialization seed 20261025; readout seed 0.
Only the frozen TRAIN and TRAIN inner-validation panel was used. No final evaluation result is claimed. Seed SD is unavailable from this single pretraining seed.

| Summary | Cells | Mean normalized improvement | Paired molecular bootstrap 95% CI |
|---|---:|---:|---|
| primary_18_cells | 18 | 0.184199 | [0.134870, 0.222489] |
| ridge | 9 | 0.067312 | [-0.008674, 0.115017] |
| linear64_relu | 9 | 0.301086 | [0.255303, 0.339412] |

All means use equal task/readout weights. The 1,000 paired bootstrap resamples group native rows/atoms/isoforms by source molecule; the frozen implementation shares each dataset's draw across tasks and readouts. These intervals are read from the bound result, not recomputed from predictions by this report tool.

| Task | Readout | Candidate error | Random error | Improvement | 95% CI | Molecules |
|---|---|---:|---:|---:|---|---:|
| cyp.2D6 | linear64_relu | 0.576923 | 0.730769 | 0.210526 | [-0.071429, 0.450114] | 26 |
| cyp.2D6 | ridge | 0.538462 | 0.5 | -0.076923 | [-0.667500, 0.250000] | 26 |
| cyp.3A4 | linear64_relu | 0.457143 | 0.685714 | 0.333333 | [0.125000, 0.541761] | 35 |
| cyp.3A4 | ridge | 0.342857 | 0.685714 | 0.500000 | [0.291518, 0.700093] | 35 |
| exp.LogD | linear64_relu | 0.443862 | 0.652815 | 0.320080 | [0.285089, 0.352678] | 1009 |
| exp.LogD | ridge | 0.434926 | 0.592409 | 0.265835 | [0.223565, 0.302351] | 1009 |
| exp.LogS | linear64_relu | 0.41741 | 0.473049 | 0.117618 | [0.086677, 0.145562] | 1025 |
| exp.LogS | ridge | 0.389948 | 0.446302 | 0.126270 | [0.084415, 0.164423] | 1025 |
| exp.Log_HLM_CLint | linear64_relu | 0.374517 | 0.43705 | 0.143080 | [0.115011, 0.171346] | 747 |
| exp.Log_HLM_CLint | ridge | 0.37461 | 0.400812 | 0.065374 | [0.019279, 0.108408] | 747 |
| qm9.U0 | linear64_relu | 8.85684 | 11.7425 | 0.245744 | [0.205966, 0.285783] | 2048 |
| qm9.U0 | ridge | 10.2926 | 7.95489 | -0.293877 | [-0.353936, -0.237723] | 2048 |
| qm9.alpha | linear64_relu | 1.72973 | 2.7484 | 0.370643 | [0.340283, 0.401301] | 2048 |
| qm9.alpha | ridge | 1.97139 | 1.44817 | -0.361298 | [-0.421047, -0.306840] | 2048 |
| qm9.homo | linear64_relu | 0.00675197 | 0.0104182 | 0.351910 | [0.328473, 0.373588] | 2048 |
| qm9.homo | ridge | 0.00778188 | 0.00889921 | 0.125554 | [0.097630, 0.151482] | 2048 |
| qm9.lumo | linear64_relu | 0.00967734 | 0.0252568 | 0.616843 | [0.600751, 0.632089] | 2048 |
| qm9.lumo | ridge | 0.0135926 | 0.0182419 | 0.254870 | [0.231586, 0.277002] | 2048 |

Negative cells: cyp.2D6@ridge, qm9.U0@ridge, qm9.alpha@ridge. Both readout means and all cells remain visible; no readout is selected after seeing results.

Regression errors retain source units (Expansion source-label scale, QM9 energy/orbitals Ha, alpha bohr^3). SoM reports 1 minus native hit@1. Observed SoM inner-validation molecule groups: cyp.2D6: 26, cyp.3A4: 35. These small populations limit confidence-interval stability and generalization; atom counts are not independent bootstrap sample counts.

Core elapsed: 538.575s. Guard wall through SDK finish/cleanup: 541.230s. Guard inclusive one-GPU-hour target: True. This is a measured B3+matching-random panel run, not a speed claim for model-v3 512 or another checkpoint.
Torch allocated-memory high-water counter: 272665088 bytes. Its scope is the evaluator process's PyTorch allocator since its last counter reset; it is not device-global, driver, all-process, or guaranteed H0-phase memory. The report does not infer a whole-run device-memory peak or 85% capacity validation from it.
Independent native SDK verification: VERIFIED. The original core flag is still False; originals are preserved. An independent certificate, when present, is separate evidence.

This report exports only aggregate errors, counts, intervals and run/source identities. It reads no downstream source store, final targets, member-ID list, cached H0 tensor or predictions.

Actual code: `9638f7c461a6a88b6b2469f2c7e9ec8023d276e5`. Published panel/rules preregistration: `39cf4929299cd227a3c361183a4b26c8b1405900`.
