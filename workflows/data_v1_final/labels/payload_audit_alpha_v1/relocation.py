"""Explicit one-file Main->Alpha relocation; no prefix fallback or data rewriting."""
from __future__ import annotations
import json,os
from pathlib import Path
ROOT=Path('/gfshome/alpha/codex_data_v1_20261026')
FROZEN=ROOT/'code/labels_payload512_frozen_v1'
MAP=ROOT/'metadata/labels_payload512_v1/relocation_map.json'
MAIN=Path('/share/home/zixiao/descriptor_analysis')
CACHE=None

def mapping():
    global CACHE
    if CACHE is None:
        value=json.loads(MAP.read_text(encoding='utf-8-sig'))
        if value.get('schema')!='LABEL_PAYLOAD512_READONLY_RELOCATION_MAP_V1':raise ValueError('EXACT_EXPLICIT_LABELS_RELOCATION_MAP_REQUIRED')
        entries=value['entries'];by_origin={};by_target={}
        for row in entries:
            origin=row['origin_reference'];target=row['target_reference'];old=Path(origin['path']);new=Path(target['path'])
            if MAIN not in old.parents or ROOT not in new.parents or '..' in old.parts or '..' in new.parts:raise ValueError('EXPLICIT_ENDPOINT_PATH_REQUIRED')
            if origin['bytes']!=target['bytes'] or origin['sha256']!=target['sha256']:raise ValueError('ORIGINAL_INPUT_BYTES_MUST_NOT_CHANGE')
            if str(old) in by_origin or str(new) in by_target:raise ValueError('ONE_TO_ONE_RELOCATION_REQUIRED')
            by_origin[str(old)]=row;by_target[str(new)]=row
        CACHE={'body':value,'origin':by_origin,'target':by_target}
    return CACHE

def resolved_path(path):
    p=Path(path).absolute()
    if MAIN in p.parents:
        row=mapping()['origin'].get(str(p))
        if row is None:raise ValueError('UNDECLARED_MAIN_PATH_CANNOT_BE_OPENED:'+str(p))
        return Path(row['target_reference']['path'])
    local=os.environ.get('LABEL_PAYLOAD512_ALPHA_MEMORY_CONTROL')
    if local and (Path(local)==p or Path(local) in p.parents):return p
    if ROOT not in p.parents:raise ValueError('INPUT_OUTPUT_OUTSIDE_ACTUAL_ALPHA_ROOT:'+str(p))
    return p

def resolved_reference(reference):
    path=reference['path'];m=mapping();row=m['origin'].get(path) or m['target'].get(path)
    if row is not None:
        expected=row['origin_reference'] if path in m['origin'] else row['target_reference']
        if any(reference[k]!=expected[k] for k in ('path','bytes','sha256')):raise ValueError('EXACT_RELOCATION_SOURCE_PIN_DIFFERS')
        return {k:row['target_reference'][k] for k in ('path','bytes','sha256')}
    p=resolved_path(path)
    return dict(reference,path=str(p))

def relocated_adapter_config(config):
    import copy
    result=copy.deepcopy(config)
    result['adapter_source_pins']=[resolved_reference(p) for p in config['adapter_source_pins']]
    return result