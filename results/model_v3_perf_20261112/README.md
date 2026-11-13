# CPU performance measurements

Step 1 completed in job 4530262 on compute-0-20, 16 CPUs, idle RTX4090 GPU-ec788ed1-7da1-8f93-bb23-b4fdb2018b02. Slurm COMPLETED 0:0, 19:06. Closed raw CSVs and flame graph are in profiling_4530262/. The observer terminated normally after recording completion.

The original pending job 4530218 was retired under the user's reduced-CPU authorization; its original scheduler records are preserved. No mainline jobs changed.

Original 5090 baseline: job4530313 on compute-0-21, 16 CPUs, GPU-c35f2434-9137-9723-1af5-dc69b6295243. All1000 loss rows and recovery.pt were written, but the old fixed-budget observer stopped the parent during shutdown (Slurm FAILED1:0). These numerical updates are retained and not replayed. No optimized child started in that job.

Rejected candidate benchmark:4530314, same5090/16CPU/14workers, execution-only no-recomputation flag. Slurm COMPLETED 0:0. Same-card84.53→96.32 samples/s (+13.94%), but this is not an accepted speedup. Outputs remain outside Git in /lfshome/zixiao/model_v3_perf_20261112/opt1_no_recompute_4530314/.

The unique equivalence comparison4530319 executed old200/new200 on compute-0-22. It FAILED: choices and clocks match, but365 numerical comparisons exceed tolerance and parameter relative L2=0.0012234179502054808 exceeds1e-5. Slurm COMPLETED means the comparison ran, not that it passed. See equivalence_4530319.json; full traces, parameters and losses remain in /lfshome/zixiao/model_v3_perf_20261112/equivalence_4530319/. Cause is unconfirmed. The candidate is abandoned and original head/training construction restored. Do not repeat the200-step comparison. Earlier4530318 exited before spawning either child because the GPU was occupied.

Concurrency and CPU scaling measurements remain pending; no recommended concurrency. At08:26 on Nov13,20's two4090s run external GROMACS,21's two5090s run GROMACS and model H1,22's5090 runs model H2. No active jobs or model-line output directories changed. PR6 remains Draft.
