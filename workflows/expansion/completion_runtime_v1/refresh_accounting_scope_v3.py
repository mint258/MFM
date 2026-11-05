"""Refresh declared goal accounting; keep running/pending costs explicitly unfinished."""
import argparse,csv,datetime,hashlib,io,json,os,pathlib,runpy,socket
MAX_BYTES=2<<20
ALPHA=('218.192.171.238:22',1264)
MAIN=('202.38.247.57:22',1278)

def ref(path):
    path=pathlib.Path(path);raw=path.read_bytes();return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def token(r):return(r['path'],r['bytes'],r['sha256'])
def frame(s):return(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid)

def build(config):
    replicas={token(x['source_reference']):x['replica_reference']for x in config.get('replicas',[])}
    def read(r):
        actual=replicas.get(token(r),r);path=pathlib.Path(actual['path']);before=path.stat()
        if actual['bytes']!=r['bytes'] or actual['sha256']!=r['sha256'] or r['bytes']>MAX_BYTES:raise ValueError('Bounded byte-identical explicit replica')
        with path.open('rb')as f:
            first=os.fstat(f.fileno());raw=f.read(MAX_BYTES+1);last=os.fstat(f.fileno())
        if not frame(before)==frame(first)==frame(last)==frame(path.stat()) or len(raw)!=r['bytes'] or hashlib.sha256(raw).hexdigest()!=r['sha256']:raise ValueError('Immutable whole-SHA accounting source')
        return raw
    base=json.loads(read(config['base_scope_reference']));selected={}
    def choose(endpoint,uid,job,stage,reason):
        key=(endpoint,uid,str(job))
        if not str(job).isdigit() or (endpoint,uid)not in(ALPHA,MAIN):raise ValueError('Actual literal own parent identity')
        if key not in selected:selected[key]=dict(endpoint=endpoint,uid=uid,job_id=str(job),stage=stage,scope_evidence=[])
        if reason not in selected[key]['scope_evidence']:selected[key]['scope_evidence'].append(reason)
    inherited=base['parents']+base.get('active_parents_observation_only',[])+base.get('active_or_pending_parents_observation_only',[])
    for item in inherited:
        choose(item['endpoint'],item['uid'],item['job_id'],item['stage'],dict(kind='previous_declared_goal_scope',reference=config['base_scope_reference']))
    runtime=json.loads(read(config['alpha_runtime_sources_reference']))
    for item in runtime['runtime_parent_sources']:
        output=pathlib.Path(item['output_directory'])
        allowed_roots=(
            '/gfshome/alpha/pubchem_expansion_20261103',
            '/gfshome/alpha/codex_data_v1_20261026/artifacts/pubchem_native735_fields_20261103',
            '/gfshome/alpha/codex_data_v1_20261026/inputs/pubchem_d27_closed_20261104',
        )
        if not item['module'].startswith('workflows.expansion.') or not any(output.is_relative_to(root)for root in allowed_roots):raise ValueError('Explicit own expansion producer only')
        choose(*ALPHA,item['job_id'],'runtime_producer:'+item['module'],dict(kind='actual_plan_startup_binding',source_manifest_reference=config['alpha_runtime_sources_reference'],plan_reference=item['plan_reference'],startup_proof_reference=item['startup_proof_reference']))
    for job in config['declared_alpha_job_ids']:
        choose(*ALPHA,str(job),'declared_pipeline_or_runtime',dict(kind='declared_actual_goal_job_id',job_id=str(job)))
    latest={};documents=[]
    for reference in config['accounting_documents']:
        document=json.loads(read(reference));identity=(document['endpoint'],document['uid'])
        if identity not in(ALPHA,MAIN):raise ValueError('Actual own endpoint/UID')
        timestamp=datetime.datetime.fromisoformat(document['captured_at'])
        raw=read(document['raw_sacct_reference']).decode('utf-8');reader=csv.DictReader(io.StringIO(raw),delimiter='|')
        required={'JobIDRaw','UID','State','ExitCode','ElapsedRaw','AllocCPUS','TotalCPU','JobName','WorkDir'}
        if not required<=set(reader.fieldnames or[]):raise ValueError('Complete native parent metadata header')
        for row in reader:
            job=row['JobIDRaw'];key=(*identity,job)
            if not job.isdigit() or int(row['UID'])!=identity[1]:raise ValueError('Parent-only own UID snapshot')
            if identity==MAIN and row['WorkDir']==config['dedicated_main_worktree']:
                stage='exact_NN_and_references'if any(t in row['JobName']for t in('rescue','inverted','benchmark'))else'dedicated_runtime_and_transfer_metadata'
                choose(*MAIN,job,stage,dict(kind='dedicated_expansion_worktree_native_accounting',workdir=row['WorkDir'],accounting_reference=reference))
            if key not in latest or timestamp>latest[key][0]:latest[key]=(timestamp,row,reference)
        documents.append(dict(reference=reference,captured_at=document['captured_at'],raw_sacct_reference=document['raw_sacct_reference']))
    parser=runpy.run_path(config['accounting_parser_path']);terminal=parser['TERMINAL'];parents=[];active=[];missing=[]
    for key,item in sorted(selected.items()):
        if key not in latest:missing.append(item);continue
        timestamp,row,reference=latest[key];state=row['State'].split()[0].rstrip('+')
        elapsed=int(row['ElapsedRaw']);cpus=int(row['AllocCPUS'])
        if elapsed<0 or cpus<0:raise ValueError('Native nonnegative time/CPU')
        value=dict(item,accounting_reference=reference,job_name=row['JobName'],state=state,exit_code=row['ExitCode'],elapsed_raw_seconds=elapsed,allocated_CPUs=cpus,native_node_list=row.get('NodeList'),native_snapshot_at=timestamp.isoformat())
        if state not in terminal:
            value['allocated_core_seconds_asof_not_final']=elapsed*cpus;active.append(value);continue
        disposition='cancelled'if state=='CANCELLED'else('failed'if state!='COMPLETED' or row['ExitCode']!='0:0'else'diagnostic')
        total=parser['cpu_seconds'](row['TotalCPU'])
        parents.append(dict(value,disposition=disposition,allocated_core_seconds=elapsed*cpus,observed_TotalCPU_seconds_decimal=None if total is None else str(total),TotalCPU_observation_is_not_actual_process_CPU=True))
    closed=sum(r['allocated_core_seconds']for r in parents)
    return dict(schema='PUBCHEM_INCREMENTAL_ACCOUNTING_SCOPE_DRAFT_V2',inventory_complete_for_declared_goal_scope=False,scientific_dataset_complete=False,
        coverage_statement='Incremental declared PubChem goal Slurm parents: previous scoped history plus proven expansion runtime plans, explicit pipeline IDs and dedicated Main worktree. Failed/cancelled/diagnostic parents retained. Other account workloads are not automatically included. Direct development metadata CPU is outside these scheduler allocation sums.',
        base_scope_reference=config['base_scope_reference'],accounting_documents=documents,replicas=config.get('replicas',[]),parents=parents,active_or_pending_parents_observation_only=active,missing_native_parent_rows_not_assumed_zero=missing,
        known_terminal_allocated_core_seconds=closed,known_terminal_allocated_core_hours=parser['hours'](closed),running_costs_not_final=True,disposition_labels_provisional_until_final_adopted_producer_refs_bound=True,
        accounting_parser_reference=ref(config['accounting_parser_path']),source_reference=ref(__file__),no_new_Root_approval_gate=True)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--config',type=pathlib.Path,required=True);ap.add_argument('--output',type=pathlib.Path,required=True);a=ap.parse_args()
    if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='compute-0-20':raise ValueError('Authorized Main20 metadata preparation only')
    result=build(json.loads(a.config.read_text()));result['config_reference']=ref(a.config)
    with a.output.open('x')as f:json.dump(result,f,sort_keys=True);f.write('\n')
    summary=dict(schema='PUBCHEM_INCREMENTAL_ACCOUNTING_SCOPE_SUMMARY_V2',scope_reference=ref(a.output),terminal_parents=len(result['parents']),active_or_pending=len(result['active_or_pending_parents_observation_only']),missing_native_rows=len(result['missing_native_parent_rows_not_assumed_zero']),known_terminal_allocated_core_seconds=result['known_terminal_allocated_core_seconds'],known_terminal_allocated_core_hours=result['known_terminal_allocated_core_hours'],inventory_complete_for_declared_goal_scope=False,scientific_dataset_complete=False)
    with a.output.with_name(a.output.stem+'_summary.json').open('x')as f:json.dump(summary,f,sort_keys=True);f.write('\n')
    print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
