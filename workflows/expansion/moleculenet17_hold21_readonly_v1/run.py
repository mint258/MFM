"""One bounded read-only audit of existing MolNet21 HOLDs; no new identity calls."""
import argparse,base64,collections,copy,hashlib,io,json,os,re,sys,time,traceback,unittest,urllib.parse
from pathlib import Path
from workflows.expansion.moleculenet17_decontamination_day_v1 import contract as C,runtime as I,acquisition as A,projection as P
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority,validate_scope_spec
from workflows.data_v1_final.execution.cpu_packed_day_v1.quota_provider import Client
from workflows.data_v1_final.execution.cpu_analysis_day_v1.contract import carveout
from workflows.expansion.marcel_drugs_decontamination_main_v1.materialize import fresh,approved
Q=C.Q;need=C.need;meta=C.meta;KEY='moleculenet17_hold21_readonly_v1';MODULE='workflows.expansion.'+KEY+'.run'
HERE=Q.REPO/'workflows/expansion'/KEY;CAP=2<<30;WALL=86400
PARAMETERS={'parent_job_id':'4524659','existing_unresolved':21,'existing_strict5_rows':806735,'original_official27_completed':22,
 'closed_input_only':True,'new_network_graph_parse_key_normalization_QM_UFF_calls':0,'original_UNKNOWN_or_READY_changed':False,
 'sparse_Parquet_identity_rows_only_after_whole_FD_SHA':True,'raw_values_in_DATA_only':True,'placeholder_spelling_is_not_source_policy':True,
 'cpus':16,'node':'compute-0-13','wall_seconds':WALL,'output_cap_bytes':CAP,'synthetic_methods':3,'global_pool_release':False}
LOCAL_COLUMNS=['dataset','source_id','role','memberships','smiles_variants','inchikeys','non_h_composition_json','missing_full_key',
 'missing_identity_or_composition','unresolved_source_variant','conservative_reason','source_metadata_json']
CSV_COLUMNS=['source_id','source_row_ordinal','role','physical_identity','source_identity_json','key_observation_json','full_keys','WP5_keys',
 'source_offset','source_record_bytes','source_record_sha256']

def positive(ref):return C.triple({k:ref[k] for k in ('path','bytes','sha256')})

def parents(header_ref):
    h=meta(header_ref);need(h['schema']=='ROOT_ACTUAL_MOLNET21_HOLD_DIAGNOSTIC_INPUT_LOCATORS_V1'
      and h['status']=='ACTUAL_C0_HOLD_LOCATORS_NOT_READY','REAL_CLOSED21_ROOT_LOCATOR_HEADER')
    p=h['old_parent'];r=meta(p['receipt']);old=meta(p['plan']);proof=meta(p['proof']);req=meta(p['request']);coverage=meta(p['coverage'])
    _,raw=C.D.K.K.account(p['accounting'],r)
    need(raw==p['raw'] and str(r['job_id'])==str(proof['job_id'])=='4524659' and r['uid']==proof['uid']==1278
      and r['node']==proof['node']=='compute-0-14' and proof['request']==req and proof['request_reference']==p['request']
      and r['plan_reference']==p['plan'] and r['startup_proof_reference']==p['proof']
      and r['input_context_reference']==old['input_context_reference']==h['input_context_reference']
      and req['scope_key']==C.KEY and req['scope_parameters']==old['scope_parameters']==C.PARAMETERS
      and req['execution_argv']==[Q.PY,'-B','-m',C.MODULE,'--plan',p['plan']['path'],'--startup-proof',p['proof']['path']]
      and req['cpus']==16 and req['kind']=='analysis' and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
      and proof['execution_admission_granted'] is True,'ACTUAL_OLD14_PARENT_NOT_NEW13_OR_FAKE_C0')
    f=r['fixtures'];need(f['tests_run']==3 and all(f[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),'ACTUAL_PARENT3_PASS')
    result=r['result'];need(r['schema']=='MOLECULENET17_DECONTAMINATION_DAY_RECEIPT_V1'
      and proof['schema']=='FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1'
      and coverage['schema']=='expansion_all_source_identity_coverage_v1' and coverage['dataset']=='moleculenet'
      and r['new_QM_UFF_calls']==0 and r['global_pool_training_release'] is False
      and r['status']=='ALL_DECLARED_CONTEXTS_READBACK_COMPLETE_UNRESOLVED_ORIGINALS_HOLD'
      and result['complete'] is False and result['unresolved']==21 and result['identity_rows']==806735 and result['official27_completed']==22
      and result['coverage_reference']==p['coverage'] and positive(result['unresolved_reference'])==positive(h['unresolved_reference'])
      and coverage['strict17_complete_candidate'] is False and coverage['unresolved_without_identity_or_composition']==21
      and coverage['identities']==result['identities_reference'] and positive(coverage['unresolved_original_source_evidence_reference'])==positive(h['unresolved_reference']),
      'TECHNICAL_C0_ORIGINAL21_HOLD_NOT_READY')
    context=meta(h['input_context_reference']);units=h['ClinTox_original_units']
    need(units==[u for u in context['local6_original_units'] if u['datasets'].get('moleculenet_clintox',0)>0],
      'EXACT_ORIGINAL_CLINTOX_UNIT_LOCATORS_NOT_NEW_POPULATION')
    need(all(u['file'] in old['data_references'] for u in units)
      and all(h[k] in old['data_references'] for k in ('normalized_CSV6_reference','original27_reference','original27_raw_reference')),
      'ONLY_ORIGINAL_PARENT_DECLARED_SOURCE_BODIES')
    remote=result['remote'];need(remote==coverage['remote_acquisition'] and remote['requests']==42
      and positive(remote['evidence_reference'])==positive(h['original_HTTP_evidence_reference'])
      and remote['actual_response_references']==h['original_HTTP_response_references'],'EXACT_CLOSED_HTTP_EVIDENCE_NO_NEW_GET')
    data=C.unique([positive(h['unresolved_reference']),h['normalized_CSV6_reference'],*(u['file'] for u in units),h['original27_reference'],
      h['original27_raw_reference'],positive(h['original_HTTP_evidence_reference']),*h['original_HTTP_response_references']])
    for ref in data:
        C.reference(ref);need(Q.ROOT/'artifacts' in Path(ref['path']).parents,'ONLY_ACTUAL_ARTIFACT_DATA_TRIPLES')
    refs=C.unique([header_ref,*p.values(),h['input_context_reference'],*(u['receipt_reference'] for u in units)])
    for ref in refs:need(Q.pin(ref['path'])==ref,'ACTUAL_SMALL_PARENT_BYTES_INCLUDING_RAW_SACCT_NOT_JSON')
    return h,data,refs

class Budget(I.OriginalBudget):
    """Resource-only context using the actual frozen long-lease CPU13 Client."""
    def __init__(self,plan,proof,out):
        super().__init__(plan,proof,out);self.carve=meta(plan['root_carveout_review_reference'])
        carveout(self.carve,{'scope_key':KEY,'node':proof['request']['node'],'resource_authority_reference':plan['resource_authority_reference'],
          'estimated_peak_output_bytes':self.cap});self.total=self.carve['total_future_reserved_bytes']
        self.client=Client(plan['quota_provider_review_reference'],proof['request']);self.next_quota=0;self.quota=None;self.written=0
        self.quota_guard_events=out/'quota_guard_events';self.quota_guard_events.mkdir(mode=0o700);self.quota_guard_event_references=[]
    def record(self,event):
        self.quota_guard_event_references.append(I.write(self.quota_guard_events/('event_%06d.json'%len(self.quota_guard_event_references)),event,self))
    def charge(self,n):
        need(type(n)is int and n>=0,'EXACT_OUTPUT_BYTES');self.written+=n;need(self.written+(258<<20)<self.cap,'FINITE_OUTPUT_PLUS_DRAIN')
    def check(self,dispatch=True,force=False):
        super().check(dispatch,force)
        if time.monotonic()>=self.next_quota:
            first=self.quota is None;self.quota=I.QuotaGuard.observe(self.client,expected_identity_reference=self.plan['quota_provider_identity_reference'],record=self.record)
            self.next_quota=time.monotonic()+60
            need(self.quota['identity_reference']==self.plan['quota_provider_identity_reference'],'EXACT_NEW_FINITE_PROVIDER_NO_RENEWAL')
            if first:need(self.quota['publisher_expires_unix_seconds']>=time.time()+self.plan['wall_seconds']-self.elapsed+300,'ACTUAL_LEASE_COVERS_REMAINING_DAY')
            need(self.quota['free_bytes']-self.total>=200000000000,'CURRENT_ACCOUNT_FUTURE_ONCE_PLUS200GB')

def field_fact(text,source_state=None):
    if text is None:return {'type':'null','source_state':source_state,'placeholder_status':'MISSING_VALUE_NOT_POLICY_ACCEPTANCE'}
    if not isinstance(text,str):return {'type':type(text).__name__,'source_state':source_state,'placeholder_status':'UNKNOWN'}
    spelling=text in ('NA','N/A','NULL','null','None','none','NaN','nan','-','?')
    try:raw=text.encode('utf-8')
    except UnicodeEncodeError:raw=None
    return {'type':'str','source_state':source_state,'UTF8_valid':raw is not None,'UTF8_bytes':None if raw is None else len(raw),
      'UTF8_sha256':None if raw is None else hashlib.sha256(raw).hexdigest(),
      'empty':text=='','whitespace_only':bool(text) and text.isspace(),'surrounding_whitespace':text!=text.strip(),
      'original_parser_ASCII33_to126_boundary':bool(text) and all(33<=ord(c)<=126 for c in text),
      'placeholder_status':'SOURCE_EXPLICIT_EMPTY_OR_MISSING_FIELD_NOT_EMPTY_RECORD' if source_state in ('EMPTY','MISSING')
        else 'SPELLING_ONLY_NOT_SOURCE_PROVEN' if spelling else 'UNKNOWN_NOT_INFERRED','identity_ignored_or_accepted':False}

CAUSE_TOKENS=set(('ORIGINAL_WHOLE_STRING_NOT_NONEMPTY_ASCII33_TO126_NO_TRIMMING_OR_PREFIX_PARSE WHOLE_ORIGINAL_SMILES_SYNTAX_NOT_PARSED '
 'EMPTY_QUERY_DUMMY_OR_UNCLOSED_ORIGINAL_ATOM_TABLE NO_ORIGINAL_NON_H_ATOMS ORIGINAL_UNSANITIZED_PARSE_OR_ATOM_ACCESS_EXCEPTION '
 'EXACT_ORIGINAL27_ID_AND_OPAQUE_ROW ORIGINAL_LIGAND_NAME_NOT_ONE_LITERAL_CCD_CODE_HOLD AMBIGUOUS_OR_NON_LIGAND_ORIGINAL_CODE_HOLD '
 'EXACT_FOUR_CHARACTER_ORIGINAL_PDB_LOCATOR OFFICIAL_QUERY_ERRORS_HOLD EXACT_REQUESTED_ENTRY_NO_REPLACEMENT BOUNDED_OFFICIAL_NONPOLYMER_ENTITIES '
 'EXACT_ORIGINAL_CCD_IN_THIS_ENTRY_NO_ARBITRARY_LIGAND_SELECTION OFFICIAL_ENTRY_RESPONSE_HOLD OFFICIAL_LIGAND_STRUCTURE_NOT_AVAILABLE_HOLD '
 'ONE_COMPLETE_OFFICIAL_CCD_STRUCTURE_NOT_HTML_OR_MULTIRECORD COMPLETE_OFFICIAL_CCD_ORIGINAL_ATOM_TABLE OFFICIAL_STORED_INCHIKEY_SYNTAX '
 'BOUNDED_ALL_OFFICIAL_DESCRIPTOR_VARIANTS COMPLETE_PUBLISHED_SMILES_VARIANT EXACT_OFFICIAL_LIGAND_FORMULA UNKNOWN_FORMULA_GRAMMAR_NO_GUESS EXACT_FORMULA_ELEMENT').split())
def cause(error):return error if isinstance(error,str) and error in CAUSE_TOKENS else 'UNKNOWN_SUBCAUSE_NOT_INFERRED'

def sparse_rows(ref,ordinals,columns,plan,budget):
    import pyarrow.parquet as pq
    need(all(type(n)is int and n>=0 for n in ordinals) and len(set(ordinals))==len(ordinals),'EXACT_DISTINCT_PHYSICAL_ORDINALS')
    wanted=set(ordinals);result={};groups=[]
    with I.held(ref,[Q.ROOT/'artifacts'],plan['data_references']) as (stream,_):
        source=pq.ParquetFile(stream,pre_buffer=False)
        try:
            need(set(columns)<=set(source.schema_arrow.names),'EXACT_PRODUCER_IDENTITY_COLUMNS_NO_ASSAY_VALUES')
            need(all(n<source.metadata.num_rows for n in wanted),'PHYSICAL_ORDINAL_WITHIN_COMPLETE_SOURCE')
            offset=0
            for i in range(source.metadata.num_row_groups):
                n=source.metadata.row_group(i).num_rows;local=sorted(v-offset for v in wanted if offset<=v<offset+n)
                if local:
                    budget.check();table=source.read_row_group(i,columns=columns,use_threads=False);groups.append(i)
                    for j in local:result[offset+j]=table.slice(j,1).to_pylist()[0]
                offset+=n
        finally:source.close()
    need(set(result)==wanted,'EVERY_REQUESTED_ROW_BOUND_ONCE');return result,{'row_groups_read':groups,'physical_rows_requested':len(wanted),'full_source_rows_scanned':False}

def response_facts(body,event,pdb,code):
    facts={'HTTP_status':event['HTTP_status'],'complete_EOF':event['complete_EOF'],'recorded_error_type':None if event['error'] is None else event['error'].get('type'),
      'missing_categories':[],'new_call_or_key_validation':False}
    if event['HTTP_status']!=200:facts['missing_categories'].append('HTTP_NON200')
    if not event['complete_EOF'] or event['error'] is not None:facts['missing_categories'].append('INCOMPLETE_OR_RECORDED_TRANSPORT_ERROR')
    if body is None:facts['missing_categories'].append('NO_POSITIVE_CLOSED_RESPONSE');return facts
    try:value=P.strict_json(body)
    except Exception as exc:facts['JSON_decode_error_type']=type(exc).__name__;facts['missing_categories'].append('NOT_STRICT_JSON_RESPONSE');return facts
    facts['JSON_type']=type(value).__name__
    if not isinstance(value,dict):facts['missing_categories'].append('JSON_TOPLEVEL_NOT_OBJECT');return facts
    facts['errors_present']=value.get('errors') not in (None,[])
    if facts['errors_present']:facts['missing_categories'].append('GRAPHQL_ERRORS_PRESENT')
    data=value.get('data');entry=data.get('entry') if isinstance(data,dict) else None
    if not isinstance(entry,dict):facts['missing_categories'].append('ENTRY_ABSENT_OR_NOT_OBJECT');return facts
    facts['entry_ID_matches_original']=entry.get('rcsb_id')==pdb.upper()
    if not facts['entry_ID_matches_original']:facts['missing_categories'].append('ENTRY_ID_MISMATCH')
    rows=entry.get('nonpolymer_entities');facts['nonpolymer_entities_type']=type(rows).__name__
    if not isinstance(rows,list):facts['missing_categories'].append('NONPOLYMER_ENTITIES_ABSENT_OR_NOT_LIST');return facts
    matches=[r.get('nonpolymer_comp') for r in rows if isinstance(r,dict) and isinstance(r.get('nonpolymer_comp'),dict)
      and isinstance(r['nonpolymer_comp'].get('chem_comp'),dict) and r['nonpolymer_comp']['chem_comp'].get('id')==code]
    facts['nonpolymer_entity_count']=len(rows);facts['exact_original_CCD_matches']=len(matches)
    if not matches:facts['missing_categories'].append('ORIGINAL_CCD_NOT_IN_ENTRY')
    else:
        facts['matching_component_variants_equal']=all(v==matches[0] for v in matches)
        facts['formula_field_types']=[type(v['chem_comp'].get('formula')).__name__ for v in matches]
        facts['stored_descriptor_field_types']=[type(v.get('rcsb_chem_comp_descriptor')).__name__ for v in matches]
        facts['stored_InChIKey_field_present']=[isinstance(v.get('rcsb_chem_comp_descriptor'),dict) and bool(v['rcsb_chem_comp_descriptor'].get('InChIKey')) for v in matches]
        if any(not isinstance(v['chem_comp'].get('formula'),str) or not v['chem_comp']['formula'] for v in matches):facts['missing_categories'].append('FORMULA_ABSENT_OR_EMPTY_OR_NONSTRING')
        if not facts['matching_component_variants_equal']:facts['missing_categories'].append('CONFLICTING_MATCHING_COMPONENT_VARIANTS')
    return facts

def sources():
    from . import test_v1
    refs=[Q.pin(HERE/'run.py'),Q.pin(HERE/'test_v1.py'),I.QuotaGuard.source_reference(),*C.sources(),
      Q.pin(Q.REPO/'workflows/data_v1_final/execution/cpu_packed_day_v1/contract.py'),
      Q.pin(Q.REPO/'workflows/data_v1_final/execution/cpu_packed_day_v1/quota_provider.py')]
    for name,module in list(sys.modules.items()):
        path=getattr(module,'__file__',None)
        if name.startswith('workflows.') and path and Path(path).suffix=='.py':
            need(Q.REPO in Path(path).absolute().parents,'ACTUAL_MAIN_WORKFLOW_SOURCE_ONLY');refs.append(Q.pin(path))
    return C.unique(refs)

def execute(plan,h,out,budget):
    original=I.Lines(out/'original21_closed_HOLD.DATA.jsonl',budget);diagnostic=I.Lines(out/'diagnostic21.DATA.jsonl',budget)
    try:
        holds=[];targets=collections.defaultdict(list);raw_refs={u['file']['path']:u['file'] for u in h['ClinTox_original_units']}
        raw_refs[h['normalized_CSV6_reference']['path']]=h['normalized_CSV6_reference']
        for item,segment in I.json_rows(h['unresolved_reference'],budget):
            need(type(item['evidence'].get('unresolved'))is int and item['evidence']['unresolved']>0,'ORIGINAL_POSITIVE_UNRESOLVED_NOT_RECLASSIFIED')
            original.append({'original':item,'original_lineage':segment});original.flush();i=len(holds);holds.append(item)
            if item['section'] in ('local6','csv6'):
                locator=item['original_source_locator'];ref=locator['reference'];need(ref['path'] in raw_refs and ref==raw_refs[ref['path']],'ONLY_ACTUAL_CLOSED_CLINTOX_OR_CSV_ROW')
                targets[ref['path']].append((i,locator['physical_row']))
        need(len(holds)==21 and sum(v['evidence']['unresolved'] for v in holds)==21,'ALL_ORIGINAL21_HOLDS_MASS_NO_DROPS')
        row_evidence={};sparse=[]
        for path,items in targets.items():
            ref=raw_refs[path];csv=ref==h['normalized_CSV6_reference'];values,observation=sparse_rows(ref,[n for _,n in items],CSV_COLUMNS if csv else LOCAL_COLUMNS,plan,budget)
            sparse.append({'reference':ref,**observation})
            for i,n in items:row_evidence[i]=values[n]
        original27={}
        for event,segment in I.json_rows(h['original27_reference'],budget):
            key=(event['source_id'],event['original_index_ordinal']);need(key not in original27,'ORIGINAL27_UNIQUE_INDEX');original27[key]=event
        need(len(original27)==27,'COMPLETE_CLOSED_ORIGINAL27_INDEX_NOT_NEW_DISCOVERY')
        http={};response_refs=h['original_HTTP_response_references']
        for event,segment in I.json_rows(h['original_HTTP_evidence_reference'],budget):
            need(event['url'] not in http and (event['response_reference'] is None or event['response_reference'] in response_refs),'EXACT_CLOSED_HTTP_URL_RESPONSE_PRODUCER_BINDING')
            http[event['url']]={'event':event,'lineage':segment}
        need(len(http)==42,'ACTUAL42_HTTP_EVENTS_NOT_NEW_REQUESTS')
        counts=collections.Counter();reasons=collections.Counter();states=collections.Counter();placeholders=collections.Counter();http_status=collections.Counter();missing=collections.Counter()
        with I.held(h['original27_raw_reference'],[Q.ROOT/'artifacts'],plan['data_references']) as (raw,_):
            for i,item in enumerate(holds):
                budget.check();e=item['evidence'];entry={'hold_ordinal':i,'original_HOLD':item,'original_UNKNOWN_preserved':True,'new_graph_or_key_computations':0};facts=[]
                if item['section']=='local6':
                    row=row_evidence[i];need(row['dataset']=='moleculenet_clintox' and e['dataset']==row['dataset'],'EXACT_ORIGINAL_CLINTOX_ROW')
                    entry.update(subdataset='ClinTox',original_identity_row=row,original_identity_locator=item['original_source_locator'])
                    facts=[field_fact(v) for v in row['smiles_variants']];entry['source_metadata_JSON_remains_opaque']=True
                elif item['section']=='csv6':
                    row=row_evidence[i];source=P.strict_json(row['source_identity_json']);result=P.strict_json(row['key_observation_json'])
                    need(source['source_id']==row['source_id']=='toxcast' and source['source_row_ordinal']==row['source_row_ordinal'] and result['source']==source
                      and result['SMILES_derived_full_keys']==row['full_keys'] and result['WP5_keys']==row['WP5_keys'],'EXACT_ORIGINAL_TOXCAST_SOURCE_RESULT_ROW_NOT_REPARSED')
                    entry.update(subdataset='ToxCast',original_identity_row=row,original_source=source,original_key_observation=result)
                    facts=[dict(literal_column_name=v['literal_column_name'],**field_fact(v.get('text'),v.get('state'))) for v in source['identity_fields'].values()]
                elif item['section']=='official27':
                    event=e['original_event'];key=(event['source_id'],event['original_index_ordinal']);need(original27.get(key)==event,'EXACT_ORIGINAL_UNRESOLVED_INDEX_EVENT')
                    part=event['opaque_full_line_output_segment'];need(type(part['offset'])is int and part['offset']>=0 and type(part['bytes'])is int and 0<part['bytes']<=1<<20,'EXACT_OPAQUE_ORIGINAL_LINE_BOUND')
                    raw.seek(part['offset']);line=raw.read(part['bytes']);need(len(line)==part['bytes'] and hashlib.sha256(line).hexdigest()==part['sha256']
                      and len(line)==event['original_details']['line_bytes'] and hashlib.sha256(line).hexdigest()==event['original_details']['line_sha256'],'EXACT_ORIGINAL_LINE_BYTES_AND_SHA')
                    entry.update(subdataset='PDBbind',original_index_event=event,original_line_base64=base64.b64encode(line).decode('ascii'),
                      affinity_or_reference_fields_decoded=False,HTTP_evidence=[])
                    try:pdb,code=A.index_ligand(line,event)
                    except Exception as exc:entry['index_locator_check']={'error_type':type(exc).__name__,'error':str(exc),'category':cause(str(exc))}
                    else:
                        query='{entry(entry_id:"'+pdb.upper()+'") {rcsb_id nonpolymer_entities {nonpolymer_comp {chem_comp {id formula} rcsb_chem_comp_descriptor {InChIKey} pdbx_chem_comp_descriptor {descriptor type program}}}}}'
                        urls=['https://data.rcsb.org/graphql?'+urllib.parse.urlencode({'query':query}),'https://files.rcsb.org/ligands/download/'+code+'_ideal.sdf']
                        for url in urls:
                            existing=http.get(url)
                            if existing is None:entry['HTTP_evidence'].append({'expected_original_url':url,'category':'NO_CLOSED_EVENT_NOT_A_NEW_REQUEST'});missing['NO_CLOSED_EVENT_NOT_A_NEW_REQUEST']+=1;continue
                            observed=existing['event'];ref=observed['response_reference'];body=None
                            if ref is not None:
                                with I.held(ref,[Q.ROOT/'artifacts'],plan['data_references']) as (stream,_):body=stream.read()
                            if url==urls[0]:observations=response_facts(body,observed,pdb,code)
                            else:
                                observations={'HTTP_status':observed['HTTP_status'],'complete_EOF':observed['complete_EOF'],'closed_response_bytes':0 if body is None else len(body),
                                  'literal_SDF_delimiter_count':0 if body is None else body.count(b'$$$$'),'format_or_graph_reparsed':False,'missing_categories':[]}
                                if not body:observations['missing_categories'].append('NO_POSITIVE_CLOSED_RESPONSE')
                                elif body.count(b'$$$$')!=1:observations['missing_categories'].append('SDF_DELIMITER_COUNT_NOT_ONE')
                                if observed['HTTP_status']!=200:observations['missing_categories'].append('HTTP_NON200')
                            http_status[str(observed['HTTP_status'])]+=1;missing.update(observations['missing_categories']);entry['HTTP_evidence'].append({'original':existing,'facts':observations})
                else:raise ValueError('UNEXPECTED_ORIGINAL_HOLD_SECTION_NOT_SILENTLY_SKIPPED')
                entry['original_identity_field_facts']=facts;counts[entry['subdataset']]+=1
                reasons.update(cause(v.get('reason')) for v in e.get('atoms_evidence',[]));reasons[cause(e.get('error'))]+=int('error' in e)
                states.update(str(v['source_state']) for v in facts);placeholders.update(v['placeholder_status'] for v in facts)
                diagnostic.append(entry);diagnostic.flush()
        need(dict(counts)=={'ClinTox':1,'ToxCast':15,'PDBbind':5},'ORIGINAL21_SOURCE_CENSUS_NOT_SOURCE_EXCLUSION')
        return {'complete_original_HOLD_reference':original.close(),'diagnostic_DATA_reference':diagnostic.close(),'HOLD_rows':21,'by_source':dict(counts),
          'original_reason_token_counts':dict(reasons),'identity_field_state_counts':dict(states),'placeholder_status_counts':dict(placeholders),
          'closed_HTTP_status_counts':dict(http_status),'HTTP_missing_category_counts':dict(missing),'sparse_Parquet_read_evidence':sparse,
          'new_network_graph_parse_key_normalization_QM_UFF_calls':0,'original_UNKNOWN_changed':False,'READY_or_pool_release':False}
    finally:original.close();diagnostic.close()

def fixtures(out):
    from . import test_v1
    test_v1.WORKSPACE=out;suite=unittest.defaultTestLoader.loadTestsFromTestCase(test_v1.Boundaries);need(suite.countTestCases()==3,'EXACT3_BEFORE_ORIGINAL_DATA_AND_BUDGET')
    text=io.StringIO();r=unittest.TextTestRunner(stream=text,verbosity=2).run(suite)
    value={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),'expected_failures':len(r.expectedFailures),
      'unexpected_successes':len(r.unexpectedSuccesses),'transcript':text.getvalue(),'all_before_original_DATA_and_Budget':True}
    Q.write_new(out/'source3.json',value);need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'SOURCE3_FAILED_NO_DATA');return value

def draft(request_path,out):
    Q.on_login();request=Q.load(request_path);need(request['schema']=='ROOT_REQUESTED_MOLNET21_HOLD_READONLY_V1'
      and request['status']=='REQUESTED_FOR_REVIEW' and request['requested_by']=='root' and request['node']=='compute-0-13','EXACT_ROOT_REQUEST_NOT_APPROVAL')
    h,data,refs=parents(request['actual_input_locators_reference']);validate_authority(request['resource_authority_reference'],read_small=Q.read_small)
    resource={k:request[k] for k in ('quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference','resource_authority_reference','cost_decision_reference')}
    for ref in resource.values():meta(ref)
    cost=meta(resource['cost_decision_reference']);need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
      and cost['scientific_quality_thresholds_unchanged'] is True,'ORIGINAL_ACTUAL_COST_AND_QUALITY_AUTHORITY')
    carveout(meta(resource['root_carveout_review_reference']),{'scope_key':KEY,'node':request['node'],'resource_authority_reference':resource['resource_authority_reference'],'estimated_peak_output_bytes':CAP})
    plan={'schema':'MOLNET21_HOLD_READONLY_PLAN_V1','scope_parameters':PARAMETERS,'wall_seconds':WALL,'output_cap_bytes':CAP,
      'output_directory':str(fresh(request['output_directory'],'artifacts')),'actual_input_locators_reference':request['actual_input_locators_reference'],'data_references':data,**resource}
    parent_refs=C.unique([*refs,Q.pin(request_path),*resource.values()]);out=fresh(out);out.mkdir(parents=True,mode=0o700)
    plan['source_references']=C.unique([*sources(),*parent_refs]);pr=Q.write_new(out/'plan.json',plan)
    fields={'kind':'analysis','scope_key':KEY,'scope_parameters':PARAMETERS,'pilot':False,'wall_seconds':WALL,'estimated_peak_output_bytes':CAP,
      'source_status_stage':'MOLNET21_ORIGINAL_HOLD_READONLY_FINDINGS','execution_argv':[Q.PY,'-B','-m',MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    src=C.unique([*plan['source_references'],pr]);template={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
      **copy.deepcopy(fields),'scope_mode':'BOUNDED_METADATA_PREPARATION','resource_authority_reference':resource['resource_authority_reference'],
      'stage_output_cap_bytes':CAP,'parent_evidence_references':parent_refs,'approved_source_references':src,'data_references':data,
      'only21_existing_HOLDs_and_closed_source_evidence_authorized':True,'new_network_or_key_QM_UFF_calls_authorized':False,'UNKNOWN_READY_or_pool_change_authorized':False}
    tr=Q.write_new(out/'root_review.template.json',template)
    return Q.write_new(out/'draft_receipt.json',{'schema':'MOLNET21_HOLD_READONLY_DRAFT_V1','plan_reference':pr,'template_reference':tr,
      'stage_fields':fields,'source_references':src,'data_references':data,'resource_authority_reference':resource['resource_authority_reference'],'scientific_DATA_read_on_login':False})

def finalize(path,review):
    Q.on_login();d=Q.load(path);need(d['schema']=='MOLNET21_HOLD_READONLY_DRAFT_V1','EXACT_DIAGNOSTIC_DRAFT');rr=approved(d['template_reference'],review)
    plan=meta(d['plan_reference']);_,data,_=parents(plan['actual_input_locators_reference']);need(data==d['data_references']==plan['data_references'],'EXACT_UNCHANGED_CLOSED_DATA_LOCATORS')
    for ref in d['source_references']:need(Q.pin(ref['path'])==ref,'ACTUAL_CURRENT_SOURCE_AND_SMALL_PARENTS')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','stage_output_cap_bytes':CAP,
      'source_references':d['source_references'],'data_references':data,'scope':{'mode':'BOUNDED_METADATA_PREPARATION','parent_profile':None,'review':rr}}
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small);return Q.write_new(Path(path).parent/'stage_spec.json',spec)

def main():
    if len(sys.argv)>1 and sys.argv[1] in ('draft','finalize'):
        p=argparse.ArgumentParser();s=p.add_subparsers(dest='action',required=True);a=s.add_parser('draft');a.add_argument('--request',required=True);a.add_argument('--output',required=True)
        a=s.add_parser('finalize');a.add_argument('--draft',required=True);a.add_argument('--root-review',required=True);a=p.parse_args()
        print(draft(a.request,a.output) if a.action=='draft' else finalize(a.draft,a.root_review));return 0
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args()
    plan=meta(Q.pin(a.plan));h,data,_=parents(plan['actual_input_locators_reference']);argv=[Q.PY,'-B','-m',MODULE,'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
    proof=require_startup(a.startup_proof,expected_kind='analysis',expected_scope_key=KEY,expected_scope_parameters=PARAMETERS,expected_execution_argv=argv,
      expected_source=HERE/'run.py',required_references=[Q.pin(a.plan),*plan['source_references']]);req=proof['request']
    need(plan['schema']=='MOLNET21_HOLD_READONLY_PLAN_V1' and plan['scope_parameters']==PARAMETERS and req['node']=='compute-0-13' and req['cpus']==16 and req['pilot'] is False
      and req['wall_seconds']==plan['wall_seconds']==WALL and req['stage_output_cap_bytes']==req['estimated_peak_output_bytes']==plan['output_cap_bytes']==CAP
      and req['data_references']==plan['data_references']==data and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED','EXACT_DIAGNOSTIC13_16_DAY2G_SOURCE_DATA')
    review=meta(req['scope']['review']);need(review['only21_existing_HOLDs_and_closed_source_evidence_authorized'] is True
      and review['new_network_or_key_QM_UFF_calls_authorized'] is False and review['UNKNOWN_READY_or_pool_change_authorized'] is False,'EXACT_ROOT_READONLY_SCOPE')
    for ref in sources():need(ref in req['source_references'],'FULL_CURRENT_SOURCE_CLOSURE')
    out=fresh(plan['output_directory'],'artifacts');need(Q.ROOT/'artifacts/expansion'/KEY in out.parents,'OWN_FRESH_DIAGNOSTIC_OUTPUT');out.mkdir(parents=True,mode=0o700)
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    gate=fixtures(out);budget=Budget(plan,proof,out)
    try:
        result=execute(plan,h,out,budget);budget.check();summary=I.write(out/'diagnosis_summary.json',result,budget)
        for ref in plan['source_references']:need(Q.pin(ref['path'])==ref,'SOURCE_AND_SMALL_PARENTS_STABLE_AFTER_DIAGNOSIS')
        Q.write_new(out/'receipt.json',{'schema':'MOLNET21_HOLD_READONLY_RECEIPT_V1','status':'ALL21_CLOSED_EVIDENCE_RECORDED_ORIGINAL_UNKNOWN_UNCHANGED',
          'job_id':str(proof['job_id']),'uid':1278,'endpoint':'202.38.247.57:22','node':req['node'],'plan_reference':Q.pin(a.plan),'startup_proof_reference':Q.pin(a.startup_proof),
          'actual_input_locators_reference':plan['actual_input_locators_reference'],'fixtures':gate,'summary_reference':summary,'result':result,
          'quota_guard_event_references':budget.quota_guard_event_references,'new_network_graph_key_QM_UFF_calls':0,'original_HOLD_changed':False,'READY_or_pool_release':False})
        return 0
    except BaseException as exc:
        I.write(out/'failure.DATA.json',{'error_type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc(),'partial_preserved':True,'automatic_retry':False},budget);raise
    finally:budget.check(dispatch=False,force=True)

if __name__=='__main__':raise SystemExit(main())
