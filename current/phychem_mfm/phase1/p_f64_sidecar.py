"""Opt-in, record-aligned original-F64 graph scalars; MFM4 bytes stay unchanged."""
import json
from dataclasses import replace
from pathlib import Path
import numpy as np

def record_handle_equal(stored,expected):
    """Restore the fixed S7 storage width after NumPy scalar trailing-NUL trimming."""
    return bytes(stored).ljust(7,b'\0')==expected

class PFloat64Sidecar:
    def __init__(self, manifest, split, directory):
        self.path=Path(manifest);self.manifest=json.loads(self.path.read_text())
        if self.manifest.get('status') not in ('COMPLETE','SUBSET_TEST'):
            raise ValueError('Only completed sidecars may be read')
        self.reference=self.manifest['splits'][split]
        if Path(self.reference['D6_directory']).resolve()!=Path(directory).resolve():
            raise ValueError('Sidecar/D6 split location differs')
        self.fields=tuple(self.manifest['enabled_fields']);self._data=self._offsets=None
    def __getstate__(self):
        state=dict(self.__dict__);state['_data']=state['_offsets']=None;return state
    def _open(self):
        if self._data is None:
            def path(key):
                p=Path(self.reference[key]);return p if p.is_absolute() else self.path.parent/p
            self._data=np.load(path('values'),mmap_mode='r',allow_pickle=False)
            self._offsets=np.load(path('molecule_offsets'),mmap_mode='r',allow_pickle=False)
    def lookup(self, molecule, conformer, kind):
        from .v31_loader import record_key
        self._open()
        if molecule<0 or molecule+1>=len(self._offsets):return {}
        start,end=map(int,self._offsets[molecule:molecule+2])
        if start==end:return {}
        rows=self._data[start:end];handle=record_key(kind,molecule,conformer)
        found=np.flatnonzero(rows['record_handle']==np.bytes_(handle))
        if len(found)>1:raise ValueError('Duplicate sidecar physical handle')
        if not len(found):return {}
        row=rows[int(found[0])]
        if int(row['molecule_index'])!=molecule or int(row['conformer_index'])!=conformer:
            raise ValueError('Sidecar index/handle alignment differs')
        return {name:float(row[name]) for name in self.fields}
    def apply(self, targets, molecule, conformer, kind, view, Z):
        from .v31_loader import normalize_values
        values=self.lookup(molecule,conformer,kind);result=dict(targets)
        definitions={f['name']:f for f in view.fields}
        for name,value in values.items():
            target=targets.get(name)
            if target is None or not np.isfinite(value):continue
            if target.raw.size!=1:raise ValueError('F64 sidecar supports graph scalars only')
            if not target.valid.all():continue
            raw=np.full_like(target.raw,value,dtype=np.float64)
            spec=definitions[name].get('normalization',view.normalizations.get(name))
            result[name]=replace(target,raw=raw,values=normalize_values(raw,spec,Z=Z))
        return result
    def close(self):
        self._data=self._offsets=None