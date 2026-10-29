"""Exact-tree method publication gate; metadata and source raw bytes only."""
from __future__ import annotations
import hashlib
from pathlib import Path
import re
from long_common import *

PREFIX='docs/model_v3/pre_registered_methods/native_S_long_operational_v8/'


def verify_method(item):
    require(binding(item['path'])==item,'Actual method receipt raw bytes changed')
    pub=read_ref(item)
    require(pub['schema']=='model_v3_exact_tree_publication_actual_v1'
        and pub['repository_full_name']=='mint258/MFM' and pub['branch']=='model-v3'
        and pub['public_branch_readback_verified'] is True
        and pub['public_Git_API_tree_readback_verified'] is True,
        'Actual new method exact-tree publication required')
    require(pub.get('truncated',False) is False,'Truncated public tree cannot qualify')
    table={row['path']:row for row in pub['files']}
    require(len(table)==len(pub['files']),'Duplicate public paths')
    pins=read(HERE/'source_pins.json')
    mapping=[(HERE/row['path'],PREFIX+row['path']) for row in pins['files']]
    mapping.append((HERE/'source_pins.json',PREFIX+'source_pins.json'))
    for row in pins['additional_publication_files']:
        source=Path(row['source']['path'])
        require(binding(source)==row['source'],'Shared auto-memory policy source changed')
        mapping.append((source,row['public_path']))
    require(len({name for _,name in mapping})==len(mapping),'Repeated required public source path')
    for source,name in mapping:
        raw=source.read_bytes();entry=table[name]
        require(entry['type']=='blob' and re.fullmatch('[0-9a-f]{40}',entry['sha'])
            and entry['sha']==hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),
            'Method source not exact published blob: '+name)
    return pub
