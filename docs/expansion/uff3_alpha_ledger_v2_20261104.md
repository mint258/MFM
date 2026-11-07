# UFF3 native accounting and continuation

Current user workflow consumes actual producer and terminal Slurm metadata
without per-job Root approval or review receipts. Only the daily human summary
is required. Scientific core/native/store/D functions, fixed30/max3/0.5 A,
seed/order, no-fill, no-scientific-retry and old saved bits remain unchanged.

Ledger schema2 stores dev/ino as lossless unsigned64 hex TEXT. Old INTEGER
ledger evidence is not migrated or relabelled. Each allocation uses a new ledger
and records actual hostname/boot/device/inode epoch. One startup reconstruction,
even on the same node, includes unregistered abandoned bytes after a failed
allocation; there is no production quota-poll tree walk.

The actual same-FD exclusive stage parent flock is held. A fresh stage has no
molecules/families/interrupted/index.sqlite history. Existing history requires
inline plan.resume_binding with actual output scope/source manifest/recipe and
previous_allocations. Each previous entry binds plan_reference,
startup_proof_reference, accounting_reference and optional runtime_receipt_reference.
Startup must bind the same real plan/UID/endpoint/job. Native raw Slurm parent,
batch and all recorded steps must be terminal; a failed terminal attempt may be
continued without pretending it was a completed production phase. Runtime
records supply full hostname, boot, PID/start ticks where present. Relevant
same-lifetime live/unreadable PIDs reject continuation; unrelated own processes
are never enumerated. Every previous derived-plan attempt must be inventoried.
Unknown stages or implicit cache/seed retries remain forbidden.

Before creating a new ledger, a complete read-only native metadata census
checks actual own regular files/directories, stable frames and hard-link
uniqueness. Process-tree RSS and node reserve are checked during traversal.
Current complete allocated bytes form the guard baseline, never partial ledger
subtotals. Old immutable regular file blocks can receive conservative credit
only if actual quota cutoff is strictly later than their greatest mtime/ctime;
mutable DBs, directories and the newly written derived plan get no startup old
credit. Old outputs are unchanged under actual terminal old-job cleanup and
exclusive scope ownership. New actual ledger/directory growth is counted.

Root/coordinator supplies ledger_rebuild_reserved_bytes from the real stage
budget. Complete baseline plus reservation must fit before any new ledger write.
Alpha quota/all-future/floor/RSS guard runs throughout reconstruction; every4096
files checks it. SQLite main file page ceiling is reserve/3, leaving journal and
allocation overhead; actual native growth is also checked. The page ceiling
persists for the whole allocation, so size this field for the full pilot/full
ledger, informed by actual pilot metadata bytes. After rebuilding, incremental
closed facts and bounded mutable paths replace startup census accounting.

Closed cache/packet/family files are not rewritten. Interrupted files remain
UNKNOWN and counted; a resumed worker does not re-enter their optimizer. D20
family row presence is not a claim that the D20 calculation succeeded or that
an unrecorded call count can be reconstructed. QA has an independent small
private SQL scope and dynamic DB/WAL/spill accounting, not this molecule ledger.

Actual Alpha deployment/whole-dataset continuation must still be measured;
stdlib source fixtures are not a production-result claim.

```sh
python -m unittest workflows.expansion.uff3_candidate_v1.test_credit workflows.expansion.uff3_candidate_v1.test_credit_threads workflows.expansion.uff3_candidate_v1.test_ledger_epoch -v
```