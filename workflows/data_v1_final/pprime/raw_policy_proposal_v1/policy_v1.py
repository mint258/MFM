"""PROPOSAL ONLY. Stable raw selection; does not activate a retention policy."""
from __future__ import annotations
import hashlib
import json


def audit_key(molecule_id, source_shard_id, size_stratum, physical_identity, seed=20261010):
    kind=physical_identity.get('namespace')
    if kind=='accepted_original_sprime':
        if set(physical_identity)!={'namespace','source_conformer_id'} or type(physical_identity['source_conformer_id']) is not int or physical_identity['source_conformer_id']<0:
            raise ValueError('EXPLICIT_ORIGINAL_INTEGER_SPRIME_ID_REQUIRED')
    elif kind=='data_v1_fill':
        if set(physical_identity)!={'namespace','seed','candidate_id','task_key'}:
            raise ValueError('EXPLICIT_FILL_PHYSICAL_IDENTITY_REQUIRED')
        if type(physical_identity['seed']) is not int or physical_identity['seed']<=0 or type(physical_identity['candidate_id']) is not int or physical_identity['candidate_id']<0:
            raise ValueError('REAL_FILL_SEED_AND_CANDIDATE_REQUIRED')
        key=physical_identity['task_key']
        if not isinstance(key,str) or len(key)!=64 or any(c not in '0123456789abcdef' for c in key):
            raise ValueError('FROZEN_FILL_ONCE_TASK_KEY_REQUIRED')
    else:
        raise ValueError('N1_EXPANDED_OR_UNKNOWN_IDENTITY_NOT_APPROVED_BY_THIS_PROPOSAL')
    if not isinstance(molecule_id,str) or not molecule_id or type(source_shard_id) is not int or not 0<=source_shard_id<=10 or size_stratum not in {'0_20','21_40','41_75','above_75'} or seed!=20261010:
        raise ValueError('FIXED_MOLECULE_STRATUM_AND_AUDIT_SEED_REQUIRED')
    # Same canonical JSON convention as P-prime source manifests. No ordinal,
    # population rank/count, native anchor, file path or Python randomized hash.
    payload=json.dumps(['pprime-full-raw-audit-v1',seed,source_shard_id,size_stratum,
        'uff_sprime',molecule_id,physical_identity],sort_keys=True,separators=(',',':'),
        ensure_ascii=False,allow_nan=False).encode('utf-8')
    sha=hashlib.sha256(payload).hexdigest()
    bucket=int(sha,16)%10000
    return {'audit_key_sha256':sha,'bucket':bucket,'selected':bucket<100}


def pilot_union(rows, original_twenty):
    """Pure proposal helper. IDs/source bytes must be verified by a future adapter."""
    if len(original_twenty)!=20 or len(set(original_twenty))!=20:
        raise ValueError('EXACT_ORIGINAL_FROZEN20_AUDIT_IDS_REQUIRED')
    ids=[row['record_id'] for row in rows]
    if len(ids)!=len(set(ids)) or not set(original_twenty)<=set(ids):
        raise ValueError('ORIGINAL_AUDIT_MUST_BE_PRESENT_IN_UNIQUE_PILOT_INPUTS')
    selected=[]
    for row in rows:
        result=audit_key(row['molecule_id'],row['source_shard_id'],row['size_stratum'],row['physical_identity'])
        original=row['record_id'] in original_twenty
        if original or result['selected']:
            selected.append(dict(row,**result,original_frozen_audit=original,
                extra_reproduction_retention=original and not result['selected'],
                retain_all_twelve_raw=True))
    return sorted(selected,key=lambda row:row['record_id'])
