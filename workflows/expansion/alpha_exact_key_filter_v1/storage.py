"""Small closed shards and explicit active-file bound, without a monolithic DB."""
import os
from pathlib import Path
import time
from .core import json_line, need


def frame(path):
    s = Path(path).lstat()
    need(not Path(path).is_symlink() and s.st_uid == os.getuid() and s.st_nlink == 1,
         'Actual owned single-link output required')
    return {k: getattr(s, k) for k in ('st_dev', 'st_ino', 'st_uid', 'st_nlink', 'st_size',
                                      'st_mtime_ns', 'st_ctime_ns', 'st_blocks')}


class Storage:
    def __init__(self, out, check, reference, active_limit=8_000_000_000):
        self.out, self.check_guard, self.reference = Path(out), check, reference
        self.spill = self.out / 'spill'
        self.spill.mkdir()
        self.active = set()
        self.limit = active_limit
        self.peak = 0
        self.last_active_check = float('-inf')
        self.closed = []
        self.journal = (self.out / 'closed_files.jsonl').open('xb', buffering=0)

    def check(self):
        self.check_guard()
        now = time.monotonic()
        if now - self.last_active_check < 1:
            return
        self.last_active_check = now
        size = 0
        for path in tuple(self.active.copy()):
            for suffix in ('', '-journal', '-wal', '-shm'):
                p = Path(str(path) + suffix)
                try:
                    s = p.stat(); size += max(s.st_size, s.st_blocks * 512)
                except FileNotFoundError:
                    pass
        for base, _, names in os.walk(self.spill):
            for name in names:
                p = Path(base) / name
                try:
                    s = p.stat(); size += max(s.st_size, s.st_blocks * 512)
                except FileNotFoundError:
                    pass
        self.peak = max(self.peak, size)
        need(size < self.limit, 'Actual currently writable output plus spill reached 8GB boundary')

    def close_file(self, path, **extra):
        path = Path(path)
        before = frame(path)
        reference = self.reference(path)
        need(frame(path) == before, 'Closed shard/index changed during whole body SHA')
        row = dict(reference=reference, frame=before, inode=before['st_ino'],
                   mtime_ns=before['st_mtime_ns'], ctime_ns=before['st_ctime_ns'],
                   allocated_bytes=before['st_blocks'] * 512,
                   closed_at_unix_seconds=time.time(), immutable_after_close=True, **extra)
        self.active.discard(path)
        self.journal.write(json_line(row)); os.fsync(self.journal.fileno())
        self.closed.append(row)
        self.check()
        return dict(reference, **extra)

    def close(self):
        self.journal.close()


def write_shards(batches, out, store, *, target_bytes=128 << 20,
                 max_rows=1_000_000, max_file_bytes=192 << 20):
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    need(0 < target_bytes <= 128 << 20 and 0 < max_rows <= 1_000_000,
         'Explicit small shard size/row bounds required')
    out = Path(out); out.mkdir()
    refs = []; total = 0; schema = None
    states = {key: dict(writer=None, current=None, rows=0, part=0) for key in '0123456789abcdef'}

    def finish(key):
        state = states[key]; current = state['current']; rows = state['rows']
        state['writer'].close(); state['writer'] = None
        need(current.stat().st_size < max_file_bytes, 'Single shard exceeds hard active-file bound')
        final = current.with_suffix('.parquet')
        need(not final.exists(), 'Never overwrite a closed shard')
        os.rename(current, final); store.active.discard(current)
        actual_rows = pq.ParquetFile(final).metadata.num_rows
        need(actual_rows == rows, 'Closed physical shard row count differs')
        refs.append(store.close_file(final, rows=rows, fp_bucket=key))
        print(json_line(dict(event='ELIGIBLE_SHARD_CLOSED', part=len(refs), rows=rows,
                             fp_bucket=key, total_rows=total, reference=refs[-1])).decode().strip(), flush=True)
        state['current'] = None; state['rows'] = 0; state['part'] += 1

    try:
        for batch in batches:
            store.check()
            if schema is None:
                schema = batch.schema
            need(batch.schema == schema, 'Every original typed candidate field/type must be retained')
            field = schema.get_field_index('ecfp4_2048_hex')
            need(field >= 0 and str(schema.field(field).type) == 'string', 'Original FP string column required')
            fp = batch.column(field)
            need(fp.null_count == 0 and pc.all(pc.match_substring_regex(fp, '^[0-9a-f]{512}$')).as_py(),
                 'Actual complete 2048bit lowercase-hex FP string required')
            prefixes = pc.utf8_slice_codeunits(fp, 0, 1)
            assigned = 0
            for key, state in states.items():
                selected = batch.filter(pc.equal(prefixes, key)); assigned += selected.num_rows
                for start in range(0, selected.num_rows, 8192):
                    item = selected.slice(start, min(8192, selected.num_rows - start))
                    if state['writer'] is None:
                        current = out / ('fp-%s-part-%06d.partial' % (key, state['part']))
                        state['current'] = current; store.active.add(current)
                        state['writer'] = pq.ParquetWriter(current, schema, compression='zstd',
                                                          use_dictionary=True, write_statistics=True)
                    state['writer'].write_batch(item, row_group_size=8192)
                    state['rows'] += item.num_rows; total += item.num_rows
                    store.check()
                    need(state['current'].stat().st_size < max_file_bytes, 'Active bucket shard must stay below192MiB')
                    if state['current'].stat().st_size >= target_bytes or state['rows'] + 8192 > max_rows:
                        finish(key)
            need(assigned == batch.num_rows, 'Every input identity assigned exactly once to its true FP first-nibble bucket')
        for key, state in states.items():
            if state['writer'] is not None:
                finish(key)
    finally:
        for state in states.values():
            if state['writer'] is not None:
                state['writer'].close()  # Preserve failed partial; never relabel it as closed.
    return refs, total, schema
