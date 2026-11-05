"""Exact21 conservative exclusion evidence; independent from original graph status."""
import argparse,base64,collections,hashlib,io,json,os,re,socket,sys,time,traceback,unittest,urllib.error,urllib.request
from pathlib import Path
from workflows.expansion.moleculenet17_hold21_readonly_v1 import run as M
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
C=M.C;I=M.I;Q=M.Q;need=M.need;meta=M.meta
KEY='moleculenet21_conservative_closure_v1';MODULE='workflows.expansion.'+KEY+'.closure';HERE=Q.REPO/'workflows/expansion'/KEY
FILES=('closure.py','metadata.py','consumer.py','test_v1.py');CAP=2<<30;WALL=86400;NODES=('compute-0-13','compute-0-14','compute-0-18')
WHITELIST=(1,5,6,7,8,9,14,15,16,17,34,35,53);COMPONENTS=('ARG','CLR','OLC','ALA','ACT','CL')
URLS=tuple('https://data.rcsb.org/rest/v1/core/chemcomp/'+s for s in COMPONENTS)+(
 'https://data.rcsb.org/rest/v1/core/polymer_entity/1PTS/2','https://files.rcsb.org/download/1PTS.pdb')
PARAMETERS={'exact_diagnostic_parent':'4524667','original_cases':21,'FAIL_marker_cases':15,'domain_disjoint_ions':3,
 'dummy_known_core_cases':1,'peptide_native_lower_bound_cases':1,'ARG_union_case':1,'maximum_new_HTTPS_calls':8,
 'maximum_HTTP_body_bytes':16<<20,'maximum_HTTP_total_bytes':64<<20,'new_full_keys_QM_UFF_calls':0,
 'original_UNKNOWN_changed':False,'legacy_strict5_objects_changed':False,'candidate_domain_each_row_checked':True,
 'new_queue_or_model_changes':False,'cpus':16,'wall_seconds':WALL,'output_cap_bytes':CAP,'source_methods':3,'READY_or_pool_release':False}

def parameters(node):
    need(node in NODES,'EXACT_EXISTING_QUOTA_CLIENT_NODE');return dict(PARAMETERS,node=node)

def positive(ref):return M.positive(ref)

def policy(plan):
    p=meta(plan['policy_reference'])
    need(p['schema']=='ROOT_MOLNET21_EXACT_CONSERVATIVE_CLOSURE_POLICY_V1'
      and p['status']=='APPROVED_FOR_SOURCE_IMPLEMENTATION_AND_SAME_PARENT_VALIDATION_NOT_READY' and p['reviewer']=='root'
      and p['actual_diagnostic_parent']=='4524667' and p['expected_total_cases']==21 and p['exact_toxcast_literal_FAIL_count']==15
      and p['invalid_marker_status']=='AUTHOR_SOURCE_INVALID_MOLECULAR_INPUT'
      and p['three_ion_annotations']=={'1jou':'Na+','2adj':'Ca2+','1z9j':'MN+'}
      and p['https_allowlist']==list(URLS) and p['maximum_new_HTTPS_calls']==8 and p['maximum_response_bytes']==16<<20
      and p['maximum_total_response_bytes']==64<<20 and p['automatic_retry_or_network_bypass'] is False,'EXACT_ROOT21_POLICY_NO_GENERAL_EXCEPTIONS')
    for k in ('invalid_marker_exact_case_bindings_required','other_identity_columns_must_be_absent','generic_parse_failure_disposal_forbidden',
      'three_ions_require_original_frozen_X02_domain_and_actual_per_candidate_domain_enforcement','reuse_matching_closed_native_evidence_first',
      'HTTP403_429_stop_new_dispatch_natural_drain','real_typed_lower_bound_veto_required','legacy_strict5_and_identity_key_objects_unchanged',
      'new_V2_index_must_fail_legacy_consumer','all11_sources_all_roles_complete_policy_coverage_required',
      'original21_UNKNOWN_and_all_raw_rows_errors_costs_retained','new_exclusion_coverage_axis_separate_from_original_identity_resolution',
      'Source_implementation_does_not_authorize_native_or_global_pool_release'):
        need(p[k] is True,'EXACT_POLICY_TRUE_'+k)
    return p

def domain(value):
    """Actual frozen source and closed screen authority, not a new element rule."""
    import ast
    need(value['schema']=='FROZEN_X02_CANDIDATE_DOMAIN_AUTHORITY_V1' and value['allowed_atomic_numbers']==list(WHITELIST)
      and value['per_candidate_elements_and_composition_enforcement_required'] is True and value['closed_screen_authority_references'],
      'REAL_FROZEN_X02_DOMAIN_AUTHORITY_REQUIRED')
    ref=value['screen_source_reference'];raw=Q.read_small(ref['path']);need(Q.pin(ref['path'])==ref
      and ref['bytes']==11880 and ref['sha256']=='bb31d57a4749f9ef9843dc075bc75f7c268cb781f60c7b4f0d77a121a73dcc88','ACTUAL_ORIGINAL_FROZEN_SCREEN_SOURCE_VERSION')
    # Login metadata validates the exact Source hash; AST runs in this CPU Parent.
    if socket.gethostname().split('.')[0] in NODES:
        need(os.environ.get('SLURM_JOB_ID','').isdecimal() and os.getuid()==1278,'ACTUAL_CPU_ALLOCATION_FOR_SOURCE_AST')
        tree=ast.parse(raw.decode('utf-8-sig'));found=[ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
          and any(isinstance(t,ast.Name) and t.id=='WHITELIST' for t in n.targets)]
        need(found==[set(WHITELIST)],'ORIGINAL_X02_ELEMENT_DOMAIN_NOT_CHANGED')
    else:Q.on_login()
    for ref in value['closed_screen_authority_references']:need(Q.pin(ref['path'])==ref,'ACTUAL_SMALL_SCREEN_AUTHORITY_NOT_FUTURE')
    return value

def inputs(plan):
    p=policy(plan);h,_,old_refs=M.parents(plan['actual_input_locators_reference']);r=meta(plan['diagnostic_receipt_reference'])
    _,raw=C.D.K.K.account(p['diagnostic_parent_accounting_reference'],r);summary=meta(p['diagnosis_summary_reference'])
    need(r['schema']=='MOLNET21_HOLD_READONLY_RECEIPT_V1' and r['status']=='ALL21_CLOSED_EVIDENCE_RECORDED_ORIGINAL_UNKNOWN_UNCHANGED'
      and str(r['job_id'])=='4524667' and r['uid']==1278 and r['node']=='compute-0-13' and r['original_HOLD_changed'] is False
      and r['actual_input_locators_reference']==plan['actual_input_locators_reference'] and r['summary_reference']==p['diagnosis_summary_reference']
      and summary==r['result'] and summary['HOLD_rows']==21 and summary['by_source']=={'ClinTox':1,'ToxCast':15,'PDBbind':5}
      and summary['diagnostic_DATA_reference']==p['exact_closed21_diagnostic_DATA_reference']
      and summary['complete_original_HOLD_reference']==p['exact_closed21_original_HOLD_DATA_reference'],'ACTUAL4667_C0_COMPLETE21_ORIGINAL_UNKNOWN_NOT_CHANGED')
    f=r['fixtures'];need(f['tests_run']==3 and all(f[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),'ACTUAL_DIAGNOSTIC3_PASS')
    proof=meta(r['startup_proof_reference']);request=meta(proof['request_reference']);old_plan=meta(r['plan_reference'])
    need(proof['request']==request and str(proof['job_id'])==str(r['job_id']) and proof['uid']==1278 and proof['node']==r['node']
      and request['scope_key']==M.KEY and request['scope_parameters']==old_plan['scope_parameters']==M.PARAMETERS
      and request['execution_argv']==[Q.PY,'-B','-m',M.MODULE,'--plan',r['plan_reference']['path'],'--startup-proof',r['startup_proof_reference']['path']],
      'REAL_DIAGNOSTIC_FULL_ARGV_PLAN_PROOF_NOT_ALIAS')
    d=domain(plan['candidate_domain_authority']);data=C.unique([positive(p['exact_closed21_diagnostic_DATA_reference']),
      positive(p['exact_closed21_original_HOLD_DATA_reference']),*h['original_HTTP_response_references']])
    refs=C.unique([plan['policy_reference'],plan['actual_input_locators_reference'],plan['diagnostic_receipt_reference'],
      p['diagnostic_parent_accounting_reference'],raw,p['diagnosis_summary_reference'],r['startup_proof_reference'],proof['request_reference'],r['plan_reference'],
      *old_refs,d['screen_source_reference'],*d['closed_screen_authority_references']])
    return p,h,data,refs,request

def sources(plan):
    _,_,_,_,request=inputs(plan)
    # A fixed actual4667 dependency closure; never all refs in a combined Parent
    # and never scientific body inventories or every source's ancestry.
    refs=[Q.pin(HERE/n) for n in FILES]
    refs.extend(Q.pin(Q.REPO/'workflows/data_v1_final/execution/cpu_analysis_day_v1'/n) for n in ('contract.py','quota_provider.py'))
    for ref in request['source_references']:
        if ref['path'].startswith(str(Q.REPO)+'/'):
            need(Q.pin(ref['path'])==ref,'FROZEN_DIAGNOSTIC_DEPENDENCY_SOURCE_CURRENT_OR_EXPLICIT_SNAPSHOT_REQUIRED');refs.append(ref)
    return C.unique(refs)

def admit(plan,proof):
    req=proof['request'];need(os.getuid()==proof['uid']==1278 and str(proof['job_id'])==os.environ.get('SLURM_JOB_ID')
      and socket.gethostname().split('.')[0]==req['node'] and req['node']==proof['node']
      and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==proof['boot_id'] and type(req['cpus'])is int and req['cpus']>=16
      and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED','SAME_ACTUAL_ADMITTED_CPU_PARENT_NO_CHILD_C0')
    need(plan['policy_reference'] in req['source_references'],'ROOT_POLICY_IN_ACTUAL_PARENT_SOURCE_AUTHORITY')
    need(all(ref in req['data_references'] for ref in plan['data_references']),'EVERY_PHASE_DATA_LOCATOR_IN_ADMITTED_PARENT')
    for ref in sources(plan):need(ref in req['source_references'],'EVERY_FIXED_SOURCE_IN_ACTUAL_PARENT')

class Budget(M.Budget):
    """Only initialization binds this scope; record/charge/check are original objects."""
    def __init__(self,plan,proof,out):
        I.OriginalBudget.__init__(self,plan,proof,out);self.carve=meta(plan['root_carveout_review_reference'])
        M.carveout(self.carve,{'scope_key':KEY,'node':proof['request']['node'],'resource_authority_reference':plan['resource_authority_reference'],'estimated_peak_output_bytes':self.cap})
        self.total=self.carve['total_future_reserved_bytes'];node=proof['request']['node'];parameters(node)
        if node=='compute-0-13':client=M.Client
        else:
            from workflows.data_v1_final.execution.cpu_analysis_day_v1.quota_provider import Client
            client=Client
        self.client=client(plan['quota_provider_review_reference'],proof['request'])
        self.next_quota=0;self.quota=None;self.written=0;self.quota_guard_events=out/'quota_guard_events';self.quota_guard_events.mkdir(mode=0o700);self.quota_guard_event_references=[]

def known_core(text,Chem,audit=None):
    need(type(text)is str and text and all(33<=ord(c)<=126 for c in text),'ORIGINAL_EXACT_FULL_STRING_REQUIRED')
    params=Chem.SmilesParserParams()
    for k,v in C.PARAMS.items():setattr(params,k,v)
    need({k:getattr(params,k) for k in C.PARAMS}==C.PARAMS,'EXACT_ORIGINAL_SIX_PARSER_PARAMS')
    if audit is not None:audit['original_MolFromSmiles_invocations']+=1
    mol=Chem.MolFromSmiles(text,params);need(mol is not None,'ORIGINAL_ATOM_TABLE_UNAVAILABLE_HOLD')
    zs=[a.GetAtomicNum() for a in mol.GetAtoms()];need(zs.count(0)==1 and all(type(z)is int and 0<=z<=118 for z in zs)
      and not any(a.HasQuery() for a in mol.GetAtoms()) and not any(b.HasQuery() for b in mol.GetBonds()),'ONE_DUMMY_FIXED_ATOMS_NOT_ARBITRARY_QUERY')
    counts=collections.Counter(z for z in zs if z>1);need(counts,'POSITIVE_KNOWN_CORE_REQUIRED')
    return [[z,counts[z]] for z in sorted(counts)],{'observed_dummy_atoms':1,'all_original_atoms_in_original_order':zs,
      'dummy_substituted_or_removed':False,'full_key_or_resolved_graph_created':False,'type':'NON_H_ATOM_COUNT_LOWER_BOUND'}

def exact_FAIL(case):
    if case.get('subdataset')!='ToxCast':return False
    source=case['original_source'];row=case['original_identity_row'];fields=list(source['identity_fields'].values())
    return (source['source_id']==row['source_id']=='toxcast' and source['source_row_ordinal']==row['source_row_ordinal']
      and len(fields)==1 and fields[0]['literal_column_name']=='smiles' and fields[0]['state']=='PRESENT' and fields[0]['text']=='FAIL'
      and not row['full_keys'] and not row['WP5_keys'])

def marker_binding(case):
    need(exact_FAIL(case),'ONLY_EXACT_SOLE_LITERAL_FAIL_CASE')
    source=case['original_source'];row=case['original_identity_row']
    need(all(source[k]==row[k] for k in ('source_record_sha256','source_record_bytes','source_offset'))
      and type(source['source_record_sha256'])is str and re.fullmatch('[0-9a-f]{64}',source['source_record_sha256']) is not None
      and type(source['source_record_bytes'])is int and source['source_record_bytes']>0
      and type(source['source_offset'])is int and source['source_offset']>=0,'EXACT_ORIGINAL_FAIL_ORDINAL_RAW_SHA_AND_SPAN')
    return source

def annotation(case):
    event=case['original_index_event'];raw=base64.b64decode(case['original_line_base64'],validate=True)
    need(hashlib.sha256(raw).hexdigest()==event['original_details']['line_sha256'] and len(raw)==event['original_details']['line_bytes']
      and raw[:4].decode('ascii')==event['original_ID']['text'],'EXACT_ORIGINAL_INDEX_RAW_ID_SHA')
    match=re.search(br'\(([^()]*)\)\s*$',raw);need(match is not None,'EXACT_ORIGINAL_ANNOTATION_REQUIRED');return match.group(1).decode('ascii')

def peptide_bounds(body,entity,table):
    ids=entity['rcsb_polymer_entity_container_identifiers'];poly=entity['entity_poly']
    seq=''.join(poly['pdbx_seq_one_letter_code_can'].split())
    need(ids['entry_id'].upper()=='1PTS' and str(ids['entity_id'])=='2' and 'C' in ids['asym_ids'] and 'P' in ids['auth_asym_ids']
      and len(seq)==7 and set(seq)<=set('ACDEFGHIKLMNPQRSTVWY'),'EXACT1PTS_ENTITY2_CHAIN_C_AUTH_P_SEVEN_STANDARD_RESIDUES')
    names=dict(zip(('ALA','CYS','ASP','GLU','PHE','GLY','HIS','ILE','LYS','LEU','MET','ASN','PRO','GLN','ARG','SER','THR','VAL','TRP','TYR'),'ACDEFGHIKLMNPQRSTVWY'))
    symbols={table.GetElementSymbol(z).upper():z for z in range(1,119)};models={};model='implicit';end=False
    for line in body.splitlines():
        record=line[:6].strip()
        if record==b'MODEL':model=line[10:14].decode('ascii').strip();need(model,'EXPLICIT_MODEL_ID');continue
        if record==b'END':end=True
        if record!=b'ATOM' or len(line)<22 or line[21:22]!=b'P':continue
        need(len(line)>=78,'EXPLICIT_NATIVE_ELEMENT_COLUMN_REQUIRED_NO_NAME_GUESS')
        element=line[76:78].decode('ascii').strip().upper();need(element in symbols,'EXACT_NATIVE_ATOM_ELEMENT')
        residue=line[17:20].decode('ascii').strip();need(residue in names,'UNEXPECTED_NATIVE_POLYMER_RESIDUE_HOLD')
        resid=(line[22:26].decode('ascii'),line[26:27].decode('ascii'));atom=line[12:16].decode('ascii').strip();alt=line[16:17].decode('ascii').strip()
        need(atom and resid[0].strip(),'ORIGINAL_NATIVE_ATOM_AND_RESIDUE_IDS_REQUIRED')
        models.setdefault(model,[]).append((resid,residue,atom,alt,symbols[element]))
    need(end and models,'COMPLETE_NATIVE_PDB_WITH_SELECTED_ATOMS_REQUIRED')
    variants=[];observations=[]
    for model,atoms in models.items():
        residues=list(dict.fromkeys((a[0],a[1]) for a in atoms));letters=[names[r[1]] for r in residues];cursor=0
        for letter in letters:
            while cursor<len(seq) and seq[cursor]!=letter:cursor+=1
            need(cursor<len(seq),'OBSERVED_RESIDUES_NOT_ORDERED_SUBSEQUENCE_OF_DECLARED_ENTITY');cursor+=1
        alts=sorted({a[3] for a in atoms if a[3]}) or ['']
        for alt in alts:
            sites=collections.defaultdict(set)
            for resid,residue,atom,label,z in atoms:
                if not label or label==alt:sites[(resid,residue,atom)].add(z)
            counts=collections.Counter(next(iter(zs)) for zs in sites.values() if len(zs)==1 and next(iter(zs))>1)
            variants.append(counts);observations.append({'model':model,'altloc':alt,'logical_sites':len(sites),'ambiguous_element_sites':sum(len(v)!=1 for v in sites.values()),'non_H_counts':sorted(counts.items()),'observed_residues':len(residues)})
    zs=set().union(*(set(v) for v in variants));bound=[[z,min(v.get(z,0) for v in variants)] for z in sorted(zs) if min(v.get(z,0) for v in variants)>0]
    need(bound,'NO_SHARED_POSITIVE_NATIVE_LOWER_BOUND_HOLD')
    return bound,{'entity_id':'2','label_asym_id':'C','auth_asym_id':'P','declared_residue_count':7,'model_altloc_variants':observations,
      'aggregation':'COMPONENTWISE_MINIMUM_NO_MODEL_OR_ALTLOC_SUM','coordinates_decoded':False,'HETATM_or_missing_atoms_inferred':False,'exact_composition_claimed':False}

class Capture:
    def __init__(self,p,out,budget):self.p=p;self.out=out;out.mkdir();self.budget=budget;self.calls=0;self.opens=0;self.total=0;self.stop=None;self.cache={};self.refs=[];self.log=I.Lines(out/'HTTP.DATA.jsonl',budget)
    def get(self,url):
        need(url in URLS and url in self.p['https_allowlist'],'ONLY_EIGHT_ROOT_APPROVED_URLS')
        if url in self.cache:
            e=self.cache[url];need(e['HTTP_status']==200 and e['complete_EOF'] and e['error'] is None and e['response_reference'] is not None,'CACHED_FAILED_RESPONSE_NO_RETRY');return e
        need(self.stop is None,'HTTP403_429_STOP_NEW_REQUESTS');need(self.calls<8,'FINITE_EIGHT_REQUESTS_NO_RETRY');self.calls+=1
        self.log.append({'phase':'GET_INTENT','url':url,'intent_ordinal':self.calls,'maximum_intents':8,'native_return_or_HTTP_success_claimed':False});self.log.flush()
        path=self.out/('response_%02d.DATA.bin'%self.calls);n=0;h=hashlib.sha256();complete=False;status=None;headers={};error=None
        try:
            self.budget.check();opener=urllib.request.build_opener(M.A.NoRedirect());request=urllib.request.Request(url,headers={'Accept-Encoding':'identity','User-Agent':'MolNet21-conservative-exclusion/1'})
            self.opens+=1
            try:response=opener.open(request,timeout=30)
            except urllib.error.HTTPError as exc:response=exc
            with response,path.open('xb') as stream:
                status=response.status;headers=dict(response.headers);need(response.geturl()==url and response.headers.get('Content-Encoding','identity')=='identity','EXACT_OFFICIAL_URL_UNENCODED_BODY')
                if status in (403,429):self.stop='HTTP_'+str(status)
                started=time.monotonic()
                while True:
                    self.budget.check();need(time.monotonic()-started<=120,'FINITE_RESPONSE_WALL');block=response.read(1<<16)
                    if not block:complete=True;break
                    need(n+len(block)<=16<<20 and self.total+len(block)<=64<<20,'FINITE_BODY_AND_TOTAL_NO_PREFIX_ACCEPTANCE')
                    self.budget.charge(len(block));stream.write(block);h.update(block);n+=len(block);self.total+=len(block)
                size=response.headers.get('Content-Length');need(size is None or (size.isdigit() and int(size)==n),'COMPLETE_HTTP_LENGTH')
                stream.flush();os.fsync(stream.fileno())
        except Exception as exc:error={'type':type(exc).__name__,'message':str(exc)}
        ref=None
        if path.exists() and path.stat().st_size>0:
            ref=I.data_pin(path,[self.out],check=lambda:self.budget.check(dispatch=False))
            if ref['bytes']!=n or ref['sha256']!=h.hexdigest():error={'type':'ValueError','message':'CLOSED_RESPONSE_ACTUAL_FD_BYTES_SHA_DIFFER'}
        if ref:self.refs.append(ref)
        event={'url':url,'HTTP_status':status,'headers':headers,'complete_EOF':complete,'error':error,'response_reference':ref,'automatic_retry':False}
        self.log.append(event);self.log.flush();self.cache[url]=event
        need(status==200 and complete and error is None and ref is not None,'OFFICIAL_RESPONSE_HOLD_NO_FALLBACK');return event
    def close(self):return {'request_intents':self.calls,'HTTP_open_function_invocations':self.opens,'actual_response_bytes':self.total,'stop_new_reason':self.stop,'evidence_reference':self.log.close(),'response_references':self.refs}

def read_body(ref,data,budget,roots=None):
    with I.held(positive(ref),roots or [Q.ROOT/'artifacts'],data) as (stream,_):budget.check();return stream.read()

def binding(case):
    hold=case['original_HOLD'];loc=hold['original_source_locator'];return {'hold_ordinal':case['hold_ordinal'],'original_source_locator':loc,'original_HOLD':hold}

def produce(plan,proof,budget,out):
    admit(plan,proof);budget.check();p,h,data,_,_=inputs(plan);need(all(ref in proof['request']['data_references'] for ref in data),'DECLARED_ORIGINAL_DATA_BEFORE_OPEN')
    from rdkit import Chem,rdBase
    need(rdBase.rdkitVersion=='2025.09.5','ORIGINAL_RDKIT_VERSION');out=Path(out);out.mkdir(parents=True,mode=0o700)
    ledger=I.Lines(out/'physical21_dispositions.DATA.jsonl',budget);overlay=I.Lines(out/'exact_composition_overlay.strict5.jsonl',budget);bounds=I.Lines(out/'lower_bound_constraints.DATA.jsonl',budget)
    cases=[];original=[];capture=Capture(p,out/'official',budget);counts=collections.Counter();unknown=0;ids=set();emitted=collections.Counter();atom_calls=collections.Counter()
    try:
        for value,_ in I.json_rows(p['exact_closed21_original_HOLD_DATA_reference'],budget):original.append(value['original'])
        for value,_ in I.json_rows(p['exact_closed21_diagnostic_DATA_reference'],budget):cases.append(value)
        need(len(cases)==len(original)==21 and [v['original_HOLD'] for v in cases]==original and [v['hold_ordinal'] for v in cases]==list(range(21)),'EXACT_CLOSED21_ORIGINAL_ROW_RESULT_BINDINGS')
        need(sum(exact_FAIL(v) for v in cases)==15,'PRECISE15_FAIL_WHITELIST_NOT_ALL_PARSE_FAILURES')
        need(collections.Counter(v['subdataset'] for v in cases)=={'ToxCast':15,'ClinTox':1,'PDBbind':5}
          and {v['original_index_event']['original_ID']['text'].lower() for v in cases if v['subdataset']=='PDBbind'}=={'1jou','2adj','1z9j','1pts','5oqt'},'EXACT_ORIGINAL21_SOURCE_AND_PDB_CASE_SCOPE')
        for case in cases:
            budget.check();record={'binding':binding(case),'original_identity_resolution':'UNKNOWN_UNCHANGED','new_exclusion_status':'HOLD','new_full_keys_QM_UFF_calls':0};identifier='case:%02d'%case['hold_ordinal']
            try:
                if exact_FAIL(case):
                    source=marker_binding(case);record.update(new_exclusion_status=p['invalid_marker_status'],exact_origin_source=source);counts['invalid_marker']+=1
                elif case['subdataset']=='ClinTox':
                    texts=case['original_identity_row']['smiles_variants'];need(len(texts)==1,'ONE_EXACT_DUMMY_SOURCE_VARIANT');bound,evidence=known_core(texts[0],Chem,atom_calls)
                    bounds.append({'rule_id':identifier,'dataset':'moleculenet','subdataset':'ClinTox','kind':'NON_H_ATOM_COUNT_LOWER_BOUND','bound':bound,'binding':binding(case),'evidence':evidence,'policy_reference':plan['policy_reference']});bounds.flush();record.update(new_exclusion_status='CONSERVATIVE_LOWER_BOUND_COVERED',evidence=evidence);counts['dummy_lower_bound']+=1
                else:
                    event=case['original_index_event'];pdb=event['original_ID']['text'].lower();need(event['source_id']=='pdbbind_general','EXACT_ORIGINAL_GENERAL_SOURCE')
                    if pdb in p['three_ion_annotations']:
                        need(annotation(case)==p['three_ion_annotations'][pdb],'EXACT_THREE_ION_RAW_ANNOTATIONS')
                        record.update(new_exclusion_status='CANDIDATE_DOMAIN_DISJOINT_X02',ion_annotation=p['three_ion_annotations'][pdb],candidate_domain_authority=plan['candidate_domain_authority']);counts['ion_domain_disjoint']+=1
                    elif pdb=='1pts':
                        need(annotation(case)=='7-mer','EXACT_ORIGINAL_SEVEN_MER_ANNOTATION')
                        ej=capture.get(URLS[-2]);pb=capture.get(URLS[-1]);entity=M.P.strict_json(read_body(ej['response_reference'],[ej['response_reference']],budget,[capture.out]))
                        bound,evidence=peptide_bounds(read_body(pb['response_reference'],[pb['response_reference']],budget,[capture.out]),entity,Chem.GetPeriodicTable())
                        bounds.append({'rule_id':identifier,'dataset':'moleculenet','subdataset':'PDBbind','kind':'NON_H_ATOM_COUNT_LOWER_BOUND','bound':bound,'binding':binding(case),'evidence':evidence,'official_references':[ej['response_reference'],pb['response_reference']],'policy_reference':plan['policy_reference']});bounds.flush();record.update(new_exclusion_status='CONSERVATIVE_LOWER_BOUND_COVERED',evidence=evidence);counts['peptide_lower_bound']+=1
                    elif pdb=='5oqt':
                        need(annotation(case)=='ARG','EXACT_ORIGINAL_ARG_ANNOTATION_NOT_ALA')
                        rows=[v['original']['event'] for v in case['HTTP_evidence'] if 'original' in v and v['original']['event']['url'].startswith('https://data.rcsb.org/graphql?')]
                        need(len(rows)==1 and rows[0]['HTTP_status']==200 and rows[0]['complete_EOF'] and rows[0]['error'] is None
                          and rows[0]['response_reference'] in h['original_HTTP_response_references'],'EXACT_CLOSED200_CURRENT5OQT_ENTRY')
                        native=M.P.strict_json(read_body(rows[0]['response_reference'],data,budget));entry=native['data']['entry'];need(entry['rcsb_id']=='5OQT' and native.get('errors') in (None,[]),'CURRENT_ENTRY_ID_AND_GRAPHQL_ERRORS')
                        existing=collections.defaultdict(list)
                        for value in entry['nonpolymer_entities']:
                            comp=value['nonpolymer_comp']['chem_comp'];existing[comp['id']].append((comp.get('formula'),rows[0]['response_reference']))
                        need(set(existing)==set(COMPONENTS[1:]),'ALL_CURRENT5OQT_COMPONENTS_EXACT_UNION_NOT_ARG_TO_ALA')
                        evidence=[]
                        for code in COMPONENTS:
                            formulas=existing.get(code,[])
                            if not formulas or any(not isinstance(f,str) or not f for f,_ in formulas):
                                captured=capture.get(URLS[COMPONENTS.index(code)]);body=M.P.strict_json(read_body(captured['response_reference'],[captured['response_reference']],budget,[capture.out]));comp=body['chem_comp'];need(comp['id']==code,'EXACT_CCD_ID');formulas=[*formulas,(comp['formula'],captured['response_reference'])]
                            usable=[(f,r) for f,r in formulas if isinstance(f,str) and f];need(usable,'NO_COMPONENT_COMPOSITION_HOLD')
                            for j,(formula,ref) in enumerate(usable):
                                composition=M.P.formula(formula,Chem);sid=M.P.locator('MoleculeNet','PDBbind','original_general27',event['original_index_ordinal'],event['original_ID'],code,j)
                                need(sid not in ids,'NO_OVERLAY_ALIAS');ids.add(sid);overlay.append(M.P.strict('PDBbind',sid,[],composition));overlay.flush();emitted['PDBbind']+=1
                                evidence.append({'CCD_id':code,'formula':formula,'composition':composition,'source_reference':ref,'original_ARG_or_current_component':'ORIGINAL_ANNOTATION' if code=='ARG' else 'CURRENT_ENTRY_POSSIBLE_COMPONENT'})
                        record.update(new_exclusion_status='CONSERVATIVE_ARG_AND_CURRENT_COMPONENT_UNION_COVERED',evidence=evidence,current_entry_ARG_match=False,original_pose_or_graph='UNKNOWN');counts['ARG_component_union']+=1
                    else:raise ValueError('UNREGISTERED_ORIGINAL_CASE_NO_GENERAL_EXCEPTION')
            except Exception as exc:
                unknown+=1;record.update(new_exclusion_status='HOLD',error_type=type(exc).__name__,error=str(exc));counts['HOLD']+=1
            ledger.append(record);ledger.flush()
        need(len(cases)==sum(counts.values()),'EXACT21_DISJOINT_DISPOSITION_MASS')
        expected={'invalid_marker':15,'ion_domain_disjoint':3,'dummy_lower_bound':1,'peptide_lower_bound':1,'ARG_component_union':1}
        complete=dict(counts)==expected;lr=ledger.close();br=bounds.close();er=overlay.close();network=capture.close()
        from . import consumer
        read_ledger=[v for v,_ in I.rows(positive(lr),lambda:budget.check(dispatch=False))]
        need(len(read_ledger)==21 and [r['binding']['hold_ordinal'] for r in read_ledger]==list(range(21)),'FULL21_DISPOSITION_FILE_READBACK')
        read_bounds=[]
        if br['rows']:
            for rule,_ in I.rows(positive(br),lambda:budget.check(dispatch=False)):
                consumer.vector(rule['bound']);need(rule['policy_reference']==plan['policy_reference'] and rule['binding'] in [r['binding'] for r in read_ledger],
                  'EXACT_WRITTEN_BOUND_CASE_POLICY_READBACK');read_bounds.append(rule)
        if er['rows']:I.readback(er,['all'],['PDBbind'],lambda:budget.check(dispatch=False))
        if complete:need(len(read_bounds)==2 and {r['subdataset'] for r in read_bounds}=={'ClinTox','PDBbind'},'BOTH_ACTUAL_TYPED_BOUNDS_DURABLE')
        result={'schema':'MOLNET21_CONSERVATIVE_CLOSURE_REPORT_V1','complete_exclusion_coverage_candidate':complete,'status':'ALL21_CONSERVATIVE_DISPOSITIONS_CANDIDATE_NOT_READY' if complete else 'REMAINING_CASE_HOLD',
          'cases':21,'disposition_counts':dict(counts),'remaining_exclusion_HOLD':unknown,'original_identity_UNKNOWN_cases':21,'original_graph_statuses_modified':False,
          'policy_reference':plan['policy_reference'],'base_receipt_reference':h['old_parent']['receipt'],'base_coverage_reference':h['old_parent']['coverage'],
          'base_strict5_reference':meta(h['old_parent']['receipt'])['result']['identities_reference'],'base_strict5_rows':806735,'physical_dispositions_reference':lr,
          'overlay_reference':er if er['rows'] else None,'lower_bound_reference':br if br['rows'] else None,'candidate_domain_authority':plan['candidate_domain_authority'],
          'network':network,'new_whole_original_SMILES_atom_table_calls':atom_calls['original_MolFromSmiles_invocations'],'new_full_keys_QM_UFF_calls':0,'all11_or_filtered_pool_or_READY_released':False}
        result['raw_artifacts']=C.unique([*meta(h['old_parent']['coverage'])['raw_artifacts'],*network['response_references'],
          positive(p['exact_closed21_diagnostic_DATA_reference']),positive(p['exact_closed21_original_HOLD_DATA_reference'])])
        result['own_output_readback']={'physical_dispositions':21,'typed_bounds':len(read_bounds),'strict5_overlay_rows':er['rows'],'original_identity_UNKNOWN_cases_unchanged':21}
        result['report_reference']=I.write(out/'closure_report.json',result,budget);return result
    finally:ledger.close();overlay.close();bounds.close();capture.close()

def fixtures(out):
    from . import test_v1
    test_v1.WORKSPACE=out;suite=unittest.defaultTestLoader.loadTestsFromTestCase(test_v1.Boundaries);need(suite.countTestCases()==3,'EXACT3_PRE_DATA_SOURCE_BOUNDARIES')
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite);value={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),
      'skips':len(r.skipped),'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':stream.getvalue(),'all_before_original_DATA_network_and_Budget':True}
    Q.write_new(out/'source3.json',value);need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'SOURCE3_FAILED_NO_DATA');return value

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args();plan=meta(Q.pin(a.plan));_,_,data,_,_=inputs(plan)
    argv=[Q.PY,'-B','-m',MODULE,'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
    expected=parameters(plan['node']);need(plan['scope_parameters']==expected,'EXACT_NODE_SPECIFIC_PARAMETERS')
    proof=require_startup(a.startup_proof,expected_kind='analysis',expected_scope_key=KEY,expected_scope_parameters=expected,expected_execution_argv=argv,expected_source=HERE/'closure.py',required_references=[Q.pin(a.plan),*plan['source_references']]);req=proof['request']
    need(plan['schema']=='MOLNET21_CONSERVATIVE_CLOSURE_PLAN_V1' and req['node']==plan['node'] and req['cpus']==16
      and req['pilot'] is False and req['wall_seconds']==plan['wall_seconds']==WALL and req['stage_output_cap_bytes']==req['estimated_peak_output_bytes']==plan['output_cap_bytes']==CAP
      and req['data_references']==plan['data_references']==data,'EXACT_GENERIC16_DAY2G_CLOSURE_SCOPE')
    review=meta(req['scope']['review']);need(review['exact21_conservative_evidence_validation_authorized'] is True and review['maximum_new_HTTPS_calls']==8
      and review['new_full_keys_QM_UFF_or_READY_release_authorized'] is False,'ROOT_SCOPE_SOURCE_VALIDATION_ONLY_NO_RELEASE')
    out=M.fresh(plan['output_directory'],'artifacts');need(Q.ROOT/'artifacts/expansion'/KEY in out.parents,'FRESH_OWN_CLOSURE_OUTPUT');out.mkdir(parents=True,mode=0o700)
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
    gate=fixtures(out);budget=Budget(plan,proof,out);budget.check(force=True)
    try:
        result=produce(plan,proof,budget,out/'evidence_v1');budget.check();Q.write_new(out/'receipt.json',{'schema':'MOLNET21_CONSERVATIVE_CLOSURE_RECEIPT_V1',
          'status':'CANDIDATE_EVIDENCE_CLOSED_PENDING_ROOT_C0_ADOPTION','job_id':str(proof['job_id']),'uid':1278,'node':req['node'],'endpoint':'202.38.247.57:22',
          'plan_reference':Q.pin(a.plan),'startup_proof_reference':Q.pin(a.startup_proof),'policy_reference':plan['policy_reference'],'fixtures':gate,'result':result,'READY_or_pool_release':False});return 0
    except BaseException as exc:I.write(out/'failure.DATA.json',{'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc(),'partial_and_cost_retained':True},budget);raise
    finally:budget.check(dispatch=False,force=True)

if __name__=='__main__':raise SystemExit(main())
