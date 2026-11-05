"""Read producer references without recomputing content hashes."""
import contextlib, os, pathlib, stat


def frame(value):
    return [value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns,value.st_ctime_ns]


@contextlib.contextmanager
def opened(reference,expected=None,hash_content=False):
    # hash_content is accepted for the inherited builder API, deliberately not
    # used. The current taskbook prohibits repeated source content hashing.
    path=pathlib.Path(reference['path'])
    if not path.is_absolute():raise ValueError('ABSOLUTE_SOURCE_PATH_REQUIRED')
    with path.open('rb') as source:
        before=os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_uid!=os.getuid() or before.st_size!=reference['bytes']:
            raise ValueError('CLOSED_SOURCE_SIZE_OR_OWNER_CHANGED:'+str(path))
        if expected is not None and frame(before)!=expected:
            raise ValueError('SOURCE_FRAME_CHANGED:'+str(path))
        try:yield source,frame(before)
        finally:
            if frame(os.fstat(source.fileno()))!=frame(before):
                raise ValueError('SOURCE_CHANGED_DURING_READ:'+str(path))
