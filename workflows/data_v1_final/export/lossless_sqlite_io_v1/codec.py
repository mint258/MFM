"""Lossless internal SQLite BLOB wrapper; final training codecs remain original."""
import hashlib,json,struct,zlib
from workflows.data_v1_final.export.d5_inputs_compound_day_v1 import core as ORIGINAL
from workflows.data_v1_final.export.d5_inputs_builder_v1 import build as FORMAT
from workflows.data_v1_final.labels.lossless_projection_pilot_v1 import projection as TREE
MAGIC=b'DV1Z1\x00'

def __getattr__(name):return getattr(ORIGINAL,name)

def encode_raw(value):
    # Exactly the original encoded bytes and signature, reusing the same tree.
    tree,floats=TREE.encode(value);h=hashlib.sha256(tree.encode('utf-8'))
    for v in floats:h.update(struct.pack('<d',v))
    raw=(json.dumps({'schema':'D5_INPUTS_LOSSLESS_MOLECULE_V1','tree':tree,
      'f64_le':[struct.pack('<d',v).hex()for v in floats],'signature':h.hexdigest()},
      ensure_ascii=False,allow_nan=False)+'\n').encode()
    FORMAT.C.need(len(raw)<=FORMAT.I.ROW_CAP,'COMPLETE_MOLECULE_PACKET_SOFTWARE_CAP_NO_TRUNCATION')
    return raw

def encode(value):return MAGIC+zlib.compress(encode_raw(value),level=1)

def original_bytes(raw):
    if not raw.startswith(MAGIC):return raw
    obj=zlib.decompressobj();value=obj.decompress(raw[len(MAGIC):],FORMAT.I.ROW_CAP+1)
    FORMAT.C.need(len(value)<=FORMAT.I.ROW_CAP and obj.eof and not obj.unused_data and not obj.unconsumed_tail,
      'BOUNDED_COMPLETE_INTERNAL_BLOB_NO_TRUNCATION_OR_TRAILING_DATA')
    return value

def decode(raw):return ORIGINAL.decode(original_bytes(raw))

def byte_proof():
    samples=[None,True,False,0,-42,'Unicode: α/碳',b'\x00\xff',
      {'numbers':[0.,-0.,1.0000000000000002,1.e300,-1.e-300,float('nan'),float('inf'),None],
       'tuple':(1,2.),'ordered':[{'i':1,'j':0,'value':-.0},{'i':1,'j':0,'value':.25}],
       'mask':[True,False],'nested':{'none':None}}]
    for value in samples:
        old=ORIGINAL.encode(value);raw=encode_raw(value);stored=encode(value)
        FORMAT.C.need(raw==old==original_bytes(stored),'ORIGINAL_FULL_WIRE_BYTES_AFTER_INTERNAL_COMPRESSION')
        FORMAT.C.need(encode_raw(decode(stored))==old and encode_raw(decode(old))==old,'ORIGINAL_DECODED_TREE_AND_F64_BYTES_IDENTICAL')
    return {'original_wire_bytes_equal':True,'compressed_bytes_expand_to_original':True,'original_decoder_used':True,
      'F64_signed_zero_None_NaN_order_tuple_bytes_Unicode_preserved':True,'fixtures':len(samples),
      'internal_blob_codec':'DV1Z1_ZLIB_ORIGINAL_LOSSLESS','final_LMDB_F32_F64_sidecar_and_parquet_formats_unchanged':True}
