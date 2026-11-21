"""Store original packed ECFP blocks as sklearn's supported sparse CSC input.

Only zero storage is omitted. Original little-endian bit order, component roles,
gas flag, sample order, targets, seeds and RF estimator parameters are unchanged.
"""
import numpy as np
from scipy.sparse import csr_matrix

def sparse_fingerprint_matrix(rows,packed_fields=("ecfp4_2048_packed",),gas_field=None):
    packed_fields=tuple(packed_fields)
    if not packed_fields or len(set(packed_fields))!=len(packed_fields):
        raise ValueError("Ordered distinct original fingerprint blocks are required")
    width=2048*len(packed_fields)+int(gas_field is not None)
    indices=[];indptr=[0]
    for row in rows:
        for block,key in enumerate(packed_fields):
            raw=row[key]
            if not isinstance(raw,(bytes,bytearray,memoryview)) or len(raw)!=256:
                raise ValueError("Each original packed ECFP4 block must have exactly2048bits")
            active=np.flatnonzero(np.unpackbits(np.frombuffer(raw,dtype=np.uint8),bitorder="little"))
            indices.extend((active+2048*block).tolist())
        if gas_field is not None:
            value=row[gas_field]
            if value not in (0,1,False,True):
                raise ValueError("The original explicit gas flag must remain binary")
            if value:indices.append(width-1)
        indptr.append(len(indices))
    if len(indices)>np.iinfo(np.int32).max:
        raise ValueError("This sklearn sparse interface requires32-bit fingerprint indices")
    values=np.ones(len(indices),dtype=np.float32)
    result=csr_matrix((values,np.asarray(indices,dtype=np.int32),np.asarray(indptr,dtype=np.int32)),
                      shape=(len(rows),width),dtype=np.float32).tocsc()
    result.sort_indices()
    return result
