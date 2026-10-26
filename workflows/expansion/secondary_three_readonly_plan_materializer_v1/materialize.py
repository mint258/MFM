"""Alpha login metadata only. Draft is unapproved; finalize consumes Root's actual review.

No scientific body, scientific module, test, process launch or scheduler command is used.
"""
import argparse,copy,csv,io,json,sys
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q

HERE=Q.ROOT/'code/secondary_three_readonly_plan_materializer_v1'
FILES=('__init__.py','materialize.py','README.md','request_schema.json')
SCOPE7=Q.ROOT/'control/secondary_cpu_queue/storage_scope_v7_pubchem_uniform_index_copy_v1.json'
INSTALL={'path':str(Q.ROOT/'control/secondary_cpu_queue/pending_sb4_sb3_actual_source_installation_20261027_v1.json'),
 'bytes':32130,'sha256':'fe599157df150a192058d2f2b486a1748f3aca78ea927d9c5db9711217f2cf82'}
B_RECEIPT={'path':str(Q.ROOT/'artifacts/coconut_identity_norm_profile_v1/v1/receipt.json'),
 'bytes':39563,'sha256':'4271a20cf3e3b14e845ef9dde0bb2405c6c4450b13c9cbcfba9c81731607340e'}
TASKS=('pprime_print_intervals','csv_newline','csv_profile')
REVIEW_FIELDS=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','kind','pilot',
 'wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references','scope_mode','performance_profile')
DENIED={str(Q.ROOT/'artifacts/pprime_native72_readonly_v2/v1/native72_report.json'),
 str(Q.ROOT/'inputs/native72_v1/main/runs/data_v1_20261025/artifacts/vector_frame_audit/cpu_auto_memory_20261026_v1/frame_evaluation.json')}


def metadata_pin(path):
    path=Q.literal(path)
    Q.need(str(path) not in DENIED and path.suffix in {'.json','.py','.md','.txt','.sbatch'},'ONLY_EXPLICIT_SMALL_SOURCE_OR_METADATA')
    return Q.ref(path)


def metadata(reference,schema=None):
    Q.normalized(reference);Q.need(reference['path'] not in DENIED and Path(reference['path']).suffix=='.json','EXPLICIT_JSON_METADATA_NOT_SCIENTIFIC_BODY')
    value=Q.load_ref(reference)
    if schema is not None:Q.need(value['schema']==schema,'EXACT_METADATA_SCHEMA:'+schema)
    return value


def merge(*groups):
    found={}
    for group in groups:
        for r in group:
            Q.normalized(r);Q.need(r['path'] not in DENIED,'BODY_MUST_NOT_ENTER_SOURCE_OR_PARENT_SET')
            Q.need(r['path'] not in found or found[r['path']]==r,'CONFLICTING_METADATA_PIN');found[r['path']]=dict(r)
    return [found[p] for p in sorted(found)]


def locator(r):
    Q.need(isinstance(r,dict) and set(r)=={'path','bytes','sha256'} and type(r['bytes']) is int and r['bytes']>0
        and isinstance(r['sha256'],str) and len(r['sha256'])==64 and all(c in '0123456789abcdef' for c in r['sha256']),
        'PURE_PRODUCER_DATA_TRIPLE_ONLY')
    Q.literal(r['path']);DENIED.add(r['path'])  # No body stat, open, SHA, parse or transfer is implemented.


def actual_account(reference,job):
    path=Q.literal(reference['path']);Q.need(Q.ROOT/'control/secondary_cpu_queue' in path.parents
        and path.name.startswith('accounting_') and path.suffix=='.json','NAMED_ACTUAL_ACCOUNTING_METADATA_ONLY')
    value=metadata(reference,'SECONDARY_CPU_ACTUAL_ACCOUNTING_EVIDENCE_V1');p=value['actual_parent'];raw=value['raw_sacct_reference']
    Q.need(value['endpoint']==Q.ENDPOINT and value['uid']==1264 and value['query_returncode']==0 and p['JobIDRaw']==job
        and p['UID']=='1264' and p['State']=='COMPLETED' and p['ExitCode']=='0:0' and p['AllocCPUS']=='16'
        and p['NodeList'] in Q.NODES and p['Partition']=='cpu','ACTUAL_ALPHA_CPU16_C0_PARENT')
    Q.normalized(raw);Q.need(Path(raw['path']).suffix=='.txt' and raw['bytes']<=65536 and raw['path'] not in DENIED,'BOUNDED_RAW_SACCT_ONLY')
    text=Q.read_small(Q.verify(raw)).decode('utf-8','strict');rows=list(csv.DictReader(io.StringIO(text),delimiter='|'))
    rows=[r for r in rows if r.get('JobIDRaw')==job]
    Q.need(len(rows)==1 and all(rows[0][k]==p[k] for k in ('UID','State','ExitCode','ElapsedRaw','AllocCPUS','NodeList','Partition'))
        and int(p['ElapsedRaw'])>=0 and value['allocated_core_seconds_observed']==16*int(p['ElapsedRaw']),'ACTUAL_PARENT_RAW_STATE_AND_ALLOCATION_COST')
    return value,raw


def installed(namespace,count,receipt):
    prefix=str(Q.ROOT/'code'/namespace)+'/'
    selected=[row for row in receipt['observed'] if row['reference']['path'].startswith(prefix)]
    Q.need(len(selected)==count and len({row['reference']['path'] for row in selected})==count,'EXACT_INSTALLED_NAMESPACE_COUNT:'+namespace)
    refs=[]
    for row in selected:
        r=row['reference'];Q.need(row['actual_uid']==1264 and row['readback_size_SHA_verified'] is True
            and Path(r['path']).parent==Q.ROOT/'code'/namespace,'EXACT_PRIOR_SOURCE_INSTALLATION_OBSERVATION')
        Q.need(metadata_pin(r['path'])==r,'ACTUAL_INSTALLED_SOURCE_CHANGED');refs.append(r)
    return refs


def identity_context(request):
    Q.need(request['identity_profile_receipt_reference']==B_RECEIPT,'ACTUAL_COCONUT_B1884785_NOT_PUBCHEM_B')
    b=metadata(B_RECEIPT,'SECONDARY_COCONUT_IDENTITY_NORM_PROFILE_RECEIPT_V1')
    Q.need(b['status']=='SAMPLED_FROZEN_IDENTITY_KEY_OBSERVATIONS_COMPLETE' and b['job_id']=='1884785' and b['mode']=='profile'
        and b['endpoint']==Q.ENDPOINT and b['uid']==1264 and b['allocated_cpus']==16 and b['node'] in Q.NODES
        and b['observed_rows']==20000 and b['observed_rows_by_table']=={'molecules':10000,'entries':10000}
        and len(b['actual_nonempty_workers'])==16 and b['full_source_normalization_or_identity_acceptance'] is False
        and b['UFF_QM_or_pool_training_release'] is False and b['X_features_neutralization_tautomer_stereo_isotope_edits'] is False,
        'ACTUAL_B_SAMPLED_KERNEL_AUTHORITY_WITHOUT_GLOBAL_RELEASE')
    f=b['fixtures'];Q.need(f['tests_run']==3 and all(f[k]==0 for k in ('failures','errors','skips')) and f['before_A_body_IO'] is True,'ACTUAL_B_THREE_FIXTURES')
    bp=metadata(b['plan'],'SECONDARY_COCONUT_IDENTITY_NORM_PROFILE_PLAN_V1')
    for r in bp['data_references']:locator(r)
    proof=metadata(b['startup_proof'],'SECONDARY_COCONUT_IDENTITY_NORM_PROFILE_STARTUP_V1')
    account,raw=actual_account(request['identity_profile_accounting_reference'],'1884785')
    Q.need(bp['scope_key']=='coconut_identity_norm_profile_alpha_v1' and bp['endpoint']==Q.ENDPOINT and bp['uid']==1264 and bp['cpus']==16
        and bp['node']==b['node']==proof['node']==account['actual_parent']['NodeList'] and str(proof['job_id'])=='1884785'
        and proof['endpoint']==Q.ENDPOINT and proof['uid']==1264 and proof['plan_reference']==b['plan'],'B_ACTUAL_PLAN_PROOF_ACCOUNT_NODE')
    source=[r for r in bp['source_references'] if Path(r['path']).parent==Q.PACKAGE]
    Q.need({Path(r['path']).name for r in source}=={'__init__.py','adapters.py','common.py','controller.py','gate.py','probe.py','source_manifest.py','test_metadata.py'},'EXACT_FROZEN_BASE_EIGHT_SOURCE_FILES')
    core=[r for r in bp['source_references'] if Path(r['path']).parent==Q.ROOT/'code/secondary_coconut_identity_norm_profile_v1']
    Q.need({Path(r['path']).name for r in core}=={'__init__.py','contracts.py','runtime.py','run.py'},'EXACT_ACTUAL_B_FOUR_KERNEL_SOURCES')
    kernel=b['kernel_proof']['exact_transitive_source_references']
    Q.need(len(kernel)==5 and set(bp['frozen_identity_source_references'])=={'projection','common'}
        and all(r in bp['source_references'] for r in kernel) and all(r in kernel for r in bp['frozen_identity_source_references'].values()),'B_ACTUAL_FROZEN_IDENTITY_SOURCE_CLOSURE')
    authority=bp['resource_authority_reference'];cost=bp['cost_decision_reference'];Q.authority(authority['path'])
    value=metadata(cost,'USER_AUTHORIZED_ALLOCATION_OVERRUN_REPORT_CONTINUE_V1')
    Q.need(value['status']=='USER_AUTHORIZED' and value['on_overrun']=='REPORT_AND_CONTINUE' and value['scientific_quality_thresholds_unchanged'] is True,'COST_REPORT_CONTINUE_QUALITY_UNCHANGED')
    parents=merge(bp['parent_evidence_references'],[B_RECEIPT,b['plan'],b['startup_proof'],request['identity_profile_accounting_reference'],raw])
    return {'plan':bp,'sources':merge(source,core,kernel,[authority,cost]),'parents':parents,
        'known_parent_allocated_core_seconds':{'1884785':account['allocated_core_seconds_observed']}}


def csv_context(request,receipt,newline):
    sources=installed('secondary_moleculenet_csv6_identity_v1',11,receipt)
    from secondary_moleculenet_csv6_identity_v1 import contracts as C
    ar=metadata_pin(C.HERE/'format792_authority.json');a=metadata(ar,'ACTUAL792_SIX_CSV_PHYSICAL_IDENTITY_AUTHORITY_V1')
    Q.need(a['actual_job_id']=='1884792' and [s['source_id'] for s in a['sources']]==list(C.IDS),'ACTUAL792_SIX_CSV_AUTHORITY')
    data=[s['payload_reference'] for s in a['sources']]
    for r in data:locator(r)
    old=metadata(a['format_receipt_reference'],'MISSING11_IDENTITY_INPUT_FORMAT_PROFILE_RECEIPT_V1')
    plan=metadata(a['format_plan_reference']);proof=metadata(a['format_proof_reference'])
    account,raw=actual_account(request['format_accounting_reference'],'1884792')
    Q.need(old['status']=='FORMAT_METADATA_PROFILE_COMPLETE_IDENTITY_ACCEPTANCE_PENDING' and old['job_id']=='1884792'
        and old['endpoint']==Q.ENDPOINT and old['uid']==1264 and old['node']==plan['node']==proof['node']==account['actual_parent']['NodeList']
        and old['plan_reference']==a['format_plan_reference'] and old['startup_proof_reference']==a['format_proof_reference']
        and plan['scope_key']=='moleculenet_missing11_identity_format_probe_alpha_v1' and str(proof['job_id'])=='1884792','ACTUAL792_FORMAT_PARENT_CLOSURE')
    tests=metadata(old['fixtures_reference']);Q.need(tests['status']=='PASS' and tests['counts']=={'run':8,'failures':0,'errors':0,'skips':0,'expected_failures':0,'unexpected_successes':0},'ACTUAL792_ORIGINAL_EIGHT_FIXTURES')
    sources=merge(sources,a['frozen_helper_source_references'],[tests['source_reference']],
        [s['format_report_reference'] for s in a['sources']])
    parents=merge([a['format_receipt_reference'],a['format_plan_reference'],a['format_proof_reference'],old['fixtures_reference'],request['format_accounting_reference'],raw])
    if newline:
        sources=merge(sources,installed('secondary_csv6_newline_diagnosis_v1',9,receipt))
        from secondary_csv6_newline_diagnosis_v1 import contracts as N
        spec=N.MODES['newline_diagnosis'];params=N.parameters('newline_diagnosis');module=N.MODULE;mode='newline_diagnosis'
    else:spec=C.MODES['profile'];params=C.parameters('profile');module=C.MODULE;mode='profile'
    return spec,params,module,data,sources,parents,{'mode':mode,'format_authority_reference':ar,
        'format_accounting_reference':request['format_accounting_reference']},{'1884792':account['allocated_core_seconds_observed']}


def build(request_path,out):
    request_path=Q.literal(request_path);Q.need(Q.ROOT/'control' in request_path.parents,'CONTROL_REQUEST_METADATA_ONLY')
    request_ref=metadata_pin(request_path);request=metadata(request_ref,'THREE_FIXED_READONLY_PLAN_REQUEST_V1')
    Q.need(request['status']=='REQUESTED_FOR_ROOT_REVIEW' and request['requested_by']=='root' and request['task'] in TASKS
        and request['endpoint']==Q.ENDPOINT and request['uid']==1264 and request['node'] in Q.NODES,'EXPLICIT_ROOT_DRAFT_REQUEST_ONLY')
    own=[metadata_pin(HERE/name) for name in FILES]
    Q.need(len(request['generator_source_references'])==len(own) and merge(request['generator_source_references'])==merge(own),'EXACT_REQUESTED_GENERATOR_SOURCES')
    Q.need(request['source_installation_reference']==INSTALL,'EXACT_ACTUAL71_INSTALLATION_RECEIPT')
    installation=metadata(INSTALL,'ACTUAL_ALPHA_NEW71_SOURCE_INSTALLATION_V1')
    Q.need(installation['status']=='EXACT71_SOURCE_BYTES_INSTALLED_AST_PASS_NOT_FIXTURE_OR_SCIENCE_ACCEPTANCE'
        and installation['endpoint']==Q.ENDPOINT and installation['uid']==1264 and len(installation['observed'])==71
        and installation['scientific_bodies_included'] is False and installation['new_jobs_submitted'] is False,'ACTUAL_SOURCE_INSTALLATION_NOT_SCIENCE_PASS')
    ctx=identity_context(request);bp=ctx['plan'];task=request['task'];wall=request['wall_seconds']
    if task=='pprime_print_intervals':
        source=installed('native72_print_intervals_alpha_v1',8,installation)
        source=merge(source,installed('secondary_cpu_readonly_queue_v15',2,installation))
        from native72_print_intervals_alpha_v1 import contract as C
        from secondary_cpu_readonly_queue_v15 import adapters as A
        for r in C.DATA:locator(r)
        data=copy.deepcopy(C.DATA);params=copy.deepcopy(C.SCOPE);module=C.MODULE
        spec={'key':C.KEY,'plan':C.PLAN,'proof':C.PROOF,'stage':C.STAGE,'pilot':False,'performance_profile':False,
            'scope_mode':'BOUNDED_READONLY_ANALYSIS','cap':32<<20,'wall_max':600}
        source=merge(source,[C.CONFIG,C.SMALL_SUMMARY],C.OLD_HELPERS,C.PREVIOUS_HELPERS)
        parents=merge([C.SMALL_SUMMARY,A.PARENT_PLAN,A.PARENT_PROOF,A.PARENT_ACCOUNT,A.PARENT_RAW,A.PARENT_REVIEW])
        extra={};costs={'1884773':actual_account(A.PARENT_ACCOUNT,'1884773')[0]['allocated_core_seconds_observed']}
        Q.need(wall==600,'FIXED600_SECOND_PRINT_INTERVAL_DIAGNOSIS')
    else:
        spec,params,module,data,source,parents,extra,costs=csv_context(request,installation,task=='csv_newline')
        queue='secondary_cpu_readonly_queue_v15' if task=='csv_newline' else 'secondary_cpu_readonly_queue_v12'
        source=merge(source,installed(queue,2,installation))
        if task=='csv_newline':Q.need(wall==1800,'FIXED1800_SECOND_NEWLINE_DIAGNOSIS')
    Q.need(type(wall) is int and 0<wall<=spec['wall_max'] and wall%60==0,'EXACT_WHOLE_MINUTE_WALL')
    scope=metadata_pin(SCOPE7);metadata(scope)
    sources=merge(source,ctx['sources'],own,[INSTALL,scope,request_ref]);parents=merge(parents,ctx['parents'])
    for r in sources+parents:Q.need(metadata_pin(r['path'])==r,'CURRENT_SMALL_SOURCE_OR_PARENT_CHANGED')
    output=Q.literal(request['output_directory']);proof=Q.literal(request['startup_proof_path'])
    Q.need(Q.ROOT/'artifacts' in output.parents and not output.exists() and Q.ROOT/'control/secondary_startup' in proof.parents
        and not proof.exists() and not proof.with_suffix(proof.suffix+'.controller_ready.json').exists(),'NEW_OUTPUT_AND_STARTUP_PROOF_ONLY')
    out=Q.literal(out);Q.need(Q.ROOT/'control' in out.parents,'METADATA_PLAN_CONTROL_LEAF_ONLY')
    plan_path=out/'plan.json';argv=[bp['python'],'-B','-m',module,'--plan',str(plan_path),'--startup-proof',str(proof)]
    plan={'schema':spec['plan'],'producer_key':spec['key'],'scope_key':spec['key'],'stage':spec['stage'],'scope_parameters':params,
        'kind':'analysis','pilot':spec['pilot'],'scope_mode':spec['scope_mode'],'performance_profile':spec['performance_profile'],
        'endpoint':Q.ENDPOINT,'uid':1264,'run_root':str(Q.ROOT),'node':request['node'],'cpus':16,'memory_policy':Q.POLICY,
        'wall_seconds':wall,'output_cap_bytes':spec['cap'],'python':bp['python'],'execution_argv':argv,'data_references':data,
        'source_references':sources,'parent_evidence_references':parents,'resource_authority_reference':bp['resource_authority_reference'],
        'cost_decision_reference':bp['cost_decision_reference'],'root_review_reference':None,'startup_proof_path':str(proof),
        'output_directory':str(output),'storage_scope_review_reference':scope,'metadata_source_installation_reference':INSTALL,
        'metadata_request_reference':request_ref,'metadata_generator_source_references':own,**extra}
    if task=='csv_profile':plan['frozen_identity_source_references']=copy.deepcopy(bp['frozen_identity_source_references'])
    review={k:copy.deepcopy(plan[k]) for k in REVIEW_FIELDS}
    review.update(schema='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1',status='PENDING_ROOT_REVIEW',reviewer=None,
        approved_source_references=copy.deepcopy(sources),storage_scope_review_reference=scope,
        original_quality_thresholds_unchanged=True,global_pool_or_full_or2000_release_authorized=False)
    known=dict(ctx['known_parent_allocated_core_seconds']);known.update(costs)
    return plan,review,{'known_parent_allocated_core_seconds':known,'scope':'THESE_LISTED_ACTUAL_ANCESTORS_ONLY_NOT_COMPLETE_DATA_LINE_COST',
        'cost_action':'REPORT_AND_CONTINUE','new_stage_actual_cost':'PENDING_NOT_RUN','quality_thresholds_unchanged':True}


def draft(request_path,out):
    out=Q.literal(out);Q.need(not out.exists(),'NEW_DRAFT_CONTROL_LEAF_ONLY')
    plan,review,cost=build(request_path,out);out.mkdir(parents=True,mode=0o700,exist_ok=False)
    Q.write_new(out/'plan_fields.json',{'schema':'UNAPPROVED_THREE_FIXED_READONLY_PLAN_FIELDS_V1','status':'NOT_EXECUTABLE_ROOT_REVIEW_PENDING','plan_fields':plan})
    Q.write_new(out/'root_review.template.json',review)
    Q.write_new(out/'transfer_requirements.json',{'schema':'THREE_FIXED_READONLY_LOCATOR_REQUIREMENTS_V1','status':'LOCATORS_ONLY_NOT_A_TRANSFER_VERIFICATION',
        'source_metadata_references':merge(plan['source_references'],plan['parent_evidence_references']),
        'data_references_producer_pins_only':plan['data_references'],'source_installation_receipt_reference':INSTALL,
        'data_bodies_opened_hashed_parsed_or_transferred_by_generator':False,'CPU_fixture_and_body_checks_still_required':True})
    Q.write_new(out/'draft_receipt.json',{'schema':'THREE_FIXED_READONLY_PLAN_DRAFT_RECEIPT_V1','status':'DRAFT_ONLY_ROOT_REVIEW_PENDING',
        'request_reference':plan['metadata_request_reference'],'draft_directory':str(out),'plan_fields_reference':metadata_pin(out/'plan_fields.json'),
        'review_template_reference':metadata_pin(out/'root_review.template.json'),'transfer_requirements_reference':metadata_pin(out/'transfer_requirements.json'),
        'known_cost_metadata':cost,'no_root_approval_generated':True,'no_startup_proof_or_job_or_science_PASS_generated':True})
    return metadata_pin(out/'draft_receipt.json')


def finalize(draft_path,review_path):
    draft_ref=metadata_pin(draft_path);d=metadata(draft_ref,'THREE_FIXED_READONLY_PLAN_DRAFT_RECEIPT_V1')
    Q.need(d['status']=='DRAFT_ONLY_ROOT_REVIEW_PENDING','EXACT_UNAPPROVED_DRAFT_ONLY');out=Q.literal(d['draft_directory'])
    Q.need(out==Path(draft_path).parent and not (out/'plan.json').exists() and not (out/'materialization_receipt.json').exists(),'FRESH_FINAL_PLAN_AND_RECEIPT_FILES')
    fields=metadata(d['plan_fields_reference'],'UNAPPROVED_THREE_FIXED_READONLY_PLAN_FIELDS_V1')
    template=metadata(d['review_template_reference']);metadata(d['transfer_requirements_reference'])
    plan,expected,cost=build(d['request_reference']['path'],out)
    Q.need(metadata_pin(d['request_reference']['path'])==d['request_reference'] and fields['plan_fields']==plan and template==expected,'DRAFT_CONTEXT_OR_ACTUAL_SOURCE_CHANGED')
    review_ref=metadata_pin(review_path);Q.need(review_ref!=d['review_template_reference'],'ROOT_MUST_SUPPLY_INDEPENDENT_REVIEW_FILE')
    review=metadata(review_ref,'EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1')
    Q.need(review['status']=='APPROVED_FOR_EXACT_STAGE' and review['reviewer']=='root','ACTUAL_ROOT_APPROVAL_REQUIRED_NOT_GENERATED_HERE')
    for k in REVIEW_FIELDS:Q.need(review[k]==expected[k],'ROOT_REVIEW_DIFFERS_FROM_EXACT_DRAFT:'+k)
    for k in ('approved_source_references','storage_scope_review_reference','original_quality_thresholds_unchanged','global_pool_or_full_or2000_release_authorized'):
        Q.need(review[k]==expected[k],'ROOT_REVIEW_SOURCE_STORAGE_OR_QUALITY_DIFFERS:'+k)
    plan['root_review_reference']=review_ref;Q.write_new(out/'plan.json',plan)
    if plan['scope_key']=='moleculenet_csv6_identity_norm_profile_alpha_v1':
        from secondary_cpu_readonly_queue_v12 import adapters as adapter
    else:
        from secondary_cpu_readonly_queue_v15 import adapters as adapter
    accepted=adapter.readonly(out/'plan.json',None,plan['node'],plan['wall_seconds'])
    Q.write_new(out/'materialization_receipt.json',{'schema':'THREE_FIXED_READONLY_PLAN_MATERIALIZATION_RECEIPT_V1',
        'status':'ROOT_REVIEW_CONSUMED_PLAN_METADATA_ADAPTER_ACCEPTED_NO_JOB_SUBMITTED','plan_reference':metadata_pin(out/'plan.json'),
        'actual_root_review_reference':review_ref,'draft_receipt_reference':draft_ref,'source_installation_reference':INSTALL,
        'adapter_scope_key':accepted['scope_key'],'data_body_hashes_or_fixtures_or_science_acceptance_claimed':False,
        'startup_proof_or_job_created':False,'known_cost_metadata':cost,'full_or2000_or_pool_release_authorized':False})
    return metadata_pin(out/'materialization_receipt.json')


def main():
    Q.login();Q.need(Path(__file__).absolute()==HERE/'materialize.py' and Path(sys.modules['__main__'].__file__).absolute()==HERE/'materialize.py','EXACT_DEPLOYED_METADATA_PRIMARY')
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('draft');p.add_argument('--request',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p=sub.add_parser('finalize');p.add_argument('--draft',required=True,type=Path);p.add_argument('--root-review',required=True,type=Path)
    args=parser.parse_args();r=draft(args.request,args.output) if args.action=='draft' else finalize(args.draft,args.root_review)
    print(json.dumps({'actual_metadata_output_reference':r,'jobs_submitted':False,'scientific_bodies_read':False},sort_keys=True),flush=True)


if __name__=='__main__':main()
