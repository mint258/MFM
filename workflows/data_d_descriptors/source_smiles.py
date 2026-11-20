"""Reuse original SMILES already copied into the closed WP5 source index.

Join the exact logical source_path and real_index from the existing native
pointer. Do not use canonical/reidentified SMILES, graph inference, filename
aliases, new hashes, or physical LMDB copies.
"""
from pathlib import Path


PROJECT = Path("/share/home/zixiao/descriptor_analysis")
COLUMNS = ("source_path", "real_index", "smiles")


def source_key(pointer):
    path = Path(pointer["source_path"])
    path = path if path.is_absolute() else PROJECT / path
    return str(path), int(pointer["real_index"])


class SourceSmiles:
    def __init__(self, values):
        self.values = values

    @classmethod
    def from_parquet(cls, filename, pointers, *, reader=None):
        if reader is None:
            import pyarrow.parquet as pq
            reader = pq.ParquetFile
        wanted = {source_key(pointer) for pointer in pointers}
        if not wanted:
            return cls({})
        paths = {path for path, _ in wanted}
        found = {}
        with reader(filename) as source:
            for batch in source.iter_batches(columns=list(COLUMNS), batch_size=65536, use_threads=False):
                columns = batch.to_pydict()
                for path, index, smiles in zip(*(columns[name] for name in COLUMNS)):
                    if path is None:
                        continue
                    logical = str(Path(path) if Path(path).is_absolute() else PROJECT / path)
                    if logical not in paths:
                        continue
                    key = (logical, int(index))
                    if key not in wanted:
                        continue
                    value = str(smiles) if smiles else None
                    if key in found and found[key] != value:
                        raise ValueError("Conflicting original SMILES for one native source pointer")
                    found[key] = value
        return cls(found)

    def get(self, pointer):
        key = source_key(pointer)
        if key not in self.values:
            raise RuntimeError("Original native pointer absent from the declared closed SMILES index: " + repr(key))
        if not self.values[key]:
            raise ValueError("Original D20 stored SMILES unavailable")
        return self.values[key]
