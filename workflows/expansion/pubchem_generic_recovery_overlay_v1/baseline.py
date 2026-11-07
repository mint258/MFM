"""Fresh corrected-population1M from a proven old top1M plus new fullkeys."""
import argparse
import csv
import io
from pathlib import Path
import traceback
import unittest
from ..alpha_runtime_v1 import common as Q
from ..alpha_runtime_v1.guard import Guard
from ..alpha_closed500_handoff_v1.sql import connection,SQLStopper,copy_parquet
from ..alpha_closed500_handoff_v1.projection import RECIPE,query_projection
from .runtime import VERSION,admit,read
from .reader import validate_header,bind,finish
from .baseline_sql import DOMAIN,SEED,SIZE,choose


def old_source(plan,pool):
    ref=plan['previous_baseline_receipt_reference'];old=read(ref);actual=read(plan['previous_baseline_actual_reference'])
    Q.need(old['schema']=='EXPANSION_PUBCHEM_PREDECON_BASELINE_V1' and old['status']=='COMPLETE'
        and old['sample_seed']==SEED and old['sample_hash_domain']==DOMAIN and old['sample_molecules']==SIZE
        and old['sample_selection']=='fixed_predecon_minCID_fullkey_unique' and old['sample_ordinal_start']==0
        and old['projection_order']=='sample_ordinal_ASC' and old['source_pool_receipt']==pool['base_pool_receipt_reference']
        and old['scope']['baseline_pool_phase']=='BEFORE_V1_DOWNSTREAM_DECONTAMINATION_AND_NOVELTY'
        and old['all_source_internal_fullkey_dedup_before_v1_or_downstream_decontamination'] is True,
        'Exact original same-seed/domain full-population predecon baseline, never a proxy sample')
    Q.need(actual['schema']=='ROOT_ACTUAL_ALPHA_PREDECON_BASELINE_ACCOUNTING_V1'
        and actual['status']=='ACCEPTED_ACTUAL_BASELINE_1M_PARENT_C0' and actual['endpoint']=='218.192.171.238:22'
        and actual['uid']==1264 and actual['receipt_reference']==ref and actual['sample_molecules']==SIZE
        and actual['phase']=='BEFORE_V1_DOWNSTREAM_DECONTAMINATION_AND_NOVELTY'
        and actual['source_pool_molecules']==109871959,'Actual frozen old full-population baseline authority')
    parents=[p for p in actual['actual_parents'] if p['JobIDRaw']=='1885155']
    Q.need(len(parents)==1 and parents[0]['State']=='COMPLETED' and parents[0]['ExitCode']=='0:0' and parents[0]['UID']=='1264',
        'Actual original1885155C0 baseline source')
    for k in ('sample_membership','features'):Q.verify(old[k])
    return old


def execute(plan,out,guard):
    pool=validate_header(read(plan['source_pool_receipt_reference']));old=old_source(plan,pool)
    db=connection(out,plan['workers'],plan['duckdb_memory_bytes']);monitor=SQLStopper(db,guard.check);witnesses=[]
    try:
        witnesses=bind(db,pool,guard.check)
        db.read_parquet(old['sample_membership']['path']).create_view('old_membership')
        db.read_parquet(old['features']['path']).create_view('old_features')
        db.read_parquet(pool['candidate_relation']['replacement_keys']['path']).create_view('replacements')
        db.read_parquet(pool['new_full_keys']['path']).create_view('new_keys')
        q='SELECT cid,full_key,sample_ordinal FROM old_features'
        Q.need(db.execute('SELECT count(*) FROM ((SELECT * FROM old_membership EXCEPT ALL '+q+') UNION ALL ('+q+' EXCEPT ALL SELECT * FROM old_membership))').fetchone()[0]==0,
            'Complete old membership and features exactly identical identity/order sets')
        changes,rank_rows=choose(db)
        Q.need(rank_rows==SIZE+pool['counts']['new_full_keys'],'Corrected rank domain is proven old topK plus all new keys')
        membership=copy_parquet(db,'SELECT * FROM chosen ORDER BY sample_ordinal',out/'sample_membership.parquet')
        db.execute('CREATE TEMP VIEW selected_features AS SELECT f.* EXCLUDE(sample_ordinal) FROM old_features f ANTI JOIN replacements USING(full_key) UNION ALL SELECT * FROM overlay_winning_delta')
        features=copy_parquet(db,'SELECT f.*,c.sample_ordinal FROM selected_features f JOIN chosen c USING(cid,full_key) ORDER BY c.sample_ordinal',out/'sample_features.parquet')
        Q.need(membership['rows']==features['rows']==SIZE,'Fresh complete corrected1M membership and winning full rows')
        db.read_parquet(features['path']).create_view('sampled')
        projection=query_projection(db,'sampled',out/'sample_query.jsonl',SIZE,guard.check,sample_order=True)
        db.execute('CHECKPOINT');guard.check();finish(witnesses)
        return dict(schema='EXPANSION_PUBCHEM_PREDECON_BASELINE_V1',status='COMPLETE',population_version=VERSION,
            source_endpoint='218.192.171.238:22',source_uid=1264,fingerprint_recipe=RECIPE,targets_present=False,downstream_features_present=False,
            source_pool_receipt=plan['source_pool_receipt_reference'],previous_baseline_receipt_reference=plan['previous_baseline_receipt_reference'],
            previous_baseline_actual_reference=plan['previous_baseline_actual_reference'],internal_deduplicated_pool_reference=plan['source_pool_receipt_reference'],
            raw_chemical_screen_reference=plan['source_pool_receipt_reference'],original_raw_screen_reference=pool['original_source_projection'],
            sample_membership=membership,features=features,projection=projection,sample_seed=SEED,sample_hash_domain=DOMAIN,
            sample_selection='fixed_predecon_minCID_fullkey_unique',sample_molecules=SIZE,source_pool_molecules=pool['unique_full_keys'],
            sample_ordinal_start=0,projection_order='sample_ordinal_ASC',all_source_internal_fullkey_dedup_before_v1_or_downstream_decontamination=True,
            scope=dict(source_pool_receipt=plan['source_pool_receipt_reference'],population_version=VERSION,seed=SEED,domain=DOMAIN,
                sample_size=SIZE,baseline_pool_phase='BEFORE_V1_DOWNSTREAM_DECONTAMINATION_AND_NOVELTY'),
            exact_incremental_method='INSERT_ONLY_TOPK_FROM_PROVEN_FROZEN_OLD_TOPK_PLUS_ALL_NEW_FULLKEYS',
            exact_whole_corrected_population_topK_proof='Old keys are never removed; rank=(SHA256(domain,seed,fullkey),fullkey,cid). Unique fullkey makes CID replacement unable to reorder distinct keys. Insertion cannot promote any old key outside old topK.',
            actual_rank_input_rows=rank_rows,changed_membership=changes,old_baseline_relabelled_or_modified=False,
            original_full_candidate_payload_scanned=False,original_screening_policy_changed=False,effective_population_recovery_changed=True,
            original_recorded_screening_decisions_changed=False,effective_row_dispositions_changed=True,
            scientific_release=False,actual_parent_C0_acceptance='PENDING_ROOT_TERMINAL_ACCOUNTING')
    finally:
        monitor.close();db.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);p.add_argument('--startup-proof',required=True,type=Path)
    a=p.parse_args();plan=Q.load(a.plan);proof=Q.load(a.startup_proof)
    authority=admit(plan,proof,a.plan,a.startup_proof,'PUBCHEM_ALPHA_GENERIC_RECOVERY_BASELINE_PLAN_V1','pubchem_alpha_generic_recovery_baseline_v1')
    from ..alpha_closed500_handoff_v1 import baseline_core,projection,sql,scientific_contract
    for path in [Path(m.__file__) for m in (baseline_core,projection,sql,scientific_contract)]+[Path(scientific_contract.__file__).with_name('original_function_contract.json')]:
        Q.need(Q.reference(path) in proof['request']['source_references'],'Actual borrowed original recipe/helper source pin')
    scientific_contract.verify()
    Q.need((DOMAIN,SEED,SIZE)==('PubChem-baseline-uniform',20261025,1000000),'Exact original scientific sampling recipe')
    guard=Guard(plan);out=Path(plan['output_directory'])
    try:
        out.mkdir(parents=True,exist_ok=False)
        from .test_baseline import Native
        log=io.StringIO();tested=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Native))
        testref=Q.write(out/'source_test.json',dict(tests=tested.testsRun,errors=len(tested.errors),failures=len(tested.failures),
            skips=len(tested.skipped),transcript=log.getvalue()))
        Q.need(tested.wasSuccessful() and tested.testsRun==1 and not tested.skipped,'Full-population/incremental topK/CID replacement native parity')
        result=execute(plan,out,guard);result.update(actual_parent=authority,resource_plan=Q.reference(a.plan),
            startup_proof_reference=Q.reference(a.startup_proof),source_test=testref,runtime=guard.receipt())
        Q.write(out/'receipt.json',result)
    except BaseException as exc:
        if out.is_dir():Q.write(out/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),partials_retained=True,old_baseline_or_population_changed=False))
        raise
    finally:guard.close()


if __name__=='__main__':main()
