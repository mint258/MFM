Optional histogram checks at actual writes
=========================================

Plan flag `histogram_guard_writes_only: true`, DEFAULT OFF. Only PP quantile and
median/MAD histogram stages activate it. TSQR/moments/default dispatch and PM7
stay unchanged. Root controls activation; no live plan/job/service is changed.

Original._group_pass uses exactly its original bytecode and original B/entry
operations. Its existing worker-local globals seam receives a directory proxy,
ParquetSink and IO.save proxy. Only after all three are installed is the private
active marker set; then readonly32-row input batches omit their disk wait.
No background heartbeat, new TTL, data scan or mathematical reduction is added.

Directory creation guards the actual path/inode. Both Parquet and JSON use one
unbuffered binary file-like stream: every underlying write is split to at most
64KiB and guard.wait checks real target/quota/bytes/inodes/reserve before that
write, including Arrow header/footer writes. Closing the underlying FD has no
user-space buffer to flush; failed creation/write/footer still closes the FD.
An Arrow destructor retry cannot write through a closed stream. JSON retains
original ensure_ascii=False,sort_keys=True,allow_nan=False,UTF8,newline and atomic
.writing/rename semantics; mkdir/creation/chunks and rename are guarded too.
The existing8GiB burst/concurrent/site floors and <=5second quota freshness are
unchanged. Unsupported future IO/path write methods fail closed rather than
silently delegate. New Original write paths require reviewing this opt-in seam.

Only the new70th fixture method; the passed69th golden fixture is NOT rerun:
python -B -m unittest workflows.data_v1_final.labels.window2_pprime_statistics_v1.test_histogram_io.HistogramIO.test_parity_readonly_batches_and_all_physical_write_denials