"""The P0 diagnostics; D6 reads frozen identity metadata and no targets."""
from __future__ import annotations
import argparse, json, time
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq

ROOT=Path('/share/home/zixiao/descriptor_analysis')
CONTROL=ROOT/'runs/p_recipe_20261113'
REPO=Path(__file__).resolve().parents[2]

def identity_gate():
    d=json.loads((CONTROL/'D6_metadata.json').read_text())
    train_ids,set_val=set(),set()
    for ref in d['common']['membership_tables']:
        table=pq.read_table(ref['path'],columns=['molecule_id','effective_role','common_population_v1'])
        for row in table.to_pylist():
            if not row['common_population_v1']:continue
            if row['effective_role']=='TRAIN':train_ids.add(row['molecule_id'])
            elif row['effective_role']=='VAL':set_val.add(row['molecule_id'])
    refs=json.loads((CONTROL/'identity_source_refs.json').read_text())
    summary=json.loads(Path(refs['membership_summary']['path']).read_text())
    downstream={}
    # Existing target-free memberships include all folds; no test labels opened.
    members=Path(summary['artifacts']['members.jsonl']['path'])
    with members.open() as stream:
        for line in stream:
            row=json.loads(line)
            if row['dataset'] in ('qm9','cyp_isoform') and row.get('inchikey'):
                downstream.setdefault(row['inchikey'],set()).add(row['dataset'])
    geometry=json.loads(Path(refs['expansion_geometry']['path']).read_text())
    for row in geometry['records']:
        if row.get('full_inchikey'):
            downstream.setdefault(row['full_inchikey'],set()).add('expansionrx')
    projection={key[:14]+':'+key[-1] for key in downstream}
    train_keys,val_keys=set(),set()
    hits={};seen=set()
    formal=ROOT/'runs/phase1_wp5_20261011/population/formal_record_index.parquet'
    for batch in pq.ParquetFile(formal).iter_batches(batch_size=65536,
            columns=['molecule_id','stored_inchikey','reidentified_inchikey']):
        for mid,source,reidentified in zip(*(batch.column(i).to_pylist() for i in range(3))):
            keys={key for key in (source,reidentified) if key}
            if mid in train_ids:
                seen.add(mid);train_keys.update(keys)
                for key in keys:
                    if key in downstream or key[:14]+':'+key[-1] in projection:
                        hits.setdefault(mid,set()).add(key)
            elif mid in set_val:val_keys.update(keys)
    result=dict(TRAIN_molecules=len(train_ids),VAL_molecules=len(set_val),
        TRAIN_molecules_with_identity=len(seen),downstream_unique_full_keys=len(downstream),
        TRAIN_VAL_molecule_id_overlap=len(train_ids&set_val),
        TRAIN_VAL_full_key_overlap=len(train_keys&val_keys),
        TRAIN_VAL_wp5_key_overlap=len({k[:14]+':'+k[-1] for k in train_keys}&{k[:14]+':'+k[-1] for k in val_keys}),
        TRAIN_downstream_overlap_molecules=len(hits),
        overlapping_molecules={mid:sorted(keys) for mid,keys in hits.items()},
        target_values_read=False,new_identity_computation=False)
    result['passed']=not any(result[k] for k in ('TRAIN_VAL_molecule_id_overlap',
        'TRAIN_VAL_full_key_overlap','TRAIN_VAL_wp5_key_overlap','TRAIN_downstream_overlap_molecules'))
    (CONTROL/'D6_identity.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='overlapping_molecules'}),flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['D6'],required=True)
    args=p.parse_args();identity_gate()
