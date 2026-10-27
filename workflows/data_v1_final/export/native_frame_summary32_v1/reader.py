"""Declared retained scientific DATA only, original bit-exact tree codec."""
from __future__ import annotations
import hashlib,json,os,re,struct
from workflows.data_v1_final.export.native_body_frame32_v1 import reader as D
from workflows.data_v1_final.export.native_availability_v1 import reader as I
from workflows.data_v1_final.labels.lossless_projection_pilot_v1.projection import decode,signature
from . import contract as C


def read(reference,references,check,cap):
    C.need(reference['bytes']<=cap,'RETAINED_DATA_PER_FILE_CAP_BEFORE_READ')
    with D.held(reference,references,check,True) as (path,fd,before):
        data=bytearray()
        while True:
            check();part=os.read(fd,1<<20)
            if not part:break
            data.extend(part);C.need(len(data)<=cap,'BOUNDED_FULL_DATA_READ')
        C.need(len(data)==reference['bytes'] and hashlib.sha256(data).hexdigest()==reference['sha256'],'SAME_FD_FULL_BYTES_AND_SHA')
        return bytes(data)


def decode_evidence(data):
    value=json.loads(data,object_pairs_hook=I.no_duplicates)
    C.need(value['schema']=='NATIVE_BODY_FRAME32_LOSSLESS_DATA_EVIDENCE_V1'
        and type(value['tree_json']) is str and type(value['values_float64_bits_little_endian']) is list,'ORIGINAL_B_LOSSLESS_TREE_SCHEMA')
    words=value['values_float64_bits_little_endian']
    C.need(all(type(w) is str and re.fullmatch('[0-9a-f]{16}',w) is not None for w in words),'EXACT_IEEE64_HEX_POOL')
    floats=[struct.unpack('<d',bytes.fromhex(w))[0] for w in words];result=decode(value['tree_json'],floats)
    C.need(signature(result)==value['scientific_signature'],'ORIGINAL_SCIENTIFIC_TREE_FULL_BIT_SIGNATURE')
    return result


def evidence(row,references,check):
    value=decode_evidence(read(row['evidence_reference'],references,check,C.B.ROW_CAP))
    C.need(value['original_raw_bundle_reference']==row['raw_reference'] and value['D1_jointly_frozen'] is False
        and value['new_QM_calls']==value['new_UFF_calls']==0,'RETAINED_ORIGINAL_B_RECORD_AND_RAW_BINDING')
    ref=C.triple(value['hash_reconstructed_input_DATA_reference'])
    C.need(ref['path']==C.expected_bundle_path(row['evidence_reference']) and ref['bytes']<=8<<20
        and ref['sha256']==value['original_raw_metadata']['input_bundle_sha256']
        ==value['native_evidence']['input_binding']['reconstructed_input_sha_bundle'],
        'ORIGINAL_B_INPUT_TRIPLE_SAME_OUTPUT_PATH_AND_ORIGINAL_INPUT_SHA')
    return value,ref


def prepare_one(row,references,check):
    value,ref=evidence(row,references,check);key=value['key']
    return {'position':row['position'],'calc_type':key['calc_type'],'key':key,
        'evidence_reference':row['evidence_reference'],'raw_reference':row['raw_reference'],'input_reference':ref,
        'authority':'actualB3708 scientific evidence exact embedded producer triple; input body not opened'}
