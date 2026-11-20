"""Reuse canonical D20 values and native element counts, without recomputing D."""
import json
from pathlib import Path

import numpy as np

from workflows.data_v1_final.export.pilot_v31_compact_v1.codec import decode, encode_key


class ExistingD20:
    def __init__(self, compact_root):
        root = Path(compact_root)
        self.manifest = json.loads((root / "manifest.json").read_text())
        schema = json.loads((root / "schema.json").read_text())
        self.columns = [(column["field_key"].removeprefix("D20."), column["column_index"])
                        for column in schema["columns"]["d20"]]
        self.environments = {}

    def read(self, split, molecule_index):
        import lmdb
        if split not in self.environments:
            self.environments[split] = lmdb.open(self.manifest["split_roots"][split],
                readonly=True, lock=False, create=False, readahead=False, max_readers=512)
        with self.environments[split].begin() as transaction:
            payload = transaction.get(encode_key("M", molecule_index))
        if payload is None:
            raise ValueError("Canonical source molecule record is missing")
        arrays = decode(payload)
        d20 = np.asarray(arrays[4]).reshape(-1)
        elements, counts = np.unique(arrays[1], return_counts=True)
        return {"existing_D20": {name: None if np.isnan(d20[index]) else float(d20[index])
                for name, index in self.columns},
            "native_element_counts": [[int(z), int(n)] for z, n in zip(elements, counts)]}

    def close(self):
        for environment in self.environments.values():
            environment.close()
        self.environments.clear()
