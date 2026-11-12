# CPU performance measurements

Step 1 job: 4530218 (16 CPUs, compute-0-20, all). Submitted only for the CPU bottleneck task; no mainline jobs changed.

Status at submission: PENDING (Resources). No timing CSV or flame graph has been produced yet.

Run artifacts will be written to `/lfshome/zixiao/model_v3_perf_20261112/step1_4530218/`.
`step1_queue.txt` and `step1_submission.txt` are actual scheduler output; `timer_units.txt` records the two timer unit tests.

The runner stops after profile (100 warmup + 1000 measured updates) and baseline (1000 updates). It does not select optimizations or launch equivalence/concurrency work without the profiling evidence.
