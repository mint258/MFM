"""Independently read the exact32 sparse original values on Alpha; zero UFF/QM."""
from __future__ import annotations
import argparse,concurrent.futures as cf,json,os,pathlib,socket,sys,traceback
from . import common as U,driver,guard,source
from .signatures import canonical,sha,compare_signatures

def verify_inputs(manifest,root,budget,fixture):
    references=manifest['alpha_data_references'];U.need(sum(r['bytes'] for r in references)<=U.CAP,'FINITE_WHOLE_SELECTED_INPUT2GIB')
    U.need(len({r['path'] for r in references})==len(references),'NO_DUPLICATE_TRANSFER_LOCATORS')
    def verify(reference):
        path=pathlib.Path(reference['path']);U.need(U.ALPHA/'inputs/n1_sparse32_readchain_v1' in path.parents
            and not any(p.is_symlink() for p in (path,*path.parents)) and path.stat().st_uid==1264,'EXPLICIT_OWNED_ALPHA_INPUT_LOCATION')
        actual=U.pin(path);U.need(actual==reference,'ACTUAL_TRANSFER_SHA_DRIFT')
        return {'expected_alpha_locator':reference,'actual_Alpha_reference':actual,'actual_Alpha_file_frame':U.frame(path.stat()),'status':'ACTUAL_FULL_SHA_AND_STABLE_FSTAT_PASS'}
    checked=[];budget.check();index=0
    with cf.ThreadPoolExecutor(max_workers=16) as pool:
        active={}
        while active or index<len(references):
            budget.observe()
            while budget.stop is None and index<len(references) and len(active)<16:
                reference=references[index];active[pool.submit(verify,reference)]=reference;index+=1
            if not active:break
            budget.observe();done,_=cf.wait(active,timeout=.5,return_when=cf.FIRST_COMPLETED)
            for future in done:active.pop(future);checked.append(future.result())
    U.need(budget.stop is None and len(checked)==len(references),budget.stop or 'TRANSFER_OBSERVATION_STOP')
    result={'schema':'ALPHA_SPARSE32_ACTUAL_TRANSFER_VERIFICATION_V1','status':'ALL_EXPECTED_BODY_FILES_ACTUAL_FULL_SHA_PASS',
        'job_id':os.environ['SLURM_JOB_ID'],'uid':os.getuid(),'node':socket.gethostname().split('.')[0],
        'fixture_reference':fixture,'all_body_hashing_after_six_fixtures':True,'body_files':len(references),
        'body_bytes':sum(r['bytes'] for r in references),'records':sorted(checked,key=lambda r:r['actual_Alpha_reference']['path'])}
    return U.save(root/'transfer_verification.json',result)

def verify_KV(manifest,budget):
    import lmdb
    records=manifest['records'];closed=[]
    for database in manifest['databases']:
        budget.check();reference=database['alpha_target_locator'];path=pathlib.Path(reference['path']);before=U.frame(path.stat())
        rows=[r for r in records if r['group_id']==database['group_id']]
        expected={bytes.fromhex(r['key_hex']):(r['raw_value_bytes'],r['raw_value_sha256']) for r in rows}
        U.need(len(expected)==len(rows)==database['unique_keys'],'EXACT_PER_ORIGIN_SELECTED_KEY_CONSERVATION')
        with lmdb.open(str(path),subdir=False,readonly=True,create=False,lock=False,readahead=False) as env:
            with env.begin() as tx:
                observed={}
                for key,value in tx.cursor():
                    U.need(len(value)<=U.RAW_CAP,'ALPHA_RAW_VALUE_SOFTWARE8MIB_STOP');observed[bytes(key)]=(len(value),sha(value))
                U.need(observed==expected and env.stat()['entries']==len(expected),'ALPHA_NEW_LMDB_ACTUAL_KEY_OR_VALUE_DRIFT')
        U.need(before==U.frame(path.stat()),'ALPHA_NEW_LMDB_CHANGED_DURING_RAW_KEY_CHECK')
        closed.append({'group_id':database['group_id'],'reference':reference,'actual_Alpha_file_frame':before,'keys':len(expected),'status':'ALL_RAW_KEYS_AND_VALUES_SHA_PASS'})
    U.need(sum(row['keys'] for row in closed)==32,'ALL32_PHYSICAL_KEYS_ACCOUNTED');return closed

def selected_items(manifest):
    items=[];expected={}
    for row in manifest['records']:
        task=U.load(row['alpha_task_reference']);baseline=U.load(row['alpha_baseline_reference']);main=U.load(row['alpha_signature_reference'])
        for original,alpha in (('origin_task_reference','alpha_task_reference'),('origin_baseline_reference','alpha_baseline_reference'),('main_signature_reference','alpha_signature_reference')):
            U.need(all(row[original][k]==row[alpha][k] for k in ('bytes','sha256')),'ORIGINAL_MAIN_BODY_BYTES_NOT_REWRITTEN')
        pointer=row['origin_pointer'];execution=row['alpha_execution_pointer'];mid=row['molecule_id'];rid=row['record_id']
        U.need(task['schema']=='N1_PPRIME2_PILOT_TASK_V2' and baseline['schema']=='N1_ORIGINAL_BASELINE_PACKET_V2'
            and task['meta']['molecule_id']==baseline['molecule_id']==mid and task['records']==[pointer]
            and pointer['record_id']==rid and sha(canonical(pointer))==row['origin_pointer_sha256']
            and task['authority_references']['accepted_baseline_evidence']==row['origin_baseline_reference']
            and task['existing_conformers']==[baseline['original_row']]
            and task['baseline_row_sha256']==sha(canonical(baseline['original_row'])),'EXACT_ORIGINAL_TASK_BASELINE_AND_POINTER_BYTES')
        database=next(db for db in manifest['databases'] if db['group_id']==row['group_id'])
        U.need(execution==U.execution_pointer(pointer,database['alpha_target_locator']['path']) and U.raw_key(execution).hex()==row['key_hex']
            and row['raw_value_sha256']==pointer['record_payload_sha256']==main['raw_sha256']
            and main['origin_pointer']==main['execution_pointer']==pointer,'ONLY_EXPLICIT_SOURCE_PATH_RELOCATION_NOT_REINDEXING')
        source.validate_graph_against_baseline(main['graph_signature'],baseline['validation'],pointer)
        U.need(main['graph_signature']['atomic_numbers']==task['source_atomic_numbers'] and rid not in expected,'EXACT_MAIN_SOURCE_GRAPH_AND_UNIQUE_RECORD')
        items.append({'origin_pointer':pointer,'execution_pointer':execution})
        expected[rid]={'row':row,'task':task,'baseline':baseline,'main':main}
    U.need(len(items)==32 and len({r['execution_pointer']['molecule_id'] for r in items})==32,'EXACT32_ORIGINAL_CONTROL_ROSTER')
    return items,expected

def run(plan,proof,manifest):
    root=U.new_output(plan['output_directory'],U.ALPHA/'artifacts/n1_sparse32_readchain_v1');budget=U.Budget(root,proof)
    try:
        fixture=driver.fixtures(root,plan['source_references']);budget.check()
        verification=verify_inputs(manifest,root,budget,fixture);keys=verify_KV(manifest,budget);items,expected=selected_items(manifest)
        actual=driver.read_pool(items,source.context(plan,proof,plan['science_sources'],plan['recipe_reference']),budget)
        (root/'records').mkdir();outcomes=[]
        for result in sorted(actual,key=lambda r:r['molecule_id']):
            original=expected[result['record_id']];main=original['main'];row=original['row']
            source.validate_graph_against_baseline(result['graph_signature'],original['baseline']['validation'],row['origin_pointer'])
            comparison=compare_signatures(main['field_signature'],result['field_signature'])
            graph_equal=result['graph_signature']==main['graph_signature'];idx_equal=result['native_idx']==main['native_idx']
            raw_equal=result['raw_sha256']==main['raw_sha256']==row['raw_value_sha256'] and result['raw_bytes']==main['raw_bytes']==row['raw_value_bytes']
            passed=comparison=='EXACT_TYPED_FIELD_BITS_MATCH' and graph_equal and idx_equal and raw_equal
            status='EXACT_ORIGINAL_READ_FIELDS_IDX_GRAPH_MATCH' if passed else 'UNKNOWN_NOT_EQUIVALENT' if comparison=='UNKNOWN_NOT_EQUIVALENT' else 'ACTUAL_READ_DRIFT'
            evidence={'schema':'ALPHA_SPARSE32_ACTUAL_ORIGINAL_READ_COMPARISON_V1','status':status,'molecule_id':result['molecule_id'],
                'record_id':result['record_id'],'Main_expected_signature_reference':row['main_signature_reference'],
                'Alpha_original_signature_copy_reference':row['alpha_signature_reference'],'actual_Alpha_read':result,
                'field_comparison':comparison,'native_idx_equal':idx_equal,'idx_reindexed_to_real_index':False,
                'source_graph_atom_order_stereo_PM7_bits_equal':graph_equal,'original_raw_value_equal':raw_equal,
                'new_UFF_calls':0,'new_QM_calls':0,'once_ledger_opened':False,'dataset_membership':False}
            reference=U.save(root/'records'/(sha(result['molecule_id'].encode())+'.json'),evidence)
            outcomes.append({'molecule_id':result['molecule_id'],'record_id':result['record_id'],'status':status,'reference':reference})
        budget.check();passed=all(row['status']=='EXACT_ORIGINAL_READ_FIELDS_IDX_GRAPH_MATCH' for row in outcomes)
        receipt={'schema':'ALPHA_SPARSE32_EXACT_READCHAIN_CONTROL_RECEIPT_V1',
            'status':'ALL32_ORIGINAL_READ_FIELD_BITS_IDX_GRAPH_MATCH_NO_UFF' if passed else 'UNKNOWN_OR_DRIFT_NO_EQUIVALENCE_NO_RELEASE',
            'endpoint':'218.192.171.238:22','uid':os.getuid(),'job_id':os.environ['SLURM_JOB_ID'],'node':socket.gethostname().split('.')[0],
            'scope_key':guard.ALPHA_KEY,'scope_parameters':guard.PARAMETERS,'actual_startup_proof_reference':U.pin(plan['actual_proof_path'],True),
            'source_references':plan['source_references'],'Main_origin_manifest_reference':plan['origin_manifest_reference'],
            'Alpha_manifest_copy_reference':plan['input_manifest_reference'],'actual_Main_export_accounting_copy':plan['main_export_accounting_reference'],
            'fixture_reference':fixture,'transfer_verification_reference':verification,'actual_key_checks':keys,'records':outcomes,
            'real_original_reader_workers':16,'actual_worker_PIDs':sorted({r['runtime']['pid'] for r in actual}),
            'matched_records':sum(r['status']=='EXACT_ORIGINAL_READ_FIELDS_IDX_GRAPH_MATCH' for r in outcomes),
            'unknown_or_drift_records':sum(r['status']!='EXACT_ORIGINAL_READ_FIELDS_IDX_GRAPH_MATCH' for r in outcomes),
            'actual_version_tuples':list({canonical(r['actual_versions']):r['actual_versions'] for r in actual}.values()),
            'Main_runtime_or_UID_reused_as_Alpha_startup':False,'original_read_function_used':True,'frozen_module_globals_monkeypatched':False,
            'new_UFF_calls':0,'new_QM_calls':0,'once_ledger_opened':False,'canonical32_attempts_consumed':False,
            'dataset_membership':False,'common':False,'production_population_release':False,'later_native_QA_or_production_authorized':False,
            'resource_evidence':budget.report()}
        result=U.save(root/'receipt.json',receipt);U.need(U.usage(root)<=U.CAP,'WHOLE_ALPHA_OUTPUT2GIB');print(json.dumps(result),flush=True);return 0 if passed else 3
    except BaseException as exc:
        U.save(root/'failure.json',{'schema':'ALPHA_SPARSE32_READCHAIN_UNKNOWN_STOP_V1','status':'UNKNOWN_STOP_NO_EQUIVALENCE_NO_RELEASE',
            'error_type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc()[-12000:],
            'new_UFF_calls':0,'new_QM_calls':0,'once_ledger_opened':False,'resource_evidence':budget.report()})
        raise

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True,type=pathlib.Path);parser.add_argument('--startup-proof',required=True,type=pathlib.Path)
    args=parser.parse_args();return run(*guard.alpha_startup(args.plan,args.startup_proof))

if __name__=='__main__':sys.exit(main())
