# Legacy190 input-hash I/O recovery v1

Isolated Source fork of formal_packed_day_v1. Original v1/v2 packages are unchanged.
The scientific build, original first2 seed20261025, original worker module, record_once_key,
global physical_records_v1 ledger, twelve tasks, original protocol/precision and900s timeout
are retained. The original scope key,64GiB total cap,12GiB parent reserve,8GB DuckDB
memory and7GB spill limits remain unchanged. Metadata keeps the original request/plan schema;
scope_parameters add the append-only I/O strategy and exact50k recovery condition.

Only the hash-write phase changes: immutable pair blobs stay in pair_inputs; input hashes
are inserted once into pair_input_hashes; a pairs view retains the original logical columns
for the unchanged worker dispatch query. This avoids UPDATE transaction accumulation and
does not rewrite pair blobs or enlarge resource limits.

Root request adds the existing generation_partition_QA_reference and
generation_partition_root_review_reference from actual planner4525197. The accepted exact
main190 exclusion header is derived from those references. Its MID-only body is declared DATA
and is read only by the admitted CPU job. Original chosen SQL must produce exactly the same
50,000 MIDs, with no duplicates, before conformers/native inputs are read. A mismatch stops
before new QM; it does not choose replacement molecules. Existing physical claims are consumed,
not retried. The original2000 pilot and its11 scientific failures remain consumed.

CLI after Root installs this new directory in canonical repository and freezes its Sources:

    python -B -m workflows.data_v1_final.pprime.legacy190_hash_io_recovery_v1.metadata draft --request ROOT_REQUEST --output FRESH_STAGE
    python -B -m workflows.data_v1_final.pprime.legacy190_hash_io_recovery_v1.metadata finalize --draft FRESH_STAGE/draft_receipt.json --root-review ROOT_REVIEW

The returned stage_spec uses the existing CPU auto-memory submit path,16CPU,24h,no sbatch
memory request. Root supplies an available node11-19, fresh output beneath the original
artifacts/pprime_formal_packed_day_v1, same original release/resource/cost references and an
actual root carveout. The new run module is the execution entry point. This Source worktree
has not been imported, compiled, tested, submitted, or used to read scientific DATA. The actual production parent validates the exact50k input domain and completed input-hash table
before Native calls. The existing
three original source checks remain; no new unit test or QM diagnostic is introduced.

This is the initial recovery only. A later continuation must retain the frozen prepared
index and original once claims; rerunning chosen after completing any of these50k may fail
the equality condition and is not an authorized replacement draw. Existing original4GiB
prepared-index bound and all output/cost gates may still stop before QM or further dispatch.
