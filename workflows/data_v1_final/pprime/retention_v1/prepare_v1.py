"""Bind original 2000 pilot inputs to stable-hit union raw retention. No QM."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

from retention_policy_v1 import IO, load, rates, selector, source_audit, source_paths


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','original-prepared','root-preflight','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--original-prepared-sha256',required=True)
    a=p.parse_args();c,pilot=load(a.config);observed=IO.runtime(prepare=True)
    IO.require_preflight(a.root_preflight,a.config,c)
    manifest=a.original_prepared/'prepared.json'
    if IO.digest(manifest)!=a.original_prepared_sha256:raise ValueError('EXACT_ORIGINAL_PREPARED_SHA_REQUIRED')
    original=json.loads(manifest.read_text())
    if original['status']!='PPRIME_PAIRS_READY_NOT_QM_EXECUTED' or original['config']!=c['pilot_config']:
        raise ValueError('EXACT_REGISTERED2000_PILOT_PREPARATION_REQUIRED')
    for pin in original['outputs']:IO.require_pin(pin)
    pair_pin=next(ref for ref in original['outputs'] if Path(ref['path']).name=='pairs.jsonl')
    pairs=[json.loads(line) for line in Path(pair_pin['path']).read_text().splitlines()]
    if len(pairs)!=2000 or len({r['record_id'] for r in pairs})!=2000:
        raise ValueError('ALL2000_UNIQUE_ORIGINAL_PILOT_INPUTS_REQUIRED')
    sources=source_paths(json.loads(IO.require_pin(pilot['source_plan']).read_text()))
    with ThreadPoolExecutor(max_workers=16) as pool:
        rows=list(pool.map(lambda pair:source_audit(pair,sources),pairs))
    import pyarrow as pa
    import pyarrow.parquet as pq
    old_membership=next(ref for ref in original['outputs'] if Path(ref['path']).name=='audit_membership.json')
    old_selected=next(ref for ref in original['outputs'] if Path(ref['path']).name=='audit_selected.parquet')
    old_rows=pq.read_table(old_selected['path']).to_pylist()
    by_id={r['record_id']:r for r in rows}
    for old in old_rows:
        actual=by_id[old['record_id']]
        if old['file_group']!=actual['legacy_engine_file_group'] or old['size_stratum']!=actual['size_stratum']:
            raise ValueError('ORIGINAL20_LEGACY_ENGINE_STRATUM_MISMATCH')
    union=selector.pilot_union(rows,[r['record_id'] for r in old_rows])
    selected={r['record_id']:r for r in union}
    source_rows=[dict(row,original_frozen_audit=row['record_id'] in {r['record_id'] for r in old_rows},
          retain_all_twelve_raw=row['record_id'] in selected,
          extra_reproduction_retention=selected.get(row['record_id'],{}).get('extra_reproduction_retention',False)) for row in rows]
    out=IO.new_output(a.output,c)
    source_ref=IO.write_json(out/'source_audit.json',source_rows)
    full_ref=IO.write_json(out/'stable_full_hits.json',[r for r in source_rows if r['selected']])
    union_ref=IO.write_json(out/'pilot_retention_union.json',union)
    engine_rows=[{'record_id':r['record_id'],'file_group':r['legacy_engine_file_group'],'size_stratum':r['size_stratum']} for r in union]
    pq.write_table(pa.Table.from_pylist(engine_rows),out/'audit_selected.parquet',compression='zstd')
    selected_ref=dict(IO.reference(out/'audit_selected.parquet'),rows=len(engine_rows))
    membership_ref=IO.write_json(out/'audit_membership.json',{'schema':'WP5_STRATIFIED_RECORD_AUDIT_V1',
       'status':'AUDIT_MEMBERSHIP_CLOSED','selected_records':selected_ref,
       'audit_policy':IO.reference(a.config),'source_audit':source_ref,'source_shard_id_is_sampling_stratum':True,
       'file_group_here_is_legacy_engine_guard_only':True,'original_frozen20':old_selected,
       'sample_type':'stable hash threshold100/10000 plus original20 extra reproduction retention',
       'original_WP5_exact_sample_identity_claimed':False})
    IO.write_json(out/'retention_manifest.json',{'schema':'PPRIME_STABLE_RAW_RETENTION_EXECUTION_BINDING_V1',
       'status':'PREPARED_NOT_QM_EXECUTED','runtime':observed,'audit_policy':IO.reference(a.config),
       'root_preflight':IO.reference(a.root_preflight),'original_prepared':IO.reference(manifest),
       'original_pairs':pair_pin,'original_audit_membership':old_membership,'original_audit_selected20':old_selected,
       'source_plan':pilot['source_plan'],'source_audit':source_ref,'stable_full_hits':full_ref,
       'pilot_retention_union':union_ref,'engine_record_audit_membership':membership_ref,
       'engine_selected':selected_ref,'source_shard_strata':rates(rows),'stable_full_hits_count':sum(r['selected'] for r in rows),
       'union_records':len(union),'required_full_raw_calls':12*len(union),
       'original_frozen_audit_records':20,'original_prepared_or_config_bytes_changed':False,
       'scientific_input_or_numerics_changed':False,'QM_started':False})


if __name__=='__main__':main()
