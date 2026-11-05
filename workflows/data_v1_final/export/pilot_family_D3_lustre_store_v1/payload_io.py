"""Lossless internal stage/F64 storage; final MFM3 codec remains original."""
import hashlib,json,pathlib,zlib
from workflows.data_v1_final.export.pilot_D5_parallel_guide_v1 import writer_adapter as A,native_io
from workflows.data_v1_final.export.pilot_D5_parallel_guide_v1.resource import ObjectProxy,clone
from workflows.data_v1_final.export.pilot_family_D3_census_resume_v3 import writer as W,io as I

PAYLOAD_MAGIC=b'DV1PZ1\x00'
METADATA_MAGIC=b'DV1JZ1\x00'

def _encode(raw,magic):return magic+zlib.compress(raw,1)

def _decode(value,magic):
    raw=bytes(value)
    if not raw.startswith(magic):return raw
    stream=zlib.decompressobj();result=stream.decompress(raw[len(magic):])+stream.flush()
    W.C.need(stream.eof and not stream.unused_data and not stream.unconsumed_tail,'COMPLETE_INTERNAL_ZLIB_STREAM')
    return result

def decode_payload(value):return _decode(value,PAYLOAD_MAGIC)

def decode_metadata(value):
    return value if isinstance(value,str) else _decode(value,METADATA_MAGIC).decode('utf-8')

def pack(arrays,annotations=None):return _encode(W.S.pack(arrays,annotations),PAYLOAD_MAGIC)
def unpack(value):return W.S.unpack(decode_payload(value))
def reason_annotations(value):return W.S.reason_annotations(decode_payload(value))

def stage_source(**overrides):
    bindings=dict(pack=pack,unpack=unpack,reason_annotations=reason_annotations);bindings.update(overrides)
    return ObjectProxy(W.S,**bindings)

class LocatorConnection(ObjectProxy):
    def execute(self,sql,parameters=()):
        statement=' '.join(sql.strip().split()).upper()
        if statement.startswith('INSERT INTO PIECES ') and len(parameters)==5:
            parameters=list(parameters);value=parameters[4]
            if isinstance(value,str):parameters[4]=_encode(value.encode('utf-8'),METADATA_MAGIC)
            elif value is not None and not bytes(value).startswith(METADATA_MAGIC):
                parameters[4]=_encode(bytes(value),METADATA_MAGIC)
            parameters=tuple(parameters)
        return self.original.execute(sql,parameters)

def stage_connection(db):
    return db if isinstance(db,LocatorConnection) else LocatorConnection(db)

def locator_json_loads(value,*args,**kwargs):
    return json.loads(decode_metadata(value),*args,**kwargs)

class Sidecar(A.Sidecar):
    def put(self,metadata,arrays):
        W.C.need(all(a.dtype.itemsize==8 for a in arrays.values() if a.dtype.kind=='f'),'PERMANENT_SOURCE_FLOAT64')
        raw=W.S.pack(arrays);sha=hashlib.sha256(raw).hexdigest();rid=metadata['export_record_id']
        text=W.CODEC.canonical_json(metadata)
        self.db.execute('INSERT INTO authority VALUES(?,?,?,?)',
            (rid,_encode(text,METADATA_MAGIC),_encode(raw,PAYLOAD_MAGIC),sha));self.count+=1
        return dict(schema='PERMANENT_F64_SIDECAR_RECORD_V1',file_name=self.path.name,record_id=rid,
                    payload_sha256=sha,source_dtype='float64',training_casts=1,
                    internal_storage_codec='ZLIB1_ORIGINAL_PAYLOAD_AND_JSON_V1')

    def finish(self):
        result=super().finish()
        result['internal_storage_codec']='ZLIB1_ORIGINAL_PAYLOAD_AND_JSON_V1'
        result['payload_codec']='DV1PZ1_ZLIB1_ORIGINAL_SPACK_BYTES_LEGACY_RAW_COMPATIBLE'
        result['metadata_codec']='DV1JZ1_ZLIB1_ORIGINAL_CANONICAL_JSON_UTF8_LEGACY_TEXT_COMPATIBLE'
        result['payload_SHA_scope']='ORIGINAL_UNCOMPRESSED_STAGE_BYTES'
        result['reader_entrypoint']=__name__+'.Reader'
        result['decode_payload_entrypoint']=__name__+'.decode_payload'
        result['decode_metadata_entrypoint']=__name__+'.decode_metadata'
        return result

class Reader(W.Reader):
    def get_f64(self,rid,sidecar_reference):
        path=pathlib.Path(sidecar_reference['path']);before=I.identity(path)
        W.C.need(before[2]==sidecar_reference['bytes'] and not any(p.is_symlink() for p in(path,*path.parents)),
                 'EXACT_CLOSED_F64_AUTHORITY_FRAME')
        db=I.connect(path,True)
        try:
            row=db.execute('SELECT metadata,payload,sha FROM authority WHERE rid=?',(rid,)).fetchone()
            W.C.need(row is not None,'EXACT_F64_AUTHORITY_RECORD')
            metadata,_=self.get(rid);raw=decode_payload(row['payload'])
            W.C.need(metadata['permanent_F64_sidecar_record']['payload_sha256']==row['sha']==hashlib.sha256(raw).hexdigest(),
                     'ORIGINAL_UNCOMPRESSED_F64_PAYLOAD_SHA')
            return json.loads(decode_metadata(row['metadata'])),W.S.unpack(raw)
        finally:
            db.close();W.C.need(I.identity(path)==before,'CLOSED_F64_AUTHORITY_FRAME_STABLE')

class TrainingWriter(A.TrainingWriter):
    """Keep full audit metadata in its existing F64 authority, once per record."""
    def write_batch(self,records):
        compact=[]
        for metadata,arrays in records:
            value=dict(metadata)
            fields=[key for key in ('actual_geometry_provenance','permanent_source_locators','source_missing_positions')if key in value]
            if fields:
                authority=value['permanent_F64_sidecar_record']
                for key in fields:value.pop(key)
                value['source_trace_authority']=dict(file_name=authority['file_name'],record_id=authority['record_id'],
                    fields=fields,complete_original_metadata_retained=True,reader_entrypoint=__name__+'.Reader.get_f64')
            compact.append((value,arrays))
        return super().write_batch(compact)

class AnnotationIO(A.AnnotationIO):
    def reason_annotations(self,packed):return super().reason_annotations(decode_payload(packed))

def write(db,root,compiled,policy,plan,proof,budget,*,metadata_factory=None):
    """Original writer; internal compression and post-closure payload release only."""
    annotations=AnnotationIO(compiled,metadata_factory or W.metadata);root=pathlib.Path(root)
    original_append=I.append
    def append(path,value):
        if pathlib.Path(path)==root/'shard_checkpoints.jsonl':
            W.C.need(value['all_stores_and_f64_closed'] is True,'SHARD_CLOSED_BEFORE_INTERNAL_PAYLOAD_RELEASE')
            budget.check()
            db.execute('UPDATE pieces SET payload=? WHERE gid IN(SELECT gid FROM geometries WHERE mid>=? AND mid<=?)',
                       (b'',value['first_mid'],value['last_mid']));db.commit()
            incremental=db.execute('PRAGMA auto_vacuum').fetchone()[0]==2
            if incremental:db.execute('PRAGMA incremental_vacuum');db.commit()
            value=dict(value,internal_payloads_released_after_authority_closure=True,
                       source_locators_and_shapes_retained=True,incremental_vacuum_applied=incremental)
        return original_append(path,value)
    geometry_arrays=clone(W.geometry_arrays,T=ObjectProxy(W.T,native_bonds=native_io.native_bonds))
    function=clone(W.write,metadata=annotations.metadata,geometry_arrays=geometry_arrays,Sidecar=Sidecar,
        I=ObjectProxy(I,append=append),S=stage_source(reason_annotations=annotations.reason_annotations),
        json=ObjectProxy(W.json,loads=locator_json_loads),
        V=ObjectProxy(W.V,annotate=annotations.annotate),B=ObjectProxy(W.B,Writer=TrainingWriter))
    return function(db,root,compiled,policy,plan,proof,budget)
