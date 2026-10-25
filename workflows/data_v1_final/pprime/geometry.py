"""Replace only the geometry at an explicit, auditable WP5 native-object boundary."""
from __future__ import annotations

import hashlib
import math
import struct

GEOMETRY_SOURCE = 'uff_sprime'
Q02_REASON = 'NOT_APPLICABLE_DIFFERENT_GEOMETRY_NO_STORED_UFF_PM7_HOF'


def geometry_hash(numbers, coordinates):
    """SB-2 convention: LE int64 Z followed by C-order LE float64 coordinates."""
    z = [int(x) for x in numbers]
    if not z or len(coordinates) != len(z):
        raise ValueError('UFF_ATOM_OR_COORDINATE_COUNT_MISMATCH')
    flat = []
    for row in coordinates:
        if len(row) != 3 or any(not math.isfinite(float(x)) for x in row):
            raise ValueError('UFF_COORDINATE_SHAPE_OR_FINITE_CHECK')
        flat.extend(float(x) for x in row)
    return hashlib.sha256(struct.pack('<' + 'q' * len(z), *z) +
                          struct.pack('<' + 'd' * len(flat), *flat)).hexdigest()


def adapt_native(original, pair, pair_cutoff_A=4.0):
    """Original reader has already checked source payload, Z and atom order.

    No old reader/function is patched. The new compute wrapper passes this native
    object directly to the unchanged WP5 invocation lifecycle.
    """
    import numpy as np
    row, conformer = pair['source'], pair['conformer']
    z = np.asarray(original['z'], dtype='<i8')
    xyz = np.asarray(conformer['coordinates'], dtype='<f8')
    observed = geometry_hash(z.tolist(), conformer['coordinates'])
    if pair.get('uff_geometry_sha256') and observed != pair['uff_geometry_sha256']:
        raise ValueError('UFF_GEOMETRY_SHA_CHANGED')
    coordinate_sha = hashlib.sha256(xyz.tobytes()).hexdigest()
    if pair.get('uff_coordinate_sha256') != coordinate_sha:
        raise ValueError('UFF_COORDINATE_SHA_CHANGED')
    atom_sha = hashlib.sha256(z.tobytes()).hexdigest()
    if atom_sha != conformer['atom_order_sha256'] or atom_sha != original['native_atom_order_sha256']:
        raise ValueError('UFF_NATIVE_ATOM_ORDER_MISMATCH')
    if conformer['source_record_id'] != row['record_id']:
        raise ValueError('UFF_SOURCE_RECORD_POINTER_CHANGED')
    if conformer['status'] != 'SUCCESS' or conformer['converged'] is not True:
        raise ValueError('UFF_CONFORMER_NOT_USABLE')
    # Source graph bonds remain even beyond the current-geometry pair cutoff.
    bonds = pair['bond_pairs']
    pairs = {(max(int(i), int(j)), min(int(i), int(j))) for i, j in bonds}
    pairs.update((i, j) for i in range(len(z)) for j in range(i)
                 if float(np.linalg.norm(xyz[i] - xyz[j])) <= pair_cutoff_A)
    if any(i == j or j < 0 or i >= len(z) for i, j in pairs):
        raise ValueError('UFF_PAIR_INDEX_INVALID')
    adapted = dict(original)
    adapted.update(coords=xyz, energy=None, pairs=sorted(pairs),
                   native_coordinates_sha256=hashlib.sha256(xyz.tobytes()).hexdigest())
    provenance = {'geometry_source': GEOMETRY_SOURCE, 'uff_geometry_sha256': observed,
                  'uff_coordinate_sha256': adapted['native_coordinates_sha256'],
                  'pm7_source_geometry_sha256': original['native_coordinates_sha256'],
                  'pm7_source_stored_HOF_kcal_mol': original.get('energy'),
                  'source_record_id': row['record_id'],
                  'source_payload_sha256': row['record_payload_sha256'],
                  'native_atom_order_sha256': atom_sha,
                  'Q02_applicable': False, 'Q02_reason': Q02_REASON}
    return adapted, provenance
