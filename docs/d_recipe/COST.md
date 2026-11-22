# D-family weekly native allocation costs

Snapshot: 2026-11-22T21:48:57.507456+00:00; Slurm query since 2026-11-19T00:00:00 CST. This is the current cumulative week, not a completed-week claim.

| Scope | Parent allocations | Allocated CPU h | One-target GPU-host wall h |
|---|---:|---:|---:|
| Terminal (including failed/cancelled) | 86 | 387.068888889 | 45.749166667 |
| Running prefix at snapshot | 2 | 1.918055556 | 0.000000000 |

Original parent allocations only. Allocated CPU hours are ElapsedRaw × AllocCPUS; parent TotalCPU is unreported and remains unavailable. GPU-host wall is the registered single-target allocation proxy, not GPU busy time, device energy, or monetary cost. Embedded training/readout time is counted once. Batch, extern, observation steps and queue time are excluded.

Scope uses original D work/submission paths plus explicitly registered own D CURRENT job fields. Cancelled-before-start entries retain zero elapsed costs. Failed jobs retain real consumed allocation time. The two live A1 jobs are partial prefixes and will continue accruing cost. No telemetry or scientific arrays were reread.

[Per-job original accounting](../../results/d_recipe/costs_weekly_20261123.json) includes status, source provenance and original unreported TotalCPU values. The short accounting producer 4539190 begins after this input snapshot and is listed separately after closure. No monetary rate has been assumed.

Accounting producer completed normally: job4539190, CPU11, 12s × 1 allocated CPU, C0. Its original supervisor reaped root4190726 and reported children=[]. [Separate post-snapshot parent cost](../../results/d_recipe/weekly_costs_producer_20261123.json); excluded from the table above to preserve the snapshot.
