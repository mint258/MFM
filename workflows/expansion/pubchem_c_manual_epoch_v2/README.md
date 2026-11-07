# Explicit, manually reviewed PubChem metadata epoch

SourceOnly. This v2 package has not run its three fixtures or any science. The actual v1 source3 C0 (1884950) is historical evidence only and cannot satisfy v2 source validation. It does not approve a grant or release a pool. Root must independently review the ten deployed source files, obtain the new source3 actual Alpha C0/account/raw, then approve one new finite grant and one actual cutover/adoption review. No future hashes, job IDs or results are manufactured.

The original grant, deadline1793149349.1500428, state, 500-part partition, ordinal claims, producer13 sources and scientific thresholds remain unchanged. Each later epoch is a separate explicit Root decision of at most20h, with its own fixed deadline and new state directory. This package never creates another epoch when that deadline arrives. Future manual epochs can use the same commands with the actual predecessor grant/state/identity; historical origin grants and states are carried explicitly. Existing sources, failed costs, technical unknowns and output files stay in place.

## Fixed execution surfaces

Metadata coordinator: `python -B -m pubchem_c_manual_epoch_v2.controller --epoch-review ABS --root-run-reviewed-manual-epoch --reason TEXT [--single-cycle] [--observe-only]`.

It runs on the actual Alpha login endpoint218.192.171.238:22/UID1264. It only reads small metadata, source and Slurm state; producer journal/features DATA are exact locators, never opened or hashed here. The source3 CPU protocol is `pubchem_c_manual_epoch_source3_alpha_v2`, plan `SECONDARY_PUBCHEM_MANUAL_EPOCH_SOURCE3_PLAN_V2`, proof `SECONDARY_PUBCHEM_MANUAL_EPOCH_SOURCE3_STARTUP_V2`, stage `PUBCHEM_MANUAL_EPOCH_SOURCE3_NO_DATA`, module `pubchem_c_manual_epoch_v2.fixture_cpu`. Its literal `PARAMETERS` is the fixed scope, including supported effective maximum12 and non-C reserve16;16CPU/no_mem/600s/2GiB/analysis/pilotfalse/storage7, DATA=[] and parents=[]. There is no range, Budget, ProcessPool or claim dependency in that fixture stage.

The three queue files expose only this source3 protocol. Their controller is byte-identical to the existing v13 controller. Future scientific children continue through the original `secondary_cpu_readonly_pubchem_cont_v1` helper and original13-source consumer, with their actual original shard key, seed, claim and250000-row bounds (last shard remains the original partial size). No new scientific scheduler or producer is introduced.

## Root sequence

Set literal Alpha paths for these shell variables. They are examples, not actual generated evidence:

```
PY=/gfshome/alpha/codex_data_v1_20261026/chemprop_compatible_v2/bin/python
ROOT=/gfshome/alpha/codex_data_v1_20261026
OLDGRANT=ABS_EXISTING_ROOT_GRANT
OLDSTATE=ABS_EXISTING_STATE
OLDLAUNCH=ABS_ACTUAL_LAUNCH_METADATA
```

1. Deploy the ten files by exact bytes. Make an unsigned source template:

```
$PY -B -m pubchem_c_manual_epoch_v2.epoch source-template --output ABS_SOURCE_TEMPLATE
```

Root independently signs a new copy with schema `ROOT_PUBCHEM_MANUAL_EPOCH_SOURCE_REVIEW_V2`, status `ROOT_APPROVED_EXACT_METADATA_SOURCES`, reviewer `root`, nonempty reason, exact new10 refs and unchanged scientific13 refs. Other template fields stay exact.

2. Generate the source3 candidate independently of any range/cutover:

```
$PY -B -m pubchem_c_manual_epoch_v2.fixture_cpu --metadata-source-review ABS_SIGNED_SOURCE_REVIEW --authority ABS_REAL_ALPHA_AUTHORITY --node compute-0-6 --plan-path ABS_NEW_PLAN --stage-output $ROOT/artifacts/pubchem_manual_epoch_source3_alpha_v2/epoch1 --proof-path ABS_NEW_PROOF --metadata-output ABS_NEW_CANDIDATE_DIR
```

Root signs the exact scope candidate in a separate file. Repeat with a fresh `--metadata-output` and `--scope-review ABS_SIGNED_SCOPE` to materialize the actual plan at the original still-absent `--plan-path`. Root must also create the existing generic queue-source review for these exact new adapter/controller bytes (separate from the metadata source review above). The queue CLI is unchanged from v13:

```
$PY -B -m secondary_cpu_readonly_pubchem_epoch_v2.controller submit --producer readonly --input ABS_NEW_PLAN --authority ABS_REAL_ALPHA_AUTHORITY --storage-review $ROOT/control/secondary_cpu_queue/storage_scope_v7_pubchem_uniform_index_copy_v1.json --controller-review ABS_NEW_GENERIC_QUEUE_SOURCE_REVIEW --output ABS_NEW_QUEUE_DIR --node compute-0-6 --job-name ROOT_NEW_SOURCE3_NAME --reviewer root --wall-seconds 600 --max-poll-seconds 90
$PY -B -m secondary_cpu_readonly_pubchem_epoch_v2.controller resume --output ABS_SAME_QUEUE_DIR --max-poll-seconds 90
$PY -B -m secondary_cpu_readonly_pubchem_epoch_v2.controller account --output ABS_SAME_QUEUE_DIR
```

`resume` only observes the same submitted ID; it does not submit again. These are Root's later commands, not commands run by this SourceOnly delivery. Actual invocation is16CPU/no_mem, fresh Alpha proof and storage7. Record actual source3 receipt/account/raw; a metadata exit or pending source job is never a C0. The actual receipt is `PUBCHEM_MANUAL_EPOCH_SOURCE3_CPU_RECEIPT_V2` and tests_run must be3, all error/skip counts0. The runtime inverse validates old v4 full-byte/AST inverse, original science13 inverse, direct original closure/queue/state objects, and byte-identical queue controller. It also checks the exact complete text and AST inverse of the two new resource functions against their actual original functions. All ten predecessor/source pairs retain complete changed old/new spans, reversible bytes and AST hashes. New registry/lifecycle methods are explicitly new coordination code; their AST hashes are recorded, not claimed equal to old methods.

3. While the predecessor is actually live, pin its exact UID/PID/boot/start/full argv/cgroup and immutable binding:

```
$PY -B -m pubchem_c_manual_epoch_v2.epoch pin-predecessor --pid ACTUAL_PID --predecessor-grant $OLDGRANT --predecessor-state $OLDSTATE --predecessor-launch $OLDLAUNCH --output ABS_NEW_IDENTITY
```

The original v4, old manual v1 and this v2 CLI are the only accepted metadata modules. A different UID or failed identity read cannot be treated as proof of death. A PID reused by another identity is recorded explicitly. If no live pin was captured, this package fails closed; Root needs a separately reviewed actual identity source rather than inventing one.

4. Create a proposed new grant, using an explicit Root-chosen absolute deadline:

```
$PY -B -m pubchem_c_manual_epoch_v2.epoch grant-candidate --predecessor-grant $OLDGRANT --predecessor-state $OLDSTATE --new-state ABS_NEW_STATE --epoch-id epoch2 --deadline ROOT_CHOSEN_UNIX --max-nonterminal-C ROOT_EXPLICIT_1_THROUGH_12 --source-review ABS_SIGNED_SOURCE_REVIEW --output ABS_NEW_GRANT_CANDIDATE
```

Root must independently sign a new grant copy: original range schema/status `ROOT_APPROVED`, reviewer `root`, reason in `delegated_template_reason`, explicit actual authorized time and deadline with duration>0 and<=72000s. Review the same population/13 source refs, actual three-node CPU pool/spare16, resource authority/storage7 and old prerequisite evidence. Root must explicitly review `manual_resource_epoch.effective_max_nonterminal_C_parents` (integer1..12), `root_explicit_resource_cap_override=true`, historical `base_v3_max_nonterminal_C_parents=6` and `reserved_non_C_cpus=16`. The untouched original13 validator requires the top-level `max_nonterminal_C_parents=6` as a historical v3 ABI frame. That old field is not effective cap12 authority; only this independently approved v2 override is. There is no default12 or count remapping. The added `manual_resource_epoch` binds the actual predecessor grant/state/deadline, exact previous origin refs, new distinct state and new metadata source review. Its previous-grant list omits the new grant itself; the runtime adds the actual new reference after the signed file exists, avoiding a self-hash cycle. Root may prepare this finite decision before old expiry, but no cutover can occur before the old fixed deadline and stopped predecessor.

5. After old deadline, capture stable cutover metadata:

```
$PY -B -m pubchem_c_manual_epoch_v2.epoch capture-cutover --predecessor-identity ABS_NEW_IDENTITY --output ABS_NEW_CUTOVER
```

Old identity still live or global finite500 lock busy yields WAIT and no output/dispatch intent. The same global lock is held throughout capture. The last actual event must show finite deadline/drain; immutable old binding and two equal whole-small-metadata inventories are retained. Earlier epoch state inventories are also bound. Old exit code remains UNKNOWN; there is no requirement or claim of exit0. No signal is sent. Permission/unknown/inconsistent identity or state does not become absent.

6. After actual source3 C0 and Root-signed new grant, make unsigned actual adoption/review:

```
$PY -B -m pubchem_c_manual_epoch_v2.epoch adoption-candidate --new-grant ABS_SIGNED_NEW_GRANT --predecessor-identity ABS_NEW_IDENTITY --cutover ABS_NEW_CUTOVER --source-review ABS_SIGNED_SOURCE_REVIEW --source3-receipt ABS_REAL_SOURCE3_RECEIPT --source3-accounting ABS_REAL_SOURCE3_ACCOUNT --cost-checkpoint ABS_ACTUAL_ALPHA_COST_CHECKPOINT --output ABS_NEW_CUTOVER_REVIEW_CANDIDATE
```

It scans actual registered original parents and claims only; old0..50 closures, failed1884853 and repaired1884855 plus QA0 remain separately charged. Every52..499 parent is checked and closed with its own origin grant using the direct original `close_new/account_row` objects. Running parents stay actual running; FAILED/UNKNOWN/consumed intent without registration never become new keys. Unclosed physical claims or contradictory cache/registration make HOLD. The helper writes new per-shard small adoption entries and a bounded top manifest; it never updates old state/cache. It may create genuine sacct/account metadata through the original helper for real terminal parents. Root approves a separate review with schema `ROOT_PUBCHEM_MANUAL_EPOCH_CUTOVER_REVIEW_V2`, status `ROOT_APPROVED_MANUAL_EPOCH_CUTOVER`, reviewer `root`, nonempty reason; all refs remain exact.

The default `explicit_old_held_admissions=[]` permits adopting already running/closed parents, not starting a held old parent after its grant deadline. If Root deliberately authorizes that existing held job under the new resource epoch, insert its exact five-field small metadata record: `shard_index`, actual `job_id`, `queue_request_reference`, `submission_reference`, `origin_grant_reference`. It must already exist in the captured adoption and is rechecked against actual request/submission/plan. No resubmission or old plan/proof rewrite occurs; a new immutable resource-adoption event records the new review before the original observe helper operates on that same job.

7. Observe one cycle first:

```
$PY -B -m pubchem_c_manual_epoch_v2.controller --epoch-review ABS_SIGNED_CUTOVER_REVIEW --root-run-reviewed-manual-epoch --reason ROOT_TEXT --single-cycle --observe-only
```

This writes only the new state/binding/actual metadata closures and observations. It never calls prepare/submit or releases an existing held job. Root then explicitly starts finite live using the same arguments without `--single-cycle --observe-only`. A resume uses the same grant, new-state binding and deadline; changing those requires another separate manual epoch review, never editing the old binding.

## Limits and failure semantics

The explicit v2 effective maximum1..12 counts every actual registered nonterminal C parent, including PENDING and RUNNING across all origin grants. Cap12 is an upper bound, not a promise that the current cluster has twelve free16CPU slots. Original contiguous16 non-C CPU reserve, actual all-user free CPUs,16CPU/no_mem/8h per child,200GB storage7 freshness,16MiB metadata cap, fixed500 partitions, claims and quality are preserved. Source3 is600s; each scientific child remains original28800s, within original48h maximum. Deadline stops new metadata dispatch; already running science drains naturally. New state is protected for the full foreground lifetime by the same global finite500 lock. Original inner controller serialization is retained for central helper calls. Submission/metadata failures HOLD with immutable intent/evidence and no automatic retry, cancellation or cleanup. Any subsequent Root action must reconcile that actual existing parent/key.

C0 closure means the original rows physically closed, not chemical identity acceptance or pool release. Technical unknown rows are preserved distinctly. Costs reported here are C physical production parents+QA0+this epoch's source3, with endpoint/UID/job deduplication; the independent actual global accounting checkpoint and prior fixture refs remain explicit. This subtotal is never presented as the global ledger. No missing exit code or unobserved parent is assigned zero cost. Finite metadata exhaustion HOLDs without deleting evidence. Final decontamination/Common/1M population acceptance remains a separate workflow gate.
## Exact resource changes and actual proof chain

`policy.resource_decision` is a complete copy of original continuation-v3 `state.decision`, with only its new name/explicit cap argument and int1..12 guard, plus forwarding that actual cap to the new resource next-shard function. `policy.resource_next_shard` copies the old finite500 `next_shard`, changing only name, cap domain and associated error label. Its two-first-actual-C0 gate, blocked statuses, ordered ordinal search and no-retry semantics remain exact. The source3 job restores both full original source texts and ASTs by declared inverse substitutions; it does not pretend these resource functions are unchanged original objects. `choose_node`, original initial gate/BLOCKED and all original closure/account/materialization objects remain the original imported objects.

Before a new intent, an immutable decision event records the real number of known nonterminal registered C parents, Root's effective cap/reference and current all-user free CPU observations. Opaque/unknown parents never get relabelled as zero or as fewer real parents: they HOLD before dispatch. A separate conservative slot count is reported alongside the known count. Before releasing an existing held job, the controller rechecks current free CPUs, contiguous reserve16 and actual cap and writes `ACTUAL_PUBCHEM_EFFECTIVE_RESOURCE_PROOF_V2` under the new state. It binds the exact Root epoch review/grant, full metadata identity, original producer-origin grant, request/submission and actual free CPU snapshot. It then calls the unchanged original observe helper. The original producer startup proof remains immutable and is separately pinned in an event with the new resource proof/authority. The new effective cap is therefore explicit in the Root grant, review, dispatch decision, held admission and resource proof; it is never asserted by rewriting an old science proof.

Original producer proofs still use the original8-base startup schema and scientific13 sources. They pin the exact per-shard scope and original grant; a new producer's scope pins the new Root grant with the explicit resource override. An adopted already-held old producer retains its original origin and requires Root's exact extra admission record. This separation is intentional: no old authorization for6 is claimed to authorize12, and no original scientific source/once state is modified. New binding, launch and live snapshot metadata also carry the effective cap and reserve16.

Only after the immutable predecessor deadline and natural metadata exit can cutover capture succeed. There is no early-cutover, stop-file writer, kill, signal, cancellation or automatic renewal path in v2. Root should pin the old live identity before it exits; pinning requires the actual allowed module, exact old grant/state CLI, UID1264, PID/start ticks/boot/full argv/cgroup. A dead or reused PID does not fabricate an exit code. Both the actual global500 lock and unchanged old state inventory are required again at new startup. Root must independently inspect any predecessor HOLD, failed or unresolved parent; new state does not make its ordinal eligible again.

## Untested delivery and remaining actual prerequisites

The only delivery checks performed here are static source reads, source hashing, declared text substitution checks and ZIP-entry verification. No Python, AST parser, test, scheduler, scientific body or network execution is performed by this handoff. Root must run the new exact three-method CPU source protocol and require actual C0/raw/accounting before signing the new epoch review. The tests cover: mixed-origin immutable parent/cost union; consumed/unknown and real cap1..12 versus the truthful old6 result plus changing CPU/reserve; and finite after-deadline cutover/global-lock wait and original-object identities. Actual Root authority, source approval, generic queue approval, source3 C0/account/raw, predecessor live pin/launch/grant/state, later natural exit/cutover, current capacity/storage and cost checkpoint must all be supplied as genuine references. No future job/proof/PASS is included.