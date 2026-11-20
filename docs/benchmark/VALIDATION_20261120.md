# Downstream benchmark validation (2026-11-20)

Source: b46f22c54648f9698e01885ced05ab3355ae9683, branch benchmark-b1-20261119.

The complete regression of all nine new downstream benchmark test modules and the original optical/gas interface passed: 90 tests, zero failures/errors/skips. Actual CPU step4536999.7 ran on compute-0-10 in1.545seconds. The tests use synthetic fixtures and do not reread or replay scientific results. They cover the selection protocol, frozen25-fold completeness, original-label/ID pairing, blind fallback, native Pprime fields/missingness, original atom maps, GPU admission/locks, C1 reporting and conditional neural confirmation.

Before that regression, the exact251-file source batch passed the required repository checker on CPU step4536999.6: 5,492 paths,3,731 Python files,1,311 server-source references,217 embedded Python programs,11 child programs,zero errors. Export-byte verification was intentionally not rerun for historical source snapshots.

New dispatch logic also parsed61 original neural model source templates. These source checks did not execute model fits or scientific payloads. The cache-order repair and C1 rebind cases are covered by their new interface fixtures and by the repaired producer's own checks.

The unrelated legacy training test suites were not rerun. This validates the downstream implementation and interfaces; it does not declare pending model producers complete. Native regression metadata/logs remain outside Git under artifacts/benchmark_B1_20261119/regression/job_4536999_step_7.

CPU partition metadata currently declares MaxTime=UNLIMITED. Corrected NMR RF/LightGBM job4537318 was still pending at zero runtime when its artificial12-hour request was removed via native scontrol; its current native TimeLimit is UNLIMITED. This preserves the same two CPUs, estimator parameters and one seed, and avoids discarding an unfinished large forest solely at that request boundary. The source driver now leaves the time unspecified.
