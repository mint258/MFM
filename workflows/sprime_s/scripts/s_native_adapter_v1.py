"""Read-only formal-population adapter for the existing native training interface.

The caller supplies the selected bound transport and view recipe. This module
does not select a scientific protocol, model, loss weights or training run.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import OrderedDict
from copy import deepcopy
import hashlib,json,os,pickle
from pathlib import Path
from types import SimpleNamespace
import lmdb,numpy as np,pyarrow as pa
from prepare import ROOT,PROJECT,sha
from phychem_mfm.phase1.identity import canonical_hash
from phychem_mfm.phase1.full_corpus_loader import FullCorpusViewsDataset,NativeByteLRU,_strict_normalizer,_load_bound_native_transport

def identity(path):
    value=Path(path).stat()
    return (value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns)

@dataclass(frozen=True)
class RecordRef:
    logical_index:int
    base_row:int
    shard_id:int
    real_index:int
    native_n_atoms:int
    record_id:str
    molecule_id:str
    payload_sha256:str

class MappedRecordIndex:
    def __init__(self,role,transport_binding,shard_snapshot,*,verify_hashes=True):
        self.role=role;self.manifest_path=ROOT/'training_inputs_v1/manifest.json'
        value=json.loads(self.manifest_path.read_text());assert value['status']=='INPUT_METADATA_CLOSED_NATIVE_SAMPLE_PASS'
        self.metadata_ref=next(r for r in value['references'] if r['role']==role and r['kind']=='record_metadata')
        self.atoms_ref=next(r for r in value['references'] if r['role']==role and r['kind']=='atom_counts')
        self.path=Path(self.metadata_ref['path']);self.atoms_path=Path(self.atoms_ref['path'])
        self.rows=value['roles'][role]['records'];self.batch_rows=value['roles'][role]['batch_rows']
        assert self.atoms_ref['bytes']==4*self.rows and self.metadata_ref['rows']==self.rows
        self.manifest={'native_transport':deepcopy(transport_binding)}
        self.content_sha256=canonical_hash({'input_manifest_sha256':sha(self.manifest_path),'role':role})
        self.shards={int(k):v for k,v in shard_snapshot['shards'].items()}
        self._metadata_identity=identity(self.path);self._atoms_identity=identity(self.atoms_path)
        if verify_hashes:self.verify_unchanged()
        self._map=self._reader=self._atoms=self._batch=self._batch_number=None

    def __len__(self):return self.rows

    def _open(self):
        if self._reader is None:
            assert identity(self.path)==self._metadata_identity and identity(self.atoms_path)==self._atoms_identity,'ACTUAL_RECORD_MANIFEST_MISMATCH'
            self._map=pa.memory_map(str(self.path),'r');self._reader=pa.ipc.open_file(self._map)
            self._atoms=np.memmap(self.atoms_path,dtype='<u4',mode='r',shape=(self.rows,))

    def ref(self,index):
        index=int(index);assert 0<=index<self.rows;self._open()
        batch_number,offset=divmod(index,self.batch_rows)
        if self._batch_number!=batch_number:
            self._batch=self._reader.get_batch(batch_number);self._batch_number=batch_number
        field=lambda name:self._batch.column(self._batch.schema.get_field_index(name))[offset].as_py()
        sid=int(field('shard_id'));n=int(self._atoms[index]);assert n==int(field('total_atoms'))
        assert field('source_path')==self.shards[sid]['declared_source_path']
        return RecordRef(index,index,sid,int(field('real_index')),n,field('record_id'),field('molecule_id'),field('record_payload_sha256'))

    def verify_shard_stats(self):
        for shard in self.shards.values():
            assert identity(shard['path'])==tuple(shard['identity']),'ACTUAL_RECORD_MANIFEST_MISMATCH'

    def verify_unchanged(self):
        assert identity(self.path)==self._metadata_identity and identity(self.atoms_path)==self._atoms_identity
        assert sha(self.path)==self.metadata_ref['sha256'] and sha(self.atoms_path)==self.atoms_ref['sha256']
        self.verify_shard_stats()

    def close(self):
        self._batch=self._reader=self._atoms=self._batch_number=None
        if self._map is not None:self._map.close()
        self._map=None

    def __getstate__(self):
        state=self.__dict__.copy();state.update(_map=None,_reader=None,_atoms=None,_batch=None,_batch_number=None);return state

class CountIndex:
    """Same bound index identity; sampler reads only four-byte native counts."""
    def __init__(self,index):
        self.content_sha256=index.content_sha256;self.path=index.atoms_path
        self.rows=len(index);self._identity=index._atoms_identity;self._atoms=None
    def __len__(self):return self.rows
    def ref(self,index):
        index=int(index);assert 0<=index<self.rows
        if self._atoms is None:
            assert identity(self.path)==self._identity
            self._atoms=np.memmap(self.path,dtype='<u4',mode='r',shape=(self.rows,))
        return SimpleNamespace(native_n_atoms=int(self._atoms[index]))
    def close(self):self._atoms=None

class ReadOnlyHandles:
    def __init__(self,shards,max_handles):
        self.shards=shards;self.max_handles=max_handles;self.entries=OrderedDict();self.pid=os.getpid()
    def get(self,sid):
        assert self.pid==os.getpid()
        if sid in self.entries:
            env=self.entries.pop(sid);self.entries[sid]=env;return env
        while len(self.entries)>=self.max_handles:self.entries.popitem(last=False)[1].close()
        shard=self.shards[sid];assert identity(shard['path'])==tuple(shard['identity'])
        env=lmdb.open(shard['path'],subdir=False,readonly=True,lock=False,readahead=False,create=False,meminit=False,max_readers=256)
        try:
            with env.begin() as tx:
                header=tx.get(b'__len__')
                assert header is not None and hashlib.sha256(header).hexdigest()==shard['length_header_sha256']
                assert tx.stat()['entries']==shard['entries']
            assert env.info()['last_txnid']==shard['last_txnid']
        except BaseException:env.close();raise
        self.entries[sid]=env;return env
    def close(self):
        for env in self.entries.values():env.close()
        self.entries.clear()

class ManifestViewsDataset(FullCorpusViewsDataset):
    """Preserve inherited native views; verify actual raw payload every access."""
    def _ensure_worker(self,logical_index):
        if self._pid!=os.getpid():
            self.close()
            if self.native_transport is None:
                self.native_transport=_load_bound_native_transport(self._transport_path,self.native_transport_binding,self._transport_identity)
            if self.normalizer is None:self.normalizer=_strict_normalizer()
            self._cache=NativeByteLRU(self.cache_bytes,max_entries=self.max_cache_entries)
            self._handles=ReadOnlyHandles(self.index.shards,self.max_handles);self._pid=os.getpid()
        block=logical_index//self.block_size
        if self._block!=block:
            assert identity(self._transport_path)==self._transport_identity
            self.index.verify_shard_stats();self._handles.close()
        self._block=block

    def _native(self,ref):
        self._ensure_worker(ref.logical_index)
        with self._handles.get(ref.shard_id).begin() as tx:raw=tx.get(f'{ref.real_index:09d}'.encode())
        assert raw is not None and len(raw)<=self.max_record_bytes and hashlib.sha256(raw).hexdigest()==ref.payload_sha256,'ACTUAL_RECORD_MANIFEST_MISMATCH'
        cached=self._cache.get((ref.shard_id,ref.real_index))
        if cached is None:
            record=self.native_transport(pickle.loads(raw),real_index=ref.real_index,normalizer=self.normalizer)
            self._validate_native(record,ref);cached=pickle.dumps(record,protocol=pickle.HIGHEST_PROTOCOL)
            assert len(cached)<=self.max_record_bytes;self._cache.put((ref.shard_id,ref.real_index),cached)
        record=pickle.loads(cached);self._validate_native(record,ref)
        record.phase1_record_key=ref.record_id;record.phase1_pool_hash=self.index.content_sha256
        record.phase1_atom_encoding='zero_based';record.phase1_native_transport_sha256=self.native_transport_binding['source_sha256']
        record.phase1_logical_ordinal=ref.logical_index;record.phase1_base_row=ref.base_row
        return record
