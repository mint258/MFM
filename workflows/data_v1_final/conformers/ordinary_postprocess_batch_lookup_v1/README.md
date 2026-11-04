# Ordinary descriptor lookup and closed-catalog continuation candidate

SOURCE ONLY. Not installed, executed, tested, submitted or adopted. Active
4525890 and its pinned sources remain untouched. Install these eight files only
as a new `workflows/data_v1_final/conformers/ordinary_postprocess_batch_lookup_v1`
namespace after Root review. Existing queue/admission/resource APIs remain;
Root must supply the real new plan/proof/provider/output and recompute source
pins and `io.parameters(plan)`.

## Lookup change

The three literal per-MID queries (roles, Common membership, UFF physical maps)
are routed to indexed tables containing only the current original descriptor's
MIDs. Each table is produced once per descriptor with `SELECT s.*` from the
unchanged full source view. Column order/types, duplicates, NULLs, all selection
conditions and original `ORDER BY sprime_conf_idx` are retained. Full source
views remain available to every other consumer, including old-UFF projection.
Only the original three SELECT strings are routed; all other SQL delegates to
the original connection. Original `cache`, `hof`, `worker`, `statistics` and
scientific functions are imported unchanged. Existing prior-cache/HOF/old-UFF
PKs are retained; no extra full-width population copy or new scanner is added.

## Actual continuation input (not supplied by this candidate)

For transition from 4525890, Root supplies `plan.closed_ordinary_resume` with:

```
actual_parent_job_id: "4525890"
plan_reference: actual old plan triple
startup_proof_reference: actual old proof triple
accounting_reference: actual terminal accounting closure triple, including raw_sacct_reference
checkpoint_references: actual old checkpoint triples in original descriptor order
catalog_part_references: actual old closed catalog Parquet triples
receipt_reference: optional actual old receipt triple, preserving original unknowns
failure_reference: optional actual original failure triple, never relabeled successful
orphan_adoption_reference: optional actual positive adoption JSON triple in a new control directory
```

No C0 is assumed: real UID1278/16CPU/node and a genuine native terminal state
are required. Original plan/proof/argv and unchanged scientific-input/source
bindings are checked. Catalog/claim/start/packet identities, runtime, records
and canonical HoF bindings remain original. Existing packet readback is used;
then the unchanged `statistics.Collector.add` rebuilds derived stats/orders.
This performs packet reading and derived-statistics reconstruction, not PM7,
RMSD, UFF, QM or geometry-order recomputation. Old packet bytes never receive
new-output quota credit. Catalog runtime/claim/packet references retain the old
producer; the new parent is recorded separately in new checkpoints/receipt.

The original Collector cannot reopen an old state: it creates a fresh results
table, exclusive cross-RMSD file and memory buffers. This candidate therefore
replays actual closed packets into a fresh Collector, skips complete descriptors
and skips already closed MIDs in a partial final descriptor. Original UNKNOWNs
are preserved and prevent new work. Real closed orphans are adopted with
`adopt_orphans.adopt(ctx, db, resume, descriptors, fresh_control_directory)`.
This uses original packet/claim/start/source-record/HoF checks and joins the
frozen closed roster to recover descriptor membership. Its new JSON manifest
preserves provenance; no old catalog, checkpoint or output is created/rewritten.
Supply its actual positive ref in `closed_ordinary_resume`, or set the new
plan/scope's `orphan_adoption_directory` to a fresh separate control directory:
the admitted new runner then generates the actual manifest before restore and
records its real ref without rewriting the frozen plan. No future SHA is used.
Every existing output remains covered or explicitly UNKNOWN. Incomplete or
invalid packets retain UNKNOWN/HOLD; they are never treated as absent.
Claim-without-packet is recorded `RESOURCE_INTERRUPTED_READONLY`; continuation
requires identical cache-key, records, canonical HoF and Common inputs, with a
new claim referring back to the old readonly claim and no new Native permission.
Any original UNKNOWN still blocks new work; this is not a scientific-failure
retry. Original failure refs and once/source histories remain unchanged.
Only the actual original `KeyboardInterrupt()` exception is treated as an
operator interruption; other original failure exceptions remain explicit
UNKNOWN/HOLD instead of being guessed to be resource failures.
Adoption/replay and the completeness guard occur before old-UFF coordinate projection,
so missing resume coverage refuses before repeating that preparation phase.

The current old runner has no cooperative stop-request handler. Do not write a
stop file or signal it and call that a supported descriptor drain. Root owns
any separately authorized switch and must establish actual terminal accounting
and complete closed-catalog coverage first. Current native work keeps running.

## Future runner's descriptor boundary

This new runner alone accepts an own-output `stop_after_descriptor.json`:
`{"job_id":"ACTUAL_NEW_JOB","stop_after_current_descriptor":true}`.
It checks the request only after all futures in the descriptor have naturally
returned and its catalog/checkpoint are closed. It does not signal workers and
does not mark a partial scientific release complete. This is an operational
drain request, not a new approval or scientific validation layer.

Shortest handoff: actual old terminal + closed metadata refs -> fresh plan and
new namespace using existing queue -> replay closed catalogs via original
Collector -> skip closed MIDs -> continue remaining original descriptors with
batch lookups. No model source, native once history, scientific filtering,
original source arrays/IDs, ordinary N/D5 or thresholds are changed.
