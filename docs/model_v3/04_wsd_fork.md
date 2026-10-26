# Explicit WSD fork controller, first revision

This delivery adds only `phase1/v3_wsd_fork.py`,
`tools/model_v3/run_wsd_fork.py` and their test/document. The parent trainer,
sampling, safe save/load, proxy runner, B protocol, H0 bridge and selector remain
unchanged. No Python/test/SSH/job/commit was run by this agent. These WSD tests
are prepared, not passed evidence.

The parent proxy implementation was actually tested separately: Slurm4521013
COMPLETED/0,43 passed including20 new proxy cases; source checker4521017 also
COMPLETED/0. Its committed source is
`5ac19e805a9ebab9dca516ba7201bae0666d2515`. That result does not certify WSD,
real D3 integration, scientific proxy curves or seed-pair SD.

## Admission and allowed change

The child uses the existing source-bound proxy request and all its default
scientific admission checks: clean committed actual HEAD/tree, rehashed runtime
sources, accepted final D authority hook, explicit Root admission, registered
scope/budget/validation and decision policies,6x512, declared precision/view
policy and physical device. The new CLI defaults to real input and rejects drafts.
Engineering still requires `--input synthetic --engineering-only` plus matching
immutable markers; it cannot enter scientific selection. No new D schema or
scientific threshold is defined.

The existing configuration gains exactly this seed-independent `wsd_fork` policy:

- `schema = model_v3_wsd_fork_policy_v1`
- `parent_configuration_identity_sha256` (only the parent's top-level training
  seed is excluded), `fork_samples`, positive explicit `decay_samples`, and
  finite `minimum_ratio` in[0,1]. There is no default scientific decay length or
  platform criterion.
- `source_additions`: exact SHA map of additions relative to the parent's actual
  runtime. Only the new WSD module/CLI are admissible additions. Existing parent
  files may not change or disappear. The CLI is separately pinned here because
  the unchanged proxy runtime collector already covers package Python files but
  names only its original CLI.
- Explicit bounded `family_ledger_bytes` (2–8MiB) and `maximum_forks` (1–8).

No other fields are accepted in this policy. The child retains the complete
parent model/heads, groups/fields/losses, optimizer options, input projection,
normalizations, corruption seed/epoch, fixed validation and populations,
precision, execution and resource/count/time/recovery caps. Allowed differences
are runtime additions, the consumed-draw final budget and panel/validation point
lists, and the registered short decay schedule. Parent original milestones stay.
Scientific mode additionally requires an exact registered `wsd_fork` policy blob,
mapped local/public trees, and actual Root successful parent terminal evidence
bound to the parent checkpoint. Root must seal parent **training** before the
fork; independent parent panel ACKs may still append to its canonical ledger.
Nested WSD forks are unsupported and reject.

Seed-specific provenance belongs in `request.fork`: raw-bound original parent
request, complete wrapper checkpoint, actual canonical ledger and segment
registration, immutable `family_root`, and scientific Root parent terminal
receipt. Scientific Root admission binds the complete child request including
these references. Actual parent checkpoint hashes are absent from the shared
configuration and recipe bindings: the existing seed-SD identity also compares
bindings, so inserting those hashes there would prevent a legitimate two-seed
comparison. Only the common WSD policy hash is a new recipe binding.

## Restore first, derive child second

The controller verifies the parent wrapper/intent/payload/COMPLETE hashes and its
actual canonical registration. It reconstructs the original parent experiment
contract in new job-owned staging metadata and invokes the **unchanged strict
parent trainer loader**. Parent files and ACKs are not modified or copied. The
full parent contract must match before restoration; a partial or pending-log
checkpoint cannot be relabelled as a stable point.

For scientific parents each original runtime file must match both current bytes
and the historical committed Git blob/tree. Current child clean-source validation
is independent. Engineering parents bind raw bytes and explicitly do not claim
their base commit contains dirty code. A changed shared source requires the
frozen parent implementation or a separate reviewed migration; arbitrary drift
is not excused as a fork addition.

The parent must be in its declared WSD stable interval:
`warmup_samples <= fork_samples < parent_decay_start`. A cosine checkpoint, a
checkpoint still warming up, or one already decaying rejects. The restored
actual LR must equal its parent scheduler base LR. The child scheduler uses that
actual LR as its base and starts its cosine decay at the same consumed sample
clock, ratio1 at the fork. Final budget is exactly `fork_samples + decay_samples`.
No artificial zero-LR first step is introduced.

The child retains the **same model, AdamW and provider objects**, complete
optimizer state, committed provider state, RNG, update count, consumed sample
cursor, saved milestones, log cursor and fixed validation state. Its explicitly
new sampler budget changes the sampler contract hash, while the original
seed/ordinal/index/conformer/geometry draw rule stays. The provider receives the
new correct sampler hash; physical draws are preserved. Validation prefix
references are retained as the common trajectory, not reinterpreted as new
post-fork validation. Fresh child SDK runs record the actual saved parent run.
Both parent and child final-authority requests are verified; a temporary child
provider is closed and never replaces the parent's restored state.

The original safe checkpoint writer and generic512 H0 bridge remain in use.
`FORK_RECEIPT.json` records the original and child contract hashes, parent binding
and preserved clocks/LRs. After a complete child checkpoint,
`verify_fork_chain()` binds:

`child wrapper COMPLETE -> actual child contract/lineage/config -> family child
registration -> immutable child request -> FAMILY -> exact parent COMPLETE`.

The resulting `FORK_CHAIN.json` contains raw-byte references, not predictions,
member identities, a copied ACK or a scientific success assertion. Root must
verify this complete chain for scientific WSD admission; an isolated payload
does not replace it. Existing strict independent panel ACK validation still
requires matching18cells,1000 bootstrap draws, actual Root successful terminal
and independent native SDK verification. Child receipts remain
`CHILD_FINISHED_PENDING_ROOT_CLOSURE` and never proclaim Slurm C0 or seed SD.

## One bounded family

`family_root` is immutable request provenance, not a freely replaceable CLI
budget. Its small metadata ledger registers child ledgers before SDK/model
initialization; their original launch allocations retain failed SDK/model roots.
Parent plus all registered child job roots, caches/SDK/history, all ledgers,
staging metadata and checkpoint directories are counted once under the original
**joint2GiB** cap. Parent or child partials remain. Global checkpoint **and segment
attempt** limits cannot exceed the original parent plan. Family allocation locks
serialize attempt reservations before SDK/model initialization. Fork counts,
metadata bytes, RSS, physical GPU85% capacity and inclusive<=2h wall stay bounded.
No checkpoint deletion, new budget per segment/fork, or guard expansion occurs.

The original milestone may cause a new initial child snapshot at the fork. That
extra complete payload is intentionally retained and counted; it is not silently
suppressed to improve apparent capacity. Resume first reconstructs the strict
parent-derived child, then invokes original strict child resume under exactly
the same contract. Canonical child ACKs remain separate and cannot roll back.

Actual parent engineering evidence4521013 measured one6x512 payload at
199,149,689bytes, model tensors89,545,204bytes and materialized Adam tensors
109,347,172bytes. Its full-moment planning scenario was268,635,356bytes. Seven
copies of that **specific engineering** payload would occupy1,394,047,823bytes;
nine copies1,792,347,201bytes before SDK, ledgers or other files. Final D heads and
their optimizer states have not been measured. The original conservative
full-moment15%+8MiB checkpoint reserve remains, so a family can safely pause
before its actual serialized payload would physically exhaust2GiB. Root must
preregister viable checkpoint/recovery/segment boundaries after measuring the
actual final configuration. This tool neither proves64M+all forks fit nor
silently relaxes the reserve to make them fit.

## Prepared CLI and tests

No new packages. Root supplies the fixed compute Git tools, existing dependency
overlay and actual owned Slurm allocation with>=16CPUs. CPU engineering has CUDA
hidden. Scientific execution uses one declared locked GPU. Original supervision
must reserve both child ledger and family allowance: for16MiB+2MiB ledgers the
outer output cap is at most2GiB−18MiB, and its existing96MiB child reserve stays.
The child checks that budget environment, all shared roots and actual cleanup.

```bash
PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
ROOT=/share/home/zixiao/descriptor_analysis
TOOL=$ROOT/MFM_model_v3_wsd_fork/tools/model_v3/run_wsd_fork.py
# After an actual explicit engineering parent WSD-stable save:
$PY "$TOOL" prepare-engineering --parent-request ABS_PARENT_REQUEST_JSON \
  --parent-complete ABS_PARENT_WRAPPER_COMPLETE_JSON --parent-ledger ABS_PARENT_LEDGER \
  --parent-segment-registration ABS_PARENT_SEGMENT_REGISTRATION_JSON \
  --family-root "$ROOT/runs/NEW/wsd_family" --output "$ROOT/runs/NEW/wsd_request" \
  --base-code-sha 5ac19e805a9ebab9dca516ba7201bae0666d2515 --decay-samples EXPLICIT_POSITIVE_DRAWS
# Under Root's unchanged validated supervisor; use machine-read request raw SHA.
$PY "$TOOL" run --request "$ROOT/runs/NEW/wsd_request/request.json" \
  --request-sha256 ACTUAL_RAW_SHA --input synthetic --engineering-only \
  --output "$ROOT/runs/NEW/wsd_job1" --lineage-root "$ROOT/runs/NEW/wsd_child_ledger" \
  --family-root "$ROOT/runs/NEW/wsd_family" --lineage wsd-child --segment-id one \
  --until-samples EXPLICIT_TOTAL_CONSUMED_DRAWS
# Fresh job2: same request/family/child ledger/lineage, a new segment-id/output,
# plus --resume-complete ACTUAL_CHILD_WRAPPER_COMPLETE_JSON.
```

`prepare-engineering` creates metadata only and has no scientific default. Real
requests are fully registered/admitted externally; neither this helper nor the
CLI fabricates an accepted data release or parent terminal receipt. Status and
independent ACK use the unchanged proxy CLI against the child canonical ledger.

Prepared CPU test command:
`python -m pytest -q -s current/tests/test_model_v3_wsd_fork.py`.
Expected collection18cases: actual6x512 strict restoration and child two-segment
resume/H0 export; first-LR/Adam/RNG/provider/clock/log/validation preservation;
draw correspondence; changed-source/addition and configuration refusals; actual
nonstable parent checkpoint refusal; shared failed-attempt/fork caps and fixed
family root; common two-seed recipe identity; actual native offline SDK child
and fresh-process resume. Tests never fabricate Slurm job IDs or CPU counts.
All generated evidence is engineering-only, not proof of actual D3, a scientific
calibration, platform/WSD selection, two-seed SD or completed workflow.
