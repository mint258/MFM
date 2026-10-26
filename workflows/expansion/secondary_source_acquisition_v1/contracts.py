"""Independent alpha-cluster source acquisition contracts; stdlib only."""
from __future__ import annotations
import hashlib,json,os,pathlib,re,socket,time,urllib.parse
SECONDARY_ROOT=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026')
ENDPOINT='218.192.171.238:22';UID=1264;SMALL=2*1024**2
ALLOWED_NODES={'compute-0-1','compute-0-3','compute-0-4','compute-0-5','compute-0-6','sonmi1'}


def need(ok,message):
    if not ok:raise ValueError(message)


def read_small(path):
    path=pathlib.Path(path)
    need(path.is_absolute() and '..' not in path.parts and path.is_file() and not path.is_symlink(),'LITERAL_SMALL_FILE_REQUIRED')
    with path.open('rb') as f:
        a=os.fstat(f.fileno());need(a.st_size<=SMALL,'SMALL_METADATA_LIMIT')
        raw=f.read(SMALL+1);b=os.fstat(f.fileno())
    need(len(raw)==a.st_size and (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns),'SMALL_FILE_CHANGED')
    return raw


def pin(path,*,small=True):
    path=pathlib.Path(path)
    if small:raw=read_small(path);return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    h=hashlib.sha256()
    with path.open('rb') as f:
        a=os.fstat(f.fileno())
        for block in iter(lambda:f.read(1024**2),b''):h.update(block)
        b=os.fstat(f.fileno())
    need((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns),'PAYLOAD_CHANGED_DURING_SHA')
    return {'path':str(path),'bytes':a.st_size,'sha256':h.hexdigest()}


def load(path):return json.loads(read_small(path))
def clean_ref(value):return {key:value[key] for key in ('path','bytes','sha256')}
def verify(reference):need(pin(reference['path'])==clean_ref(reference),'SMALL_DEPLOYED_REFERENCE_CHANGED');return pathlib.Path(reference['path'])


def write_new(path,obj,cap=SMALL):
    raw=(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    need(len(raw)<=cap,'SMALL_OUTPUT_LIMIT')
    with pathlib.Path(path).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())


def source_from_head(value,source_id):
    need(value['source_id']==source_id and value['method']=='HEAD' and value['outcome']=='HEAD_OBSERVED' and value['http_status']==200,'ACTUAL_SUCCESSFUL_HEAD_REQUIRED')
    need(value['physical_sha256'] is None and value['record_count'] is None and value['release_version_proven'] is False,'HEAD_IS_NOT_A_RELEASE_OR_SHA_PIN')
    url=value['candidate']['url'];final=value['final_url']['url'];parsed=urllib.parse.urlsplit(url)
    need(url==final and parsed.scheme=='https' and parsed.hostname=='coconut.s3.uni-jena.de'
         and parsed.username is None and parsed.password is None and not parsed.query and not parsed.fragment,'EXACT_OFFICIAL_COCONUT_HTTPS_LOCATOR_REQUIRED')
    need(hashlib.sha256(url.encode()).hexdigest()==value['candidate']['unredacted_url_sha256'],'ACTUAL_URL_DIGEST_REQUIRED')
    block=value['redirect_chain'][-1]['http_blocks'][-1]
    need(block['http_status']==200 and block['content_length_state']=='CONSISTENT_DECIMAL','ACTUAL_FINAL_HEAD_LENGTH_REQUIRED')
    def header(key):
        rows=block['headers'].get(key,[])
        need(len(rows)==1 and rows[0]['truncated'] is False,'EXACT_SINGLE_HEAD_HEADER_REQUIRED:'+key)
        text=rows[0]['value'];need(hashlib.sha256(text.encode()).hexdigest()==rows[0]['full_value_sha256'],'HEAD_HEADER_VALUE_DIGEST_REQUIRED')
        return text
    length=int(header('content-length'));need(length==block['content_length_bytes'] and length>0,'HEAD_LENGTH_INCONSISTENT')
    result={'source_id':source_id,'url':url,'expected_content_length':length,'etag':header('etag'),
        'last_modified':header('last-modified'),'content_type':header('content-type'),
        'official_text_reference':value['official_text_reference'],'locator_semantics':value['locator_semantics'],
        'etag_is_physical_sha256':False,'month_is_immutable_release_pin':False,'inactive_coverage_proven':False}
    if source_id=='coconut_csv_full':need(result['content_type']=='application/zip' and url.endswith('.zip'),'CSV_FULL_IS_ZIP_REQUIRED')
    if source_id=='coconut_sql':need(result['content_type']=='application/sql' and url.endswith('.sql'),'SQL_IS_PLAIN_APPLICATION_SQL_REQUIRED')
    return result


def validate_alpha_authority(authority):
    need(authority['schema']=='USER_AUTHORIZED_SECONDARY_DATA_CLUSTER_V1' and authority['status']=='USER_AUTHORIZED'
        and authority['endpoint']==ENDPOINT and authority['username']=='alpha' and authority['observed_uid']==UID
        and pathlib.Path(authority['run_root'])==SECONDARY_ROOT,'EXACT_ALPHA_AUTHORITY_REQUIRED')
    need(set(authority['actual_cpu_nodes'])==ALLOWED_NODES and authority['cpus_per_task']==16 and authority['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
        and authority['no_gpu'] and authority['no_exclusive'] and authority['scientific_parameters_and_quality_gates_unchanged'],'ACTUAL_SECONDARY_CPU_AUTHORITY_REQUIRED')


def parse_slurm_duration(value):
    match=re.fullmatch(r'(?:(\d+)-)?(\d+):([0-5]\d):([0-5]\d)',value)
    need(match is not None,'FINITE_SLURM_DAYS_HMS_DURATION_REQUIRED')
    day,hour,minute,second=match.groups()
    need(day is None or int(hour)<24,'SLURM_DAY_HOUR_OUT_OF_RANGE')
    return int(day or 0)*86400+int(hour)*3600+int(minute)*60+int(second)


def validate_wall_binding(wall_seconds,actual_time_limit):
    need(type(wall_seconds) is int and 0<wall_seconds<=172800 and wall_seconds%60==0,
        'EXACT_WALL_REQUIRES_WHOLE_SLURM_MINUTES_WITHIN48H')
    need(parse_slurm_duration(actual_time_limit)==wall_seconds,'ACTUAL_SLURM_TIMELIMIT_DIFFERS_FROM_EXACT_PLAN_WALL')


def validate_primary_entry(actual_source,main_source,argv):
    expected=SECONDARY_ROOT/'workflows/expansion/secondary_source_acquisition_v1/run_v1.py'
    need(pathlib.Path(actual_source).absolute()==expected and main_source is not None
        and pathlib.Path(main_source).absolute()==expected and bool(argv)
        and pathlib.Path(argv[0]).absolute()==expected,'ACTUAL_MAIN_MODULE_AND_ARGV0_MUST_BE_PRIMARY_RUN_SOURCE')


def validate_startup(plan,plan_ref,review,review_ref,proof,*,uid,node,hostname,env,boot_id,now):
    need(plan['schema']=='SECONDARY_COCONUT_ACQUISITION_PLAN_V1' and plan['endpoint']==ENDPOINT and plan['uid']==UID
        and plan['run_root']==str(SECONDARY_ROOT),'NO_MAIN_CLUSTER_PLAN_REUSE')
    need(review['schema']=='EXACT_SECONDARY_SOURCE_ROOT_REVIEW_V1' and review['status']=='APPROVED_FOR_EXACT_STAGE' and review['reviewer']=='root','INDEPENDENT_ROOT_REVIEW_REQUIRED')
    for key in ('stage','source','scope_parameters','wall_seconds','output_cap_bytes','endpoint','uid','run_root','execution_argv','parent_evidence_references'):
        need(review[key]==plan[key],'EXACT_ROOT_REVIEW_FIELD_DIFFERS:'+key)
    need(review['approved_source_references']==[r for r in plan['source_references'] if r!=plan['root_review_reference']],
        'EXACT_REVIEWED_DEPLOYED_CODE_AND_METADATA_REQUIRED')
    need(proof['schema']=='SECONDARY_SOURCE_ACQUISITION_STARTUP_V1' and proof['endpoint']==ENDPOINT and proof['uid']==uid==UID
        and proof['node']==node==plan['node'] and node in ALLOWED_NODES and proof['hostname']==hostname and proof['boot_id']==boot_id,'ACTUAL_ALPHA_RUNTIME_IDENTITY_REQUIRED')
    need(proof['plan_reference']==plan_ref and proof['root_review_reference']==review_ref,'CURRENT_PLAN_REVIEW_STARTUP_BINDING_REQUIRED')
    need(env.get('SLURM_JOB_ID','').isdecimal() and proof['job_id']==env['SLURM_JOB_ID'] and env.get('SLURM_JOB_PARTITION')=='cpu'
        and env.get('SLURM_CPUS_PER_TASK')=='16' and env.get('CUDA_VISIBLE_DEVICES')=='','ACTUAL_SECONDARY_SLURM_CPU16_REQUIRED')
    need(proof['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and proof['memory_limits_requested'] is False and proof['exclusive_requested'] is False,'NO_EXPLICIT_MEMORY_OR_EXCLUSIVE_REQUEST')
    need(0<=now-proof['observed_unix_seconds']<=300,'FRESH_SECONDARY_STARTUP_REQUIRED')
    storage=proof['storage_observation']
    need(type(storage['effective_free_bytes']) is int and storage['effective_free_bytes']-plan['output_cap_bytes']>=200000000000
        and bool(storage['effective_free_basis']) and storage['evidence_references'],'EFFECTIVE_FREE_AND200GB_RESERVE_REQUIRED')
    need(0<=now-storage['observed_unix_seconds']<=300,'FRESH_EFFECTIVE_STORAGE_OBSERVATION_REQUIRED')
    raw=proof['job_metadata']
    for key,expected in (('JobId',proof['job_id']),('JobState','RUNNING'),('Partition','cpu'),('NumCPUs','16'),('NodeList',node)):
        found=re.findall(r'(?:^|\s)'+key+r'=([^\s]+)',raw);need(found==[expected],'ACTUAL_JOB_METADATA_DIFFERS:'+key)
    need(re.findall(r'(?:^|\s)UserId=([^\s]+)',raw)==['alpha(1264)'],'ACTUAL_ALPHA_SLURM_OWNER_REQUIRED')
    actual_limits=re.findall(r'(?:^|\s)TimeLimit=([^\s]+)',raw)
    need(len(actual_limits)==1,'ACTUAL_UNIQUE_SLURM_TIMELIMIT_REQUIRED')
    validate_wall_binding(plan['wall_seconds'],actual_limits[0])
    if plan['stage']=='CSV_ZIP_PROFILE':
        need(plan['source']['source_id']=='coconut_csv_full' and plan['wall_seconds']<=3600 and plan['output_cap_bytes']<=1024**3,'BOUNDED_CSV_PROFILE_ONLY')
    else:
        need(plan['stage']=='PLAIN_SQL_FULL_DOWNLOAD' and plan['source']['source_id']=='coconut_sql'
            and review.get('actual_profile_and_cost_reviewed') is True and plan.get('accepted_profile_reference') in plan['parent_evidence_references'],
            'SQL_REQUIRES_SEPARATE_ACTUAL_PROFILE_COST_REVIEW')
    need(plan['source']['expected_content_length']+64*1024**2<=plan['output_cap_bytes'],'WHOLE_STORAGE_CAP_MUST_COVER_SOURCE_AND_METADATA')
    need(plan['scope_parameters']['expected_raw_bytes']==plan['source']['expected_content_length'],'EXACT_RAW_SOURCE_BYTE_SCOPE_REQUIRED')
    need(plan['scope_parameters']['network_workers']==1 and plan['scope_parameters']['maximum_host_concurrency']==2
        and plan['scope_parameters']['range_requests_authorized'] is False,'SINGLE_FULL_GET_NO_AUTOMATIC_RANGE_OR_RETRY')
