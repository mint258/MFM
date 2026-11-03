# Same pilot, bounded metadata lookup caches

The v6 original metadata function scans 134,771,820 raw metadata rows for the
unchanged 55,000-molecule pilot. Its static PM7 base table is queried once per raw
row, although most raw records have no pilot base. This private adapter retains
the entire original metadata code object, every raw row and physical position,
all input hashes, child/view reconstruction, geometry checks and SQL writes.

Only the exact static PM7 base SELECT uses a complete in-memory RID set and an
8 GiB bounded cache of the original immutable encoded blobs. Positive misses
fall through to SQLite. Non-string parameters retain SQLite affinity semantics.
The original canonical lookup runs only for pilot RIDs; owners of nonpilot rows
were discarded by the original loop before classification. No global module is
patched. The original six Source methods and byte/F64/table checks remain; the
existing Source proof also compares cached lookups against direct SQLite.

A separate 12 GiB bounded cache stores the original decoder's result for exact
immutable PM7 base bytes. Every call gets a private deep copy, preserving F64,
entry order and mutable-row isolation. The Source proof mutates one result and
compares the next with original lossless bytes. New children/views still use the
original encoder/decoder. The original 64 GiB/RSS/wall/output limits remain.

The same six closed geometry tables are independently admitted. There are no
new QM, UFF or S-prime calls. The 146 fields, 171 groups, diagnostic exclusion,
TRAIN-only statistics, two independent replays and r674 LOSS_DISABLED remain.
