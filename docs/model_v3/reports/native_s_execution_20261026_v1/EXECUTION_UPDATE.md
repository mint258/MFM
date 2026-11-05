# Existing Native-S execution: actual readiness and exact operational source

This report records stage 2 infrastructure progress. It is not a model/recipe freeze, a B acceptance decision, or formal pretraining. The scientific core remains execution commit `3d9b1cc0c580dacc9398a5570b0c2fff3e257618`, published as `ce7cbf5776ff546cd47538b120c8f884e2e5867d` with the same tree. The preceding progress publication is `98a0f66b02a7dc65bb54099707b60e8264e0c2dd`.

## Question and preregistration

Can the unchanged 6x512 Native-S implementation safely execute the preregistered fp32/bf16, two-seed, 20,000-update comparison on existing S data? The original scientific rules, sampling, validation grid, matched raw-unit RMSE limit and true two-fp32-seed envelope remain those registered in ce7cbf5. Neither lower pretraining loss nor these engineering checks select a final architecture.

The scope is original TRAIN with 11,104,772 records and fixed PRETRAIN_VAL of 1,024 records / 55,650 atoms, disjoint from the entire TRAIN population. It has no D-5 authority. The model has 22,352,859 parameters, six layers and 512-dimensional H0. All four members start at their own seed's u0; short-profile weights are not a science prefix.

## Actual results

| Evidence | Actual result and limit |
| --- | --- |
| GPU 4521331 / fp32 | C0, 252 seconds; 20 updates, 7,680 base records / 23,040 view graphs; separate VAL 1,024 base records / 3,072 graphs. |
| GPU 4521332 / bf16 | C0, 90 seconds; same counts and consumed input chain. Cold validation differs, so total wall times do not establish stable precision speedup. |
| CPU 4521405 | C0, 595 seconds, 16 CPUs on compute-0-13; all nine sequential readiness stages completed. |
| Native log verification | 29 metadata cases PASS, zero skip; both original SDKs match full expected configuration, summary, committed history, run ID, explicit steps, clean EOF and exit. |
| Safe checkpoint inventory | Four cases PASS, zero skip; both actual payloads loaded CPU-only with weights_only. Future bounds are 392,093,961 / 392,094,025 bytes, each below the 402,653,184-byte cap, with no unknown assumptions. |
| Full accounting pressure | Actual 512 roots / 32,768 JSON records / 536,870,912 metadata bytes; 33,286 inodes exercised under the 100,000-inode protection ceiling. Three measurements of eight complete passes: 194.286751, 177.633536 and 176.036748 seconds. This is the conservative refresh-component estimate, not a model step or GPU throughput measurement. |
| Existing Native V2 admission | Root assembled the same CPU parent's actual components and raw terminal, then the unchanged Native V2 validator accepted the complete evidence graph. No quota reservation or science training is inferred from validation alone. |

The original reader mistook valid literal sibling keys such as `loss` and `loss/s_element` for hierarchical overlap. The new source-bound derivative uses RFC6901 segment escaping and retains true duplicate/ancestor rejection and all typed comparisons. It identifies its actual new SHA; the immutable historical v7 reader is unchanged. Actual 4521401 failed after its original 21 cases passed; that evidence is retained.

Two new terminal metadata projections add the original GPU supervisors and their exact source references from each already-closed Root profile. They retain the original GPU job IDs, raw sacct and original projections; no extra execution or new C0 is invented. This repairs missing references required by the unchanged validator.

## Execution source and decision

The exact source archive is `tools/model_v3/analysis_sources/native_s_execution_20261026_v1/`. It contains source, tests, static dependency inventories and the finite operational policy. The original executed files remain under `runs/model_v3_20261026/`, with raw SHA bindings. Data, checkpoints, SDKs, history mirrors, dynamic requests and private members are excluded. The source snapshot preserves original line endings.

The long policy is an existing-S engineering plan: four members on the same physical 5090, 80 planned 1,000-update segments, finite 96 successful / 12 failed / 108 launch / 216 checkpoint attempts, total durable cap 128 GiB. Per-job limits remain 16 CPUs, 32 GiB requested RAM, 28 GiB RSS, two hours, 2 GiB whole output and 2 GiB private storage. Shared metadata has a 512 MiB ceiling charged conservatively within each whole-job cap. This policy is not recipe_v3_frozen or B-star.

The engineering evidence permits attempting the first science segment after exact source publication and fresh resource/quota/GPU checks. Full 20,000-update curves, every segment's SDK closure, numerical B acceptance and the final training recipe remain uncompleted.

## Other open requirements

CPU C4 diagnostic 4521404 completed all 384 forwards / 48 unhooked plus 48 instrumented cases with bitwise observer controls; the original fp32 case pass count remains 0/48. GPU 4521406 preserved four forwards and 11 fixed-input operations: ten vary under original policy, while all eleven are stable in the separate strict deterministic diagnostic. That does not establish production equivariance. A numerical candidate will be tested separately with the original 1e-5 threshold.

Historical W&B classification 4521403 completed 57 logs: 50 structurally complete, seven incomplete. Authentication is available, but online synchronization is still being validated; original failed exits and incomplete logs are retained. D-final integration, downstream-driven architecture decisions, recipe scans, B-star confirmation, final smoke, tag and PR remain pending. No paid school server or final downstream evaluation was used.