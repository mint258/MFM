"""Redirect physical reads only; no cache creation, hashing or scientific changes."""
from __future__ import annotations
import functools
import json
from pathlib import Path


class KeepSourceMap:
    """Exact original path keys only; absent sources use the original reader path.

    Root adds a mapping only after the corresponding rsync --sparse has actually
    completed. This reader never inspects partially copied files or derives
    aliases from names, prefixes, path resolution, file sizes or content hashes.
    """
    def __init__(self,closed_source_path_map=None):
        self.closed_source_path_map=dict(closed_source_path_map or {})

    @classmethod
    def from_plan(cls,plan=None):
        if plan is None:return cls()
        if isinstance(plan,(str,Path)):
            plan=json.loads(Path(plan).read_text(encoding='utf-8-sig'))
        return cls(plan.get('closed_source_path_map',{}))

    def physical_path(self,logical_source_path):
        return self.closed_source_path_map.get(logical_source_path,logical_source_path)

    def wrap_native(self,reader):
        """Give the unchanged native reader a temporary physical-I/O row copy.

        The caller's logical row, source/RID/real_index and provenance remain
        untouched. The wrapped D7 native reader keeps its own original LMDB open
        arguments, transaction key, unpickle logic and handle-cache policy.
        """
        @functools.wraps(reader)
        def read(row):
            physical=self.physical_path(row['source_path'])
            if physical==row['source_path']:return reader(row)
            return reader(dict(row,source_path=physical))
        return read


def install_native_reader(module,plan=None):
    """Call once in a future worker initializer, after the normal initialize."""
    sources=KeepSourceMap.from_plan(plan)
    module.native=sources.wrap_native(module.native)
    return sources