# Native max-singleton R1: one-run SDK audit and selective transport

This source-only adapter admits only GPU job `4524600`, run `pnugbb4q`, and its original offline SDK. The machine-bound Root closure in `scope.json` establishes the actual GPU C0/source/resource closure. It does not establish an independent SDK audit or online publication. Neither operation has been executed by this package's author.

The original maximum-native-size diagnostic performed 22 optimizer updates: two warmup and twenty observed updates, each containing all three views of the selected native 712-atom record. This is a capacity-shape diagnostic. It is not the original sampler, ABBA, a 20-batch/500-update numeric gate, automatic checkpoint policy qualification, universal 8M capacity coverage, or scientific adoption. A5's failed two-run SDKs are excluded.

## Exact existing components

`dependencies.json` binds the original producer/selector, its frozen source inventory, the actual Root closure, literal749, tap2, the reviewed native framing/CRC/fragment-chain scanner, the v7 protocol, and the original v3 transport/installed-source snapshots. No decoder, monitor, scheduler, or QA framework is added. `one_run_max.py` must be byte-identical to original v3 `one_run.py` except for its single eligibility import. `installed_sources.json` remains a raw-byte copy.

Root preparation reads only bounded source and small JSON metadata and stats the exact SDK and `steps.jsonl`. It does not open either payload, initialize W&B, or upload. SDK/journal hashing and comparison occur only inside the actual 16-CPU allocation. The saved Root proof has explicit cross-host filesystem identity handling; this adapter does not compare a compute `st_dev` with a login `st_dev` or rerun the GPU census.

## CPU audit

`audit_max.py` uses every original `steps.jsonl` row's `SDK_history_projection`. The plain-row adapter follows literal749's actual `A_plain` interface, whose explicit step is the top-level `optimizer_updates`. It checks all 22 sequential steps, the exact producer metric set, source loss/LR/count/resource projections, original selection/tie values, and the code-derived compute-only rates. `update_seconds_before_SDK_log` is an observed saved value; its duration is not reconstructed.

All original configuration fields are compared before history and at EOF using typed comparison. The explicit `SDK_expected_summary.json` must equal the last saved SDK row plus the original nested `capacity_diagnostic` update, and its complete native summary is compared. The original RunRecord supplies run ID/name/project/entity; the project is `mfm_model_v3_development`. The audit independently checks the full native stream, framing/CRC/fragment EOF, one matching RunRecord, exit 0, no uncommitted requests, 22 committed rows at steps 1..22, installed decoder sources, and SDK/journal/source hashes before and after. Native packet count is not equated with history count. Four inline functional metadata checks use the actual existing parser/tap and reject malformed typed input; they create no SDK fixture or separate QA parent.

Limits remain CPU16/16GiB, RSS12GiB, 900-second supervisor and 20-minute Slurm allocation, with original whole-output/private 2GiB limits. SDK input is at most 128MiB, source journal 16MiB, total explicit input envelope 256MiB, one decoder comparison at most 180 seconds, 500,000 native records, 100,000 history rows, 4MiB per native record and 64MiB normalized export accounting. The audit retains only a bounded JSON certificate and metadata, not journal/history contents.

Root's metadata preparation command, after its own source/AST review:

```sh
P=/share/home/zixiao/descriptor_analysis
N=$P/runs/model_v3_20261026
O=$P/runs/model_v3_20261025
S=$N/performance_native_max_R1_SDK_v1_source
PY=$P/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
PIN=$(sha256sum "$S/source_pins.json" | cut -d' ' -f1)
"$PY" -B "$S/prepare.py" --mode audit --pins-sha256 "$PIN" \
  --plan-output "$N/native_max_R1_SDK_audit_request_v1" \
  --job-output "$N/native_max_R1_SDK_audit_actual_v1"
```

The existing submit helper requires its script under `O`. Root may copy `audit_cpu.sbatch` byte-for-byte to `O/run_native_max_R1_SDK_audit_v1.sbatch`, compare its SHA to this inventory, and submit that copy with the generated bindings:

```sh
"$PY" -B "$O/submit_cpu_task_v2.py" --node compute-0-13 --memory-MiB 16384 \
  --script "$O/run_native_max_R1_SDK_audit_v1.sbatch" \
  --bindings "$N/native_max_R1_SDK_audit_request_v1/bindings.json" \
  --output "$O/native_max_R1_SDK_audit_submission_v1.json"
```

The node is an explicit Root choice subject to the original fresh admission checks. The helper injects `MODEL_V3_EXPECTED_NODE` and retains actual idle-16CPU, all-user declared-memory/AllocMem 85%, live MemAvailable and quota admission. Submission ambiguity is not an invitation to repeat submission. Fresh paths are required; failures and original files are preserved.

## One-run selective synchronization

Only after a genuine audit C0 may Root prepare the one-run manifest. Preparation captures fresh exact CPU sacct C0 and checks its actual supervisor, argv/UID, certificate and current source graph. It reuses the already completed original v3 transport method pilot; it does not launch another pilot or attribute that pilot to this run.

```sh
"$PY" -B "$S/prepare.py" --mode sync --pins-sha256 "$PIN" \
  --audit-result "$N/native_max_R1_SDK_audit_actual_v1/RESULT.json" \
  --audit-supervisor "$N/native_max_R1_SDK_audit_actual_v1.supervisor.json" \
  --plan-output "$N/native_max_R1_selective_sync_request_v1" \
  --job-output "$N/native_max_R1_selective_sync_actual_v1"
```

Root may copy `sync_cpu.sbatch` byte-for-byte to `O/run_native_max_R1_selective_sync_v1.sbatch` and use the same helper, memory and explicit fresh node admission with that generated bindings file and a new submission receipt. The original sync supervisor remains 3300 seconds/RSS12GiB, Slurm one hour/16CPU16GiB, whole-output/private 2GiB. The original sequential transport allows at most three runs; this request contains exactly one. Its child/CLI/readback bounds remain 3000/600/180 seconds, with an actual typed-Path invocation persisted before starting the subprocess.

The native project is retained. An empty native entity is resolved from the actual authenticated account and actual default entity inside the CPU transport; no entity/project is guessed. Only the certified SDK is copied exactly and passed to original official v3 one-file sync flags. No sync-all, repair, append, original marker edit, config/summary/state mutation API, SDK deletion, or original SDK rewrite occurs. Auth/CLI/API output stays in owned bounded private storage. Exceptions export only safe type/stage/frame metadata, not messages, credentials or metric payloads.

Online completion requires the actual sync CPU C0 and original remote route/run ID/finished/history-count/explicit step endpoint readback. The independently verified remote scope does not include a second full metric-value comparison. Neither an audit certificate nor the original GPU C0 is an online-success claim. All execution and publication remain Root's responsibility.
