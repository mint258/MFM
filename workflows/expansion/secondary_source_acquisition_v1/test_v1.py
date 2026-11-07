"""Four secondary acquisition boundaries; stdlib only, no network or scientific data."""
import copy,os,pathlib,tempfile,time,unittest,zipfile
from contracts import ENDPOINT,SECONDARY_ROOT,validate_startup,validate_primary_entry,parse_slurm_duration,validate_wall_binding
from transport import parse_headers,validate_response,PipeCapture
from profile import profile_zip


def runtime_fixture():
    review_ref={'path':'/fixture/review.json','bytes':1,'sha256':'a'};plan_ref={'path':'/fixture/plan.json','bytes':1,'sha256':'b'}
    common={'stage':'CSV_ZIP_PROFILE','source':{'source_id':'coconut_csv_full','expected_content_length':5},
        'scope_parameters':{'network_workers':1,'maximum_host_concurrency':2,'range_requests_authorized':False,'expected_raw_bytes':5},
        'wall_seconds':3600,'output_cap_bytes':1024**3,'endpoint':ENDPOINT,'uid':1264,'run_root':str(SECONDARY_ROOT),
        'execution_argv':['python'],'parent_evidence_references':[]}
    plan=dict(common,schema='SECONDARY_COCONUT_ACQUISITION_PLAN_V1',node='compute-0-1',root_review_reference=review_ref,source_references=[review_ref])
    review=dict(common,schema='EXACT_SECONDARY_SOURCE_ROOT_REVIEW_V1',status='APPROVED_FOR_EXACT_STAGE',reviewer='root',approved_source_references=[])
    proof={'schema':'SECONDARY_SOURCE_ACQUISITION_STARTUP_V1','endpoint':ENDPOINT,'uid':1264,'node':'compute-0-1','hostname':'compute-0-1','boot_id':'boot',
        'plan_reference':plan_ref,'root_review_reference':review_ref,'job_id':'9','memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
        'memory_limits_requested':False,'exclusive_requested':False,'observed_unix_seconds':1000,
        'storage_observation':{'effective_free_bytes':1000000000000,'effective_free_basis':'fixture verified basis','evidence_references':[{}],'observed_unix_seconds':1000},
        'job_metadata':'JobId=9 UserId=alpha(1264) JobState=RUNNING Partition=cpu NumCPUs=16 NodeList=compute-0-1 TimeLimit=01:00:00 RunTime=00:00:01'}
    env={'SLURM_JOB_ID':'9','SLURM_JOB_PARTITION':'cpu','SLURM_CPUS_PER_TASK':'16','CUDA_VISIBLE_DEVICES':''}
    return plan,plan_ref,review,review_ref,proof,env


def limits():
    return {'max_zip_members':8,'max_csv_members':2,'max_total_inflated_bytes':1024**2,'max_columns':16,
        'max_header_name_characters':128,'max_field_characters':4096,'max_physical_line_characters':8192,
        'max_physical_lines_per_record':8,'max_logical_record_characters':16384}


class SecondarySourceBoundaries(unittest.TestCase):
    def test_secondary_identity_rejects_main_uid_and_stale_storage(self):
        plan,pin,review,rr,proof,env=runtime_fixture()
        validate_startup(plan,pin,review,rr,proof,uid=1264,node='compute-0-1',hostname='compute-0-1',env=env,boot_id='boot',now=1001)
        for bad in ('main_uid','main_schema','stale_storage','different_wall'):
            p=copy.deepcopy(proof)
            if bad=='main_uid':p['uid']=1278
            elif bad=='main_schema':p['schema']='FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1'
            elif bad=='stale_storage':p['storage_observation']['observed_unix_seconds']=600
            else:p['job_metadata']=p['job_metadata'].replace('TimeLimit=01:00:00','TimeLimit=01:01:00')
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                validate_startup(plan,pin,review,rr,p,uid=1264,node='compute-0-1',hostname='compute-0-1',env=env,boot_id='boot',now=1001)
        primary=SECONDARY_ROOT/'workflows/expansion/secondary_source_acquisition_v1/run_v1.py'
        wrapper=SECONDARY_ROOT/'workflows/expansion/wrapper.py'
        same_tail=['--plan','/fixture/plan.json','--startup-proof','/fixture/proof.json']
        validate_primary_entry(primary,str(primary),[str(primary),*same_tail])
        for main,argv0 in ((wrapper,primary),(primary,wrapper),(wrapper,wrapper)):
            with self.subTest(main=main,argv0=argv0),self.assertRaisesRegex(ValueError,'MAIN_MODULE_AND_ARGV0'):
                validate_primary_entry(primary,str(main),[str(argv0),*same_tail])
        self.assertEqual(parse_slurm_duration('1-12:00:00'),129600)
        self.assertIsNone(validate_wall_binding(129600,'1-12:00:00'))
        self.assertIsNone(validate_wall_binding(5520,'01:32:00'))
        with self.assertRaisesRegex(ValueError,'WHOLE_SLURM_MINUTES'):
            validate_wall_binding(5500,'01:32:00')
        with self.assertRaisesRegex(ValueError,'TIMELIMIT_DIFFERS'):
            validate_wall_binding(5520,'01:33:00')
    def test_http403_etag_drift_and_unrequested_range_rejected(self):
        source={'expected_content_length':5,'etag':'"multipart-30"','last_modified':'Mon, 01 Oct 2026 00:00:00 GMT','content_type':'application/zip'}
        raw=b'HTTP/1.1 200 Connection established\r\n\r\nHTTP/2 200\r\nContent-Length: 5\r\nETag: "multipart-30"\r\nLast-Modified: Mon, 01 Oct 2026 00:00:00 GMT\r\nContent-Type: application/zip\r\n\r\n'
        blocks=parse_headers(raw);self.assertEqual(validate_response(source,blocks,200,5)['status'],'ACTUAL_FULL_GET_METADATA_VALIDATED')
        for change in ('403','etag','range'):
            b=copy.deepcopy(blocks);status=200
            if change=='403':b[-1]['http_status']=status=403
            elif change=='etag':b[-1]['headers']['etag']=['"different"']
            else:b[-1]['headers']['content-range']=['bytes 0-4/5']
            with self.subTest(change=change),self.assertRaises(ValueError):validate_response(source,b,status,5)
    def test_zip_csv_eof_crc_counts_do_not_prove_inactive_universe(self):
        with tempfile.TemporaryDirectory(prefix='secondary_source_fixture_') as folder:
            path=pathlib.Path(folder)/'fixture.zip'
            with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:z.writestr('coconut.csv','id,status\n1,active\n2,inactive\n')
            result=profile_zip(path,limits(),time.monotonic()+30)
            self.assertTrue(result['all_member_EOF_CRC_observed']);self.assertEqual(result['members'][0]['csv']['logical_data_records_including_blank'],2)
            self.assertFalse(result['inactive_or_deleted_coverage_proven'])
            bad=limits();bad['max_total_inflated_bytes']=2
            with self.assertRaisesRegex(ValueError,'INFLATED_CAP'):profile_zip(path,bad,time.monotonic()+30)
    def test_body_capture_keeps_bounded_partial_and_drains_without_signals(self):
        with tempfile.TemporaryDirectory(prefix='secondary_pipe_fixture_') as folder:
            read,write=os.pipe();path=pathlib.Path(folder)/'body.part';capture=PipeCapture(read,3,path);capture.thread.start()
            os.write(write,b'abcde');os.close(write);capture.thread.join(timeout=5)
            self.assertFalse(capture.thread.is_alive());self.assertIsNone(capture.error)
            self.assertEqual((capture.total,capture.kept,path.read_bytes()),(5,3,b'abc'));self.assertTrue(capture.truncated)
if __name__=='__main__':unittest.main()
