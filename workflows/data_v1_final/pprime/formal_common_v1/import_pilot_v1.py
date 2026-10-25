"""Import closed real pilot outcomes into the once ledger; never recompute labels."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from common_v1 import IO, ledger_file, load, pilot_review, runtime, task_key


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','pilot-review','root-preflight','output'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();c,pilot=load(a.config);runtime(c,a.root_preflight,a.config)
    decision,result,gates=pilot_review(a.pilot_review,c['pilot_config']['path'])
    proof=json.loads(IO.require_pin(result['stable_raw_retention_proof']).read_text())
    retention=json.loads(IO.require_pin(result['retention']).read_text())
    if proof['status']!='ALL_REQUIRED_RETAINED_CALLS_SHA_VERIFIED' or proof['audit_policy']!=c['raw_policy'] or result['retention_policy']!=c['raw_policy']:
        raise ValueError('PILOT_IMPORT_REQUIRES_REGISTERED_STABLE_RAW_POLICY_AND_ALL12_PROOF')
    source_audit=json.loads(IO.require_pin(retention['source_audit']).read_text())
    audit_by_id={r['record_id']:r for r in source_audit}
    if len(source_audit)!=2000 or len(audit_by_id)!=2000:
        raise ValueError('ALL2000_STABLE_PHYSICAL_SOURCE_IDENTITIES_REQUIRED')
    from retention_policy_v1 import audit_key
    for row in source_audit:
        calculated=audit_key(row['molecule_id'],row['source_shard_id'],row['size_stratum'],row['physical_identity'])
        if any(calculated[k]!=row[k] for k in calculated):
            raise ValueError('PILOT_STABLE_RAW_IDENTITY_OR_BUCKET_CHANGED')
    import pyarrow.parquet as pq
    from geometry import geometry_hash
    from prepare_pilot import coordinate_sha
    base=next(pin for pin in result['family_parquets'] if pin['family']=='base_geometry')
    qc=next(pin for pin in result['family_parquets'] if pin['family']=='QC')
    bases=pq.read_table(IO.require_pin(base)).to_pylist()
    quality=pq.read_table(IO.require_pin(qc)).to_pylist()
    by_qc={r['record_id']:r for r in quality}
    if len(bases)!=2000 or len(by_qc)!=2000 or len(quality)!=2000:
        raise ValueError('ALL2000_UNIQUE_PILOT_BASE_AND_QC_RECORDS_REQUIRED')
    prepared=json.loads(Path(result['prepared']['path']).read_text())
    for pin in prepared['outputs']:IO.require_pin(pin)
    pair_pin=next(pin for pin in prepared['outputs'] if Path(pin['path']).name=='pairs.jsonl')
    pairs={r['record_id']:r for r in (json.loads(line) for line in Path(pair_pin['path']).read_text().splitlines())}
    if len(pairs)!=2000 or set(pairs)!=set(by_qc):raise ValueError('PILOT_INPUT_IDS_CHANGED')
    contract=json.loads(IO.require_pin(pilot['legacy_contract']).read_text())
    protocol_sha=contract['protocol']['sha256'];IO.require_pin(contract['protocol'])
    audited=next(pin for pin in prepared['outputs'] if Path(pin['path']).name=='audit_selected.parquet')
    audited_ids=set(pq.read_table(IO.require_pin(audited),columns=['record_id'])['record_id'].to_pylist())
    out=IO.new_output(a.output,c);imports=[]
    # Retention is verified against durable output bundles, not inferred from IDs.
    from raw_archive import RawReader
    e,_,_=IO.load_engine(pilot)
    raw_calls={}
    for worker in result['workers']:
        if not worker.get('raw_container'):continue
        reader=RawReader(IO.require_pin(worker['raw_container']),e.OUTPUT_ARCHIVE)
        try:
            for rid,calc,execution in reader.db.execute('SELECT record_id,calc_type,execution_id FROM raw').fetchall():
                retained=reader.get(rid,calc,execution)
                raw_calls.setdefault(rid,set()).add(calc)
        finally:reader.close()
    required_ids=audited_ids|{r['record_id'] for r in source_audit if r['selected']}
    if any(raw_calls.get(rid,set())!=set(IO.TASKS) for rid in required_ids):
        raise ValueError('ALL_TWELVE_DURABLE_RAW_BUNDLES_REQUIRED_FOR_ORIGINAL20_PLUS_STABLE_HITS')
    # First validate the complete source before consuming any ledger key.
    proposed=[]
    for row in bases:
        pair=pairs[row['record_id']];qrow=by_qc[row['record_id']]
        if row['record_id'] not in audit_by_id:raise ValueError('PILOT_RECORD_HAS_NO_STABLE_SOURCE_AUDIT')
        if row['geometry_source']!='uff_sprime' or row['Q02_applicable'] is not False or row['Q02_delta_HOF_kcal_mol'] is not None:
            raise ValueError('PILOT_GEOMETRY_OR_CROSS_GEOMETRY_Q02_CHANGED')
        if coordinate_sha(row['positions_A'])!=row['uff_coordinate_sha256'] or row['uff_coordinate_sha256']!=pair['uff_coordinate_sha256'] or geometry_hash(row['atomic_numbers'],row['positions_A'])!=row['uff_geometry_sha256']:
            raise ValueError('PILOT_BASE_COORDINATES_CHANGED')
        statuses=json.loads(qrow['task_statuses_json'])
        if {r['calc_type'] for r in statuses}!=set(IO.TASKS) or len(statuses)!=12:
            raise ValueError('EXACT_TWELVE_ACTUAL_PILOT_TASKS_REQUIRED')
        success=all(r['status']=='SUCCESS' for r in statuses)
        if success!=qrow['all_twelve_tasks_success']:
            raise ValueError('PILOT_SUCCESS_SUMMARY_DISAGREES_WITH_TASKS')
        key=task_key(row['molecule_id'],row['native_atom_order_sha256'],row['uff_coordinate_sha256'],protocol_sha,row['record_id'])
        proposed.append((key,row,success))
    if len({key for key,_,_ in proposed})!=2000:
        raise ValueError('PILOT_SCIENTIFIC_INPUT_KEY_COLLISION')
    if any(ledger_file(c,key).exists() for key,_,_ in proposed):
        raise ValueError('PILOT_IMPORT_ALREADY_STARTED_NO_AUTOMATIC_REPEAT')
    for key,row,success in proposed:
        entry={'schema':'PPRIME_IMPORTED_REAL_PILOT_ATTEMPT_V1',
               'status':'PILOT_SUCCESS_REUSABLE' if success else 'PILOT_SCIENTIFIC_FAILURE_CONSUMED_NO_AUTO_RETRY',
               'key':key,'record_id':row['record_id'],'molecule_id':row['molecule_id'],
               'pilot_review':IO.reference(a.pilot_review),'actual_pilot_result':decision['result'],
               'base_family':base,'QC_family':qc,'all_twelve_success':success,
               'raw_policy':c['raw_policy'],'source_audit':retention['source_audit'],
               'stable_raw_audit_key_sha256':audit_by_id[row['record_id']]['audit_key_sha256'],
               'stable_raw_audit_selected':audit_by_id[row['record_id']]['selected'],
               'all_twelve_raw_retained_verified':raw_calls.get(row['record_id'],set())==set(IO.TASKS)}
        ref=IO.write_json(ledger_file(c,key),entry)
        imports.append({'key':key,'record_id':row['record_id'],'all_twelve_success':success,
                        'stable_raw_audit_key_sha256':entry['stable_raw_audit_key_sha256'],
                        'stable_raw_audit_selected':entry['stable_raw_audit_selected'],
                        'all_twelve_raw_retained_verified':entry['all_twelve_raw_retained_verified'],'ledger':ref})
    IO.write_json(out/'pilot_import.json',{'schema':'PPRIME_REAL_PILOT_IMPORT_CLOSED_V1',
        'status':'REAL2000_PILOT_KEYS_IMPORTED_NO_QM','config':IO.reference(a.config),
        'pilot_review':IO.reference(a.pilot_review),'entries':imports,
        'raw_policy':c['raw_policy'],'stable_raw_proof':result['stable_raw_retention_proof'],
        'failed_records_consumed':sum(not r['all_twelve_success'] for r in imports),
        'QC_family':qc,'base_family':base,'family_parquets':result['family_parquets'],
        'raw_worker_containers':[r['raw_container'] for r in result['workers'] if r.get('raw_container')],
        'QM_started':False,'label_values_copied_or_filled':False})


if __name__=='__main__':main()
