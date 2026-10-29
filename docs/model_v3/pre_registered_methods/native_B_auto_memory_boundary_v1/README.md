# Native B one-time dispatch boundary (source only)

This finite Root helper uses only the existing phase `.dispatch.lock` and original controller mutex. It does not submit, signal, mutate the old source or change an active segment. The original controller has no cooperative stop marker: its next `submit-next` takes the dispatch mutex nonblocking and fails before observing resources, preparing a lease, writing intent or calling sbatch when this helper owns that mutex.

Lock fairness is not guaranteed. Another frozen segment may start first. The helper reports the actual latest closed slot, not an invented exact slot026 stop. It waits at most9000s, then requires the existing latest segment C0/closed supervisor and all submitted attempts closed, no unresolved intent/future lease, original PIDgone and original controller mutex available. Controller exit has a90s bound. It holds the boundary at most3600s for Root review/publication/adoption. Timeout or unknown metadata fails with an explicit status and releases its own locks; no automatic retry or submission follows. Historical failed attempts are retained, and the latest segment must be C0.

Root may launch only after reading this source. Use the actual machine hashes in `source_pins.json`; `--source-sha256` is the boundary_gate.py SHA and `--controller-identity-sha256` is the dependency ref for the original identity.json. The Python is the existing metadata Python, never a project model interpreter command. Example (Root supplies the two actual SHA strings):

```bash
PY=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python
S=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/native_B_auto_memory_boundary_v1_source
O=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/native_B_auto_memory_boundary_actual_v1
"$PY" -u -B "$S/boundary_gate.py" --output "$O" --source-sha256 SOURCE_SHA --controller-identity-sha256 IDENTITY_SHA --minimum-slot 26 --wait-seconds 9000 --hold-seconds 3600
```

Root's normal hidden/background process wrapper can retain stdout/stderr. This is one metadata-only mutex holder, not a training loop or dispatcher. The command stays active while holding locks. The old active segment and controller are untouched until they naturally reach the boundary. The helper does not query Slurm or independently reverify the scientific payload: it binds actual existing terminal/supervisor/closure metadata. SDK and B acceptance are not claimed. All output is small Root operational metadata in the explicit new N-level output, not excluded scientific output or an unbounded log.

While status is `BOUNDARY_HELD_PENDING_ROOT_EXPLICIT_RELEASE`, Root prepares and publishes the new resource-only operations and independently verifies them. Root then writes exactly one `RELEASE.json` (exclusive create, no overwrite) in that output directory:

```json
{"schema":"native_B_Root_dispatch_boundary_release_v1","authority":"ROOT_ACTUAL","boundary_receipt":{"path":"ACTUAL_BOUNDARY_HELD.json","bytes":0,"sha256":"MACHINE_VALUE"},"new_operations_source_pins":{"path":"ACTUAL_SOURCE_PINS","bytes":0,"sha256":"MACHINE_VALUE"},"new_operations_adoption":{"path":"ACTUAL_ADOPTION","bytes":0,"sha256":"MACHINE_VALUE"},"method_publication":{"path":"ACTUAL_PUBLICATION","bytes":0,"sha256":"MACHINE_VALUE"}}
```

The displayed rawrefs are format placeholders, not executable inputs. Every byte count/SHA must come from each real file. The boundary helper checks exact raw bytes only for these new refs; it does not certify that the new operations are ready or published. Root owns those separate admission checks. After `ROOT_EXPLICITLY_RELEASED_READY_FOR_SEPARATE_ROOT_SUBMIT`, wait for this helper's actual exit before the separately explicit new submit-next. No new controller/automatic training loop is supplied here. An expired hold leaves the old controller stopped and requires Root reconciliation; a wait failure may leave it live, as recorded. Never signal the old PID or change its source to force this procedure.

The source has not been run, AST-checked or used to take either mutex by its author. Root owns source review and actual launch.
