Future PPstats / comparison temporary files
==========================================

No active Native job or spooled sbatch is modified. Before future PPstats starts,
Root adds explicit `temporary_root`, `temporary_spill_limit_bytes` and the existing
`disk_protection` configuration to its live-read plan. The destination is selected
by Root; this change does not bind it to Lustre. `/share` may be budgeted after
actual mount/byte/inode/account-quota inspection. Root filesystem and `/tmp` or
`/var/tmp` paths are forbidden. Unknown capacity waits before creating anything.

Use one disk-guard target per actual filesystem, combining same-filesystem paths.
The PPstats profile must cover both its shared `output` and temporary root;
separate filesystems need separate targets. Existing `disk_guard` requires real
findmnt/df/quota information and explicit peak/concurrent/reserve/burst budgets.
Failed/partial allocations already reduce actual available space. No old data is
deleted, and the scientific checkpoint inputs do not include these runtime paths.

`run` applies TMPDIR/TMP/TEMP/SQLITE_TMPDIR and Python's cached tempfile directory
after reading the plan, before opening output SQLite or starting workers.
SQLite progress checks and producer batch boundaries wait before reserves.
Persistent eligibility SQLite and its rollback journal remain beside `output`;
environment variables relocate temporary SQLite files, not that main database.

Set optional `compare_temporary_runtime` to a separate complete runtime profile
for the later comparison. PPstats copies it into its closed statistics manifest.
An already-spooled comparison CLI thus obtains the explicit profile from the
closed PPstats manifest; `--temporary-plan PATH` is also available. DuckDB gets
an explicit private temp_directory and max_temp_directory_size before queries.
A disk/quota monitor interrupts its query before reserves; partials remain.
This limit is a recoverable storage budget, not a scientific cutoff. Root may
increase it or choose another verified target and rerun only the unfinished
comparison of already produced summaries, with no raw-label QA or new QM.

Planning values are not measured artifact sizes: reserve SQLite temporary
working peak separately (e.g.16GiB initial proposal) and DuckDB spill ceiling
(e.g.64GiB), plus persistent projection/eligibility/journals, concurrent windows,
site/quota reserve and a write-burst margin. On the same filesystem include their
true overlapping peak, not the sum of mutually exclusive phases. Do not admit
an unknown projection bound as if it were a measurement. Existing closed binding
DB bytes are a metadata input for eligibility planning; they are not label-cache
bytes. The exact label-cache bytes and unregistered geometry count are emitted
by the existing projection producer, without an additional scan.

Only new fixture, once in an actual parent (do not repeat prior tests):
`python -B -m unittest workflows.data_v1_final.labels.window2_pprime_statistics_v1.test_temporary_runtime`
