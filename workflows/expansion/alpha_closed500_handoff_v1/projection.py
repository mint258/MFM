"""Lossless graph-only query projection for typed pool/baseline consumers."""
import json
import os
from pathlib import Path
from ..alpha_runtime_v1.common import need, reference, write as write_new

QUERY_FIELDS = ('cid', 'full_key', 'heavy_atoms', 'element_combination', 'generic_murcko', 'generic_ring_systems', 'ecfp4_2048_hex')
RECIPE = 'ECFP4_2048_radius2_chiralityFalse_rdkit2025.09.5'


def query_projection(db, relation, path, expected, check, *, sample_order=False):
    cursor = db.execute('SELECT ' + ','.join(QUERY_FIELDS) + ' FROM ' + relation + ' ORDER BY ' + ('sample_ordinal' if sample_order else 'full_key,cid'))
    n = 0
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        while True:
            values = cursor.fetchmany(8192)
            if not values:
                break
            check()
            for values_row in values:
                stream.write(json.dumps(dict(zip(QUERY_FIELDS, values_row)), separators=(',', ':'), ensure_ascii=True, allow_nan=False) + '\n')
                n += 1
        stream.flush(); os.fsync(stream.fileno())
    need(n == expected, 'Exact graph query projection must conserve full molecular membership')
    return {**reference(path), 'rows': n}
