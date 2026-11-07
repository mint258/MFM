"""Original MFM3 transactions/reader with explicit transport-only validation seam."""
from __future__ import annotations
import numpy as np
from . import contract as C,transport as T
L=C.legacy();B=L['wire_v1.store'];G=L['pipeline_v1.granular_store'];CODEC=L['wire_v1.codec']
FamilyWriter=B.FamilyWriter;FamilyReader=B.FamilyReader;_key=B._key
encode_record=CODEC.encode_record;decode_record=CODEC.decode_record;MASK_PREFIXES=G.MASK_PREFIXES


def validate_record(metadata,arrays,schema):
    if schema['kind']=='geometry':
        expected={'native_bond_index','native_bond_order'};C.need(expected<=set(arrays),'NATIVE_S_BOND_TRANSPORT_REQUIRED')
        idx,order=arrays['native_bond_index'],arrays['native_bond_order'];n=metadata['n_atoms']
        C.need(idx.dtype.str=='<i8' and idx.ndim==2 and idx.shape[0]==2 and order.dtype.str=='<i8' and order.shape==(idx.shape[1],)
            and np.all(idx>=0) and np.all(idx<n) and np.all(np.isin(order,[1,2,3,4])),'NATIVE_BOND_SOURCE_ORDER_CODES_AND_ATOM_ENDPOINTS')
        B._validate(metadata,{k:v for k,v in arrays.items() if k not in expected},schema);return
    temporary=dict(arrays);notes=dict(metadata.get('reason_granularity',{}))
    for tid,target in schema.get('ordered_record_targets',{}).items():
        note=notes.pop(tid);key=target['members'][0]['field_key'];prefix='transport/'+tid+'/';values=temporary.pop(prefix+'values');keep=temporary.pop('valid/'+prefix)
        C.need(note['mode']=='SOURCE_ORDERED_RECORDS_V1' and note['member']==key and note['order_and_duplicates_preserved'] is True,'EXPLICIT_R73_TRANSPORT_HEADER')
        count=len(values);C.need(values.dtype.str=='<f4' and values.shape==(count,) and keep.dtype.str=='|u1' and keep.shape==(count,)
            and np.all(keep<=1) and np.isfinite(values[keep.astype(bool)]).all(),'SOURCE_RECORD_F32_VALUES_AND_EXACT_MASK')
        atoms=[]
        for name in ('atom_i','atom_j','ordinal'):
            a=temporary.pop(prefix+name);C.need(a.dtype.str=='<i8' and a.shape==(count,),'R73_INDEX_OR_ORDINAL_LAYOUT');atoms.append(a)
        C.need(np.all(atoms[0]>=0) and np.all(atoms[0]<metadata['n_atoms']) and np.all(atoms[1]>=0) and np.all(atoms[1]<metadata['n_atoms'])
            and np.array_equal(atoms[2],np.arange(count,dtype='<i8')),'SOURCE_ORDINAL_NO_REORDER_AND_NATIVE_ATOM_RANGE')
        for name in ('basis_i','basis_j','channel'):
            data=temporary.pop(prefix+name+'_utf8');offset=temporary.pop(prefix+name+'_offsets')
            C.need(len(T.decode_strings(data,offset))==count,'EVERY_ORIGINAL_ENDPOINT_BASIS_CHANNEL_RETAINED')
        for name in ('channel_present','onsite_present','onsite'):
            a=temporary.pop(prefix+name);C.need(a.dtype.str=='|u1' and a.shape==(count,) and np.all(a<=1),'OPTIONAL_SOURCE_PRESENCE_NOT_INFERRED_FALSE')
        causes=[]
        for scope in ('source','new','review'):
            a=temporary.pop('reason_fields_'+scope+'/'+key)
            C.need(a.dtype.str=='<u2' and a.ndim==1 and np.all(a>0) and np.all(a<65535) and len(a)==len(np.unique(a)),'SOURCE_FIELD_REASON_SET_EXACT')
            if scope!='review':causes.extend(a.tolist())
        ix=temporary.pop('reason_leaf_index/'+key);codes=temporary.pop('reason_leaf_code/'+key)
        C.need(ix.dtype.str=='<i4' and ix.ndim==1 and codes.dtype.str=='<u2' and codes.shape==ix.shape
            and np.all(ix>=0) and np.all(ix<count) and len(np.unique(ix))==len(ix) and np.all(codes>0) and np.all(codes<65535)
            and np.all(keep[ix]==0),'SPARSE_LEAF_CAUSES_ORIGINAL_VALIDITY_ONLY')
        C.need(not np.any(keep==0) or causes or len(ix)==int(np.sum(keep==0)),'INVALID_RECORDS_REQUIRE_REAL_SOURCE_OR_NEW_CAUSES')
        C.need(note['source_container_state'] in ('PRESENT_ORDERED_RECORD_LIST','ORIGINAL_NULL_UNKNOWN_LAYOUT_NOT_EMPTY_SOURCE'),'SOURCE_NULL_LAYOUT_STATE_REQUIRED')
        if note['source_container_state'].startswith('ORIGINAL_NULL'):C.need(count==0 and note['source_record_count'] is None,'UNKNOWN_NULL_NOT_FAKE_ZERO_RECORD_SOURCE')
        else:C.need(note['source_record_count']==count,'EXACT_SOURCE_ORDERED_RECORD_COUNT')
    # Ordinary targets (including r674) retain the original granular validator.
    G.validate(dict(metadata,reason_granularity=notes),temporary,schema)


class Writer(FamilyWriter):
    def write_batch(self, records):
        if self.finished or self.env is None:
            raise ValueError("WRITER_ALREADY_CLOSED")
        added = molecules = 0
        with self.env.begin(write=True) as tx:
            for metadata, arrays in records:
                meta, encoded = decode_record(encode_record(metadata, arrays))
                validate_record(meta, encoded, self.schema)
                record_key, molecule_key = _key(meta["export_record_id"]), _key(meta["molecule_id"])
                data = {k: v for k, v in encoded.items() if not k.startswith(MASK_PREFIXES)} if self.masks is not None else encoded
                masks = {k: v for k, v in encoded.items() if k.startswith(MASK_PREFIXES)}
                if self.masks is not None and not tx.put(record_key, encode_record(meta, masks), db=self.masks, overwrite=False):
                    raise ValueError("DUPLICATE_MASK_RECORD_ID")
                if not tx.put(record_key, encode_record(meta, data), db=self.records, overwrite=False):
                    raise ValueError("DUPLICATE_EXPORT_RECORD_ID")
                molecules += int(tx.get(molecule_key, db=self.molecules) is None)
                if not tx.put(molecule_key, record_key, db=self.molecules, dupdata=False):
                    raise ValueError("DUPLICATE_MOLECULE_RECORD_INDEX")
                added += 1
        self.count += added; self.molecule_count += molecules


class Reader(FamilyReader):
    def get(self, record_id):
        with self.env.begin() as tx:
            raw = tx.get(_key(record_id), db=self.records)
            mask = tx.get(_key(record_id), db=self.masks) if self.masks is not None else None
        if raw is None:
            raise KeyError(record_id)
        meta, arrays = decode_record(raw)
        if self.masks is not None:
            if mask is None:
                raise ValueError("MISSING_MASK_RECORD")
            mask_meta, mask_arrays = decode_record(mask)
            if meta != mask_meta or set(arrays) & set(mask_arrays):
                raise ValueError("MASK_PAYLOAD_IDENTITY_MISMATCH")
            arrays.update(mask_arrays)
        if meta["export_record_id"] != record_id:
            raise ValueError("INDEX_PAYLOAD_ID_MISMATCH")
        validate_record(meta, arrays, self.schema)
        return meta, arrays

def open_accepted(release_reference,store_name):
    """Consumer API: internal candidate COMPLETE alone never authorizes a reader."""
    import json
    from . import io as I
    release=C.meta(release_reference)
    C.validate_published_release(release)
    C.need(release['schema']=='ROOT_ACCEPTED_FAMILY_EXPORT_RELEASE_V1' and release['consumer_release'] is True
        and release['status'] in ('FULL_V1_FROZEN','BOUNDED_D3_50K_TRAIN_5K_VAL_FROZEN_NOT_FULL'),'ACTUAL_EXTERNAL_RELEASE_NOT_INNER_CANDIDATE_STATE')
    receipt,_,plan=C.validate_actual_closure(release['actual_closure_references']);labels=C.meta(release['final_label_release_reference'])
    C.need(labels['final_consumer_release'] is True and labels['candidate_reference']==receipt['inline_final_label_candidate']['candidate_reference']
        and all(labels[k]==receipt['inline_final_label_candidate'][k] for k in ('registry_reference','mapping_reference','normalization_reference','mask_release_reference')),
        'EXTERNAL_SCIENTIFIC_CONFIG_EXACT_SAME_OBJECTS_NOT_DIFFERENT_SHA_EQUIVALENCE_ASSERTION')
    C.need(release['stores_catalogue_reference']==receipt['stores_catalogue_reference'],'RELEASED_CPU_WHOLE_SHA_CATALOGUE')
    found=None
    for item in I.jsonl(release['stores_catalogue_reference'],[release['stores_catalogue_reference']],lambda:None):
        if item['name']==store_name:C.need(found is None,'UNIQUE_ACCEPTED_STORE_NAME');found=item
    C.need(found is not None,'STORE_NOT_IN_ACTUAL_ACCEPTED_EXPORT')
    for key in ('manifest','data'):
        with I.held(found[key],[found[key]],lambda:None):pass
    reader=Reader(found['path'])
    try:
        C.need(reader.count==found['records'] and reader.molecule_count==found['molecules'],'ACCEPTED_COUNTS_NOT_CANDIDATE_ALIAS')
        C.need(reader.schema['exact_final_label_candidate']=={k:receipt['inline_final_label_candidate'][k] for k in ('registry_reference','mapping_reference','normalization_reference','mask_release_reference','candidate_reference')},
            'LMDB_EMBEDDED_IMMUTABLE_SCIENTIFIC_CONFIG_BINDING')
    except BaseException:reader.close();raise
    return reader