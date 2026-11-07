"""Small metadata and real control32 authority; never login-read task bodies."""
import csv,hashlib,io,json,pathlib
from workflows.data_v1_final.conformers.pm7_population_cache_v1 import metadata as M
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import shared as Q
RUN=Q.ROOT;REPO=Q.REPO;HERE=REPO/'workflows/data_v1_final/conformers/pm7_multinode_compat32_v1'
BASE=RUN/'artifacts/conformers/pm7_multinode_compat32_v1';OLD=M.OLD
FILES=('__init__.py','contract.py','resources.py','compute.py','worker.py','io.py','run.py','materialize.py','test_v1.py','README.md')
CAP=2<<30;PROBE_CAP=16<<20;ADMIN=64<<20;NODE='compute-0-19';ENDPOINT='202.38.247.57:22';UID=1278
SCHEMA='ROOT_PM7_MULTINODE_COMPAT32_PLAN_V1';BINDING='ROOT_PM7_NODE19_COMPAT_RESOURCE_BINDING_V1'
RESOURCE_STATUS='APPROVED_ACTUAL_NODE19_COMPAT32_RESOURCE_ONLY'
OPTIONS=('plan','root-preflight','output');KEY='pm7_multinode_compat32_v1'
need=M.C.need;canonical=M.C.canonical;digest=M.C.digest


def key(mode):need(mode in ('probe','compat32'),'EXACT_INDEPENDENT_QA_MODE');return KEY+'_'+mode


def scope(mode):
    value={'stage':'PM7_NODE19_STORAGE_METADATA_PROBE' if mode=='probe' else 'PM7_NODE19_EXACT32_COMPATIBILITY_CONTROLS',
        'endpoint':ENDPOINT,'uid':UID,'node':NODE,'allocated_cpus':16,'pilot':False,'production_ledger_opened':False,
        'new_population_rows':0,'new_UFF_calls':0,'new_QM_calls':0,'full_release':False,'cost_policy':'REPORT_AND_CONTINUE'}
    if mode=='probe':value.update(canonical_stat_only=True,canonical_body_read=False,marker_metadata_only=True,output_cap_bytes=PROBE_CAP)
    else:value.update(molecules=32,records=203,golden=16,old_pure_methods=17,new_adapter_methods=4,all21_before_DATA=True,
        current_canonical_whole_SHA=True,per_record_native_payload_SHA=True,real_recompute_not_import=True,
        original_kernel_body_inverse_AST_required=True,original_native_reader_graph_RMSD_HOF_orders=True,
        numeric_tolerance_added=False,order_seed=20261025,rmsd_A=0.5,full_graph_stereo_claim=False,
        maximum_workers=16,output_cap_bytes=CAP,effective_disk_soft_stop_bytes=min(8<<30,CAP))
    return value


def reference(value):return M.C.reference(value)
def meta(value):return M.actual(value)
def unique(values):return M.unique(values)


def actual_account(reference,jid,node=NODE,C0=True):
    value=meta(reference);raw=value['raw_sacct_reference'];need(M.pin(raw['path'])==raw,'ACTUAL_STANDARD_ACCOUNT_RAW_PIN')
    rows=[r for r in csv.DictReader(io.StringIO(Q.read_small(raw['path']).decode()),delimiter='|') if r.get('JobIDRaw')==str(jid)]
    need(value['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and value['endpoint']==ENDPOINT and value['uid']==UID
        and value['query_returncode']==0 and len(value['parents'])==len(rows)==1,'ONE_REAL_MAIN_PARENT_ACCOUNTING')
    p=value['parents'][0];r=rows[0];need(p['job_id']==r['JobIDRaw']==str(jid) and p['state']==r['State'].split()[0]
        and p['exit_code']==r['ExitCode'] and p['node']==r['NodeList']==node and r['UID']=='1278'
        and p['alloc_cpus']==int(r['AllocCPUS'])==16 and p['elapsed_raw_seconds']==int(r['ElapsedRaw'])
        and value['allocated_core_seconds']==16*p['elapsed_raw_seconds'],'ACTUAL_NODE_UID_AND_FULL_ELAPSED_COST')
    if C0:need(p['state']=='COMPLETED' and p['exit_code']=='0:0','ACTUAL_C0_REQUIRED_NOT_FUTURE_RESULT')
    return raw


def controls():
    refs={name:M.pin(OLD/path) for name,path in (
        ('prepared','prepared_v1/prepared.json'),('geometry','run_v1/receipt.json'),('hof','hof_augmentation_v1/receipt.json'))}
    p,g,h=(meta(refs[n]) for n in ('prepared','geometry','hof'));base=meta(p['plan_reference']);hp=meta(h['plan_reference'])
    need(p['job_id']=='4521593' and p['status']=='ACTUAL32_FROZEN_NO_GEOMETRY_COMPUTED' and len(p['tasks'])==32
        and len({t['molecule_id'] for t in p['tasks']})==32 and sum(t['golden'] for t in p['tasks'])==16
        and sum(t['software_bound']['records'] for t in p['tasks'])==203,'EXACT_EXISTING32_203_GOLDEN16_NO_NEW_SELECTION')
    need(g['job_id']=='4521602' and g['geometry_complete']==g['completed_packets']==32 and g['golden_geometry_equal_count']==16
        and not g['errors'] and h['job_id']=='4521643' and h['records']==h['valid_hof_records']==203
        and h['complete_molecules']==h['completed_packets']==32 and not h['errors'],'REAL_GEOMETRY32_AND_CANONICAL_HOF32')
    need(set(r['molecule_id'] for r in g['packets'])==set(r['molecule_id'] for r in h['packets'])==set(t['molecule_id'] for t in p['tasks'])
        and hp['geometry_receipt_reference']==refs['geometry'] and hp['prepared_reference']==refs['prepared']
        and hp['source_authority_reference']==p['source_authority_reference'] and hp['hof_mode']=='CANONICAL_VERIFIED',
        'SAME_SOURCE32_NATIVE_IDS_AND_ACTUAL_LATER_CANONICAL_AUTHORITY')
    source=[*refs.values(),p['plan_reference'],h['plan_reference'],p['source_authority_reference'],base['mapping_review'],base['hof_authority_review'],hp['hof_authority_review']]
    data=[]
    for receipt in (p,g,h):
        proof=meta(receipt['startup_proof_reference']);source.extend([receipt['startup_proof_reference'],*proof['request']['source_references']]);data.extend(proof['request']['data_references'])
    for name,jid in (('pm7_cache32_prepare_4521593_v1.json','4521593'),('pm7_cache32_run_4521602_v1.json','4521602'),('pm7_hof_aug32_4521643_v1.json','4521643')):
        r=M.pin(RUN/'control/accounting'/name);source.extend((r,actual_account(r,jid,'compute-0-13')))
    for row in p['tasks']:data.append(row['task_reference'])
    for row in p['golden_packet_references']:data.append(row['reference'])
    for receipt in (g,h):
        for row in receipt['packets']:data.append(row['packet_reference'])
    data.extend((base['formal_source'],base['per_molecule']));source=unique(source);paths={r['path'] for r in source};data=unique(r for r in data if r['path'] not in paths)
    return {'references':refs,'prepared':p,'geometry':g,'hof':h,'base':base,'hof_plan':hp,'source_references':source,'data_references':data}


def package_sources():
    return [M.pin(HERE/n) for n in FILES]


def request_sources(control):return unique([*control['source_references'],*[M.pin(M.C.HERE/n) for n in M.C.FILES],*package_sources()])
