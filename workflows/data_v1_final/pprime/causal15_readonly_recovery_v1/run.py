"""Recover existing raw bytes only. No initialize_worker/invoke/once writes."""
import argparse,copy,gzip,io,json,os,pathlib,re,sys,traceback,unittest
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as R
from workflows.data_v1_final.pprime.causal15_main_v1 import render as T,analysis as A
from . import contract as C,io as W,reader as D
Q=C.Q


def fixtures(out,output,archive):
    from .test_v1 import Boundaries
    Boundaries.archive=archive
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT3_PURE_BOUNDARIES')
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    value={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':stream.getvalue(),'before_scientific_bodies':True}
    ref=output.json(out/'fixtures3.json',value);Q.need(r.wasSuccessful() and r.testsRun==3
        and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'PURE3_PASS_BEFORE_EXISTING_RAW');return ref


def bind(task,prepared_row,claim_ref,start_ref,intent_ref,oldproof,prepared_ref,receipt):
    claim=C.I.read(claim_ref);start=C.I.read(start_ref);intent=C.I.read(intent_ref);qa=prepared_row['qa_id']
    Q.need(task['qa_id']==qa and claim['qa_id']==start['qa_id']==intent['qa_id']==qa
        and claim['schema']=='PPRIME_CAUSAL15_QA_DISPATCH_INTENT_V1' and claim['prepared_reference']==prepared_ref
        and claim['task_reference']==start['task_reference']==prepared_row['task_reference']
        and start['claim_reference']==claim_ref and claim['startup_proof_reference']==receipt['startup_proof_reference']
        and claim['job_id']==start['job_id']=='4521766' and claim['uid']==start['uid']==1278
        and claim['boot_id']==start['boot_id']==oldproof['boot_id'] and start['pid'] in receipt['actual_worker_pids']
        and any(p['pid']==start['pid'] and p['alive'] is False for p in receipt['process_closure'])
        and start['pid_start_ticks']>0 and claim_ref['path']==str(C.O.BASE/'qa_once_ledger'/(C.O.key(prepared_ref,qa)+'.json')),
        'EXACT_ORIGINAL_TASK_CLAIM_ACTUAL_WORKER_PID_BOOT_AND_FAILED_PARENT')
    Q.need(intent['state']=='DURABLE_NATIVE_CALL_INTENT_NOT_RETURN' and intent['actual_frozen_timeout_seconds']==900
        and intent['original_record_id']==task['original_record_id']==task['case']['row']['record_id']
        and intent['seed']==task['seed'],'ORIGINAL_NATIVE_INTENT_SEED_RECORD_NO_NEW_CALL')
    return start,intent


def inputs(task,intent,paths,archive):
    expected={pathlib.Path(r['path']).name:r for r in task['target_input_references']};actual={}
    Q.need(set(paths)==set(expected),'EXACT_ORIGINAL_INPUT_MEMBER_NAMES')
    for name,path in paths.items():
        Q.need(path.lstat().st_uid==1278 and path.lstat().st_size==expected[name]['bytes']<=C.O.INPUT_CAP
            and not any(p.is_symlink() for p in (path,*path.parents)),'OWN_REGULAR_BOUNDED_ACTUAL_INPUT')
        before=path.lstat();raw=C.I.body(expected[name],C.O.INPUT_CAP)
        with path.open('rb') as f:
            value=f.read(C.O.INPUT_CAP+1);Q.need(D.frame(os.fstat(f.fileno()))==D.frame(before)==D.frame(path.lstat()),'ACTUAL_INPUT_STABLE_FD_FRAME')
        Q.need(value==raw,'EXISTING_ACTUAL_INPUT_BYTES_EQUAL_ORIGINAL_PREPARED');actual[name]=value
    hashes=[{'name':name,'sha256':C.O.sha(raw)} for name,raw in sorted(actual.items())]
    envelope,_=archive.bundle([{'name':n,'data':v} for n,v in sorted(actual.items())])
    Q.need(hashes==intent['input_file_sha256'] and C.O.sha(envelope)==intent['input_bundle_sha256'],'ORIGINAL_DURABLE_PRECALL_INPUT_BUNDLE_SHA')
    return actual,hashes


def record_template(task,qa,actual):
    case=copy.deepcopy(task['case']);case.update(case_id=qa,native_coordinates_A=task['native_coordinates_A'],
        actual_rendered_coordinates_A=T.arrays(actual,task['case']['symbols']).tolist(),expected_actual_coordinates_A=T.arrays(actual,task['case']['symbols']).tolist())
    return {'schema':'PPRIME_CAUSAL15_READONLY_RECOVERED_OBSERVATION_V1','qa_id':qa,'condition':task['condition'],'arm':task['arm'],
        'rotation_matrix':task['rotation_matrix'],'case':case,'origin_case':copy.deepcopy(task['case']),
        'origin_case_id':task['case']['case_id'],'original_evidence_reference':task['original_evidence_reference'],
        'parsed_wp5_result':{},'original_parsed_WP5_status_and_returncode':'UNKNOWN_MISSING_PRODUCER_RESULT_OR_BEFORE_PARSE_STAGING',
        'original15FAIL_preserved':True,'scientific_PASS':False,'full_or2000_release':'HOLD','new_QM_calls':0}


def recover(plan,receipt,prepared,source,oldproof,obs,out,output):
    engine,legacy,protocol,_=T.engine(source,C.I.read)
    from common import read_staging,staging_bytes
    from read_outputs_v1 import parse_outputs
    expected_rows={r['path']:r for r in obs['observations']};result_refs={pathlib.Path(r['path']).parent.name:r for r in receipt['results']}
    records=[];observations=[];failures=[];evidence={}
    for item in prepared['tasks']:
        qa=item['qa_id'];folder=out/qa;folder.mkdir()
        try:
            refs=plan['case_metadata'][qa];task=C.I.read(item['task_reference'])
            start,intent=bind(task,item,refs['claim_reference'],refs['worker_start_reference'],refs['invoke_intent_reference'],oldproof,receipt['prepared_reference'],receipt)
            original=read_staging(C.I.body(result_refs[qa],C.O.RESULT_CAP)) if qa in result_refs else None
            if original is not None:Q.need(original['qa_id']==qa and original['task_reference']==item['task_reference']
                and original['claim_reference']==refs['claim_reference'] and original['worker_start_reference']==refs['worker_start_reference'],'EXACT_PRODUCER_RESULT_SOURCE_CHAIN')
            if qa!='qa-08':
                database=C.BASE/qa/'all_output_raw.sqlite'
                for suffix in ('-journal','-wal','-shm'):
                    p=pathlib.Path(str(database)+suffix);Q.need(not p.exists() and not p.is_symlink(),'CLOSED_SQLITE_REQUIRED_NO_SIDECAR:'+str(p))
                _,copied,bootstrap=D.copy_observed(expected_rows[str(database)],folder/'original_raw_snapshot.sqlite',output)
                raw_reference=original['raw_reference'] if original is not None else None
                if raw_reference is not None:Q.need(raw_reference['container_path']==str(database),'EXACT_ORIGINAL_RAW_CONTAINER_LOCATOR')
                retained,raw_key=D.keyed_raw(copied['path'],engine.OUTPUT_ARCHIVE,task,qa,raw_reference)
                metadata=retained['metadata'];files=retained['output_files'];actual_paths={}
                for target in item['target_input_references']:
                    name=pathlib.Path(target['path']).name;p=C.BASE/qa/'actual_postcall_inputs'/name
                    actual_paths[name]=p
                actual,hashes=inputs(task,intent,actual_paths,engine.OUTPUT_ARCHIVE)
                frozen=task['original_task'];keywords=frozen.get('keywords',frozen.get('args'))
                if frozen['family']=='mopac':keywords=keywords+' THREADS=1'
                Q.need(metadata['context']['job_id']==4521766 and metadata['context']['QA_arm']==task['arm']
                    and metadata['execution_id']==metadata['context']['execution_id']=='causal15:4521766:'+qa
                    and metadata['context']['audit_only'] is True and metadata['record_id']==task['original_record_id']
                    and metadata['calc_type']==task['case']['calc_type'] and metadata['input_file_sha256']==hashes
                    and metadata['input_bundle_sha256']==intent['input_bundle_sha256']
                    and metadata['source_payload_sha256']==task['case']['row']['record_payload_sha256']
                    and metadata['reproduction_package_sha256']==legacy['reproduction_package']['sha256']
                    and metadata['audit_membership_sha256']==source['audit_membership']['sha256']
                    and metadata['keywords']==keywords and metadata['keywordSHA']==engine.stable_sha(keywords)
                    and metadata['software']=={'family':frozen['family'],'version':protocol['expected_versions'][frozen['family']]},
                    'EXACT_COMMITTED_RAW_CONTEXT_INPUT_SOURCE_VERSION_AND_KEYWORDS')
                output.json(folder/'first_SHA_and_raw_key.json',{'opaque_copy':bootstrap,'raw_key':raw_key,'metadata':metadata})
                parsed=parse_outputs(files,task['case']['calc_type'],task['case']['symbols'])
                if original is not None:
                    Q.need(original.get('error') is None and original['raw_reference']['raw_call_durable'] is True
                        and staging_bytes(parsed)==staging_bytes(original['independent_raw_readback']),'ORIGINAL13_VALID_RAW_READBACK_EQUAL')
                    record=copy.deepcopy(original);kind='ORIGINAL_SUCCESS_RESULT_AND_RAW_REVALIDATED_UNMODIFIED'
                else:
                    record=record_template(task,qa,actual);record['independent_raw_readback']=parsed
                    record['native_return_evidence']='INFERRED_ONLY_FROM_FROZEN_PRODUCER_COMMITTED_RAW_PHASE_NOT_OBSERVED_RESULT_FIELD'
                    kind='QA02_COMMITTED_RAW_AND_INPUTS_RECOVERED_ORIGINAL_WP5_STATUS_UNKNOWN'
            else:
                Q.need(original['native_return_observed'] is True and original['QM_call_attempted'] is True
                    and original['node_scratch_preserved']==str(C.SCRATCH) and original['engine_close']['worker_pid']==start['pid']==2163802
                    and original['engine_close']['local_work_root']==str(C.SCRATCH/'wp5engine_1278_4521766_2163802_0at1los0')
                    and start['boot_id']==obs['boot_id']==pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                    'QA08_ACTUAL_NATIVE_RETURN_AND_EXACT_OWN_WORKER_SCRATCH_BOOT')
                for row in obs['observations']:
                    if row['path']==str(C.SCRATCH) or C.SCRATCH in pathlib.Path(row['path']).parents:D.verify(row)
                directories=[p for p in C.SCRATCH.iterdir() if p.is_dir() and re.fullmatch(r'wp4native_1278_4521766_[A-Za-z0-9_]+',p.name)]
                Q.need(len(directories)==1,'EXACT_ONE_ORIGINAL_QA08_NATIVE_CALL_DIRECTORY');call=directories[0]
                listed={r['path'] for r in obs['observations'] if pathlib.Path(r['path']).parent==call}
                Q.need({str(p) for p in call.iterdir()}==listed,'COMPLETE_OBSERVED_CALL_DIRECTORY_NO_NEW_FILES')
                actual_paths={pathlib.Path(t['path']).name:call/pathlib.Path(t['path']).name for t in item['target_input_references']}
                actual,hashes=inputs(task,intent,actual_paths,engine.OUTPUT_ARCHIVE)
                first=[]
                for path in sorted(call.iterdir()):
                    row=expected_rows[str(path)];_,_,observed=D.copy_observed(row,folder/'scratch_snapshot'/path.name,output);first.append(observed)
                files=engine._capture_files(call)
                Q.need(sum(x['byte_count'] for x in files)<=C.O.RAW_CAP,'ORIGINAL_CAPTURE_WITHIN_FROZEN_RAW_CAP')
                first_by_name={pathlib.Path(v['source_path']).name:v for v in first}
                Q.need(all(x['sha256']==first_by_name[x['name']]['first_actual_CPU_sha256']
                    and x['byte_count']==first_by_name[x['name']]['source_observed_frame']['bytes'] for x in files),
                    'ORIGINAL_CAPTURE_EXACTLY_EQUALS_FIRST_SAME_FD_SOURCE_SNAPSHOTS')
                for row in obs['observations']:
                    if pathlib.Path(row['path']).parent==call:D.verify(row)
                bundle,manifest=engine.OUTPUT_ARCHIVE.bundle(files);compressed=gzip.compress(bundle,mtime=0)
                archive_ref=output.write(folder/'recovered_output.bundle.gz',compressed)
                decoded=D.Parent.get.__globals__['bounded_gzip'](C.I.body(archive_ref,C.O.RAW_CAP+(1<<20)),C.O.RAW_CAP)
                readback,again=engine.OUTPUT_ARCHIVE.unbundle(decoded)
                Q.need(again==manifest and C.O.sha(decoded)==C.O.sha(bundle),'NEW_STABLE_BUNDLE_ORIGINAL_GZIP_UNBUNDLE_READBACK')
                parsed=parse_outputs(readback,task['case']['calc_type'],task['case']['symbols']);record=record_template(task,qa,actual)
                record['independent_raw_readback']=parsed;record['original_native_return_observed']=original['native_return_observed']
                record['original_error_preserved']=original['error'];record['recovered_raw_archive_reference']=archive_ref
                output.json(folder/'scratch_first_SHA_observations.json',{'source_lstat_reference':plan['source_lstat_reference'],'files':first,
                    'original_capture_function_file':engine._capture_files.__code__.co_filename,'output_manifest':manifest,'input_file_sha256':hashes})
                kind='QA08_PRESERVED_NATIVE_OUTPUT_AND_INPUTS_RECOVERED_ORIGINAL_WP5_STATUS_UNKNOWN'
            record['readonly_recovery_source_result_reference']=result_refs.get(qa)
            saved=output.write(folder/'readonly_recovery_record.json',staging_bytes(record)+b'\n');records.append(record)
            observations.append({'qa_id':qa,'state':kind,'record_reference':saved,'worker_pid':start['pid'],'worker_start_ticks':start['pid_start_ticks'],
                'new_native_calls':0,'old_result_modified':False,'original_WP5_state_unknown':qa in ('qa-02','qa-08')})
            evidence[qa]=C.I.read(task['original_evidence_reference'])
        except Exception as exc:
            failures.append({'qa_id':qa,'state':'READONLY_RECOVERY_UNKNOWN_HOLD','error':repr(exc),'traceback':traceback.format_exc(),
                'new_native_calls':0,'original_evidence_preserved':True})
    try:findings=A.analyze(records,C.I.read(source['audit_config']),evidence)
    except Exception as exc:
        findings={'schema':'PPRIME_CAUSAL15_READONLY_ANALYSIS_UNKNOWN_V1','error':repr(exc),'traceback':traceback.format_exc(),
            'cause':'UNKNOWN_REQUIRES_ROOT_REVIEW','original15FAIL_preserved':True,'scientific_PASS':False,'full_or2000_release':'HOLD'}
        failures.append({'phase':'ORIGINAL_ANALYSIS','state':'UNKNOWN_HOLD','error':repr(exc)})
    return observations,failures,output.write(out/'causal_analysis_readonly.json',staging_bytes(findings)+b'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True);p.add_argument('--startup-proof',type=pathlib.Path,required=True);a=p.parse_args()
    plan=Q.load(a.plan);Q.need(plan['schema']=='PPRIME_CAUSAL15_READONLY_RECOVERY_PLAN_V1' and plan['scope_parameters']==C.PARAMETERS,'EXACT_NEW_READONLY_PLAN')
    receipt,prepared,source,oldproof,obs,locations,parents=C.parents(plan)
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
    proof=R.require_startup(a.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=C.PARAMETERS,expected_execution_argv=argv,
        expected_source=__file__,expected_kind='analysis',required_references=[Q.pin(a.plan),*parents,*plan['source_references'],*plan['data_references']])
    req=proof['request'];Q.need(req['node']=='compute-0-13' and req['cpus']==16 and req['pilot'] is False
        and req['estimated_peak_output_bytes']==C.CAP and req['deferred_authority_references']==locations
        and req['data_references']==plan['data_references'] and req['wall_seconds']==plan['wall_seconds']
        and 600<=plan['wall_seconds']<=3600 and plan['wall_seconds']%60==0,'EXACT_ZERO_QM_RECOVERY_SCOPE')
    review=C.meta(req['scope']['review']);Q.need(review['zero_native_calls_no_once_writes_first_SHA_only_after_fixtures'] is True,'ROOT_EXACT_READONLY_RECOVERY_AUTHORITY')
    cost=C.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'UNCHANGED_SCIENCE_AND_COST_AUTHORITY')
    Q.need(pathlib.Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py' and sys.argv==[str(C.HERE/'run.py'),*argv[4:]],'PRIMARY_FULL_ARGV')
    for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):os.environ[name]='1'
    os.environ['CUDA_VISIBLE_DEVICES']=''
    out=pathlib.Path(plan['output_directory']);Q.need(Q.ROOT/'artifacts' in out.parents and not out.exists(),'NEW_RECOVERY_OUTPUT');out.mkdir(parents=True,mode=0o700)
    output=W.Output(out,proof,plan['quota_reuse_review_reference'])
    engine,_,_,_=T.engine(source,C.I.read);gate=fixtures(out,output,engine.OUTPUT_ARCHIVE)
    observations,failures,findings=recover(plan,receipt,prepared,source,oldproof,obs,out,output)
    output.json(out/'finding_summary.json',{'schema':'PPRIME_CAUSAL15_READONLY_RECOVERY_SUMMARY_V1',
        'status':'ALL15_READONLY_OUTPUT_OBSERVATIONS_AVAILABLE_ROOT_REVIEW_REQUIRED' if len(observations)==15 and not failures else 'READONLY_RECOVERY_PARTIAL_UNKNOWN_HOLD',
        'job_id':str(proof['job_id']),'original_job_id':'4521766','original_parent_failed_state_preserved':True,
        'observations':observations,'failures':failures,'causal_analysis_reference':findings,'fixtures_reference':gate,
        'original_WP5_status_unknown_cases':['qa-02','qa-08'],'original_missing_call_returncode_not_fabricated':True,
        'native_child_PID_when_not_retained':'UNKNOWN_NOT_INFERRED_FROM_ORIGINAL_WORKER_PID',
        'new_QM_calls':0,'native_initialize_or_invoke_calls':0,'once_ledger_writes':0,'original_data_modified_or_deleted':False,
        'original15FAIL_preserved':True,'scientific_PASS':False,'full_or2000_release':'HOLD','budget':output.report(),
        'actual_terminal_accounting':'PENDING_ROOT_CAPTURE'})
    return 0 if len(observations)==15 and not failures else 3


if __name__=='__main__':raise SystemExit(main())
