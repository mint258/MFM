CONTROL-ONLY PREPARATION. No signal, copy or fixture has been executed by child.

Pinned source compatibility:
wp5_engine_v3.py WORK=mkdtemp(prefix=wp5engine_UID_JOB_PID_,dir=scratch_base).
wp4_native_pilot_v4.py invoke and cleanup use lexical CONFIG.scratch_base;
neither resolves nor forbids a symlink at that base. The cleanup lstat tree
starts at the WORK/call child, not its base parent. All path strings stay intact.

Root first reviews on actual node0:
  /share/home/zixiao/.conda/envs/chemprop/bin/python -B CONTROL/rotate_pp6126_scratch_quiescent.py --parent-pid EXACT_NATIVE_PARENT --target-root /dev/shm/window2_pp6126_native_scratch
This default only previews metadata and actual findmnt/df/statvfs capacity.

One new toy filesystem/proc mock fixture (no real signal/Native/data), after
Root verifies RAM and uses a RAM temporary directory:
  TMPDIR=/dev/shm /share/home/zixiao/.conda/envs/chemprop/bin/python -B CONTROL/test_rotate_pp6126_scratch_quiescent.py

Only Root then adds --execute. One pass skips busy/racing workers; Root may
repeat preview/execute while the same parent is alive. It NEVER signals a Native
child. Every worker STOP has a bound-process CONT in nested finally, including
copy/capacity/interruption failures. Pre-stopped workers are refused. Copy is
limited to64MiB and2 seconds between safety checks; oversized/slow copies are
retained in RAM and skipped before namespace switching. Current source roots
were externally observed by Root at8KiB~8.8MiB; this script does not assume it.

Only exact UID1278/job4526126/module parent and direct owned spawn_main workers
are eligible, with PID/start/argv/cgroup rechecks and pidfd signals. The source
base must have one exact wp5engine_UID_JOB_workerPID child. No active non-zombie
descendant, writable scratch FD/mapping or scratch cwd/directory FD is allowed.
The helper copies regular owned bytes with copy2, preserves the original root
by same-FS rename, then places the original pathname as a symlink to the RAM
copy. It deletes no old file, changes no keyword/seed/timeout and retries no QM.

RAM budget reserves full32*1GiB original per-worker future call roles, all current
copy-size bounds,20GiB cross-window/site growth,32*65536 future role inodes and
1million concurrent inodes. Existing partial/failed copies already reduce real
statvfs availability. findmnt -T, df -B1 and df -Pi run for actual source/target;
statvfs reserve protection runs before copying and before/after each copy2.
The root disk is only renamed/aliased, with no bulk copy or deletion there.
After rotation Root continues independent live RAM/disk monitoring; this is not
a general daemon and does not stop active900-second Native calls.

Pending PPstats: run/projection/statistics have no hardcoded/tmp or tempfile
creation. Output SQLite and Parquet use plan.output; read-only binding DBs stay
at their frozen refs. Before its future Python process starts, set TMPDIR and
SQLITE_TMPDIR to a Root-verified reserved RAM/shared temp path, never root/tmp.
The separate compare.py uses in-memory DuckDB; its spill temp_directory is not
explicitly configured, so do not claim TMPDIR alone relocates DuckDB spill.
