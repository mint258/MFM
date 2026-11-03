"""Aggregate original D masks/reviews over every real R/N candidate molecule.

This is an analysis pass over closed outputs. It neither generates geometry nor
refits a TRAIN reference on R/N. Reports remain pending independent Root review.
"""
from __future__ import annotations
import argparse
import collections
import json
import os
from pathlib import Path
import socket
import sqlite3
from . import core as C, store as S
from .resources import Budget
from .run import verify


def run(plan):
    import duckdb
    workers=plan.get('workers',16)
    node=socket.gethostname().split('.')[0]
    if (os.getuid()!=1278 or node=='sonmi' or not os.environ.get('SLURM_JOB_ID')
            or workers<16 or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<workers
            or node not in plan['allowed_nodes']):
        raise RuntimeError('ACTUAL_ALLOCATED_MAIN_CPU_ANALYSIS_REQUIRED')
    output=Path(plan['output_directory']);output.mkdir(parents=True,exist_ok=False)
    budget=Budget(plan,output)
    quality_ref=plan['quality_reference_review']
    from workflows.expansion.no_pm7_uff_d_main_v1 import contract as Original
    review,_=Original.quality_reference({'quality_reference_review_reference':quality_ref})
    if not review.get('TRAIN_calibration_reference') or not review.get('TRAIN_reference_domain_reference'):
        raise RuntimeError('REAL_MATCHED_TRAIN_REFERENCE_REQUIRED_FOR_FULL_1P5_ROBUST_REVIEW')
    field_map=S.read_json(verify(review['field_map_reference']))
    expected={str(f['field_id']) for f in field_map if f['task'] in ('D20','D3')}
    census=sqlite3.connect(output/'source_census.sqlite')
    census.execute('CREATE TABLE molecules(mid TEXT PRIMARY KEY,stream TEXT,status TEXT,manifest TEXT)')
    family_refs={};mask_refs={};batch_refs={};source_fingerprints=set()
    for receipt_ref in plan['generation_receipts']:
        receipt=S.read_json(verify(receipt_ref))
        if (receipt['schema']!='PUBCHEM_UFF3_ALLOCATION_RECEIPT_V1'
                or receipt['source_total_molecules']!=2500000 or receipt['maximum_conformers']!=3):
            raise RuntimeError('ACTUAL_UFF3_ALLOCATION_RECEIPTS_REQUIRED')
        source_fingerprints.add(C.sha(C.canonical(receipt['source_manifest'])))
        root=Path(receipt_ref['path']).parent
        db=sqlite3.connect((root/'index.sqlite').as_uri()+'?mode=ro',uri=True)
        try:
            for mid,stream,status,manifest in db.execute('SELECT s.mid,s.stream,d.status,d.manifest FROM source s JOIN done d USING(ordinal)'):
                old=census.execute('SELECT stream,status,manifest FROM molecules WHERE mid=?',(mid,)).fetchone()
                if old is not None and old!=(stream,status,manifest):
                    raise RuntimeError('OVERLAPPING_MOLECULE_WITH_DIFFERENT_CLOSED_RESULT')
                census.execute('INSERT OR IGNORE INTO molecules VALUES(?,?,?,?)',(mid,stream,status,manifest))
            for path,body in db.execute('SELECT path,body FROM batches'):
                batch=json.loads(body)
                if batch['quality_reference_review']!=quality_ref:
                    raise RuntimeError('MIXED_OR_MISSING_ORIGINAL_MASK_REFERENCE_DOMAIN')
                batch_refs[path]=S.reference(path)
                for ref in batch['family_files']:
                    clean={k:ref[k] for k in ('path','bytes','sha256')}
                    verify(clean);family_refs[clean['path']]=ref
                    if ref['family']=='validity_masks':mask_refs[clean['path']]=clean
        finally:db.close()
        census.commit();budget.register(output/'source_census.sqlite');budget.check()
    counts=dict(census.execute('SELECT stream,count(*) FROM molecules GROUP BY stream'))
    states=dict(census.execute('SELECT status,count(*) FROM molecules GROUP BY status'))
    if len(source_fingerprints)!=1 or counts!={'R':1250000,'N':1250000}:
        raise RuntimeError('FULL_UNIQUE_2P5M_R_N_CENSUS_REQUIRED')
    if not mask_refs:raise RuntimeError('NO_ORIGINAL_PER_COMPONENT_MASK_OUTPUTS')
    db=duckdb.connect(str(output/'validity.duckdb'))
    db.execute('SET threads=?',[workers])
    db.execute("SET memory_limit=?",[plan.get('duckdb_memory_limit','8GB')])
    db.execute("SET temp_directory=?",[str(output/'spill')])
    try:
        db.read_parquet(list(mask_refs),union_by_name=False).create_view('masks')
        actual={row[0] for row in db.execute('SELECT DISTINCT field_id FROM masks').fetchall()}
        if not actual<=expected:raise RuntimeError('UNDECLARED_D_FIELD_IN_MASKS')
        if db.execute('SELECT count(*) FROM masks WHERE len(values_float64)<>len(value_mask) OR len(values_float64)<>len(source_value_mask)').fetchone()[0]:
            raise RuntimeError('VALUE_AND_MASK_COMPONENT_LENGTHS_DIFFER')
        db.execute('''CREATE TABLE component AS SELECT field_id,field_key,source_path,
            record_id,molecule_id,stream,unnest(values_float64) AS value,
            unnest(source_value_mask) AS source_valid,unnest(value_mask) AS valid
            FROM masks''')
        db.execute('''CREATE TABLE summary AS SELECT field_id,field_key,source_path,stream,
            count(*) AS components,count(DISTINCT record_id) AS records,
            count(DISTINCT molecule_id) AS molecules,
            count(*) FILTER(WHERE valid IS NOT TRUE) AS masked_components,
            count(*) FILTER(WHERE source_valid IS TRUE AND valid IS NOT TRUE) AS newly_masked_components,
            count(*) FILTER(WHERE value IS NULL OR NOT isfinite(value)) AS missing_nonfinite_components
            FROM component GROUP BY ALL''')
        rows=db.execute('SELECT * FROM summary ORDER BY field_id,stream').fetchall()
        columns=[c[0] for c in db.description]
        summaries=[dict(zip(columns,row)) for row in rows]
        for row in summaries:
            row['masked_fraction']=row['masked_components']/row['components']
            row['newly_masked_fraction']=row['newly_masked_components']/row['components']
        db.execute('''CREATE TABLE reason_sets AS SELECT field_id,stream,source_reasons_json,
            new_reasons_json,review_reasons_json,count(*) AS records FROM masks GROUP BY ALL''')
        db.execute('''CREATE TABLE worst20 AS SELECT * EXCLUDE(rn) FROM (
            SELECT *,row_number() OVER(PARTITION BY field_id ORDER BY
                list_has_any(value_mask,[false]) DESC,
                abs(try_cast(robust_z_review_score_json AS DOUBLE)) DESC NULLS LAST,
                molecule_id,record_id) AS rn FROM masks) WHERE rn<=20''')
        for table in ('summary','reason_sets','worst20'):
            db.execute('COPY (SELECT * FROM '+table+') TO ? (FORMAT PARQUET,COMPRESSION ZSTD)',[str(output/(table+'.parquet'))])
        db.execute('CHECKPOINT')
        combined={}
        for row in summaries:
            target=combined.setdefault(row['field_id'],{'field_id':row['field_id'],
                'field_key':row['field_key'],'components':0,'masked_components':0,'newly_masked_components':0})
            for name in ('components','masked_components','newly_masked_components'):target[name]+=row[name]
        for row in combined.values():
            row['masked_fraction']=row['masked_components']/row['components']
            row['newly_masked_fraction']=row['newly_masked_components']/row['components']
        over_one_percent=[row for row in combined.values() if row['masked_fraction']>.01]
        result={'schema':'PUBCHEM_UFF3_VALIDITY_REVIEW_V1',
            'status':'SCAN_COMPLETE_PENDING_INDEPENDENT_ROOT_REVIEW',
            'source_molecules_by_stream':counts,'source_state_counts':states,
            'technical_unknown_sources_preserved_not_fabricated_as_valid':True,
            'actual_mask_field_ids':sorted(actual),'expected_D_field_ids':sorted(expected),
            'fields_without_any_actual_value_rows':sorted(expected-actual),
            'field_stream_counts':summaries,'all_stream_field_counts':list(combined.values()),
            'fields_over_one_percent_masked':over_one_percent,
            'quality_reference_review':quality_ref,'new_R_N_TRAIN_fit':False,
            'source_mask_functions_unchanged':True,'mask_reason_sets':S.reference(output/'reason_sets.parquet'),
            'worst20_per_field':S.reference(output/'worst20.parquet'),
            'field_summary':S.reference(output/'summary.parquet'),
            'all_family_file_references':list(family_refs.values()),
            'closed_batch_manifest_references':list(batch_refs.values()),
            'generation_receipts':plan['generation_receipts'],'new_UFF_QM_calls':0,
            'training_eligible':False}
        S.write_new(output/'result.json',result)
        return result
    finally:db.close();census.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(run(S.read_json(args.plan)),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
