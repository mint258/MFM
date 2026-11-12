# CPU performance measurements

Original job 4530218 was verified PENDING and cancelled after the user authorized fewer CPUs. Adaptive observer PID3251303 on compute-0-20 now selects an idle authorized GPU and 4–16 available CPUs before submission. No mainline jobs changed.

Current status: WAITING_FOR_IDLE_AUTHORIZED_GPU. No timing CSV or flame graph has been produced yet. adaptive_state.json records the current process identity and live inventory; the original submission files preserve the retired plan.

Run artifacts will be written to `/lfshome/zixiao/model_v3_perf_20261112/step1_<actual_job>/`.
`step1_queue.txt` and `step1_submission.txt` are actual scheduler output; `timer_units.txt` records the two timer unit tests.

The runner stops after profile (100 warmup + 1000 measured updates) and baseline (1000 updates). It does not select optimizations or launch equivalence/concurrency work without the profiling evidence.
