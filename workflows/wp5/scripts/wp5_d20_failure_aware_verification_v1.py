"""Narrow D20 failure-aware QC derivation from original full readback plus exact957 proof.
No QM; original SCI,3181-file report,957QC, status/count/distribution bytes remain untouched.
"""
from pathlib import Path
import argparse,collections,concurrent.futures,copy,hashlib,importlib.util,json,math,os,re,socket,stat,struct,time
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011');F=ROOT/'acceptance/final_20261016_v1'
SCOPE=F/'D20_failure_aware_scope_prepared_v1.json';SCOPE_SHA='0decacdd2aca8024c9c894e055d2af3e82d612126ec8049a15c155ae8cc34d59'
REQUIRED_FAILURE_ISSUES={'D20_VALUES_MISSING_OR_INVALID_LENGTH','D20_MASK_MISSING_OR_INVALID_LENGTH_OR_TYPE','D20_DESCRIPTOR_NAMES_MISSING_OR_INVALID_LENGTH'}
READ_COLUMNS=['record_id','molecule_id','file_group','attempt_id','job_id','task_id','schema_ref','descriptor_names','values_float64','valid_mask','status','issues']
def require(x,message):
    if not x:raise ValueError(message)
def ref(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(8<<20),b''):h.update(block)
    return {'path':str(p),'bytes':Path(p).stat().st_size,'sha256':h.hexdigest()}
def checked(r,load=False):
    actual=ref(r['path']);require(actual['sha256']==r['sha256'] and ('bytes' not in r or actual['bytes']==r['bytes']),'BOUND_SOURCE_CHANGED:'+r['path']);return json.loads(Path(r['path']).read_text()) if load else None
def identity(p):
    x=Path(p).lstat();return {'device':x.st_dev,'inode':x.st_ino,'uid':x.st_uid,'mode':x.st_mode,'nlink':x.st_nlink,'bytes':x.st_size,'mtime_ns':x.st_mtime_ns}
def stable(p,old):require(identity(p)==old,'FILE_CHANGED_DURING_TARGETED_READ:'+str(p))
def safe(value):
    if isinstance(value,float) and not math.isfinite(value):return {'nonfinite_float64_bits':struct.pack('>d',value).hex()}
    if isinstance(value,dict):return {k:safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [safe(v) for v in value]
    return value
def write(p,value):
    with p.open('x') as f:json.dump(safe(value),f,indent=2,allow_nan=False);f.write('\n')
def key(row):return (row['molecule_id'],row['attempt_id'],row['job_id'],row['task_id'])
def failure_rule(row):
    reasons=[];names=row.get('descriptor_names');values=row.get('values_float64');mask=row.get('valid_mask');issues=row.get('issues')
    if row.get('status')!='PROPERTY_FAILED':reasons.append('STATUS_NOT_EXPLICIT_PROPERTY_FAILED')
    if names is not None and names!=[]:reasons.append('NONEMPTY_DESCRIPTOR_NAMES_NOT_EXEMPTED')
    if not isinstance(values,list) or len(values)!=20 or any(v is not None for v in values):reasons.append('VALUES_NOT_EXACT20_NULL')
    if not isinstance(mask,list) or len(mask)!=20 or any(type(v) is not bool or v is not False for v in mask):reasons.append('MASK_NOT_EXACT20_BOOL_FALSE')
    if row.get('schema_ref') not in (None,'C4_D20_D3D_REGISTRY_V1'):reasons.append('UNKNOWN_DESCRIPTOR_SCHEMA_REFERENCE')
    if not isinstance(issues,list) or not all(isinstance(v,str) and v.strip() for v in issues) or not REQUIRED_FAILURE_ISSUES<=set(issues or []):reasons.append('EXPLICIT_PRODUCER_FAILURE_ISSUE_CHAIN_MISSING')
    else:
        extras=[v for v in issues if v not in REQUIRED_FAILURE_ISSUES]
        if any(re.match(r'^[A-Za-z_][A-Za-z_0-9]*(?:Error|Exception):\s*\S',v) is None for v in extras):reasons.append('UNKNOWN_ADDITIONAL_FAILURE_ISSUE_REPRESENTATION')
    return {'accepted_declared_property_failure':not reasons,'remaining_serious_reasons':reasons,'classification':'D20_DECLARED_PROPERTY_FAILURE_WITH_NO_DESCRIPTOR_VALUES' if not reasons else 'UNRESOLVED_SERIOUS_D20_NAME_SCHEMA_ISSUE','original_status':row.get('status'),'failure_cause_scope':'Persisted explicitD20 failure codes + frozen producer fallback contract; exception text included only if actually persisted, never invented.'}
def semantic_boundaries(base_row=None):
    base=copy.deepcopy(base_row) if base_row is not None else {'status':'PROPERTY_FAILED','descriptor_names':None,'values_float64':[None]*20,'valid_mask':[False]*20,'schema_ref':None,'issues':sorted(REQUIRED_FAILURE_ISSUES)};require(failure_rule(base)['accepted_declared_property_failure'],'LEGAL_EXPLICIT_NULL_FAILURE_REJECTED');empty=copy.deepcopy(base);empty['descriptor_names']=[];require(failure_rule(empty)['accepted_declared_property_failure'],'LEGAL_EMPTY_NAMES_REJECTED')
    cases={'SUCCESS':('status','SUCCESS'),'unknown_status':('status','UNKNOWN'),'other_failure':('status','TIMEOUT'),'wrong_nonempty_names':('descriptor_names',['wrong']*20),'numeric_zero_values':('values_float64',[0.0]*20),'partial_values':('values_float64',[None]*19+[1.0]),'wrong_mask_type':('valid_mask',[0]*20),'true_mask':('valid_mask',[False]*19+[True]),'short_mask':('valid_mask',[False]*19),'missing_issues':('issues',[]),'missing_one_marker':('issues',[v for v in base['issues'] if v!='D20_DESCRIPTOR_NAMES_MISSING_OR_INVALID_LENGTH']),'unknown_extra_issue':('issues',sorted(REQUIRED_FAILURE_ISSUES)+['UNKNOWN_HEADER']),'unknown_schema_ref':('schema_ref','UNKNOWN')}
    for name,(field,value) in cases.items():
        row=copy.deepcopy(base);row[field]=value;require(not failure_rule(row)['accepted_declared_property_failure'],'SEMANTIC_BOUNDARY_ACCEPTED:'+name)
    return {'status':'D20_FAILURE_RULE_SEMANTIC_BOUNDARIES_PASS','accepted_known_failure_forms':2,'rejected_cases':sorted(cases),'real_failure_row_copied':base_row is not None,'real_record_id':base_row.get('record_id') if base_row else None,'all_negative_cases_in_memory_only':True,'original_science_row_mutated':False}
def read_affected_file(item):
    import pyarrow as pa,pyarrow.dataset as ds,pyarrow.parquet as pq,wp5_parquet_v2 as wire
    pa.set_cpu_count(1);pa.set_io_thread_count(1);file_ref,wanted=item;p=Path(file_ref['path']);before=identity(p);require(stat.S_ISREG(before['mode']) and before['uid']==1278 and before['bytes']==file_ref['bytes'],'AFFECTED_D20_FILE_TYPE_OWNER_OR_SIZE_DIFFERS');require(ref(p)=={k:file_ref[k] for k in ('path','bytes','sha256')},'AFFECTED_D20_SHA_DIFFERS_FROM_FULL_VERIFIER');require(pq.ParquetFile(p).schema_arrow.remove_metadata().equals(wire.D20_SCHEMA.remove_metadata()),'AFFECTED_D20_ARROW_SCHEMA_CHANGED')
    table=ds.dataset(str(p),format='parquet').to_table(filter=ds.field('record_id').isin([r['record_id'] for r in wanted]),columns=READ_COLUMNS,use_threads=False);rows=table.to_pylist();stable(p,before);require(len(rows)==len(wanted) and len({r['record_id'] for r in rows})==len(rows),'EXACT_SELECTED_D20_ROW_CARDINALITY_DIFFERS');byid={r['record_id']:r for r in rows};selected=[]
    for issue in wanted:
        row=byid[issue['record_id']];require(row['molecule_id']==issue['molecule_id'] and row['status']==issue['status'],'EXACT_ORIGINAL_ISSUE_ROW_IDENTITY_DIFFERS');selected.append({'original_issue':issue,'D20_row':row,'rule':failure_rule(row)})
    return {'path':str(p),'full_verifier_file_reference':file_ref,'actual_D20_file_SHA_rechecked':True,'identity_before_and_after_selected_read':before,'limited_columns':READ_COLUMNS,'rows':selected,'worker_pid':os.getpid(),'other_families_or_QM_read':False}
def main(a):
    require(os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-17','EXACT_NODE17_UID1278_REQUIRED');require(os.environ.get('SLURM_JOB_ID','').isdigit() and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))>=24,'24CPU_SLURM_REQUIRED');require(a.out.is_absolute() and a.out.parent==F and not a.out.exists(),'FRESH_OWN_FINAL_OUTPUT_REQUIRED');require(ref(SCOPE)['sha256']==SCOPE_SHA,'EXACT_D20_SCOPE_CHANGED');scope=json.loads(SCOPE.read_text());fixture=None
    for field in ('engine3','wire2','runner10','runner14','protocol','frozen_D20_D3_source'):checked(scope[field])
    diagnostic=checked(scope['diagnostic598'],True);report=checked(scope['sources']['original_verification_report'],True);catalog=checked(scope['sources']['closed_catalog'],True);checked(scope['sources']['frozen_verifier']);checked(scope['sources']['original_issue_parquet']);all957=checked(scope['all957_json'],True)
    require(report['status']=='NOT_PASS' and report['schema_qc_issue_rows']==report['serious_schema_issue_rows']==957 and report['file_exceptions']==[] and report['latest_closed'] is True and report['effective_workers']>=24 and catalog['status']=='CLOSED','ORIGINAL_FULL_READBACK_AND957_GATE_DIFFERS');require(report['bindings']['catalog_sha256']==scope['sources']['closed_catalog']['sha256'] and report['bindings']['script_sha256']==scope['sources']['frozen_verifier']['sha256'],'ORIGINAL_BINDING_DIFFERS')
    import pyarrow as pa,pyarrow.dataset as ds,pyarrow.parquet as pq
    pa.set_cpu_count(1);pa.set_io_thread_count(1);issues_table=pq.read_table(scope['sources']['original_issue_parquet']['path'],use_threads=False);issues=issues_table.to_pylist();require(issues==all957['rows'] and len(issues)==957 and len({r['record_id'] for r in issues})==957,'ORIGINAL957_ROWS_OR_FULL_LIST_CHANGED');require(all(r['issue']=='D20_NAME_SCHEMA_INVALID' and r['status']=='PROPERTY_FAILED' and r['field'] is None and r['calc_type'] is None for r in issues),'NON_D20_OR_NON_FAILURE_ISSUE_NOT_EXEMPTED')
    oldfiles={r['path']:r for r in report['files_verified']};catfiles={r['path']:r for r in catalog['artifacts']};require(set(oldfiles)==set(catfiles) and len(oldfiles)==len(report['files_verified'])==3181,'ORIGINAL3181_ARTIFACT_SET_DIFFERS')
    for p in oldfiles:require(all(oldfiles[p][k]==catfiles[p][k] for k in ('path','sha256','bytes')),'FULL_READBACK_CATALOG_ARTIFACT_REFERENCE_DIFFERS')
    grouped=collections.defaultdict(list)
    for row in issues:grouped[row['path']].append(row)
    require(len(grouped)==len(scope['path_groups']) and {p:len(v) for p,v in grouped.items()}=={r['key']:r['count'] for r in scope['path_groups']},'EXACT_AFFECTED_D20_PATH_GROUPS_CHANGED');require(all(oldfiles[p]['family']=='D20' and catfiles[p]['family']=='D20' and Path(p).name=='D20.parquet' for p in grouped),'ONLY_AFFECTED_D20_FAMILY_FILES_ALLOWED')
    with concurrent.futures.ProcessPoolExecutor(max_workers=24) as pool:parts=list(pool.map(read_affected_file,[(oldfiles[p],rows) for p,rows in sorted(grouped.items())],chunksize=1))
    selected=[row for part in parts for row in part['rows']];require(len(selected)==957,'EXACT957_TARGETED_ROWS_NOT_CLOSED');molecules={r['D20_row']['molecule_id'] for r in selected};require(len(molecules)==323,'EXACT323_MOLECULE_SCOPE_CHANGED');latest=Path(catalog['latest_molecules']);latest_before=identity(latest);lookup=ds.dataset(str(latest),format='parquet').to_table(filter=ds.field('molecule_id').isin(sorted(molecules)),columns=['molecule_id','attempt_id','job_id','task_id','receipt_context_consistent','export_published'],use_threads=False).to_pylist();stable(latest,latest_before);require(len(lookup)==323 and len({r['molecule_id'] for r in lookup})==323 and all(r['receipt_context_consistent'] and r['export_published'] for r in lookup),'CLOSED323_LATEST_MOLECULE_AUTHORITY_DIFFERS');current={r['molecule_id']:r for r in lookup}
    legal_rows=[r['D20_row'] for r in selected if r['rule']['accepted_declared_property_failure']];fixture=semantic_boundaries(legal_rows[0] if legal_rows else None)
    classifications=[];remaining=[]
    for row in selected:
        data=row['D20_row'];is_latest=key(data)==key(current[data['molecule_id']]);row['is_latest_canonical_molecule_context']=is_latest;row['canonical_latest_context']=current[data['molecule_id']];classifications.append({**row['original_issue'],**row['rule'],'is_latest_canonical_molecule_context':is_latest,'attempt_id':data['attempt_id'],'job_id':data['job_id'],'task_id':data['task_id']})
        if not row['rule']['accepted_declared_property_failure']:remaining.append(row['original_issue'])
    for field in ('original_verification_report','closed_catalog','frozen_verifier','original_issue_parquet'):checked(scope['sources'][field])
    a.out.mkdir();write(a.out/'rule_semantic_fixture.json',fixture);write(a.out/'D20_all957_targeted_rows.json',{'rows':selected,'original_D20_status_values_and_masks_preserved':True,'nonfinite_unknown_values_json_encoding':'Explicit float64 bits, never imputed to zero'});pq.write_table(pa.Table.from_pylist(classifications),a.out/'schema_qc_classifications.parquet',compression='zstd');pq.write_table(pa.Table.from_pylist(remaining,schema=issues_table.schema),a.out/'remaining_serious_schema_qc_issues.parquet',compression='zstd')
    accepted=957-len(remaining);evidence={'schema':'WP5_D20_FAILURE_AWARE_EXACT957_TARGETED_EVIDENCE_V1','status':'ALL957_EXPLICIT_PRODUCER_FAILURE_REPRESENTATIONS_CONFIRMED' if not remaining else 'UNKNOWN_D20_REPRESENTATIONS_REMAIN_SERIOUS','created_epoch':time.time(),'actual_job_id':os.environ['SLURM_JOB_ID'],'node':socket.gethostname(),'source':ref(__file__),'scope':ref(SCOPE),'original_full_readback_report':scope['sources']['original_verification_report'],'original_full_verifier_source':scope['sources']['frozen_verifier'],'original_issue_parquet':scope['sources']['original_issue_parquet'],'diagnostic598':scope['diagnostic598'],'targeted_files':[{k:v for k,v in p.items() if k!='rows'} for p in parts],'targeted_D20_file_count':len(parts),'targeted_requested_workers':24,'targeted_effective_worker_pids':sorted({p['worker_pid'] for p in parts}),'exact_targeted_rows':957,'exact_targeted_molecules':323,'accepted_declared_property_failure_rows':accepted,'unknown_serious_rows':len(remaining),'latest_context_counts':dict(collections.Counter(str(r['is_latest_canonical_molecule_context']) for r in selected)),'persisted_failure_issue_counts':dict(collections.Counter(v for r in selected for v in r['D20_row']['issues'] or [])),'latest323_index_read':{'path':str(latest),'identity_before_after':latest_before,'filtered_molecule_count':323,'full_index_not_rehashed':True,'authority_basis':'ExactSHA-bound closedcatalog index path and original full verification; selected receipt/export flags and4-part latest key checked here'},'all957_targeted_rows':ref(a.out/'D20_all957_targeted_rows.json'),'classification_table':ref(a.out/'schema_qc_classifications.parquet'),'remaining_serious_table':ref(a.out/'remaining_serious_schema_qc_issues.parquet'),'rule_semantic_fixture':ref(a.out/'rule_semantic_fixture.json'),'full3181_proof_reused_not_rerun':True,'other_family_bodies_read':False,'QM_calls':0,'SCI_or_queue_or_old_reports_changed':False};write(a.out/'targeted_evidence.json',evidence)
    inherited=[]
    for name in ('field_missingness.parquet','task_status_distribution.parquet','label_scalar_distributions.parquet','schema_array_qc_issues.parquet'):
        old=Path(scope['sources']['original_verification_report']['path']).parent/name;oldref=ref(old);(a.out/name).symlink_to(os.path.relpath(old,a.out));require((a.out/name).resolve()==old.resolve(),'ORIGINAL_STATISTICS_RELATIVE_LINK_TARGET_DIFFERS');inherited.append({'name':name,'original':oldref,'new_relative_symlink':str(a.out/name),'bytes_or_counts_rewritten':False})
    derived=copy.deepcopy(report);derived.update(status='PASS' if not remaining else 'NOT_PASS',serious_schema_issue_rows=len(remaining),original_full_verifier_status='NOT_PASS',original_serious_schema_issue_rows=957,recorded_D20_property_failure_qc_rows=accepted,verification_basis='ORIGINAL3181_FULL_SHA_ARRAY_RAW_READBACK_PLUS_EXACT957_D20_FAILURE_AWARE_TARGETED_CLASSIFICATION',new_program_repeated_full_population_readback=False,derived_source=ref(__file__),derived_scope=ref(SCOPE),original_full_verification_report=scope['sources']['original_verification_report'],targeted_D20_evidence=ref(a.out/'targeted_evidence.json'),targeted_classification_table=ref(a.out/'schema_qc_classifications.parquet'),remaining_serious_issue_table=ref(a.out/'remaining_serious_schema_qc_issues.parquet'),inherited_original_statistics_and_QC=inherited,original_status_distribution_missingness_counts_and_957_QC_preserved=True,descriptor_failure_status_or_values_changed=False,success_rule_or_unknown_failure_exemption_relaxed=False,new_QM_calls=0,original_data_written=False)
    require(derived['schema_qc_issue_rows']==957 and derived['files_verified']==report['files_verified'] and derived['latest_qm_rows']==report['latest_qm_rows'] and derived['latest_non_qm_rows']==report['latest_non_qm_rows'],'INHERITED_FULL_PROOF_OR_COUNTS_CHANGED');write(a.out/'verification_report.json',derived);print(json.dumps({'status':derived['status'],'targeted_D20_files':len(parts),'explicit_property_failures_classified':accepted,'unknown_serious_rows':len(remaining),'original_report_retained_NOT_PASS':True,'new_report':str(a.out/'verification_report.json')}))
    if remaining:raise SystemExit(2)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);main(p.parse_args())
