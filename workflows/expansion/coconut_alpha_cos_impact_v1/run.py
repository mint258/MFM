"""Allocated complete C/O/S composition impact audit; never a candidate filter."""
import argparse
import csv
import io
import json
import os
from pathlib import Path
import stat
import socket
import sys
import threading
import traceback
import unittest
from workflows.expansion.coconut_alpha_cached735_v1 import support as S
from .query import census,summarize,query,X


def account(ref,job,receipt_ref=None):
    value=S.load(ref)
    S.need(value['endpoint']=='218.192.171.238:22' and value['uid']==1264
           and value['query_returncode']==0,'REAL_ALPHA_ROOT_ACCOUNTING')
    rows=list(csv.DictReader(io.StringIO(value['actual_sacct']),delimiter='|')) if 'actual_sacct' in value else value.get('actual_parents',[value.get('actual_parent',{})])
    selected=[r for r in rows if str(r.get('JobIDRaw'))==job]
    S.need(len(selected)==1 and selected[0]['State']=='COMPLETED' and selected[0]['ExitCode']=='0:0'
           and str(selected[0]['UID'])=='1264' and selected[0]['User']=='alpha','ACTUAL_SOURCE_PARENT_C0_'+job)
    if receipt_ref is not None:S.need(value['receipt']==receipt_ref,'SOURCE_PARENT_EXACT_RECEIPT')
    return value


def admit(plan,proof,plan_path,proof_path):
    from workflows.expansion.alpha_runtime_v1 import profile
    authority=profile.admit(plan,minimum_workers=16);req=proof['request']
    S.need(plan['schema']=='COCONUT_ALPHA_COS_IMPACT_PLAN_V1'
           and plan['scope_key']==req['scope_key']=='coconut_alpha_cos_impact_v1'
           and req['producer_plan_reference']==S.pin(plan_path),'EXACT_ROOT_IMPACT_PLAN')
    argv=req['execution_argv']
    S.need(argv==plan['execution_argv'] and argv[argv.index('--plan')+1]==str(plan_path)
           and argv[argv.index('--startup-proof')+1]==str(proof_path)
           and sys.argv[-4:]==['--plan',str(plan_path),'--startup-proof',str(proof_path)],'EXACT_IMPACT_CLI')
    S.need(proof['endpoint']==plan['endpoint']=='218.192.171.238:22'
           and proof['uid']==plan['uid']==os.getuid()==1264
           and str(proof['job_id'])==os.environ.get('SLURM_JOB_ID')
           and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'ACTUAL_ALPHA_IMPACT_JOB_BOOT')
    refs={r['path']:r for r in req['source_references']}
    for file in [*Path(__file__).parent.glob('*.py'),Path(S.__file__)]:
        S.need(refs.get(str(file.absolute()))==S.pin(file),'EXACT_IMPACT_AND_BORROWED_METADATA_SOURCE')
    for ref in req['source_references']:S.read(ref,2<<20)
    return authority


def source(plan):
    ref=plan['candidate_pool_receipt_reference'];pool=S.load(ref)
    actual=account(plan['candidate_actual_parent_reference'],'1885149',ref)
    S.need(actual['schema']=='ROOT_ACTUAL_ALPHA_MINCID_POOL_V1'
           and pool['schema']=='PUBCHEM_EXACT_MINCID_CANDIDATE_POOL_V2'
           and pool['status']=='MATERIALIZED_UNFILTERED_NO_RELEASE'
           and pool['source_rows']==actual['source_rows']==124857440
           and pool['unique_full_keys']==actual['unique_full_keys']==109871959
           and pool['candidates']==actual['candidates']
           and pool['original_SQL_minimum_CID_semantics'] is True
           and pool['all_original_Arrow_fields_and_F64_preserved'] is True
           and pool['decontamination_filter_rank_or_training_release'] is False,'FULL_UNFILTERED_ACTUAL_MINCID_POOL')
    primary_ref=plan['primary3_receipt_reference'];primary=S.load(primary_ref)
    account(plan['primary3_actual_parent_reference'],'1885152',primary_ref)
    S.need(primary['schema']=='COCONUT_ALPHA_PRIMARY3_PRODUCER_V1'
           and primary['result']['original_UNKNOWN735_retained'] is True
           and primary['result']['upstream_source_or_formula_composition_accepted'] is False,'UNADOPTED_ORIGINAL_SOURCE_OBSERVATIONS')
    antichain_ref=primary['result']['lower_bound_metadata_antichain'];bounds=S.load(antichain_ref)
    cached=S.load(bounds['producer_receipt_reference']);account(bounds['actual_accounting_reference'],'1885150')
    S.need(cached['profile_admission']['job_id']=='1885150' and cached['result']['DATA']==bounds['DATA_reference']
           and bounds['schema']=='COCONUT_CACHED729_LOWER_BOUND_METADATA_ANTICHAIN_V1'
           and bounds['rows_with_positive_observations']==729 and bounds['bounds_accepted'] is False
           and [r['vector'] for r in bounds['global_union_minimal_antichain']]==[[[6,1]],[[8,1]],[[16,1]]]
           and all(r['original_source_witnesses'] for r in bounds['global_union_minimal_antichain'])
           and bounds['original_X_whitelist']==list(X),'ACTUAL_UNADOPTED_C_O_S_ANTICHAIN_AND_SOURCE_IDS')
    outside=bounds['out_of_X_vectors_not_projected_to_smaller_bounds']
    S.need(len(outside)==1 and outside[0]['vector']==[[6,3],[7,3],[8,6],[26,1]]
           and outside[0]['original_source_witnesses'][0]['original_id']=='24906','FULL_Fe_BOUND_PRESERVED_NOT_TRUNCATED')
    S.read(bounds['original_X_screen_reference'],2<<20)
    return pool,dict(candidate_receipt=ref,candidate_actual_parent=plan['candidate_actual_parent_reference'],
        primary3_receipt=primary_ref,primary3_actual_parent=plan['primary3_actual_parent_reference'],
        antichain_reference=antichain_ref,cached735_receipt=bounds['producer_receipt_reference'],
        cached735_actual_parent=bounds['actual_accounting_reference'],
        minimal_antichain=bounds['global_union_minimal_antichain'],
        out_of_X_vectors_preserved=outside,original_X_screen_reference=bounds['original_X_screen_reference'])


def physical(ref,fd):
    path=Path(ref['path']);s=os.fstat(fd)
    S.need(path.is_absolute() and not any(p.is_symlink() for p in (path,*path.parents))
           and stat.S_ISREG(s.st_mode) and s.st_uid==1264 and s.st_nlink==1
           and s.st_size==ref['bytes'] and S.frame(s)==S.frame(path.stat()),'OWNED_IMMUTABLE_DECLARED_CANDIDATE_PHYSICAL_FILE')
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,
                uid=s.st_uid,nlink=s.st_nlink)


def native_input_volume(plan,ref,current):
    from workflows.expansion.alpha_runtime_v1.common import load
    from workflows.expansion.alpha_runtime_v1.quota import validate_snapshot
    authority=plan['quota_authority']
    snapshot=validate_snapshot(load(plan['quota_snapshot']),authority)
    S.need(Path(ref['path']).is_relative_to(Path(authority['quota_root']))
           and current['device']==snapshot['quota_root_statfs']['device']
           and snapshot['publisher']['hostname']==socket.gethostname(),
           'CURRENT_CANDIDATE_AND_FRESH_SAME_NODE_NATIVE_ALPHA_QUOTA_SHARE_LOCAL_VOLUME')
    return dict(quota_authority=authority,validated_same_node_snapshot=snapshot,
        candidate_current_local_device=current['device'],
        candidate_is_under_verified_Alpha_quota_root=True,
        native_backend_volume_UUID_mount_source_and_roots_validated=True,
        historical_ledger_host_or_volume_identity_used=False,
        historical_volume_identity_independently_reconstructed=False)


def execute(plan,out,guard):
    import duckdb
    S.need(duckdb.__version__=='1.2.2','ACTUAL_APPROVED_DUCKDB_1_2_2')
    pool,provenance=source(plan);ref=pool['candidates'];fd=os.open(ref['path'],os.O_RDONLY|os.O_NOFOLLOW)
    try:
        before=physical(ref,fd);volume_proof=native_input_volume(plan,ref,before);historic=None
        if plan.get('closed_candidate_frames_reference'):
            ledger=S.load(plan['closed_candidate_frames_reference'])
            S.need(ledger['schema']=='ROOT_OTHER_FUTURE_CLOSED_SCOPE_CREDIT_V1'
                   and ledger['endpoint']=='218.192.171.238:22' and ledger['uid']==1264,'REAL_CLOSED_SOURCE_FRAME_LEDGER')
            found=[r for r in ledger['closed_immutable_retained_files'] if r['reference']==ref]
            S.need(len(found)==1,'EXACT_HISTORIC_CANDIDATE_BODY_PIN_IN_LEDGER');historic=found[0]
            S.need(all(before[k]==historic[k] for k in ('inode','mtime_ns','ctime_ns')),'CURRENT_SOURCE_EQUALS_HISTORIC_CLOSED_INODE_AND_TIMESTAMPS: '+json.dumps(dict(current=before,historic=historic),sort_keys=True))
        guard.check();db=duckdb.connect();finished=threading.Event();errors=[]
        def observe():
            while not finished.wait(1):
                try:guard.check()
                except BaseException as exc:errors.append(repr(exc));db.interrupt();return
        monitor=threading.Thread(target=observe,daemon=True);monitor.start()
        try:
            db.execute('SET threads='+str(int(plan['workers'])))
            db.execute("SET memory_limit='"+str(int(plan['duckdb_memory_bytes']))+"B'")
            db.execute("SET temp_directory='"+str(out/'spill').replace("'","''")+"'")
            db.read_parquet(ref['path']).project('non_h_composition').create_view('candidates')
            columns=db.execute('DESCRIBE candidates').fetchall()
            S.need(len(columns)==1 and columns[0][0:2]==('non_h_composition','VARCHAR'),'ACTUAL_SINGLE_TEXT_COMPOSITION_COLUMN')
            result=summarize(census(db,'candidates'))
            S.need(not errors and result['total_rows']==pool['unique_full_keys'] and result['all_rows_accounted'],
                   'EXACT_FULL109871959_CANDIDATE_CENSUS_NO_SAMPLE')
        finally:
            finished.set();monitor.join();db.close()
        after=physical(ref,fd);S.need(before==after,'UNCHANGED_SOURCE_DURING_EXACT_COLUMN_SCAN');guard.check()
        return dict(schema='COCONUT_ALPHA_COS_IMPACT_DIAGNOSTIC_V1',
            status='COMPLETE_EXACT_DIAGNOSTIC_CENSUS_NO_FILTER_OR_ADOPTION',counts=result,
            complete_valid_composition_census=result['invalid_or_noncanonical_composition_rows']==0,
            input_candidate_reference=ref,input_physical_frame=before,historic_closed_frame=historic,
            historic_frame_ledger_reference=plan.get('closed_candidate_frames_reference'),
            native_input_volume_proof=volume_proof,
            historical_device_comparison=dict(current_client_device=before['device'],
                historical_client_device=None if historic is None else historic['device'],
                equality_required_across_clients=False,
                interpretation='GLUSTER_ST_DEV_IS_CLIENT_LOCAL;_HISTORIC_REFERENCE_INODE_MTIME_CTIME_REQUIRED;_CURRENT_BEFORE_AFTER_FULL_FRAME_INCLUDING_DEVICE_REQUIRED'),
            fresh_full_body_sha256_recomputed=False,
            input_sha256_authority='ACTUAL1885149_C0_CLOSED_RECEIPT_AND_ROOT_READBACK;_CURRENT_IMMUTABLE_PHYSICAL_FRAME',
            source_observation_provenance=provenance,executed_SQL=query('candidates'),
            duckdb_version=duckdb.__version__,workers=plan['workers'],columns_scanned=['non_h_composition'],
            comparison='HYPOTHETICAL_POSITIVE_COUNT_C_GE1_OR_O_GE1_OR_S_GE1;_SOURCE_EXPLICIT_NON_H_PAIRS_ONLY',
            empty_non_H_vectors_retained=True,Fe_source_vector_shortened=False,
            chemical_calls=0,approximation_or_sampling=False,graph_UNKNOWN735_unchanged=True,
            lower_bounds_or_exclusions_accepted=False,candidate_filtering_performed=False,
            index_or_queue_written=False,source_scope_changed=False,all11_ready=False,global_pool_release=False)
    finally:os.close(fd)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--startup-proof',type=Path,required=True);args=p.parse_args()
    plan=json.loads(args.plan.read_text());proof=json.loads(args.startup_proof.read_text())
    authority=admit(plan,proof,args.plan,args.startup_proof)
    from workflows.expansion.alpha_runtime_v1.guard import Guard
    guard=Guard(plan);out=Path(plan['output_directory'])
    try:
        out.mkdir(parents=True,exist_ok=False)
        from .test_source import Source
        transcript=io.StringIO();tested=unittest.TextTestRunner(stream=transcript,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Source))
        tests=S.save(out/'source_tests.json',dict(tests=tested.testsRun,errors=len(tested.errors),failures=len(tested.failures),skips=len(tested.skipped),transcript=transcript.getvalue()))
        S.need(tested.wasSuccessful() and tested.testsRun==1 and not tested.skipped,'ONE_EXACT_SQL_FIXTURE_BEFORE_FULL_CENSUS')
        result=execute(plan,out,guard);result_ref=S.save(out/'impact_diagnostic.json',result)
        S.save(out/'receipt.json',dict(schema='COCONUT_ALPHA_COS_IMPACT_PRODUCER_V1',plan=S.pin(args.plan),
            startup_proof=S.pin(args.startup_proof),profile_admission=authority,source_tests=tests,
            result_reference=result_ref,result=result,runtime=guard.receipt(),actual_parent_C0_pending_root_readback=True,
            scientific_acceptance=False,all11_ready=False,global_pool_release=False))
    except BaseException as exc:
        if out.is_dir():S.save(out/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),partials_retained=True,scientific_acceptance=False))
        raise
    finally:guard.close()


if __name__=='__main__':main()
