# New PubChem no-PM7 UFF and D producer

Source-only implementation, not an executed pilot, populated R/N authority or
dataset release. Existing science, source ledgers and output objects are not
edited. Only Main UID1278 and the existing central-v2 CPU gate are supported;
there is no Alpha identity substitution or new queue algorithm. Root dispatches
this work after S′ and P′ priorities, using an actually available authorized CPU
node and a current account-quota provider mapping. The current finite provider
maps CPU13 only; an allowlist does not create a mapping for another node.

## Scientific seam

The actual frozen `ranking.batch1` has exactly stream/CID/full_key/stream_rank,
R then N, 1,250,000 each. `source` verifies the complete Parquet and immutable
filtered SQLite whole SHA on CPU, joins unique CID **and** full_key, and writes
250 closed source parts. A Root graph-source review must explicitly authorize
the actual screen producer's `features.isomeric_smiles` field and retain
`source_smiles`. No SMILES field is chosen from its name alone. The original
screen/ranking/decontamination release gates are called directly. No existing
ranking, nearest-neighbor math or filtering implementation is replaced.

Root freezes MID content as
`expansion-pubchem:{pubchem_version}:{cid}:{full_key}`. Version/CID/key, source
row SHA and original producer references remain provenance. Files and claims
use only lower-case SHA256 paths, never this potentially unsafe MID text.

The new seam calls default `MolFromSmiles` and `AddHs`, then the original
`stereo_scope` predicate and `FindPotentialStereo`. It does not call the old
PM7-pointer/HoF/fix-stereo `process_task`. Potentially relevant unspecified
stereo has no PM7 truth here: it retains real graph D20 and a technical
`STEREO_REFERENCE_UNAVAILABLE_NO_PM7` result, no invented coordinates/D3,
no graph repair and no new chemical exclusion. Isotopes and specified stereo
are retained. Generated graph/full-key or atom-order disagreement is HOLD.

Embedding seed is exactly original `science.seed_for(newMID, False)`.
20261025 is the original three-order seed and this new profile's sample seed,
not a constant embedding seed. Original N1 `_embedding` is reused with
requested=min(10*10,300)=100: ETKDGv3/thread1/chirality/enforce/no pruning,
maxIterations200, normal coordinates then only its original zero-return
same-seed random-coordinate fallback. No 400-iteration technical retry or
new seed is introduced. Each actual UFF uses native MinimizeTrajectory,
snapshotFreq1/maxIts2000/energyTol1e-6/forceTol1e-4 and the original graph,
stereo and fixed-index proper-Kabsch objects. The original `select_fill`,
0.5Å rule, below-threshold flags and three-order functions are used unchanged.
All original selected native IDs and exact-SHA alias events remain in packets.
Exact-identical coordinates are exported once and cannot create an independent
second geometry. Distinct below-0.5Å fallback geometries keep the original flag.
Insufficient/alias-only results remain technical UNKNOWN, not new exclusions.

D20 uses original RDKit function objects, float64, current HBA, no Kappa.
The original descriptor module and relative schema are loaded under a fresh
isolated package name to avoid unrelated dataset/LMDB builders; old modules
and scientific functions are not modified or monkeypatched. D3 uses original
`corrected_base` on an explicitly new UFF graph/coordinate wire, not a fake PM7
record: PMI1/2/3, PBF_A, volume_A3, SASA_total_A2 plus atom SASA. Original exact
explicit-H Z/edge order is checked. PM7 pointer, HoF, truth and RMSD stay null.
The original wire's historical PM7 documentation is not claimed as the new
geometry's provenance. `compat` independently calls those same original D3
APIs on actual generated coordinates and compares binary64 bits. This checks
the new raw-wire seam; it is not PM7-dependent process equivalence.

## Runtime and retention

The primary module is
`workflows.expansion.no_pm7_uff_d_main_v1.run`, exact eight argv:

```text
PY -B -m workflows.expansion.no_pm7_uff_d_main_v1.run --plan PLAN --startup-proof PROOF
```

Six finite modes are implemented: source, compat32, profile10000, full,
resume and coverage. Native modes allocate16 CPU, no Slurm memory/exclusive,
16 actual initialized worker PIDs, bounded32 pending source molecules, native
threads1. Analysis modes have the same fresh central admission. All3 synthetic
methods finish before DATA, Budget, embedding or UFF. They cover source/sampler/
large locator/atomic once, synthetic D20-D3-stereo wire, and selection/order/
exact-alias/proper-Kabsch boundaries; they never embed or minimize.

The profile is one Python3.11.14 Random(20261025): sample5000 from each R/N
first1.25M, in successive RNG calls, without replacement. Selection order is
retained; dispatch follows source rank for bounded I/O. Compat32 is the first16
of each sample, not completion-order or descriptor-selected. Every source,
failure and property UNKNOWN stays in its original stream.

Cache once binds ranking receipt SHA, original kernel fingerprint, original
release/CID/full_key/source-row SHA. Mode and job are absent. A full original
claim is O_EXCL/fsync committed before dispatch. Normal/fallback/native failure
consume the same claim. There is no automatic native retry. Worker continuation
requires the same still-live parent PID/start ticks, boot, job, node and small
source pins, not an unlimited fresh-proof waiver. A dead parent cannot commit
a new successful packet. Missing packets retain consumed-UNKNOWN status.

Each source and native intention is fsync durable before its call; all returned
candidate final coordinates, energy, native code, iteration/snapshot count and
stereo/finite flags are durable before the next call. A 128MiB framed gzip
journal retains its complete prefix if interrupted, without pretending that a
partial last frame or missing native return is closed. A failure, descriptor
UNKNOWN or deterministic original 1% MID hash retains that entire candidate
journal and source/seed/config/source-code/proof bindings. Successful nonaudit
new transient journals are removed only after complete durable packet commit;
their actual SHA remains recorded. No old source/cache/ledger is removed.
Per-iteration coordinate snapshots are not additionally duplicated; native
trajectory length, all final candidate outputs and complete seeded reproduction
inputs are retained. A raw/software cap produces UNKNOWN/HOLD, not truncation
presented as a complete package.

Workers own 256MiB cache partitions, including raw journal and packet. Parent
reserves all32 roles before calls and replaces them by exact quiescent bytes;
it never scans an active worker tree. Parent family batching is at most128
packets and a 32MiB serialized soft threshold (one bounded64MiB packet may
exceed that threshold); this is not a claim about total process RSS. Original
atomic WP5 float64 schemas/writer produce D20, D3, explicit geometry and source
status Parquet with v2_candidate/stream/CID/release/key/packet provenance.
No zero geometry, energy or D3 row is fabricated for a missing/unknown packet.
Status actual-count is null when a consumed packet cannot be read back.

The actual Budget/Writer and finite account-quota Client are reused. Current
whole-wave reservations plus this remaining cap plus200GB are verified against
both actual account free and physical statvfs, as separate observations. Actual
own-tree RSS≥16GiB or MemAvailable<max(4GiB,15%), expired/unknown quota, wall or
cap stops new dispatch. No signals kill an optimizer. A running native call
finishes; before the next candidate it may close the molecule as partial
technical UNKNOWN. A single native call can outlast the drain reserve; Slurm
timeout is retained honestly. No soft observation is a total scratch hard limit.
Cap exhaustion keeps raw/claims and stops; it never permits automatic retry.

## Root metadata and execution sequence

Use Linux PY from the existing gate in an appropriate Main context. Metadata
helpers run on login and read only source/small metadata; never DATA bodies.
They do not submit, approve or invent source hashes/accounting/real R/N parents.

```text
PY -B -m workflows.expansion.no_pm7_uff_d_main_v1.metadata catalog --output CONTROL/FRESH_CATALOG
PY -B -m workflows.expansion.no_pm7_uff_d_main_v1.metadata draft --request ROOT_REQUEST.json --output CONTROL/FRESH_STAGE
PY -B -m workflows.expansion.no_pm7_uff_d_main_v1.metadata finalize --draft CONTROL/FRESH_STAGE/draft_receipt.json --root-review INDEPENDENT_APPROVED_REVIEW.json
```

Root request schema=`ROOT_REQUESTED_NO_PM7_UFF_D_STAGE_V1`,
status=`REQUESTED_FOR_REVIEW`, requested_by=`root`, mode, wall_seconds (whole
minute,600..86400), output_cap_bytes (2..128GiB; native minimum16GiB),
lower_inclusive/upper_exclusive (full/resume), and these exact actual fields:

* ranking_receipt_reference; graph_source_review_reference;
  kernel_catalog_reference; quota_reuse_reference;
  resource_authority_reference; cost_decision_reference; output_directory.
* All modes after source: source_preparation_receipt_reference and its actual
  standard Main accounting_reference including raw sacct.
* Profile/full: accepted_previous_receipt_reference, its accounting_reference,
  previous_stage_root_review_reference; and CPU-produced reuse_snapshot_reference
  plus reuse_accounting_reference. Profile accepts actual compat32; full accepts
  actual profile10000. Receipt/source/proof/job/recipe identity must all agree.
* Resume: prior_runs_reference and resume_selection_mode (compat/profile/full).
  Compat/profile resume uses bounds [0,2500000) while reading only its exact
  declared sample. Full resume uses its explicit interval.
  The Root prior-run header is `ROOT_NO_PM7_UFF_D_ACTUAL_PRIOR_RUNS_V1`, reviewer
  root, status `TERMINAL_ACCOUNTING_LOCATORS_ONLY_NOT_PACKET_ACCEPTANCE`. It has
  runs or pinned small parts containing runs, each actual job_id/plan_reference/
  startup_proof_reference/accounting_reference. Do not include live jobs.
* Coverage: whole [0,2500000) full-selection CPU resume snapshot plus accounting;
  it visits all R/N source rows and preserves every unknown.
* Optional quality_reference_review_reference, described below.

Missing actual refs create only NONEXECUTABLE.json, no executable stage spec.
Once complete, Root independently changes only reviewer/status of the generated
exact scope template to root/APPROVED_FOR_EXACT_STAGE in a new file; finalize
checks every other value and source pin. Submit stage_spec.json through existing
central-v2 prepare/submit_held/observe, not a new queue or direct invocation.
The `conformer` kind is used for compat/profile/full, pilot true only for
compat/profile; source/resume/coverage use analysis/pilotfalse.

Recommended actual sequence: source → compat32 → resume(compat) → profile10000
with actual Root compat review → resume(profile) → actual Root 10k cost/failure/
output review → independent full intervals, each width≤1024 → terminal-only
resume/readback → whole-scope coverage. Adjacent full intervals must partition
[0,2500000); overlaps cannot reopen once. Full stages need the actual10k
receipt/account, not a future prediction. Parent failures and incomplete packets
are read only after terminal accounting. Snapshot validates full FD SHA/fstat,
gzip CRC/EOF/source/claim/recipe; it may reuse valid UNKNOWN but never retry it.
Unclaimed rows may get their first claim in a later Root stage. Full export is
inventory generation; pool/decontamination/training release always false.

`ROOT_EXPANSION_PUBCHEM_GRAPH_SOURCE_REVIEW_V1` is an independent Root file,
status APPROVED_FROZEN_SOURCE_GRAPH; exact required bindings and literal MID/
graph fields are in `contract.source_parents`. The previous-stage Root review
schema is `ROOT_NO_PM7_UFF_D_PREVIOUS_STAGE_REVIEW_V1`, status
APPROVED_NEXT_BOUNDED_STAGE, actual receipt/account refs,
UNKNOWN_failures_and_source_seam_reviewed=true and
new_forcefield_stereo_or_chemical_rule=false. Full additionally binds actual
profile allocation core-seconds, molecule and label-state histograms, denominator
10000, profile_variable_output_bytes, an explicit positive integer descriptive
output expansion factor, first_batch_total2500000/R=N1250000,
large_compute_over500_corehours_reviewed=true and descriptive_not_worst_bound=true.
Each cap must cover ceil(actual variable bytes/10000)*interval_length*factor
plus9GiB (32 private roles plus1GiB drain). This is a reviewed descriptive
projection, not a guarantee; actual resource STOP remains. Historical cost1.5
overrun is report-and-continue under the real user decision; quality is unchanged.
Worker/molecule time per known conformer, actual native/unknown counts, actual
cache+family+journal/mask bytes, and linear2.5M/10M variable storage are reported.
Actual allocated cost is only terminal sacct, including failures/startup; Root
keeps the full related ledger and fixed source/resume/QC costs separately.

## Original masks and real TRAIN references

R/N are not TRAIN. No v1 reference is fitted from them. An optional independent
`ROOT_NO_PM7_UFF_D_MATCHED_TRAIN_REFERENCE_V1` review must have status
APPROVED_REFERENCE_APPLICATION_ONLY, reviewer root, R_N_fit_as_TRAIN=false,
same_D_function_units_and_family_field_map_reviewed=true,
UFF_D3_vs_original_TRAIN_domain_difference_reviewed=true, actual field_map_reference
(original20+7 D fields) and original_mask_config_reference (original adapter pins).
Optional TRAIN_calibration_reference remains the unmodified original
TRAIN_ONLY/coverage_fingerprint/fields calibration. A separate actual
TRAIN_reference_domain_reference binds that calibration reference and matching
coverage_fingerprint, fit_role TRAIN_ONLY and actual_source_and_role_census_closed.
No historical reference needs a fabricated field added.

After all UFF workers exit, a separate bounded16-process phase directly calls
the original task_components, source_value_mask, add_cross_field_checks and
scan_v2.add_reference_reviews objects. It retains per-leaf masks/source/new/review
reasons, units/field IDs from the frozen original map, robust-z>20 review-only,
original same-sign within-MID magnitude-jump review and >1% newly masked-field
STOP. It does not alter raw labels, refit or convert review-only outliers to masks.
Coverage can run the same original functions across all actual packets. Missing
field-map/config or actual matching TRAIN calibration explicitly leaves the
corresponding scan/full1.5 open; no acceptance is claimed even when present until
independent Root audit. Historical SOURCE differences and technical UNKNOWN
are not converted into new chemical rejection. Current missing R/N/graph/TRAIN
parents are genuine unclosed dependencies, not placeholder hashes or a reason
to replace the implemented runtime with a candidate-only CLI.
