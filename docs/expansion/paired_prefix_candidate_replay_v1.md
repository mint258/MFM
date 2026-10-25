# Proposed paired10000-row replay: NOT_READY

This implementation has not run. It creates no request, central scope, Slurm
script or submission. The template is NOT_READY. `validate_ready` refuses it
before reading an intent, invoking the CPU guard or touching large inputs. A
READY copy with the existing `prefix_feature_three_cid` scope is also refused.
Root must separately review the future `prefix_feature_paired_10000` parameters
and resources; this proposed name does not add a policy entry or grant authority.

The three-CID candidate evaluation4520555 completed with three passes and a
COMPLETED_NO_MEMORY_DENIAL monitor. The prior545 four tests passed, while its
evaluation failed on stale quota. These are prerequisites only. No10000-row
claim follows from them. The template pins their actual small receipts/logs.

## Comparisons and honest historical coverage

All original raw ordinals1..10000 are replayed independently through the frozen
`screen.features` and the unchanged proposed `features_candidate`. Chemical
rules, RDKit2025.09.5, isotope/stereo policy and unlimited heavy-atom definition
remain the frozen implementations. The candidate's existing byte/AST proof is
checked again and its exact code must match both actual545 and555 authorities.
The full X414 COMMON_PENDING proof is revalidated through the frozen full-gate
validator. No new chemical function is introduced.

Historical427 contains8197 complete deduplicated feature dictionaries and8198
CID/full-key/ordinal aliases. It does not contain a separate complete feature
dictionary for the one duplicate alias. The replay therefore reports distinct
proofs: all8197 stored full dictionaries versus current legacy output, all8198
alias identities versus original rows, and all8198 current independent legacy
versus candidate dictionaries across every field including generic ring systems.
The duplicate alias is explicitly recorded as having no separate historical
feature dictionary. No missing field is reconstructed from the old3CID trace.
JSON value/type comparison also distinguishes integer1 from booleantrue.

All1802 original rejections are bound from the small complete JSONL. All1049
chemical rejections must retain exact reasons and their order in both feature
calls. All753 prior IDENTITY_OR_FEATURE_FAILED records receive their own table
row and retained historical error, full current legacy/candidate outcomes,
tracebacks and fragment audit. A recovery is confirmed only if the exact prior
error is reproduced, the traceback locates the unchanged old SanitizeMol call,
independent legacy fragments fail, and all proposed generic fragments preserve
heavy-atom adjacency. A different prior error, changed chemical reason,
unlocalized recovery, or old-pass feature drift is a mismatch. Still-failing
proposed features remain classified and retained; they are never silently
promoted to a permanent exclusion. Evaluation success requires all753 confirmed
recoveries and zero mismatches after complete coverage.

## Bounded execution prepared for separate review

The runner uses16 spawned processes, a16-party startup barrier,64-record batches,
and at most32 submitted batches. It records actual PID coverage and requires all
16 workers to process records. Parent and workers use unchanged centralv2 local
checkpoint calls. Work drains naturally on failure; there are no signals,
automatic retries, approximate identities or downstream labels/features.

Root must bind small metadata/code references (each<=2MiB), including original
427 plan/receipt/rejections, raw producer, full414 proof bundle, actual545/555
evidence, quota publisher and complete current import chain. `data_references`
must contain only the original1.49GB raw and the12,017,664B historical SQLite.
Both receive complete current SHA checks and stable current frames inside the
allocation. Raw inode/mtime/size/UID must also match427; only cross-node device
number may differ. The historical SQLite opens immutable/read-only and must
have no active sidecar. Original inputs are stat-checked again after replay.

A new output directory under artifacts/expansion/diagnostics is required.
`paired_prefix_evaluation.sqlite` stores every paired case, all753 error cases,
every mismatch, and proposed unreleased feature/alias rows. The historical DB
and pool are never changed. The new disposable diagnostic DB uses journalOFF to
avoid a second DB-sized rollback file; failures are retained, never resumed or
accepted. Success requires integrity_check, normal close and full output SHA.
Page count reserves8MiB from the science cap for receipts/metadata; intermediate
and final total-byte checks preserve a4MiB receipt/failure margin. The template
proposes a maximum256MiB science cap, plus a separately declared32MiB combined
local/global guard budget. This is an output bound, not a measured output size.

Memory/node/wall requests are deliberately unmaterialized. A future request must
use16CPU, <=1h and independently reviewed central policy; its total output budget
must equal science cap+32MiB. There is no measured paired10000-row wall/RSS
profile yet, and1h is an upper bound rather than a prediction. Fresh real quota
is checked at start and again after input hashes, with the200GB reserve.

## Pending Root-only verification

New tests are three boundary methods: refuse NOT_READY/three-CID plans before
guard or data access; distinguish stored-row/alias/current-pair comparisons and
catch field/type drift; preserve chemical reason ordering and classify every
error outcome. They use synthetic dictionaries and mocks, not RDKit or raw data.
No test was run by the author. Root may run the finite unit entry under an
appropriate separately authorized environment:

`python -B -m unittest workflows.expansion.test_candidate_prefix_replay_v1 -v`

The future scientific CLI, unusable with this NOT_READY template, is:

`python -B -m workflows.expansion.candidate_prefix_replay_v1 --plan ABS_READY_PLAN --root-submit-intent ABS_NEW_INTENT`

Root still needs static/source review, actual boundary evidence, a separate
scope/decision, a fresh READY plan with actual code pins, and an immutable new
request. None is generated here. Even a successful replay keeps repair_applied,
pool_modified and all pool/decontamination/UFF/training/full-source releases
false, with COMMON_PENDING retained.
