"""Strict admitted logical-population reader. Pending producers are not authorities."""
from ..alpha_runtime_v1 import common as Q
from ..alpha_closed500_handoff_v1.sql import literal
from .runtime import VERSION,read,actual_parent
from .physical import historical,unchanged


def validate_header(pool):
    Q.need(pool['schema']=='PUBCHEM_EXACT_MINCID_OVERLAY_POOL_V1' and pool['status']=='MATERIALIZED_UNFILTERED_NO_RELEASE'
        and pool['population_version']==VERSION and pool['source_endpoint']=='218.192.171.238:22' and pool['source_uid']==1264,
        'Explicit sealed new population authority; no old-source fallback')
    producer=read(pool['producer_receipt_reference']);review=read(pool['root_actual_review_reference'])
    Q.need(producer['schema']=='PUBCHEM_EXACT_MINCID_OVERLAY_PRODUCER_V1'
        and producer['status']=='OVERLAY_CLOSED_PENDING_ROOT_ACTUAL_C0'
        and producer['population_version']==VERSION and review['reviewer']=='root'
        and review['schema']=='ROOT_PUBCHEM_GENERIC_RECOVERY_OVERLAY_ACTUAL_REVIEW_V1'
        and review['status']=='APPROVED_UNFILTERED_POPULATION_OVERLAY'
        and review['producer_receipt_reference']==pool['producer_receipt_reference']
        and review['scientific_population_recovery_accepted'] is True,'Actual Root-reviewed completed overlay producer')
    p=actual_parent(review);Q.need(str(p['JobIDRaw'])==producer['profile_admission']['job_id'],'Same actual completed overlay parent')
    r=producer['result']
    for k in ('population_version','source_rows','candidate_relation','aliases_relation','new_full_keys','counts',
              'base_pool_receipt_reference','base_pool_actual_reference','base_closed_frame_ledger_reference',
              'recovery_delta_receipt_reference','recovery_delta_actual_reference','original_source_projection',
              'coverage_reference','frozen_manifest_reference','source_snapshot_sha256'):
        Q.need(pool[k]==r[k],'Authority must preserve complete producer field: '+k)
    Q.need(pool['source_rows']==124857440 and pool['source_counts']==r['proposed_effective_source_counts']
        =={'accepted':110050006,'chemReject':14764875,'technicalUnresolved':42559}
        and pool['aliases_rows']==pool['counts']['aliases_rows']==110050006
        and pool['unique_full_keys']==pool['counts']['unique_full_keys']
        and pool['scientific_population_recovery_accepted'] is True
        and pool['original_UNKNOWN_rows_preserved']==46201 and pool['original_SQL_minimum_CID_semantics'] is True
        and pool['decontamination_filter_rank_or_training_release'] is False,'Actual corrected whole-source census and no downstream release')
    Q.need(pool['candidate_relation']['schema']=='PUBCHEM_LOGICAL_MINCID_OVERLAY_RELATION_V1'
        and pool['aliases_relation']['schema']=='PUBCHEM_PRESERVED_ALIAS_UNION_V1','Exact declared relation semantics')
    return pool


def bind(db,pool,check):
    validate_header(pool);ledger=read(pool['base_closed_frame_ledger_reference'])
    c=pool['candidate_relation'];a=pool['aliases_relation'];base=read(pool['base_pool_receipt_reference'])
    Q.need(c['base_candidates']==base['candidates'] and a['parts'][0]==base['aliases'] and len(a['parts'])==2,
        'Actual complete immutable old population/aliases, not a subset')
    witnesses=[historical(c['base_candidates'],ledger),historical(a['parts'][0],ledger)]
    for ref in (c['replacement_keys'],c['winning_delta'],a['parts'][1],pool['new_full_keys']):Q.verify(ref)
    db.read_parquet(c['base_candidates']['path']).create_view('overlay_base')
    db.read_parquet(c['replacement_keys']['path']).create_view('overlay_replaced')
    db.read_parquet(c['winning_delta']['path']).create_view('overlay_winning_delta')
    db.execute('CREATE TEMP VIEW candidates AS SELECT b.* FROM overlay_base b ANTI JOIN overlay_replaced r USING(full_key) UNION ALL SELECT * FROM overlay_winning_delta')
    db.execute('CREATE TEMP VIEW aliases AS SELECT * FROM read_parquet('+literal(a['parts'][0]['path'])+') UNION ALL SELECT * FROM read_parquet('+literal(a['parts'][1]['path'])+')')
    check()
    return witnesses


def finish(witnesses):
    for witness in witnesses:unchanged(witness)
