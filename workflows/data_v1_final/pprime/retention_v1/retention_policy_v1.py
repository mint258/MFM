"""Stable raw-audit helpers. Scientific inputs and frozen source rows are immutable."""
from __future__ import annotations
from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys

PARENT=Path(__file__).absolute().parent.parent
sys.path.insert(0,str(PARENT))
import common as IO
from prepare_pilot import source_paths

SELECTOR=PARENT/'raw_policy_proposal_v1'/'policy_v1.py'
spec=importlib.util.spec_from_file_location('_pprime_stable_raw_selector_v1',SELECTOR)
selector=importlib.util.module_from_spec(spec);spec.loader.exec_module(selector)
audit_key=selector.audit_key


def load(path):
    c=json.loads(Path(path).read_text())
    if c.get('schema')!='PPRIME_STABLE_RAW_RETENTION_POLICY_V1' or c.get('seed')!=20261010 or c.get('basis_points')!=100 or c.get('modulus')!=10000:
        raise ValueError('REGISTERED_STABLE_RAW_POLICY_REQUIRED')
    for pin in c['parent_source_pins']:
        IO.require_pin(pin)
        local=PARENT/Path(pin['path']).name
        if local.is_file() and IO.digest(local)!=pin['sha256']:raise ValueError('ACTUALLY_IMPORTED_RETENTION_PARENT_CHANGED')
    IO.require_pin(c['selector'])
    if IO.digest(SELECTOR)!=c['selector']['sha256']:raise ValueError('ACTUAL_STABLE_SELECTOR_CHANGED')
    pilot=IO.load_config(IO.require_pin(c['pilot_config']))
    return c,pilot


def heavy_bin(n):
    if type(n) is not int or n<=0:raise ValueError('ACTUAL_SOURCE_HEAVY_ATOM_COUNT_REQUIRED')
    return '0_20' if n<=20 else '21_40' if n<=40 else '41_75' if n<=75 else 'above_75'


def stable_source_row(record_id,molecule_id,source,identity,sources):
    paths={r['path']:int(r['shard_id']) for r in sources}
    if len(paths)!=11 or set(paths.values())!=set(range(11)):
        raise ValueError('EXACT_ORIGINAL_ELEVEN_SOURCE_SHARDS_REQUIRED')
    if source.get('source_path') not in paths or paths[source['source_path']]!=source.get('shard_id'):
        raise ValueError('SOURCE_PATH_AND_ORIGINAL_SHARD_ID_MISMATCH')
    if source.get('molecule_id')!=molecule_id:
        raise ValueError('SOURCE_MOLECULE_MISMATCH')
    size=heavy_bin(source.get('heavy_atoms'))
    if size!=source.get('size_stratum') or type(source.get('file_group')) is not int:
        raise ValueError('FROZEN_HEAVY_BIN_OR_LEGACY_ENGINE_GROUP_MISMATCH')
    result=audit_key(molecule_id,source['shard_id'],size,identity)
    return {'record_id':record_id,'geometry_source':'uff_sprime','molecule_id':molecule_id,
        'physical_identity':identity,'source_shard_id':source['shard_id'],
        'legacy_engine_file_group':source['file_group'],'size_stratum':size,
        'source_path':source['source_path'],'source_record_id':source['record_id'],
        'source_payload_sha256':source['record_payload_sha256'],**result}


def source_audit(pair,sources):
    source=pair['source'];conf=pair['conformer']
    if conf.get('source_record_id')!=source.get('record_id'):
        raise ValueError('CONFORMER_SOURCE_ANCHOR_MISMATCH')
    if conf.get('status')!='SUCCESS' or conf.get('converged') is not True:
        raise ValueError('ACTUAL_USABLE_SOURCE_CONFORMER_REQUIRED')
    source_id=conf.get('sprime_conf_idx')
    if type(source_id) is not int or source_id<0:
        raise ValueError('ORIGINAL_SPRIME_PHYSICAL_ID_REQUIRED_NO_ORDINAL_FALLBACK')
    identity={'namespace':'accepted_original_sprime','source_conformer_id':source_id}
    row=stable_source_row(pair['record_id'],pair['molecule_id'],source,identity,sources)
    return dict(row,uff_coordinate_sha256=pair['uff_coordinate_sha256'])


def rates(rows):
    denominators=Counter((r['source_shard_id'],r['size_stratum']) for r in rows)
    hits=Counter((r['source_shard_id'],r['size_stratum']) for r in rows if r['selected'])
    return [{'source_shard_id':k[0],'size_stratum':k[1],'universe':n,'stable_hits':hits[k],
             'actual_fraction':hits[k]/n} for k,n in sorted(denominators.items())]


def prove_raw(workers,source_rows,records,engine):
    """Read durable bundles and compare every retained call's input/output SHAs."""
    from raw_archive import RawReader
    sources={r['record_id']:r for r in source_rows}
    expected={r['record_id']:r for r in source_rows if r['retain_all_twelve_raw']}
    parsed={(r['record_id'],d['task']):d for r in records for d in r['tasks']}
    required={(rid,calc) for rid in expected for calc in IO.TASKS}
    failed={(rid,calc) for (rid,calc),detail in parsed.items() if detail.get('scope_status','SUCCESS')!='SUCCESS'}
    required |= failed
    calls=[];seen=set()
    for worker in workers:
        if not worker.get('raw_container'):continue
        container=worker['raw_container'];IO.require_pin(container)
        reader=RawReader(container['path'],engine.OUTPUT_ARCHIVE)
        try:
            for rid,calc,execution in reader.db.execute('SELECT record_id,calc_type,execution_id FROM raw').fetchall():
                if (rid,calc) not in required:continue
                if (rid,calc) in seen:raise ValueError('DUPLICATE_RETAINED_CALL_FOR_ONE_PILOT_RECORD_TASK')
                raw=reader.get(rid,calc,execution);meta=raw['metadata']
                detail=parsed.get((rid,calc))
                if detail is None or meta['input_bundle_sha256']!=detail['provenance']['input_bundle_sha256'] or meta['input_file_sha256']!=detail['provenance']['input_file_sha256']:
                    raise ValueError('RAW_AND_PARSED_SCIENTIFIC_INPUT_SHA_MISMATCH')
                if rid not in sources or meta['source_reference']['shard_id']!=sources[rid]['source_shard_id'] or meta['file_group']!=sources[rid]['legacy_engine_file_group']:
                    raise ValueError('RAW_SOURCE_SHARD_OR_LEGACY_GROUP_MISMATCH')
                seen.add((rid,calc))
                calls.append({'record_id':rid,'calc_type':calc,'execution_id':execution,
                  'input_bundle_sha256':meta['input_bundle_sha256'],'input_file_sha256':meta['input_file_sha256'],
                  'keywordSHA':meta['keywordSHA'],'container':container,'output_members':meta['output_file_manifest'],
                  'raw_readback_verified':True,'input_bodies_saved':False})
        finally:reader.close()
    missing=[{'record_id':rid,'calc_type':calc} for rid,calc in sorted(required) if (rid,calc) not in seen]
    return {'schema':'PPRIME_STABLE_RAW_ALL12_PROOF_V1',
       'status':'ALL_REQUIRED_RETAINED_CALLS_SHA_VERIFIED' if not missing else 'REQUIRED_RETAINED_CALLS_MISSING',
       'required_full12_records':len(expected),'required_failed_calls':len(failed),
       'required_calls':len(required),'verified_calls':len(calls),
       'calls':calls,'missing':missing,'all_raw_read_after_durable_commit':True}
