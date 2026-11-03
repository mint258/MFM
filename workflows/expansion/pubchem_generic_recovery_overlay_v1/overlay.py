"""Native exact minCID overlay; no copy/rewrite of old candidate or alias bodies."""
import argparse
import csv
import io
import json
from pathlib import Path
import struct
import traceback
import unittest
from ..alpha_runtime_v1 import common as Q
from ..alpha_runtime_v1.guard import Guard
from ..alpha_closed500_handoff_v1.sql import connection,SQLStopper,copy_parquet,literal
from .runtime import VERSION,admit,actual_parent,read
from .physical import historical,unchanged
from .mincid_sql import reduce

ORIGINAL_COUNTS={'accepted':110046364,'chemReject':14764875,'technicalUnresolved':46201}


def inputs(plan):
    pool=read(plan['base_pool_receipt_reference']);review=read(plan['base_pool_actual_reference'])
    Q.need(pool['schema']=='PUBCHEM_EXACT_MINCID_CANDIDATE_POOL_V2' and pool['status']=='MATERIALIZED_UNFILTERED_NO_RELEASE'
        and pool['source_rows']==124857440 and pool['source_counts']==ORIGINAL_COUNTS
        and pool['unique_full_keys']==109871959 and pool['aliases_rows']==110046364
        and pool['original_SQL_minimum_CID_semantics'] is True and pool['all_original_Arrow_fields_and_F64_preserved'] is True,
        'Complete actual original minCID population')
    Q.need(review['schema']=='ROOT_ACTUAL_ALPHA_MINCID_POOL_V1' and review['actual_terminal'] is True
        and review['endpoint']=='218.192.171.238:22' and review['uid']==1264 and review['query_returncode']==0
        and review['receipt']==plan['base_pool_receipt_reference'] and review['candidates']==pool['candidates']
        and review['aliases']==pool['aliases'],'Actual closed original pool body pins')
    rows=[r for r in csv.DictReader(io.StringIO(review['actual_sacct']),delimiter='|') if r['JobIDRaw']=='1885149']
    Q.need(len(rows)==1 and rows[0]['State']=='COMPLETED' and rows[0]['ExitCode']=='0:0' and rows[0]['UID']=='1264','Actual original1885149C0')
    projection=read(pool['scope']['source_projection'])
    Q.need(projection['producer_schema']=='PUBCHEM_ALPHA_ORIGINAL502_TYPED_COVERAGE_V1'
        and projection['source_endpoint']=='218.192.171.238:22' and projection['source_uid']==1264
        and projection['fragment_count']==502 and projection['logical_descriptor_count']==500
        and projection['source_typed_bodies_full_SHA_verified'] is True and projection['counts']==ORIGINAL_COUNTS,
        'Honest complete original Alpha502 source closure')
    delta=read(plan['recovery_delta_receipt_reference']);accepted=read(plan['recovery_delta_actual_reference'])
    Q.need(accepted['schema']=='ROOT_PUBCHEM_GENERIC_RECOVERY_DELTA_ACTUAL_REVIEW_V1'
        and accepted['status']=='APPROVED_CANDIDATE_DELTA_3642' and accepted['reviewer']=='root'
        and accepted['producer_receipt_reference']==plan['recovery_delta_receipt_reference'],'Actual candidate-delta source review')
    actual_parent(accepted);d=delta['result']
    Q.need(delta['schema']=='PUBCHEM_GENERIC_RECOVERY_DELTA_PRODUCER_V1' and delta['population_version']==VERSION
        and d['schema']=='PUBCHEM_GENERIC_RECOVERY_CANDIDATE_DELTA_V1' and d['candidate_rows']==3642
        and d['all_per_row_native_strict_statuses_verified'] is True and d['all_recovered_F64_readback_bits_equal'] is True
        and d['original_rows_modified']==0 and d['original_UNKNOWN_rows_preserved']==46201,'Exact immutable actual3642 delta')
    for k in ('candidates','aliases','source_lineage'):Q.verify(d[k])
    ledger=read(plan['base_closed_frame_ledger_reference'])
    witnesses=[historical(pool[k],ledger) for k in ('candidates','aliases')]
    return pool,d,projection,witnesses


def execute(plan,out,guard):
    import pyarrow.parquet as pq
    base,d,projection,witnesses=inputs(plan)
    db=connection(out,plan['workers'],plan['duckdb_memory_bytes']);monitor=SQLStopper(db,guard.check)
    try:
        db.read_parquet(base['candidates']['path']).create_view('base')
        db.read_parquet(base['aliases']['path']).create_view('old_aliases')
        db.read_parquet(d['candidates']['path']).create_view('delta')
        db.read_parquet(d['aliases']['path']).create_view('delta_aliases')
        Q.need(pq.ParquetFile(base['candidates']['path']).metadata.num_rows==base['unique_full_keys']
            and pq.ParquetFile(base['aliases']['path']).metadata.num_rows==base['aliases_rows'],'Current complete original physical row footers')
        Q.need(db.execute('SELECT count(*) FROM delta').fetchone()[0]==3642,'All3642 delta candidates')
        q='SELECT cid,full_key,ordinal AS source_ordinal,source_fragment_id FROM delta'
        Q.need(db.execute('SELECT count(*) FROM (('+q+' EXCEPT ALL SELECT * FROM delta_aliases) UNION ALL (SELECT * FROM delta_aliases EXCEPT ALL '+q+'))').fetchone()[0]==0,
            'Every delta alias exactly matches its complete source candidate identity/ordinal')
        stats=reduce(db)
        floats=('molecular_weight_Da','tpsa_A2','logp')
        before=db.execute('SELECT cid,'+','.join(floats)+' FROM winning_delta ORDER BY full_key,cid').fetchall()
        winning=copy_parquet(db,'SELECT * FROM winning_delta ORDER BY full_key,cid',out/'winning_delta.parquet')
        with pq.ParquetFile(winning['path']) as f:
            after=f.read(columns=['cid',*floats]).to_pylist()
        Q.need(len(before)==len(after) and all(a[0]==b['cid'] and all(struct.pack('>d',a[i+1])==struct.pack('>d',b[k]) for i,k in enumerate(floats))
            for a,b in zip(before,after)),'All exported winning-delta F64 values bitwise equal SQL-selected input')
        replaced=copy_parquet(db,'SELECT * FROM replacement_keys ORDER BY full_key',out/'replacement_keys.parquet')
        new=copy_parquet(db,'SELECT * FROM new_keys ORDER BY full_key,cid',out/'new_full_keys.parquet')
        Q.need(winning['rows']==stats['winning_delta_rows']==stats['new_full_keys']+stats['replaced_representatives']
            and replaced['rows']==stats['replaced_representatives'] and new['rows']==stats['new_full_keys'],'All exported small overlay table counts')
        stats.update(base_unique_full_keys=base['unique_full_keys'],base_aliases=base['aliases_rows'],
            unique_full_keys=base['unique_full_keys']+stats['new_full_keys'],aliases_rows=base['aliases_rows']+3642)
        stats['duplicate_fullkey_aliases']=stats['aliases_rows']-stats['unique_full_keys']
        effective=dict(base['source_counts']);effective['accepted']+=3642;effective['technicalUnresolved']-=3642
        Q.need(sum(effective.values())==124857440 and effective['accepted']==stats['aliases_rows'],'Whole original source mass conserved')
        db.execute('CHECKPOINT');guard.check()
        for witness in witnesses:unchanged(witness)
        return dict(schema='PUBCHEM_EXACT_MINCID_OVERLAY_MATERIALIZATION_V1',population_version=VERSION,
            source_rows=124857440,original_source_counts=ORIGINAL_COUNTS,proposed_effective_source_counts=effective,counts=stats,
            candidate_relation=dict(schema='PUBCHEM_LOGICAL_MINCID_OVERLAY_RELATION_V1',base_candidates=base['candidates'],
                replacement_keys=replaced,winning_delta=winning),
            aliases_relation=dict(schema='PUBCHEM_PRESERVED_ALIAS_UNION_V1',parts=[base['aliases'],d['aliases']],rows=stats['aliases_rows']),
            new_full_keys=new,base_pool_receipt_reference=plan['base_pool_receipt_reference'],
            base_pool_actual_reference=plan['base_pool_actual_reference'],base_closed_frame_ledger_reference=plan['base_closed_frame_ledger_reference'],
            recovery_delta_receipt_reference=plan['recovery_delta_receipt_reference'],recovery_delta_actual_reference=plan['recovery_delta_actual_reference'],
            original_source_projection=base['scope']['source_projection'],coverage_reference=projection['coverage_reference'],
            frozen_manifest_reference=projection['frozen_manifest_reference'],source_snapshot_sha256=projection['source_snapshot_sha256'],
            original_SQL_minimum_CID_semantics=True,all_original_aliases_preserved_by_reference=True,
            all_unaffected_original_Arrow_fields_and_F64_preserved=True,all_recovered_non_generic_values_exact=True,
            minimum_CID_all_aliases_basis='actual old complete minCID C0 + exact small delta minimum + old/delta CID-disjoint full-alias scan',
            source_current_witnesses=witnesses,old_34GB_candidate_or_1GB_alias_copied=False,new_chemistry_calls=0,
            old_UNKNOWN_rows_modified=0,original_UNKNOWN_rows_preserved=46201,remaining_technical_UNKNOWN_if_adopted=42559,
            source_scope_or_old_baseline_changed=False,scientific_population_recovery_accepted=False,
            decontamination_filter_rank_or_training_release=False)
    finally:monitor.close();db.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);p.add_argument('--startup-proof',required=True,type=Path)
    a=p.parse_args();plan=Q.load(a.plan);proof=Q.load(a.startup_proof)
    authority=admit(plan,proof,a.plan,a.startup_proof,'PUBCHEM_ALPHA_GENERIC_RECOVERY_OVERLAY_PLAN_V1','pubchem_alpha_generic_recovery_overlay_v1')
    guard=Guard(plan);out=Path(plan['output_directory'])
    try:
        out.mkdir(parents=True,exist_ok=False)
        from .test_overlay import Native
        text=io.StringIO();tests=unittest.TextTestRunner(stream=text,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Native))
        testref=Q.write(out/'source_test.json',dict(tests=tests.testsRun,errors=len(tests.errors),failures=len(tests.failures),
            skips=len(tests.skipped),transcript=text.getvalue()))
        Q.need(tests.wasSuccessful() and tests.testsRun==1 and not tests.skipped,'Actual minCID/alias/H-only parity fixture')
        result=execute(plan,out,guard)
        Q.write(out/'receipt.json',dict(schema='PUBCHEM_EXACT_MINCID_OVERLAY_PRODUCER_V1',
            status='OVERLAY_CLOSED_PENDING_ROOT_ACTUAL_C0',population_version=VERSION,plan_reference=Q.reference(a.plan),
            startup_proof_reference=Q.reference(a.startup_proof),profile_admission=authority,source_test=testref,result=result,
            scientific_population_recovery_accepted=False,actual_parent_C0_pending_root_readback=True,runtime=guard.receipt()))
    except BaseException as exc:
        if out.is_dir():Q.write(out/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),partials_retained=True,old_population_changed=False))
        raise
    finally:guard.close()


if __name__=='__main__':main()
