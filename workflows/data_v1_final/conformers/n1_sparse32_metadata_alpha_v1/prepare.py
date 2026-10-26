"""Build an expected Alpha plan/SFTP list from real Main C0 and source metadata."""
from __future__ import annotations
import argparse,csv,hashlib,io,json,os,re,stat
from pathlib import Path,PurePosixPath as P
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.shared import ROOT,REPO,on_login,write_new
from workflows.data_v1_final.conformers.n1_sparse32_metadata_main_v1 import prepare as M

HERE=REPO/'workflows/data_v1_final/conformers/n1_sparse32_metadata_alpha_v1'
ALPHA=P('/gfshome/alpha/codex_data_v1_20261026');MAIN=P('/share/home/zixiao/descriptor_analysis')
EXPORT=P(str(ROOT))/'artifacts/conformers/n1_sparse32_readchain_v1';INPUT=ALPHA/'inputs/n1_sparse32_readchain_v1'
CONSUMER=ALPHA/'code/n1_sparse32_readchain_v1';V14=ALPHA/'code/secondary_cpu_readonly_queue_v14';SMALL=2<<20;CAP=2<<30
MODE='EXACT_CANONICAL32_ORIGINAL_READ_ONLY_CONTROL';READS=[]

def need(value,message):
    if not value:raise ValueError(message)

def triple(value,base=None,small=False):
    need(isinstance(value,dict) and set(value)=={'path','bytes','sha256'} and type(value['bytes']) is int and value['bytes']>=0
        and isinstance(value['sha256'],str) and re.fullmatch('[0-9a-f]{64}',value['sha256']),'EXACT_LITERAL_REFERENCE_TRIPLE')
    path=P(value['path']);need(path.is_absolute() and '..' not in path.parts and (base is None or base in path.parents)
        and (not small or value['bytes']<=SMALL),'EXPLICIT_ENDPOINT_BOUNDED_REFERENCE')
    return dict(value)

def small(path,expected=None):
    path=Path(path);need(path.is_absolute() and '..' not in path.parts and not any(p.is_symlink() for p in (path,*path.parents))
        and path.suffix.lower() in ('.json','.py','.md','.txt','.sbatch','.sh')
        and not any(p in path.parts for p in ('tasks','baselines','baseline','packets','main_signatures')),'SMALL_HEADERS_CODE_ONLY_NO_SCIENTIFIC_BODY')
    with path.open('rb') as stream:
        a=os.fstat(stream.fileno());need(stat.S_ISREG(a.st_mode) and a.st_uid==1278 and a.st_size<=SMALL,'OWN_MAIN_SMALL_METADATA_COPY_ONLY')
        raw=stream.read(SMALL+1);b=os.fstat(stream.fileno())
    frame=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    need(frame(a)==frame(b)==frame(path.stat()) and len(raw)==a.st_size,'SMALL_METADATA_CHANGED')
    ref={'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    if expected is not None:need(ref==expected,'ACTUAL_SMALL_MAIN_SOURCE_COPY_SHA_MISMATCH')
    if ref not in READS:READS.append(ref)
    return raw,ref

def reference(path):return small(path)[1]
def load(path):
    raw,ref=small(path);return json.loads(raw),ref
def load_ref(ref):
    triple(ref,small=True);return json.loads(small(ref['path'],ref)[0])
def same_bytes(a,b):need(all(a[k]==b[k] for k in ('bytes','sha256')),'EXPLICIT_COPY_BYTES_SHA_MUST_MATCH')
def relocated(ref,path):return dict(triple(ref),path=str(path))

def actual_main(manifest,manifest_ref,account,account_ref,params):
    need(manifest.get('schema')=='MAIN_N1_SPARSE32_EXACT_READCHAIN_EXPORT_V1'
        and manifest.get('status')=='ALL32_RAW_KV_EXPORTED_AND_REOPEN_VERIFIED_NO_GENERATION'
        and manifest.get('endpoint')=='202.38.247.57:22' and manifest.get('uid')==1278 and manifest.get('node')=='compute-0-13'
        and manifest.get('scope_key')=='n1_sparse32_readchain_export_v1' and manifest.get('scope_parameters')==params
        and manifest.get('logical_record_count')==manifest.get('unique_molecule_count')==manifest.get('unique_KV_count')==32
        and len(manifest['records'])==32 and manifest.get('complete_field_signatures')==32 and manifest.get('unknown_field_signatures')==0
        and manifest.get('new_UFF_calls')==manifest.get('new_QM_calls')==0 and manifest.get('once_ledger_opened') is False
        and manifest.get('alpha_transfer_verified') is False and manifest['resource_evidence']['stop'] is None,'ACTUAL_COMPLETE_MAIN32_EXPORT_NO_UNKNOWN_OR_GENERATION')
    jid=manifest['job_id'];need(type(jid) is str and jid.isdecimal() and jid not in ('4521417','4521418','1884766','1884768'),'NEW_MAIN_EXPORT_JOB_NOT_CANONICAL_OR_ALPHA_QA')
    need(account.get('schema')=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and account.get('status')=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
        and account.get('query_returncode')==0 and account.get('endpoint')=='202.38.247.57:22' and account.get('uid')==1278,'ACTUAL_MAIN_C0_CLOSURE')
    raw_ref=account['raw_sacct_reference'];raw=small(raw_ref['path'],raw_ref)[0].decode();rows=list(csv.DictReader(io.StringIO(raw),delimiter='|'))
    selected=[r for r in rows if r.get('JobIDRaw',r.get('JobID'))==jid];declared=[r for r in account['parents'] if str(r['job_id'])==jid]
    need(len(selected)==len(declared)==1,'EXACT_MAIN_EXPORT_PARENT_ACCOUNTING_ROW');r=selected[0];d=declared[0]
    need(r['State']=='COMPLETED' and r['ExitCode']=='0:0' and r['AllocCPUS']=='16' and r['UID']=='1278' and r['NodeList']=='compute-0-13'
        and d['state']=='COMPLETED' and d['exit_code']=='0:0' and d['alloc_cpus']==16 and d['elapsed_raw_seconds']==int(r['ElapsedRaw']),
        'ACTUAL_MAIN_EXPORT_C0_CPU16_UID1278_NOT_ALPHA_STARTUP')
    proof_ref=manifest['actual_parent_proof_reference'];proof=load_ref(proof_ref);request_ref=proof['request_reference'];request=load_ref(request_ref)
    script_ref=request['script_reference'];script=small(script_ref['path'],script_ref)[0].decode()
    need(proof.get('schema')=='FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1' and proof.get('uid')==1278 and str(proof.get('job_id'))==jid
        and proof['request']==request and proof['source_references']==request['source_references']==manifest['source_references']
        and proof['script_reference']==script_ref and request['scope_key']=='n1_sparse32_readchain_export_v1'
        and request['scope_parameters']==params and request['kind']=='analysis' and request['pilot'] is False and request['cpus']==16
        and request['node']=='compute-0-13' and request['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED','ACTUAL_MAIN_EXECUTION_SOURCE_AND_REQUEST_CHAIN')
    for line in script.splitlines():
        if line.strip().startswith('#SBATCH'):need(not any(s in line for s in ('--mem','--exclusive','--gres','--gpu')),'MAIN_NO_MEM_NO_GPU_NO_EXCLUSIVE')
    return raw_ref,proof_ref,request_ref,script_ref,request

def installed_sources(install,handoff):
    need(install.get('schema')=='ROOT_ALPHA_SPARSE32_ACTUAL_SOURCE_INSTALL_MAP_V1'
        and install.get('status')=='ACTUAL_ALPHA_SMALL_SOURCE_PINS_VERIFIED' and install.get('reviewer')=='root'
        and install.get('endpoint')=='218.192.171.238:22' and install.get('uid')==1264,'INDEPENDENT_ACTUAL_ALPHA_SOURCE_OBSERVATIONS_REQUIRED')
    observed=[triple(r,ALPHA,True) for r in install['observed_references']];by_path={r['path']:r for r in observed}
    need(len(by_path)==len(observed),'UNIQUE_ACTUAL_ALPHA_OBSERVED_SMALL_SOURCE_PINS')
    handoff_rows={r['name']:r for r in handoff['files']};need(len(handoff_rows)==len(handoff['files'])==11,'EXACT_FROZEN11_HANDOFF')
    expected_code=set()
    for name,row in handoff_rows.items():
        _,current=small(row['expected_Root_reference']['path'],row['expected_Root_reference'])
        need(row['expected_Alpha_reference']['path']==str(CONSUMER/name) and by_path.get(str(CONSUMER/name))==row['expected_Alpha_reference'],
            'ACTUAL_ALPHA_FROZEN_SOURCE_INSTALL_NOT_MAIN_SAME_SHA_ASSUMPTION');same_bytes(current,row['expected_Alpha_reference']);expected_code.add(str(CONSUMER/name))
    root_dirs=[(REPO/'workflows/data_v1_final/execution/secondary_cpu_readonly_queue_v14',V14),
        (REPO/'workflows/data_v1_final/execution/secondary_cpu_queue_v1',ALPHA/'code/secondary_cpu_queue_v1')]
    for origin,target in root_dirs:
        for p in origin.iterdir():
            if p.suffix not in ('.py','.md') or target.name=='secondary_cpu_queue_v1' and p.suffix!='.py':continue
            _,current=small(p);wanted=relocated(current,target/p.name)
            need(by_path.get(wanted['path'])==wanted,'ACTUAL_ALPHA_V14_AND_BASE_RUNTIME_SOURCE_INSTALL_REQUIRED')
            expected_code.add(wanted['path'])
    named=install['references'];names={'resource_authority_reference','cost_decision_reference','source_handoff_reference','controller_source_review_reference','storage_scope_reference'}
    need(set(named)==names and all(by_path.get(r['path'])==triple(r,ALPHA,True) for r in named.values()),'EXACT_FIVE_OBSERVED_NAMED_ALPHA_AUTHORITIES')
    need(set(by_path)==expected_code|{r['path'] for r in named.values()},'INSTALL_MAP_ONLY_EXACT_CODE_AND_FIVE_AUTHORITY_SOURCES_NO_PAYLOAD')
    need(named['storage_scope_reference']['path']==str(ALPHA/'control/secondary_cpu_queue/storage_scope_v7_pubchem_uniform_index_copy_v1.json'),'EXACT_STORAGE_SCOPE7')
    return observed,named

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--approve',action='store_true',required=True);p.add_argument('--reason',required=True)
    for name in ('main-manifest','accounting','source-install-map','source-install-map-alpha-path','metadata-output','alpha-metadata-root','alpha-output','alpha-startup-proof'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--alpha-node',required=True);p.add_argument('--alpha-python',required=True);p.add_argument('--wall-seconds',type=int,default=3600)
    p.add_argument('--source-handoff',type=Path,default=REPO/'docs/data_v1/n1_sparse32_readchain_v1_source_handoff.json')
    a=p.parse_args();on_login();need(Path(__file__).absolute().parent==HERE,'ACTUAL_ROOT_ALPHA_METADATA_BUILDER')
    need(a.approve and a.reason.strip() and len(a.reason.encode())<=8192,'EXPLICIT_EXACT_ROOT_APPROVAL_REASON')
    need(120<a.wall_seconds<=3600 and a.wall_seconds%60==0,'WHOLE_MINUTE_READ_ONLY_ONE_HOUR_BOUND')
    need(a.alpha_node in {'compute-0-1','compute-0-3','compute-0-4','compute-0-5','compute-0-6','sonmi1'},'ACTUAL_ALLOWED_ALPHA_CPU_NODE')
    output=Path(a.metadata_output);need(output.is_absolute() and ROOT/'control' in output.parents and '..' not in output.parts
        and not any(p.is_symlink() for p in (output,*output.parents)) and not output.exists(),'FRESH_MAIN_METADATA_OUTPUT_ONLY')
    alpha_meta=P(str(a.alpha_metadata_root));alpha_out=P(str(a.alpha_output));alpha_proof=P(str(a.alpha_startup_proof));alpha_install=P(str(a.source_install_map_alpha_path))
    for value in (alpha_meta,alpha_out,alpha_proof,alpha_install,P(a.alpha_python)):
        need(value.is_absolute() and '..' not in value.parts and ALPHA in value.parents,'EXPLICIT_ALPHA_LOCATOR_NOT_LOCAL_PATH_CHECK')
    need(ALPHA/'control/readonly_specs' in alpha_meta.parents and ALPHA/'artifacts/n1_sparse32_readchain_v1' in alpha_out.parents
        and ALPHA/'control/secondary_startup' in alpha_proof.parents,'EXACT_NEW_ALPHA_METADATA_OUTPUT_AND_PROOF_PREFIXES')
    handoff,handoff_ref=load(a.source_handoff);install,install_ref=load(a.source_install_map);observed,named=installed_sources(install,handoff)
    same_bytes(handoff_ref,named['source_handoff_reference'])
    values=M.constants(REPO/'workflows/data_v1_final/conformers/n1_sparse32_readchain_v1/guard.py',{'PARAMETERS'});params=values['PARAMETERS']
    manifest,manifest_ref=load(a.main_manifest);account,account_ref=load(a.accounting)
    triple(manifest_ref,EXPORT,True);raw_ref,proof_ref,request_ref,script_ref,request=actual_main(manifest,manifest_ref,account,account_ref,params)
    for row in handoff['files']:need(row['expected_Root_reference'] in request['source_references'],'ACTUAL_MAIN_C0_EXECUTED_FROZEN11')
    output.mkdir(parents=True,exist_ok=False,mode=0o700);pairs=[];data=[]
    def pair(kind,origin,target,body=False):
        origin=triple(origin,MAIN);target=triple(target,ALPHA);same_bytes(origin,target)
        row={'kind':kind,'origin_reference':origin,'target_locator':target};pairs.append(row)
        if body:data.append(target)
        return target
    for db in manifest['databases']:
        need(db['all_original_KV_bytes_equal_after_reopen'] is True and db['original_whole_LMDB_SHA256'] is None,'ACTUAL_NEW_DB_SHA_AND_REOPEN_NOT_ORIGINAL715GB_HASH')
        pair('sparse_lmdb',db['reference'],db['alpha_target_locator'],True)
    for row in manifest['records']:
        need(row['main_sparse_original_reader_comparison']=='EXACT_TYPED_FIELD_BITS_MATCH','NO_FIELD_UNKNOWN_SILENTLY_RELEASED')
        for kind,old,new in (('original_task','main_task_copy_reference','alpha_task_reference'),('original_baseline','main_baseline_copy_reference','alpha_baseline_reference'),
            ('main_signature','main_signature_reference','alpha_signature_reference')):pair(kind,row[old],row[new],True)
    need(data==manifest['alpha_data_references'] and len(data)==len(manifest['databases'])+96
        and len({r['path'] for r in data})==len(data) and sum(r['bytes'] for r in data)==manifest['alpha_expected_input_bytes']<=CAP,'ACTUAL_PRODUCER_TRANSFER_INVENTORY')
    for row in manifest['science_source_copies']:pair('frozen_'+row['name'],row['main_copy_reference'],row['alpha_target_locator'])
    pair('original_recipe',manifest['original_recipe_copy_reference'],manifest['alpha_original_recipe_reference'])
    pair('relocated_recipe',manifest['alpha_recipe_copy_reference'],manifest['alpha_recipe_reference'])
    parent_names=[('Main_export_manifest',manifest_ref,'input_manifest_reference','Main_manifest.json'),
        ('Main_export_accounting',account_ref,'main_export_accounting_reference','Main_accounting.json'),
        ('Main_export_raw_sacct',raw_ref,'main_export_raw_sacct_reference','Main_sacct.txt'),
        ('Main_export_startup_proof',proof_ref,'main_export_startup_proof_reference','Main_startup_proof.json'),
        ('Main_export_request',request_ref,'main_export_request_reference','Main_request.json'),
        ('Main_export_script',script_ref,'main_export_script_reference','Main_script.sbatch')]
    parents={key:pair(kind,origin,relocated(origin,alpha_meta/name)) for kind,origin,key,name in parent_names}
    need(len(pairs)==len(manifest['databases'])+107 and len({r['origin_reference']['path'] for r in pairs})==len(pairs)
        and len({r['target_locator']['path'] for r in pairs})==len(pairs),'EXACT_G_PLUS107_ROOT_COPY_RELOCATION_NO_ALIAS')
    relocation={'schema':'ROOT_MAIN_SPARSE32_ALPHA_COPY_RELOCATION_V1','status':'ROOT_REVIEWED_EXPECTED_LOCATORS_NOT_BODY_HASH_ACCEPTANCE','reviewer':'root',
        'source_endpoint':'202.38.247.57:22','target_endpoint':'218.192.171.238:22','Main_export_manifest_origin_reference':manifest_ref,
        'Alpha_manifest_copy_reference':parents['input_manifest_reference'],'Alpha_body_hash_acceptance_claimed':False,'entries':pairs}
    relocation_ref=write_new(output/'copy_relocation.json',relocation);alpha_relocation=relocated(relocation_ref,alpha_meta/'copy_relocation.json')
    sources={r['path']:r for r in [*observed,relocated(install_ref,alpha_install),alpha_relocation,*parents.values()]}
    for row in pairs:
        if row['target_locator'] not in data:sources[row['target_locator']['path']]=row['target_locator']
    need(not {r['path'] for r in data}.intersection(sources),'BODY_DATA_MUST_NOT_BECOME_PRE_FIXTURE_SOURCE')
    alpha_plan=alpha_meta/'plan.json';argv=[a.alpha_python,'-B','-m','n1_sparse32_readchain_v1.alpha_read','--plan',str(alpha_plan),'--startup-proof',str(alpha_proof)]
    plan={'schema':'SECONDARY_N1_SPARSE32_READCHAIN_PLAN_V1','scope_key':'n1_sparse32_readchain_alpha_v1','producer_key':'n1_sparse32_readchain_alpha_v1',
        'scope_parameters':params,'stage':'READ_ORIGINAL_LMDB_VALUES_FIELD_GRAPH_CONTROL32','endpoint':'218.192.171.238:22','uid':1264,
        'run_root':str(ALPHA),'node':a.alpha_node,'python':a.alpha_python,'kind':'analysis','pilot':False,'cpus':16,
        'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','wall_seconds':a.wall_seconds,'output_cap_bytes':CAP,'output_directory':str(alpha_out),
        'startup_proof_path':str(alpha_proof),'execution_argv':argv,'scope_mode':MODE,'performance_profile':False,
        'source_references':list(sources.values()),'data_references':data,'parent_evidence_references':list(parents.values()),
        'origin_manifest_reference':manifest_ref,'main_export_accounting_origin_reference':account_ref,**parents,
        'science_sources':manifest['alpha_science_sources'],'recipe_reference':manifest['alpha_recipe_reference'],
        'original_recipe_reference':manifest['alpha_original_recipe_reference'],'resource_authority_reference':named['resource_authority_reference'],
        'cost_decision_reference':named['cost_decision_reference'],'source_handoff_reference':named['source_handoff_reference'],
        'copy_relocation_reference':alpha_relocation,'source_install_map_reference':relocated(install_ref,alpha_install),
        'transfer_verification_reference':None,'transfer_verification_expected_output_path':str(alpha_out/'transfer_verification.json')}
    review_keys=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','kind','pilot','wall_seconds',
        'output_cap_bytes','output_directory','execution_argv','data_references','parent_evidence_references','scope_mode','performance_profile')
    root_review={k:plan[k] for k in review_keys};root_review.update(schema='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1',status='APPROVED_FOR_EXACT_STAGE',reviewer='root',
        approved_source_references=plan['source_references'],root_review_reason=a.reason.strip(),explicit_Root_approve_argument=True,
        new_UFF_QM_calls=0,once_ledger_opened=False,dataset_membership=False,Alpha_body_transfer_or_read_acceptance_claimed=False)
    review_ref=write_new(output/'root_review.json',root_review);plan['root_review_reference']=relocated(review_ref,alpha_meta/'root_review.json')
    plan_ref=write_new(output/'plan.json',plan)
    transfer=[dict(row,expected_role='CPU_BODY_AFTER_SIX_FIXTURES' if row['target_locator'] in data else 'SMALL_SOURCE_OR_PARENT_METADATA') for row in pairs]
    for kind,origin,target in (('new_copy_relocation',relocation_ref,alpha_relocation),('new_Root_review',review_ref,plan['root_review_reference']),('new_Alpha_plan',plan_ref,relocated(plan_ref,alpha_plan))):
        transfer.append({'kind':kind,'origin_reference':origin,'target_locator':target,'expected_role':'NEW_EXPECTED_ONLY_SMALL_METADATA'})
    sftp_ref=write_new(output/'sftp_inventory.json',{'schema':'ROOT_SPARSE32_ALPHA_EXPECTED_SFTP_INVENTORY_V1',
        'status':'EXPECTED_ONLY_ACTUAL_MAIN_SOURCE_PINS_NOT_ALPHA_TRANSFER_ACCEPTANCE','source_endpoint':'202.38.247.57:22','target_endpoint':'218.192.171.238:22',
        'Main_export_job_id':manifest['job_id'],'Main_export_manifest_reference':manifest_ref,'data_files':len(data),'data_bytes':sum(r['bytes'] for r in data),
        'copy_relocation_entries':len(pairs),'entries':transfer,'total_expected_transfer_bytes':sum(r['origin_reference']['bytes'] for r in transfer),
        'actual_Alpha_source_install_map_Main_copy_reference':install_ref,'actual_Alpha_source_install_map_locator':relocated(install_ref,alpha_install),
        'already_installed_sources_are_not_future_body_hash_acceptance':True,'automatic_transfer_or_submit':False,'future_hash_receipt_reference':None})
    command=[a.alpha_python,'-B','-m','secondary_cpu_readonly_queue_v14.controller','submit','--producer','readonly','--input',str(alpha_plan),
        '--authority',named['resource_authority_reference']['path'],'--storage-review',named['storage_scope_reference']['path'],
        '--controller-review',named['controller_source_review_reference']['path'],'--output','__ROOT_CHOSEN_NEW_ALPHA_QUEUE_DIRECTORY__',
        '--node',a.alpha_node,'--job-name','__ROOT_CHOSEN_NEW_JOB_NAME__','--reviewer','root','--wall-seconds',str(a.wall_seconds)]
    handoff_out=write_new(output/'metadata_handoff.json',{'schema':'ROOT_SPARSE32_EXPECTED_ALPHA_METADATA_HANDOFF_V1',
        'status':'EXPECTED_ONLY_NOT_TRANSFERRED_NOT_PREPARED_NOT_SUBMITTED','plan':plan_ref,'Root_review':review_ref,'copy_relocation':relocation_ref,'SFTP_inventory':sftp_ref,
        'actual_Main_metadata_read':READS,'source_install_map_Main_copy_reference':install_ref,'actual_Main_C0_job_id':manifest['job_id'],
        'after_actual_SFTP_Root_review_controller_argv_template':command,'scientific_body_open_or_hash':False,'new_UFF_QM_calls':0,'once_ledger_opened':False,
        'Alpha_body_installed_or_verified_claimed':False,'old_Main_or_Alpha_QA_proof_reused_as_new_startup':False})
    print(json.dumps({'plan':plan_ref,'Root_review':review_ref,'copy_relocation':relocation_ref,'SFTP_inventory':sftp_ref,'metadata_handoff':handoff_out,
        'expected_data_files':len(data),'expected_data_bytes':sum(r['bytes'] for r in data),'submitted':False,'body_read':False}))

if __name__=='__main__':main()
