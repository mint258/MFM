# UFF source-index cache

The first pilot was still rebuilding metadata after 150,000 of 2,500,000 source rows. Native process inspection showed an open source JSONL part, zero child workers and no completed source census. It had made zero UFF/D calls.

Only two connection-local SQLite settings change: a 4 GiB maximum suggested main page cache and in-memory temporary tables. DELETE journaling, FULL synchronous commits, all uniqueness constraints, complete source SHA/frame checks, exact batch1/rank EXCEPT checks, random pilot membership, and every scientific call remain unchanged. Removing the two statements reproduces the original run.py SHA256 c0ab32e28f47cbc1d0696cee3e92bf813ab08664cf75e73259c33c59160bee54. The cache is demand-allocated and belongs to the existing parent/tree memory allowance.

The immutable Alpha deployment copies all other candidate source files byte for byte and retains the complete previous capsule. Two metadata regressions verify exact reversal and SQLite settings, durable committed data, uniqueness failures and rollback; they do not certify the unfinished scientific batch.

Root prepared five held successor jobs before stopping the metadata-only pilot at a second native boundary check. Its partial index and journal were copied into the same stage's interrupted metadata archive. After native terminal accounting and zero completed science were confirmed, the replacement reused the same stage with registered prior plan/startup/accounting, and retained all source/recipe/cache history. No live external SQL was used. The replacement full job automatically follows the normal pilot QA; no human approval is added. All old allocation costs remain in final accounting.

Actual successors: pilot 1885272 → pilot QA 1885273 → full 1885274 → full QA 1885275 → finalizer 1885276, all 32 CPU cores on compute-0-2 with no GPU request. Reference pack 1885222, after-coverage 1885271 and graph reports are independent. This repair does not assert a faster measured runtime before actual progress is observed.
