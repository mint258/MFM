"""SOURCE ONLY: optional node-local store staging; no runner or release policy.

Caller wiring replaces only physical writer paths and their closing section:
  stage = choose(shared_root, local_parent, name, forecast_bytes=estimate)
  side = P.Sidecar(stage.sidecar_path)
  writer = P.TrainingWriter(stage.store_path, schema, map_bytes=original_map)
  ... original metadata/arrays/flush64 loop ...
  receipt, f64 = stage.finish_and_publish(writer, side)
  ... original shared I.pin(shared_root/name/manifest.json), closed_store save ...
  # Keep logical manifest.path and parent metadata pointing to shared_root/name.

Keep global ROOT/ACTIVE_CENSUS at the shared output. Local bytes never receive
Lustre credit. Forecast only selects a cache path; insufficient/unavailable local
space returns shared paths immediately, with no wait/time/RSS/task limit. Caller
supplies its prior-store estimate, not a fabricated upper bound. An unexpected
mid-write I/O failure is left to the original DATA repair path; no automatic
re-encoding, second QA or silent source replay is performed here.
"""
import contextlib, fcntl, json, os, pathlib, stat, uuid
from . import writer as W
canonical_json = W.CODEC.canonical_json


def _own(path):
    path = pathlib.Path(path)
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('LITERAL_OWN_STAGING_PATH_REQUIRED')
    value = path.stat()
    if value.st_uid != os.getuid():raise ValueError('OWN_STAGING_PATH_REQUIRED')
    return value


@contextlib.contextmanager
def _locked(base):
    with (base / '.lock').open('a+b') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(stream, fcntl.LOCK_UN)


def _allocated_main_files(work, name):
    # These two original writers only grow their main files until close. All
    # removal is under _locked, so earlier blocks are already in later statvfs.
    # Never credit transient SQLite journal files or any other filesystem.
    total = 0
    for path in (work / name / 'data.mdb', work / (name + '.authority_f64.sqlite')):
        if path.exists():
            value = _own(path)
            if not stat.S_ISREG(value.st_mode):raise ValueError('REGULAR_STAGING_FILE_REQUIRED')
            total += value.st_blocks * 512
    return total


def choose(shared_root, local_parent, name, *, forecast_bytes=None, reserve_bytes=4 << 30):
    """At most15 admitted forecasts under one private flock; else original paths."""
    shared = pathlib.Path(shared_root)
    if not name or name in ('.', '..') or pathlib.Path(name).name != name:raise ValueError('LEAF_STORE_NAME_REQUIRED')
    _own(shared)
    result = StoreStage(shared, name)
    if type(forecast_bytes) is not int or forecast_bytes <= 0:return result
    if type(reserve_bytes) is not int or reserve_bytes < 0:return result
    try:
        parent = pathlib.Path(local_parent); parent_stat = _own(parent)
        in_tmp = pathlib.Path('/tmp') in parent.parents
        private_shm = (pathlib.Path('/dev/shm') in parent.parents and stat.S_ISDIR(parent_stat.st_mode)
                       and stat.S_IMODE(parent_stat.st_mode) == 0o700)
        if not (in_tmp or private_shm):raise ValueError('NODE_LOCAL_PRIVATE_TMP_OR_SHM_REQUIRED')
        base = parent / 'local_store_stages'; base.mkdir(mode=0o700, exist_ok=True); _own(base)
        with _locked(base):
            remaining = []; active = 0
            for work in base.iterdir():
                if not work.name.startswith('stage_'):continue
                _own(work); reservation = work / 'reservation.json'; _own(reservation)
                if reservation.stat().st_size > 2048:raise ValueError('SMALL_OWN_RESERVATION_REQUIRED')
                row = json.loads(reservation.read_text())
                amount = row['forecast_bytes']; old_name = row['name']
                if type(amount) is not int or amount <= 0 or old_name in ('.', '..') or pathlib.Path(old_name).name != old_name:
                    raise ValueError('EXACT_OWN_STORE_FORECAST_REQUIRED')
                remaining.append(max(0, amount - _allocated_main_files(work, old_name))); active += 1
            disk = os.statvfs(parent); free = disk.f_bavail * disk.f_frsize
            if active >= 15 or free - sum(remaining) < forecast_bytes + reserve_bytes:return result
            work = base / ('stage_' + uuid.uuid4().hex); work.mkdir(mode=0o700)
            with (work / 'reservation.json').open('x') as stream:
                json.dump(dict(name=name, forecast_bytes=forecast_bytes), stream)
            result.base, result.work, result.staged = base, work, True
            result.store_path = work / name
            result.sidecar_path = work / (name + '.authority_f64.sqlite')
    except (OSError, ValueError, KeyError, TypeError):
        # Stale/unavailable staging never blocks an original shared writer.
        return result
    return result


def _fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def _copy_once(source, target, expected_bytes):
    before = _own(source)
    if not stat.S_ISREG(before.st_mode) or before.st_size != expected_bytes:
        raise ValueError('EXACT_CLOSED_STORE_FILE_REQUIRED')
    frame = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
    copied = 0
    with source.open('rb') as incoming, target.open('xb') as outgoing:
        for block in iter(lambda:incoming.read(4 << 20), b''):
            outgoing.write(block); copied += len(block)
        outgoing.flush(); os.fsync(outgoing.fileno())
    after = _own(source)
    if frame != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) or copied != expected_bytes:
        raise ValueError('CLOSED_STORE_COPY_FRAME_OR_BYTE_COUNT_CHANGED')
    # Original finish already produced the content SHA once. Copy does not hash.


class StoreStage:
    def __init__(self, shared, name):
        self.shared, self.name = shared, name
        self.store_path = shared / name
        self.sidecar_path = shared / (name + '.authority_f64.sqlite')
        self.base = self.work = None; self.staged = False; self.cleanup_error = None
        self._handles_closed = False

    def finish_and_publish(self, writer, sidecar):
        # Identical original finish order and original object methods. Both
        # objects are actually closed before any staging file is copied.
        try:
            f64 = sidecar.finish(); receipt = writer.finish()
        finally:
            try:sidecar.close()
            finally:writer.close()
        self._handles_closed = sidecar.db is None and writer.env is None
        if not self._handles_closed:raise ValueError('ORIGINAL_STORE_HANDLES_NOT_CLOSED')
        if not self.staged:return receipt, f64
        final_store = self.shared / self.name
        final_side = self.shared / (self.name + '.authority_f64.sqlite')
        if final_store.exists() or final_side.exists():raise FileExistsError('FRESH_SHARED_STORE_DESTINATIONS_REQUIRED')
        if pathlib.Path(receipt['data']['path']) != self.store_path / 'data.mdb' or pathlib.Path(f64['reference']['path']) != self.sidecar_path:
            raise ValueError('EXACT_ORIGINAL_CLOSED_STAGING_REFERENCES_REQUIRED')
        # Paths occur in external refs only. No record, array, schema header,
        # r73 order, original metadata, precision or mask is rewritten.
        receipt = dict(receipt, data=dict(receipt['data'], path=str(final_store / 'data.mdb')))
        f64 = dict(f64, reference=dict(f64['reference'], path=str(final_side)))
        token = self.work.name
        pending_store = self.shared / ('.' + self.name + '.copying_' + token)
        pending_side = self.shared / ('.' + final_side.name + '.copying_' + token)
        pending_store.mkdir(mode=0o700)
        _copy_once(self.store_path / 'data.mdb', pending_store / 'data.mdb', receipt['data']['bytes'])
        _copy_once(self.sidecar_path, pending_side, f64['reference']['bytes'])
        with (pending_store / 'manifest.json').open('xb') as stream:
            stream.write(canonical_json(receipt) + bytes([10])); stream.flush(); os.fsync(stream.fileno())
        _fsync_directory(pending_store)
        # Caller owns each unique store task once. No closed_store/parent meta
        # exists yet, so partial copies are never advertised to consumers.
        os.rename(pending_side, final_side); os.rename(pending_store, final_store)
        _fsync_directory(self.shared)
        self.cleanup_after_handles_closed()
        return receipt, f64

    def cleanup_after_handles_closed(self, *, writer=None, sidecar=None):
        """Remove only this object's known temp files, never shared/other stores."""
        if not self.staged:return
        if not self._handles_closed:
            if writer is None or sidecar is None or writer.env is not None or sidecar.db is not None:return
            self._handles_closed = True
        try:
            with _locked(self.base):
                _own(self.work)
                paths = [self.store_path / name for name in ('data.mdb', 'manifest.json', 'lock.mdb')]
                paths += [pathlib.Path(str(self.sidecar_path) + suffix) for suffix in ('', '-journal', '-wal', '-shm')]
                for path in paths:
                    if path.exists():
                        value = _own(path)
                        if not stat.S_ISREG(value.st_mode):raise ValueError('ONLY_OWN_REGULAR_TEMP_FILES_CAN_BE_REMOVED')
                        path.unlink()
                if self.store_path.exists():self.store_path.rmdir()
                reservation = self.work / 'reservation.json'; _own(reservation); reservation.unlink()
                self.work.rmdir(); self.staged = False
        except (OSError, ValueError) as error:
            # Completed shared DATA remain valid. Leave conservative own local
            # reservation for Root cleanup; do not fail/re-encode delivery.
            self.cleanup_error = repr(error)