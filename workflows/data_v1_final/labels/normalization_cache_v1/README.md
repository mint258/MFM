# Source TRAIN typed-cache compatibility and finite calibration profile

Source-only handoff; no Python, AST, fixture, cache, original scientific source,
SSH, Git or Slurm execution by the child. Existing full8, bounded6, mathematics
and original data remain unchanged. This is an exact-input adapter/profile for
the already produced512molecule/4251record/16owner cache. It is not full-source
TRAIN acceptance, a final mask release, or final Common normalization.

## Compatibility audit

| Needed input | Actual cache support / boundary |
|---|---|
| TRAIN role, canonical identity, task, source/RG/physical row |provenance.owner and exact original owner-index pins; owner five-key/lane/natom/role compared |
| ordered scalar/atom/pair leaves |cells, component_map ordered paths, atom_indices, original type/F64 pool; no dedup/symmetrize/sorting |
| source/new mask inputs |source_status_and_precision retains status, numeric_issues, converged, scf_iterations, precision_by_field_json, failure_code; native D20/D3 scientific columns are in cells |
| original candidate masks |compact source/new bits, grouped reasons and sparse exceptions are retained, but explicitly not final |
| energy element counts / size |base.original_geometry has Z, order/payload hashes and geometry status; compare with the exact old owner-index heavy count/payload hash without LMDB |
| source floating width/native print precision |original source bit pools remain in cache; no conversion or native print precision inference from Parquet dtype |
| native original JSON text |successful cells retain decoded object/list/key order and original text SHA, not original text; cannot recover lexemes or raw program logs |
| duplicate/unidentified CELL semantics |legacy task_components would raise; payload.evaluate can retain review/false-mask evidence. Do not quietly replace this incompatibility with an empty accepted input |

The adapter creates an explicit in-memory logical CELL view and calls unchanged
common.task_components, source_value_mask and add_cross_field_checks. A successful
CELL must roundtrip through the frozen decoder with exact original scalar types,
dict/list order and floating bits. JSON is a logical decoder view, never claimed
to be the original text. Any non-roundtrippable value or legacy-incompatible CELL
is a CompatibilityGap. Raw undecodable cells already retained in cache remain
raw. No new parser, masks, precision, physical bounds or quality tolerance.

All regenerated entries independently match cached component-map pointers and
owned indices. Compact source/new bits/reasons/leaf exceptions must match every
record; calibration-dependent reviews do not alter this comparison. A supplied
PENDING candidate is never relabeled final by passing these checks.
If a later independently approved final-mask rule intentionally changes validity,
that requires a separate versioned overlay/review driver; this finite profile
does not provide a switch to suppress candidate parity or hide the differences.

When original text, a changed parser/lexeme rule or native logs are genuinely
required, the bounded recovery request names exact source triple, original RG,
physical row, record/molecule IDs and reason. The profile does not read it. Root
can separately approve a predicate read of that single original row, with the
canonical owner check. Missing native raw/logs stay UNKNOWN; no whole575.9GB
rescan,715GB LMDB read, invented convergence or default value is implied.

## First actual profile

Inputs come from actual small producer/legacy receipts:

- `artifacts/labels/source_status_v1/lossless_projection512_v1/manifest.json`:
  the Main4521610 C0 cache,16files plus exact group reports,63765typed rows.
- `artifacts/labels/streaming_v1/prepared_pilot_v1/group_plan.json` and field map:
  the same4251records/512molecules and16owner indices, with a mix of source roles.
- `artifacts/labels/streaming_v1/profile_pilot_v2/scan_manifest.json`:
  original round0query and16closed group reports/radix histograms/TSQR states.
- the existing matched512median/MAD reference is only an exact-input/scale QA
  oracle. Its source TRAIN count is not assumed to equal all4251records.

The metadata helper derives cache body counts and bytes from actual producer
triples. The prior494,609,729unique output bytes include metadata and must not be
misreported as a fresh input-transfer byte measurement. The profile consumes
16cache+16owner+16legacy histogram body locators, not original label sources.

```text
PY -B -m workflows.data_v1_final.labels.normalization_cache_v1.materialize
  --cache-manifest ACTUAL512 --cache-proof ACTUAL --cache-accounting ACTUAL
  --cache-raw ACTUAL --legacy-profile ACTUAL_PROFILE_V2
  --resource-authority CURRENT --metadata-directory NEW --output NEW
  --approve --reason ROOT_FINITE_PROFILE_REVIEW

PY -B -m workflows.data_v1_final.labels.normalization_cache_v1.run
  --config ACTUAL_CONFIG --startup-proof FRESH_CENTRAL_V2_PROOF --output NEW
```

Only metadata is processed by materialize. It emits the existing central v2
stage spec; no queue/controller is copied, no job is submitted. Runtime is new
analysis/16CPU/noSBATCHmem/noexclusive, pilottrue,<=2h and4GiB whole output cap.
Worker3GiB RSS and64MiB row limits remain software bounds; local output128MiB
per worker includes pointer index/histogram/report/partials. Observer64MiB and
4GiB absolute MemAvailable natural-drain floor are unchanged. No forced kill.

After fresh admission and exact small/source pins, six new incremental fixtures
run in the same allocation before any real cache/owner/histogram body. They test
selected F64 rebasing/type/NaN payload/signedzero, CELL kinds/JSON order, strict
duplicate failure, regenerated partial masks/NULL convergence, role filtering,
and Z-only projection/pointer duplicate detection. Old13/19/24 suites are not
rerun. Unexecuted source does not mean these new fixtures passed.

Every worker uses one actual owner group, not16copies of the whole index. It
verifies the old cache whole SHA once, opens that cache Parquet once, reuses it
for base and task RGs, observes stable same-fd identity, then closes it. Actual
row-kind statistics skip irrelevant pure-base/task RGs; unknown/mixed RGs are
conservatively included. Base projection does not read XYZ F64values. Task
projection needs the numeric pool; selected tagged subtrees are rebased and
decoded with the frozen function, excluding unrelated bit-pool/provenance
branches. It does not repeat the full scientific-signature calculation already
performed by the producer. Initial whole SHA still binds those original bits.

Each pointer index records exact `(ordinal,task)->(cache RG,local physical row)`;
any duplicate key is HOLD even if values match. No full logical index or giant
long-leaf numeric export is allocated. More general physical part/RG indexing
must be separately profiled before full-cache use; this finite group loader
does not pretend to already handle the full2208source directory.

Frozen train_values/RadixCounts/TSQR receive only source-TRAIN valid leaves.
For round0, per-group radix rows must equal the actual old histogram and TSQR
states must equal the old states, without introducing a numeric tolerance.
Every pass additionally checks original matched TRAIN leaf counts and source
mask parity. Per-field/global input hashes include canonical keys, role, mask
length/bits and eligible binary64 leaves. A different numerical environment can
fail exact TSQR replay; report it, do not silently call it input equality.

Reports separate input whole-SHA time, Z/order metadata projection, numeric
decode+legacy mask/oracle+histogram+TSQR, old-result comparison, parent reduction,
output bytes, pointer index and actual RSS. Cache referenced bytes are not
physical storage-read bytes. No timing is extrapolated to full population here.

## Exact refinement and reviews

One allocation makes one finite source pass. `next_query_stage.json` wraps the
unchanged exact radix query with cache/field-map scope and cumulative finished
fields. Root can call the same metadata helper with `--query-stage ACTUAL_NEXT`
to prepare a separate pass. No automatic retry, continuation or Slurm submission.
Refinement additionally requires `--previous-manifest/--previous-proof/
--previous-accounting/--previous-raw`: actual C0 and exact published next-query
binding are checked. A query file left by a failed/partial stage cannot advance.
After exact medians close, the next query is MAD using those actual medians;
after MAD closes, the reference is compared with the matched old512values and
counts. Empty scales remain undefined; no mean/std or final D4 is manufactured.

Source TRAIN provisional element references remain the original per-field/task
contexts and deterministic16group TSQR order, with original chunk/rcond math.
These are not final Common TRAIN energy references. The profile does not
recompute or freeze size rho. It exposes unchanged original raw ordered cells,
field entries/indices and Z for the separately frozen approved aggregate pass
(scalar/norm/Frobenius/atom sum-or-RMS/stored pair rules). Existing r73 basis
invariance and ordered-key conflict caveats remain UNKNOWN and cannot be fixed
by symmetrizing cache keys. Size rho changes registry-family evidence, not a
validity bit by itself.

Median/MAD can support a later unchanged z>20/zero-MAD review pass; they do not
automatically mask values. A real all-source calibration, full field/record
coverage, within-molecule checks, physical/unit evidence and Root's final mask
rule/version review are still required. The>1%new mask HOLD is unchanged.

Final Common normalization stays hard-locked. It additionally needs genuinely
FROZEN Common/effectiveTRAIN, opaque physical geometry/order mapping and exact
diagnostic base/view exclusions. Pprime needs its own source/quality/mask
closure; its geometry/parser C0 does not lift original R1 scientific HOLD.
The old norm runtime's explicit64GiB request cannot be reused with no_mem.
No SourceTRAIN512reference, size result or P label substitutes for final D4/Pprime.
