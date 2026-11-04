"""Actual closed producer headers and opaque same-byte transfers; no body reads."""
import os,re,stat,sys
from pathlib import Path
from workflows.expansion.marcel_drugs_decontamination_main_v1 import contract as D
from workflows.expansion.local6_tdc_decontamination_day_v1 import contract as L
from workflows.expansion.tdc_zip44_identity_main_v1.contract import FROZEN
Q=D.Q;need=Q.need;meta=D.meta;reference=D.data_reference;unique=D.unique
HERE=Q.REPO/'workflows/expansion/moleculenet17_decontamination_day_v1'
KEY='moleculenet17_decontamination_day_v1';MODULE='workflows.expansion.moleculenet17_decontamination_day_v1.run'
FILES=('__init__.py','contract.py','atoms.py','projection.py','acquisition.py','runtime.py','run.py','materialize.py','test_v1.py','README.md')
NAMES=('BACE','BBBP','ClinTox','ESOL','FreeSolv','HIV','Lipophilicity','MUV','PCBA','PDBbind','QM7','QM7b','QM8','QM9','SIDER','Tox21','ToxCast')
LOCAL={'moleculenet_bace':('BACE',1513),'moleculenet_bbbp':('BBBP',2050),'moleculenet_clintox':('ClinTox',1484),
 'moleculenet_esol':('ESOL',1128),'moleculenet_freesolv':('FreeSolv',642),'moleculenet_lipophilicity':('Lipophilicity',4200)}
CSV={'hiv':('HIV',82255),'muv':('MUV',186175),'pcba':('PCBA',875859),'sider':('SIDER',1427),'tox21':('Tox21',7831),'toxcast':('ToxCast',8597)}
IDS={'qm8_sdf':21786,'pdbbind_core':193,'pdbbind_general':17679,'pdbbind_refined':4852}
PARAMS={'sanitize':False,'removeHs':False,'parseName':False,'allowCXSMILES':False,'strictCXSMILES':True,'debugParse':False}
WALL=86400;CAP=16<<30
PARAMETERS={'all17_subdatasets':list(NAMES),'all_original_splits_roles_and_variants':True,'no_Common_or_training_population_filter':True,
 'local6_rows':11017,'csv6_physical_records':1162144,'native_physical_SDF':39633,'native_context_records':57480,'native_index_records':44510,
 'PDB_original_missing_context':27,'missing27_not_general12119_graph_unknown':True,'existing39633_graphs_reparsed':False,
 'true_empty_record_requires_exact_span_SHA_no_ID_or_other_fields':True,'short_row_is_not_empty_or_rejected':True,
 'original_identity_keys_and_native_composition':True,'atoms_only_original_function_inverse':True,'RDKit':'2025.09.5',
 'bounded_official27_acquisition_in_same_parent':True,'unmatched_ligand_or_unknown_composition_is_HOLD':True,
 'old_unknown_graph_cause_or_native_split_not_repaired':True,'new_QM_UFF_calls':0,'workers_max':16,'pending_max':32,
 'actual_cpus':16,'wall_seconds':WALL,'output_cap_bytes':CAP,'global_exclusion_pool_training_release':False}

def triple(value):
    need(type(value)is dict and set(value)=={'path','bytes','sha256'} and type(value['path'])is str and Path(value['path']).is_absolute()
      and '..' not in Path(value['path']).parts and type(value['bytes'])is int and value['bytes']>0
      and type(value['sha256'])is str and re.fullmatch('[0-9a-f]{64}',value['sha256']) is not None,'EXACT_POSITIVE_FOREIGN_OR_MAIN_PRODUCER_TRIPLE')
    return value

def alias(context,origin):
    triple(origin);rows=[r for r in context['opaque_transfers'] if r['origin_reference']==origin]
    if origin['path'].startswith(str(Q.ROOT)+'/'):return origin
    need(len(rows)==1,'EXACT_FOREIGN_PRODUCER_OPAQUE_TRANSFER_REQUIRED')
    value=triple(rows[0]['Main_reference']);need(Q.ROOT in Path(value['path']).parents and value['bytes']==origin['bytes'] and value['sha256']==origin['sha256'],
      'OPAQUE_COPY_BYTES_SHA_MUST_EQUAL_ACTUAL_PRODUCER');return value

def header(context,origin):return meta(alias(context,origin))

def closed(context,name,jid,uid):
    p=context['closed_parents'][name];r=meta(p['receipt_reference']);proof=meta(p['startup_proof_reference']);a=meta(p['accounting_reference'])
    need(str(r['job_id'])==str(proof['job_id'])==str(jid) and r['uid']==uid and proof['uid']==uid,'ACTUAL_PRODUCER_IDENTITY_NOT_FUTURE')
    need(alias(context,r.get('startup_proof_reference',r.get('startup_proof')))==p['startup_proof_reference'],
      'EXACT_RECEIPT_PROOF_BINDING')
    original_plan=r.get('plan_reference',r.get('plan'));plan=header(context,original_plan)
    if 'plan_reference' in proof:
        argv=proof['request']['execution_argv']
        need(proof['plan_reference']==original_plan and proof['scope_key']==plan['scope_key']
          and r['scope_parameters']==plan['scope_parameters'] and '--plan' in argv and argv[argv.index('--plan')+1]==original_plan['path'],
          'EXACT_ALPHA_PLAN_SCOPE_PROOF_ORIGINAL_FIELDS_NOT_INVENTED_TOPLEVEL_PARAMETERS')
    else:
        request=proof['request'];argv=request['execution_argv']
        need(meta(proof['request_reference'])==request and proof['execution_admission_granted'] is True
          and original_plan in request['source_references'] and '--plan' in argv and argv[argv.index('--plan')+1]==original_plan['path'],
          'EXACT_ORIGINAL_MAIN_PLAN_FULL_ARGV_SOURCE')
    raw=Q.read_small(p['raw_accounting_reference']['path']);need(Q.pin(p['raw_accounting_reference']['path'])==p['raw_accounting_reference'],'RAW_ACCOUNTING_PIN')
    if a.get('schema')=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1':
        rows=[x for x in a['parents'] if str(x['job_id'])==str(jid)]
        endpoint='202.38.247.57:22' if uid==1278 else '218.192.171.238:22'
        need(a['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED' and a['uid']==uid and a['endpoint']==endpoint and a['query_returncode']==0
          and alias(context,a['raw_sacct_reference'])==p['raw_accounting_reference'] and len(rows)==1
          and rows[0]['state']=='COMPLETED' and rows[0]['exit_code']=='0:0' and rows[0]['alloc_cpus']==16,
          'ACTUAL_STANDARD_ORIGINAL_ENDPOINT_UID16_C0_PARENT_NOT_MAIN_ALIAS')
    else:
        row=a['actual_parent'];need(uid==1264 and row['JobIDRaw']==str(jid) and row['UID']=='1264' and row['State']=='COMPLETED' and row['ExitCode']=='0:0'
          and alias(context,a['raw_sacct_reference'])==p['raw_accounting_reference'],'ALPHA_ACTUAL_C0_PARENT_NO_UID_ALIAS')
    lines=raw.decode('utf-8-sig').splitlines();keys=lines[0].split('|');rows=[dict(zip(keys,v.split('|'))) for v in lines[1:] if v.split('|')[0]==str(jid)]
    need(len(rows)==1 and rows[0]['UID']==str(uid) and rows[0]['State']=='COMPLETED' and rows[0]['ExitCode']=='0:0','ACTUAL_RAW_C0_ROW')
    return r

def inputs(context):
    need(context['schema']=='ROOT_MOLECULENET17_CLOSED_INPUT_CONTEXT_V1' and context['status']=='ACTUAL_CLOSED_HEADERS_AND_OPAQUE_LOCATORS_NOT_READY'
      and context['all17_subdatasets']==list(NAMES),'REAL_COMPLETE17_INPUT_CONTEXT_NO_SCIENTIFIC_ACCEPTANCE')
    registry=meta(context['partial9_registry_reference']);entries={r['dataset']:r for r in registry['sources']}
    need(registry['all11_source_complete'] is False and entries['moleculenet']['required_subdatasets']==list(NAMES),'ORIGINAL_COMPLETE17_POLICY')
    for relative,(size,sha) in FROZEN.items():
        ref=Q.pin(Q.REPO/relative);need(ref['bytes']==size and ref['sha256']==sha,'EXACT_FROZEN_ORIGINAL_IDENTITY_FUNCTION_SOURCE')
    local=closed(context,'local','4521192',1278)
    need(local['schema']=='FULL_IDENTITY_READONLY_CLOSURE_RECEIPT_V1' and len(local['closed_units'])==404,'ORIGINAL404_CLOSED_LOCAL_POPULATION')
    originals={v['unit_id']:v['file'] for v in local['closed_units']};units=context['local6_original_units'];counts={d:0 for d in LOCAL};data=[]
    for u in units:
        need(u['unit_id'] in originals and u['file']==originals[u['unit_id']],'LOCAL_UNIT_IS_ACTUAL_CLOSED_PRODUCER')
        receipt=meta(u['receipt_reference']);need(receipt['file']==u['file'] and receipt['unit_id']==u['unit_id'] and receipt['datasets']==u['datasets'],'LOCAL_UNIT_SMALL_CENSUS')
        need(any(d in LOCAL for d in u['datasets']),'ONLY_UNITS_WITH_NEEDED_LOCAL6_RECORDS')
        for d in LOCAL:counts[d]+=u['datasets'].get(d,0)
        data.append(reference(u['file']))
    need(counts=={d:v[1] for d,v in LOCAL.items()} and len({u['unit_id'] for u in units})==len(units),'ALL11017_LOCAL6_ROWS_ONCE')
    csv=closed(context,'csv6','1884803',1264)
    need(csv['schema']=='MOLECULENET_CSV6_IDENTITY_RECEIPT_V1' and csv['status']=='SIX_CSV_FULL_PHYSICAL_IDENTITY_OBSERVATIONS_COMPLETE'
      and csv['mode']=='full' and csv['observed_rows']==1162144 and csv['full_payload_sha_crc_eof_reverified'] is True
      and csv['pipeline']['technical_execution_error_count']==0,'ACTUAL_FULLCSV6_NOT_PROFILE_OR_ROW_MOLECULE_COUNT')
    need(csv['fixtures']['tests_run']==7 and all(csv['fixtures'][k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),
      'ACTUAL_ORIGINAL_FULLCSV7_BOUNDARIES')
    native=closed(context,'native4','1884866',1264)
    need(native['schema']=='SECONDARY_NATIVE4_FULL_PHYSICAL_INVENTORY_RECEIPT_V1'
      and native['status']=='ALL39633_SDF_ATTEMPT_RESULTS_AND_ORIGINAL_CONTEXT_RECORDED_UNKNOWNS_RETAINED'
      and native['entity_unions']['physical_native_records']==57480 and native['entity_unions']['entities']==39438
      and native['native_result_inventory']['result_counts']=={'qm8_sdf':21786,'pdbbind_core':195,'pdbbind_general':12800,'pdbbind_refined':4852}
      and native['all_original_index_relations']['all_ID_rows_by_source']==IDS,
      'ACTUAL39633_AND57480_AND44510_NOT17_SOURCE_CLOSURE')
    need(native['fixtures']['tests_run']==3 and all(native['fixtures'][k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),
      'ACTUAL_ORIGINAL_NATIVE_FULL3_BOUNDARIES')
    gap=closed(context,'pdb27','1884885',1264)
    need(gap['schema']=='SECONDARY_PDBBIND_UNRESOLVED27_INDEX_RECEIPT_V1'
      and gap['status']=='ALL27_EXACT_ORIGINAL_INDEX_ROWS_AND_FROZEN_SOURCE_MAPPING_CLOSED_NOT_IDENTITY_ACCEPTANCE'
      and alias(context,gap['full_inventory_receipt_reference'])==context['closed_parents']['native4']['receipt_reference'],'EXACT27_PARENT_NOT12119')
    qm=closed(context,'qm7b','4523546',1278)
    need(qm['schema']=='QM7B_AUTHOR_NATIVE_COMPOSITION_RECEIPT_V1' and qm['result']['identity_rows']==7211
      and qm['MAT_row_or_native_graph_mapping'] is False,'ACTUAL_AUTHOR7211_CONSERVATIVE_SET_NOT_MAT_MAPPING')
    qp=meta(context['closed_parents']['qm7b']['startup_proof_reference']);qr=meta(qp['request']['scope']['review'])
    need(qr['author_asserted_all7211_set_conservative_composition_only_authorized'] is True
      and qr['exact_MAT_ID_native_graph_or_pool_release_authorized'] is False,'REAL_ROOT_AUTHOR_SET_ONLY_ACCEPTANCE_NOT_GRAPH_OR_MAT')
    selected={'csv6':alias(context,csv['outputs']['Parquet']),'native_unions':alias(context,native['entity_unions']['reference']),
      'native_relations':alias(context,native['all_original_index_relations']['reference'])}
    gs=[r for r in gap['DATA_references'] if Path(r['path']).name=='original27_rows.DATA.jsonl'];need(len(gs)==1,'EXACT27_RAW_LINE_EVIDENCE_LOCATOR')
    selected['pdb27']=alias(context,gs[0])
    raw=[r for r in gap['DATA_references'] if Path(r['path']).name=='original27_index_lines.DATA.raw'];need(len(raw)==1,'EXACT27_RAW_INDEX_BYTES_LOCATOR')
    selected['pdb27_raw']=alias(context,raw[0])
    qs=[r for r in qm['result']['data_references'] if Path(r['path']).name=='all7211_conservative_composition_identities.jsonl'];need(len(qs)==1,'EXACT7211_IDENTITY_OUTPUT')
    selected['qm7b']=alias(context,qs[0])
    for name,n in (('qm7',7165),('qm9',133885)):
        e=entries[name];need(e['status']=='READY' and e['identities']['rows']==n,'EXISTING_FULL_QM7_QM9_READY_AUTHORITY')
        selected[name]={k:e['identities'][k] for k in ('path','bytes','sha256')}
    data=unique([*data,*selected.values()])
    for ref in data:
        reference(ref);p=Path(ref['path']);s=p.lstat()
        need(not any(q.is_symlink() for q in (p,*p.parents)) and stat.S_ISREG(s.st_mode) and s.st_uid==1278
          and s.st_nlink==1 and s.st_size==ref['bytes'],'ACTUAL_CLOSED_INPUT_EXISTS_SIZE_UID_REGULAR_NO_FUTURE_OR_PARTIAL_LOCATOR')
    remote=meta(context['remote_acquisition_authority_reference'])
    need(remote['schema']=='ROOT_BOUNDED_MOLECULENET27_OFFICIAL_ACQUISITION_V1' and remote['status']=='APPROVED_FOR_SAME_PARENT_FINITE_READONLY_GET'
      and remote['reviewer']=='root' and all(type(remote[k])is int for k in ('maximum_original_index_rows','maximum_requests','maximum_response_bytes','maximum_total_bytes'))
      and remote['maximum_original_index_rows']==27 and 0<remote['maximum_requests']<=81
      and 0<remote['maximum_response_bytes']<=8<<20 and 0<remote['maximum_total_bytes']<=256<<20
      and remote['allowed_hosts']==['data.rcsb.org','files.rcsb.org'] and remote['new_QM_UFF_calls']==0,'EXPLICIT_BOUNDED_REMOTE_AUTHORITY_NOT_FUTURE_DATA_PIN')
    return {'selected':selected,'pdb27_raw_origin':raw[0],'data_references':data,'registry':registry,'remote':remote}

def sources():
    # Metadata imports only definitions; no native initialize, body or tests.
    from . import projection,acquisition,runtime,run,atoms,test_v1,materialize
    refs=[Q.pin(HERE/n) for n in FILES]
    refs.append(runtime.QuotaGuard.source_reference())
    for name,m in list(sys.modules.items()):
        p=getattr(m,'__file__',None)
        if name.startswith('workflows.') and p and Path(p).suffix=='.py':
            need(Q.REPO in Path(p).absolute().parents,'ALL_WORKFLOW_DEFINITIONS_FROM_ACTUAL_MAIN_SOURCE');refs.append(Q.pin(p))
    refs.extend(Q.pin(p) for p in (Q.REPO/'workflows/expansion/secondary_tdc_exact2_composition_v1/projection.py',
      Q.REPO/'workflows/expansion/secondary_tdc_exact2_composition_v1/contracts.py'))
    return unique(refs)
