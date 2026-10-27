"""Acquire exactly one author ZIP in a fresh Alpha CPU allocation; no chemistry."""
import argparse,hashlib,io,json,os,stat,sys,time,unittest
from pathlib import Path
from urllib import error,request
from secondary_moleculenet_csv6_identity_v1.runtime import Budget
from secondary_moleculenet_csv6_identity_v1 import journal as J
from . import contracts as C,guard as G,archive as A
Q=C.Q


def frame(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid)


def fixtures(out):
    from .test_v1 import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT_NEW3_SINGLE_SOURCE_ACQUISITION_BOUNDARIES')
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    value={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),'expected_failures':len(r.expectedFailures),
        'unexpected_successes':len(r.unexpectedSuccesses),'transcript':stream.getvalue(),'before_network_DATA_and_Budget':True,'old_methods_reexecuted':False}
    Q.write_new(out/'fixtures3.json',value);Q.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'NEW3_BEFORE_ANY_NETWORK_BODY_AND_MONITOR');return value


def imports(plan):
    for name,module in list(sys.modules.items()):
        p=getattr(module,'__file__',None)
        if p and Path(p).suffix=='.py' and name.startswith('secondary_'):
            Q.need(C.ROOT/'code' in Path(p).absolute().parents and Q.ref(p) in plan['source_references'],'ALL_ACTUAL_NEW_AND_ORIGINAL_IMPORT_SOURCE_PINS:'+name)


class StableOutput:
    def __init__(self,path):self.file=path.open('xb');self.path=path
    def write(self,raw):return self.file.write(raw)
    def flush(self):self.file.flush()
    def durable(self):self.file.flush();os.fsync(self.file.fileno())
    def close(self):
        if not self.file.closed:self.durable();self.file.close()


def downloaded_file(path,body,budget):
    p=Q.literal(path);s=p.lstat();fr=frame(s);Q.need(stat.S_ISREG(s.st_mode) and s.st_uid==1264 and s.st_size==body['observed_body_bytes'],'OWNED_CURRENT_DOWNLOADED_OPAQUE_FILE')
    f=p.open('rb')
    try:
        Q.need(frame(os.fstat(f.fileno()))==fr,'SAME_OPAQUE_ARCHIVE_OPENED_FD');h=hashlib.sha256();n=0
        while True:
            budget.check();raw=f.read(1<<20)
            if not raw:break
            n+=len(raw);h.update(raw)
        Q.need(n==body['observed_body_bytes'] and h.hexdigest()==body['sha256_of_observed_bytes'] and frame(os.fstat(f.fileno()))==fr==frame(p.lstat()),'ACTUAL_FIRST_PRODUCER_SHA_AND_STABLE_FD_BEFORE_ZIP_DECODE');f.seek(0)
        return f,fr,{'path':str(path),'bytes':n,'sha256':h.hexdigest()}
    except BaseException:f.close();raise


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args()
    plan,proof=G.require_startup(a.plan,a.startup_proof);parents=C.inputs(plan);out=Q.literal(plan['output_directory']);Q.need(not out.exists(),'NEW_SINGLE_SOURCE_OUTPUT');out.mkdir(parents=True,mode=0o700)
    fx=None;budget=None;body=None;response_meta=None;response_file=None;blob=None;inventory_file=None;archive_fd=None;started=time.monotonic();progress={};success=False
    try:
        fx=fixtures(out);imports(plan);budget=Budget(plan,proof,out);budget.check();C.exact_url(C.URL)
        response_file=StableOutput(out/'author_2013_actual_response.DATA.bin');opener=request.build_opener(A.NoRedirect)
        req=request.Request(C.URL,method='GET');response=None
        try:
            try:response=opener.open(req,timeout=60)
            except error.HTTPError as exc:response=exc
            response_meta={'schema':'ACTUAL_AUTHOR2013_HTTP_RESPONSE_METADATA_V1','requested_URL':C.URL,'actual_response_URL':response.geturl(),
                'HTTP_status':response.getcode(),'whitelisted_headers':A.safe_headers(response.headers),'GET_attempts':1,'redirects_followed':0,'ranges_or_retries':0,
                'network_proxy_environment_changed':False,'actual_body_closed':False}
            J.write_json(out/'actual_HTTP_response.json',response_meta,budget)
            body=A.copy_response(response,response_file,lambda n=0:budget.check(n),C.DOWNLOAD,C.EXPECTED)
        finally:
            if response is not None:response.close()
            response_file.close()
        progress.update(body);response_meta={**response_meta,'actual_body_closed':True,'body_observation':body}
        J.write_json(out/'actual_HTTP_body_observation.json',response_meta,budget)
        Q.need(response_meta['actual_response_URL']==C.URL and A.response_acceptable(response_meta['HTTP_status'],response_meta['whitelisted_headers'],body,C.EXPECTED),'HTTP_OR_ORIGINAL_HEAD_LENGTH_MISMATCH_ACTUAL_RESPONSE_RETAINED_NO_FALLBACK')
        archive_fd,fr,payload=downloaded_file(response_file.path,body,budget);blob=StableOutput(out/'all_original_uncompressed_members.DATA.raw');inventory_file=(out/'all_original_members.DATA.jsonl').open('xb')
        def emit(value):
            J.append(inventory_file,value,budget);progress.update(verified_member_prefix=value['physical_member_ordinal']+1,verified_uncompressed_prefix_bytes=blob.file.tell())
        result=A.inventory(archive_fd,blob,emit,lambda n=0:budget.check(n),C.EXPANDED,C.MEMBERS)
        blob.close();inventory_file.flush();os.fsync(inventory_file.fileno());inventory_file.close()
        Q.need(frame(os.fstat(archive_fd.fileno()))==fr==frame(response_file.path.lstat()),'CURRENT_ARCHIVE_UNCHANGED_AFTER_ALL_MEMBER_CRC');archive_fd.close();archive_fd=None
        refs={'original_archive_reference':payload,'all_uncompressed_original_bytes_reference':J.pin(blob.path),'member_inventory_DATA_reference':J.pin(out/'all_original_members.DATA.jsonl')}
        budget.sample();Q.need(budget.reason is None,'RESOURCE_STOP_NO_COMPLETE_ARCHIVE_CLAIM')
        summary={'schema':'QM7B_OFFICIAL2013_OPAQUE_ARCHIVE_SUMMARY_V1','status':'OFFICIAL_ARCHIVE_SHA_ALL_MEMBER_EOF_CRC_INVENTORY_COMPLETE_GRAPH_AND_ROW_MAPPING_UNKNOWN',
            'source_URL':C.URL,'HTTP_status':response_meta['HTTP_status'],'actual_original_archive_bytes':payload['bytes'],'ZIP_observation':result,**refs,
            'graph_SMILES_SDF_or_explicit_MAT_mapping_presence_examined':False,'all_members_remain_opaque_DATA_for_separate_CPU_format_review':True,
            'original_UNKNOWNs_changed':False,'automatic_graph_policy_decontamination_pool_release':False,'new_graph_parse_key_UFF_QM_calls':0}
        sr=J.write_json(out/'finding_summary.json',summary,budget)
        receipt={'schema':'SECONDARY_QM7B_OFFICIAL2013_ARCHIVE_RECEIPT_V1','status':summary['status'],'job_id':str(proof['job_id']),'endpoint':Q.ENDPOINT,'uid':1264,'node':plan['node'],
            'plan_reference':Q.ref(a.plan),'startup_proof_reference':Q.ref(a.startup_proof),'scope_parameters':C.PARAMETERS,'primary_research_reference':plan['primary_research_reference'],
            'official_HEAD_reference':plan['official_HEAD_reference'],'fixtures':fx,'actual_HTTP_observation_reference':J.pin(out/'actual_HTTP_body_observation.json'),**refs,
            'whole_original_archive_frame':list(fr),'all_member_observation':result,'finding_summary_reference':sr,'runtime':budget.receipt(),'elapsed_seconds':time.monotonic()-started,
            'maximum_reader_processes':1,'allocated_cpus':16,'new_graph_parse_key_UFF_QM_calls':0,'graph_SMILES_MAT_mapping_accepted':False,'global_pool_decontamination_release':False,
            'actual_new_parent_terminal_cost_pending_Root':True,'cost_overrun_action':'REPORT_AND_CONTINUE'}
        J.write_json(out/'receipt.json',receipt,budget);success=True;print(json.dumps({'status':summary['status'],'receipt_reference':J.pin(out/'receipt.json')}));return 0
    except BaseException as exc:
        if response_file:response_file.close()
        if blob:blob.close()
        if inventory_file and not inventory_file.closed:inventory_file.flush();os.fsync(inventory_file.fileno());inventory_file.close()
        Q.write_new(out/'partial_hold.json',{'schema':'QM7B_OFFICIAL2013_ACQUISITION_PARTIAL_HOLD_V1','status':'ACTUAL_RESPONSE_AND_OPAQUE_PREFIX_RETAINED_NOT_ACCEPTED',
            'error_type':type(exc).__name__,'contract_error':str(exc) if isinstance(exc,ValueError) else 'NONCONTRACT_EXCEPTION','fixtures':fx,'progress':progress,
            'actual_HTTP_metadata':response_meta,'current_owned_output_paths':[str(p) for p in (response_file.path if response_file else None,blob.path if blob else None,out/'all_original_members.DATA.jsonl' if inventory_file else None) if p is not None],
            'runtime':budget.receipt() if budget else None,'no_mirror_retry_or_source_data_deletion':True,'graph_SMILES_MAT_mapping_accepted':False,
            'original_UNKNOWNs_unchanged':True,'full_or_pool_release':False,'actual_new_parent_cost_pending_Root':True});raise
    finally:
        if archive_fd:archive_fd.close()
        if budget:budget.finish()


if __name__=='__main__':raise SystemExit(main())
