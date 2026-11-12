# CPU performance measurements

Step 1 completed in job 4530262 on compute-0-20, 16 CPUs, idle RTX4090 GPU-ec788ed1-7da1-8f93-bb23-b4fdb2018b02. Slurm COMPLETED 0:0, 19:06. Closed raw CSVs and flame graph are in profiling_4530262/. The observer terminated normally after recording completion.

The original pending job 4530218 was retired under the user's reduced-CPU authorization; its original scheduler records are preserved. No mainline jobs changed.

Original 5090 baseline: job4530313 on compute-0-21, 16 CPUs, GPU-c35f2434-9137-9723-1af5-dc69b6295243. All1000 loss rows and recovery.pt were written, but the old fixed-budget observer stopped the parent during shutdown (Slurm FAILED1:0). These numerical updates are retained and not replayed. No optimized child started in that job.

Candidate1 benchmark:4530314, same5090/16CPU/14workers, execution-only no-recomputation flag. Slurm COMPLETED 0:0. Same-card84.53→96.32 samples/s (+13.94%); correctness not accepted yet. Current outputs remain outside Git in /lfshome/zixiao/model_v3_perf_20261112/opt1_no_recompute_4530314/. Equivalence job4530318 exited before spawning either200-step child because the GPU was occupied. No acceptance capture exists; the dedicated equivalence observer waits for a free card. Concurrency work has not started.
