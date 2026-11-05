"""Original lossless wire bytes, constructing the unchanged tree only once."""
import hashlib,json,struct
from workflows.data_v1_final.export.d5_inputs_compound_day_v1 import core as ORIGINAL
from workflows.data_v1_final.export.d5_inputs_builder_v1 import build as FORMAT
from workflows.data_v1_final.labels.lossless_projection_pilot_v1 import projection as TREE

def __getattr__(name):return getattr(ORIGINAL,name)

def encode(value):
    # Original signature(value) redoes TREE.encode(value). Reuse precisely
    # those same original tree/floats to compute the same original signature.
    tree,floats=TREE.encode(value);h=hashlib.sha256(tree.encode('utf-8'))
    for v in floats:h.update(struct.pack('<d',v))
    raw=(json.dumps({'schema':'D5_INPUTS_LOSSLESS_MOLECULE_V1','tree':tree,
       'f64_le':[struct.pack('<d',v).hex()for v in floats],'signature':h.hexdigest()},
       ensure_ascii=False,allow_nan=False)+'\n').encode()
    FORMAT.C.need(len(raw)<=FORMAT.I.ROW_CAP,'COMPLETE_MOLECULE_PACKET_SOFTWARE_CAP_NO_TRUNCATION')
    return raw

def byte_proof():
    # Same required Source IO method, small original-format fixtures only.
    samples=[None,True,False,0,-42,'Unicode: α/碳',b'\x00\xff',
      {'numbers':[0.,-0.,1.0000000000000002,1.e300,-1.e-300,float('nan'),float('inf'),None],
       'tuple':(1,2.),'ordered':[{'i':1,'j':0,'value':-.0},{'i':1,'j':0,'value':.25}],
       'mask':[True,False],'nested':{'none':None}}]
    for value in samples:
        original=ORIGINAL.encode(value);current=encode(value)
        FORMAT.C.need(current==original,'EXACT_ORIGINAL_WIRE_BYTES_NOT_NEW_CODEC_OR_PRECISION')
        FORMAT.C.need(encode(ORIGINAL.decode(current))==original,'ORIGINAL_DECODER_ACCEPTS_EXACT_SAME_BYTES')
    return {'original_tree_encoder_object':True,'original_wire_bytes_equal':True,
      'original_decoder_unchanged':True,'schema_dtype_order_and_signature_unchanged':True,
      'redundant_tree_construction_removed':True,'fixtures':len(samples),'scientific_values_or_masks_changed':False}
