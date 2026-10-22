"""Exact read-only diagnosis of the frozen full-verifier957 issue rows. No QM/SCI scan."""
from pathlib import Path
import argparse,ast,collections,concurrent.futures,hashlib,json,os,socket,time
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011');F=ROOT/'acceptance/final_20261016_v1'
REPORT=F/'verify/verification_report.json';REPORT_SHA='3e9870c21d72be70ce9ad5f43de8b0a9cc9b9b06f4b02510d914d64fedf9270f'
ISSUES=F/'verify/schema_array_qc_issues.parquet';CATALOG=F/'catalog/catalog.json';CATALOG_SHA='b5aed096ae0dc4c479a64b9b05e8709205911a0f9a474b71ae1490992ce28765'
VERIFIER=ROOT/'scripts/wp5_acceptance_verify_v10.py';VERIFIER_SHA='d6521527b41925fa39085d5d63ce85828378f5b02b4cb4e8b4d6494b60ae1151'
def require(x,message):
    if not x:raise ValueError(message)
def ref(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(4<<20),b''):h.update(block)
    return {'path':str(p),'bytes':Path(p).stat().st_size,'sha256':h.hexdigest()}
def write(p,value):
    with p.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def worker(chunk):
    counts={name:collections.Counter() for name in ('issue','field','calc_type','status','path','issue_field_calc')}
    for row in chunk:
        for name in ('issue','field','calc_type','status','path'):counts[name][json.dumps(row.get(name),sort_keys=True)]+=1
        counts['issue_field_calc'][json.dumps([row.get('issue'),row.get('field'),row.get('calc_type')])]+=1
    return {'pid':os.getpid(),'rows':len(chunk),'counts':{k:dict(v) for k,v in counts.items()}}
def source_rules():
    text=VERIFIER.read_text();lines=text.splitlines();tree=ast.parse(text);result=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='issue' and len(node.args)>=3:
            code=node.args[2].value if isinstance(node.args[2],ast.Constant) else ast.unparse(node.args[2]);result.append({'issue_code':code,'line':node.lineno,'call':ast.get_source_segment(text,node),'context':'\n'.join(str(i+1)+': '+lines[i] for i in range(max(0,node.lineno-5),min(len(lines),node.end_lineno+3)))})
    return sorted(result,key=lambda r:r['line'])
def main(a):
    require(os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-17','NODE17_UID1278_REQUIRED');require(os.environ.get('SLURM_JOB_ID','').isdigit() and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))>=24,'24CPU_SLURM_REQUIRED');require(a.out.is_absolute() and a.out.parent==F and not a.out.exists(),'FRESH_DIAGNOSTIC_FINAL_OUTPUT_REQUIRED')
    rr=ref(REPORT);cr=ref(CATALOG);vr=ref(VERIFIER);require(rr['sha256']==REPORT_SHA and cr['sha256']==CATALOG_SHA and vr['sha256']==VERIFIER_SHA,'FROZEN_REPORT_CATALOG_OR_VERIFIER_CHANGED');report=json.loads(REPORT.read_text());catalog=json.loads(CATALOG.read_text());require(report['status']=='NOT_PASS' and report['schema_qc_issue_rows']==957 and report['serious_schema_issue_rows']==957 and report['file_exceptions']==[] and report['latest_closed'] is True,'EXACT957_ORIGINAL_NOT_PASS_REQUIRED');require(catalog['status']=='CLOSED' and report['bindings']['catalog_sha256']==CATALOG_SHA and report['bindings']['script_sha256']==VERIFIER_SHA,'ORIGINAL_METADATA_BINDING_DIFFERS')
    import pyarrow as pa,pyarrow.parquet as pq
    pa.set_cpu_count(1);pa.set_io_thread_count(1);ir=ref(ISSUES);file=pq.ParquetFile(ISSUES);require(file.metadata.num_rows==957,'EXACT957_PARQUET_ROWS_REQUIRED');schema=str(file.schema_arrow);rows=file.read(use_threads=False).to_pylist();require(len(rows)==957 and all(set(r)=={'record_id','molecule_id','calc_type','status','issue','field','path'} for r in rows),'ORIGINAL_ISSUE_SCHEMA_DIFFERS');require(all(r['issue']!='ATOMIC_ARRAY_QC_RECORDED_FAILURE' for r in rows),'ORIGINAL_SERIOUS_COUNT_DIFFERS')
    issue_paths={r['path'] for r in rows};verified_paths={r['path'] for r in report['files_verified']};catalog_paths={r['path'] for r in catalog['artifacts']};require(issue_paths<=verified_paths and issue_paths<=catalog_paths,'ISSUE_SOURCE_PATH_NOT_IN_ORIGINAL_CATALOG_VERIFIED_SET')
    chunks=[rows[i::24] for i in range(24)]
    with concurrent.futures.ProcessPoolExecutor(max_workers=24) as pool:parts=list(pool.map(worker,chunks,chunksize=1))
    counts={name:collections.Counter() for name in ('issue','field','calc_type','status','path','issue_field_calc')}
    for part in parts:
        for key,values in part['counts'].items():counts[key].update(values)
    grouped={name:[{'key':json.loads(k),'count':v} for k,v in sorted(counter.items(),key=lambda x:(-x[1],x[0]))] for name,counter in counts.items()};require(all(sum(x['count'] for x in values)==957 for values in grouped.values()),'GROUP_TOTAL_DIFFERS')
    records=collections.Counter(r['record_id'] for r in rows);molecules=collections.Counter(r['molecule_id'] for r in rows);rules=source_rules();matched_rules=[r for r in rules if r['issue_code'] in {row['issue'] for row in rows}];require(ref(ISSUES)==ir and ref(REPORT)==rr and ref(VERIFIER)==vr,'INPUT_METADATA_CHANGED_DURING_DIAGNOSTIC');a.out.mkdir()
    allrows={'schema':'WP5_EXACT957_ORIGINAL_SCHEMA_QC_ISSUES_V1','row_count':957,'source':ir,'original_arrow_schema':schema,'rows':rows,'original_issue_values_or_status_changed':False};write(a.out/'issues_all_957.json',allrows)
    result={'schema':'WP5_EXACT957_READONLY_DIAGNOSTIC_V1','status':'READONLY957_DIAGNOSIS_CLOSED_ORIGINAL_VERIFIER_NOT_PASS_UNCHANGED','created_epoch':time.time(),'actual_job_id':os.environ['SLURM_JOB_ID'],'node':socket.gethostname(),'sources':{'original_verification_report':rr,'original_issue_parquet':ir,'closed_catalog':cr,'frozen_verifier':vr},'requested_workers':24,'actual_aggregation_worker_pids':sorted({p['pid'] for p in parts}),'worker_rows':parts,'issue_rows':957,'unique_record_ids':len(records),'unique_molecule_ids':len(molecules),'issue_source_paths':sorted(issue_paths),'issue_source_file_metadata':[r for r in report['files_verified'] if r['path'] in issue_paths],'grouped_counts':grouped,'record_issue_counts':[{'record_id':k,'count':v} for k,v in sorted(records.items(),key=lambda x:(-x[1],str(x[0])))],'molecule_issue_counts':[{'molecule_id':k,'count':v} for k,v in sorted(molecules.items(),key=lambda x:(-x[1],str(x[0])))],'all957_rows':ref(a.out/'issues_all_957.json'),'matched_frozen_source_rules':matched_rules,'all_frozen_issue_rules':rules,'original_verification_status':report['status'],'original_full_verify_binding':report['bindings'],'original_closed_counts':{k:report[k] for k in ('latest_qm_rows','latest_raw_rows','expected_retained_raw_rows','latest_non_qm_rows','expected_record_tasks','latest_closed','effective_workers')},'scientific_acceptance_PASS_claimed':False,'SCI_or_raw_or_other_Parquet_read':False,'population_rescan':False,'QM_calls':0,'queue_or_frozen_source_or_original_reports_modified':False};write(a.out/'diagnostic.json',result);print(json.dumps({'status':result['status'],'issue_rows':957,'unique_records':len(records),'groups_by_issue':grouped['issue'],'groups_by_field':grouped['field'],'diagnostic':str(a.out/'diagnostic.json')}))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);main(p.parse_args())
