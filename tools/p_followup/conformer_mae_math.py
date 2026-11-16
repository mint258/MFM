"""Paired native-label differences, preserving canonical atoms and directed pairs."""
import numpy as np


def paired_error(ca,cb,da,db):
    # Entries contain prediction, original label, mask, and optional pair endpoints.
    for c,d in [(ca,da),(cb,db)]:
        for i in [1,2,3]:
            if c[i] is None or d[i] is None:
                if c[i] is not d[i]:raise ValueError('C/D original target identity differs')
            elif not np.array_equal(c[i],d[i],equal_nan=True):raise ValueError('C/D original labels, masks or endpoints differ')
    if ca[3] is None and cb[3] is None:
        if ca[1].shape!=cb[1].shape:raise ValueError('Same-MID canonical target shape differs')
        ia,ib=np.arange(len(ca[1])),np.arange(len(cb[1]))
    elif ca[3] is not None and cb[3] is not None:
        indices=[]
        for entry in [ca,cb]:
            keys=[tuple(map(int,p)) for p in entry[3]]
            if len(set(keys))!=len(keys):raise ValueError('Duplicate directed atom-pair endpoints')
            indices.append({key:i for i,key in enumerate(keys)})
        shared=sorted(indices[0].keys() & indices[1].keys())
        ia=np.asarray([indices[0][k] for k in shared],dtype=np.int64)
        ib=np.asarray([indices[1][k] for k in shared],dtype=np.int64)
    else:raise ValueError('Incompatible same-field pair identities')
    ca,da=[(v[0][ia],v[1][ia],v[2][ia]) for v in [ca,da]]
    cb,db=[(v[0][ib],v[1][ib],v[2][ib]) for v in [cb,db]]
    valid=ca[2]&cb[2]&np.isfinite(ca[1])&np.isfinite(cb[1])
    valid=valid&np.isfinite(ca[0])&np.isfinite(cb[0])&np.isfinite(da[0])&np.isfinite(db[0])
    reference=ca[1]-cb[1]
    return dict(observations=int(valid.sum()),
        C_absolute_error=float(np.abs(ca[0]-cb[0]-reference)[valid].sum()),
        D_absolute_error=float(np.abs(da[0]-db[0]-reference)[valid].sum()))
