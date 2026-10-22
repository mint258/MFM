"""Complete the two verified missing budget-1 retries with frozen runner14.

Preparation writes only a fresh two-row private queue.  Adoption is a separate
Root action after immutable 240-slot exports and actual terminal accounting.
No old scientific artifact or retry budget is rewritten.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,os,sqlite3,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
PROJECT=ROOT.parent.parent
MIDS=('principal_01100742','principal_01152793')
RUNNER=ROOT/'scripts/wp5_runner_v14.py'
RUNNER_SHA='7d4aa3932be408ff051003446ae7f3fd1eab7b7bdb386d67a41eadb18e3af740'
CONTRACT=ROOT/'configs/production_contract_v7.json'
CONTRACT_SHA='f2966094cc57ef82ca79292a9640a9bbbcf99f46d12626d28dccbe0a507fe33f'
PYTHON='/share/home/zixiao/.conda/envs/chemprop/bin/python'
CALCS=('pm7_B','pm7_cation','pm7_anion','pm7_water','pm7_octanol','xtb_singlepoint','xtb_vipea','xtb_vfukui','xtb_ALPB_water','xtb_ALPB_octanol','xtb_fod','xtb_perturbed_gradient')
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8<<20),b''):h.update(block)
    return h.hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
def publish(path,value):
    path=Path(path)
    if path.exists():raise FileExistsError('WRITE_ONCE:'+str(path))
    pending=path.with_name(path.name+'.pending')
    with pending.open('xb') as stream:stream.write(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2).encode()+b'\n');stream.flush();os.fsync(stream.fileno())
    pending.rename(path)
def ro(path):
    db=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True);db.row_factory=sqlite3.Row;return db
def ref(path):return {'path':str(path),'bytes':Path(path).stat().st_size,'sha256':sha(path)}
def check_ref(reference):
    if Path(reference['path']).stat().st_size!=reference['bytes'] or sha(reference['path'])!=reference['sha256']:raise ValueError('BOUND_FILE_CHANGED:'+reference['path'])
def subset_row(row):
    if row['molecule_id'] not in MIDS or row['task_id']!='69' or row['attempt']!=1 or row['record_count']!=10:raise ValueError('EXACT_TWO_SCOPE_OR_RETRY_BUDGET_DIFFERS')
def prepare(args):
    from wp5_runner_v14 import bootstrap_metadata,Queue
    if sha(RUNNER)!=RUNNER_SHA or sha(CONTRACT)!=CONTRACT_SHA:raise ValueError('FROZEN_RUNNER_OR_CONTRACT_CHANGED')
    probe=json.loads(args.probe.read_text())
    if probe['schema']!='WP5_EXACT_TWO_RETRY_EXECUTION_READ_ONLY_PROBE_V1' or {m['queue']['molecule_id'] for m in probe['molecules']}!=set(MIDS):raise ValueError('ACTUAL_TWO_MOLECULE_PROBE_REQUIRED')
    if not args.out.resolve().is_relative_to(ROOT/'acceptance') or args.out.exists():raise ValueError('FRESH_ACCEPTANCE_PRIVATE_ROOT_REQUIRED')
    args.out.mkdir(parents=True)
    db=ro(ROOT/'queue/pending.sqlite');db.execute('BEGIN')
    try:
        meta=dict(db.execute('SELECT key,value FROM meta'));task=dict(db.execute("SELECT * FROM tasks WHERE task_id='69'").fetchone())
        before=[dict(db.execute('SELECT * FROM molecules WHERE molecule_id=?',(mid,)).fetchone()) for mid in MIDS]
        for row in before:
            subset_row(row)
            if row['state']!='COMPLETE':raise ValueError('SOURCE_NOT_TERMINAL_COMPLETE')
            receipt=json.loads(row['receipt_json']);context=receipt['context']
            actual=next(m for m in probe['molecules'] if m['queue']['molecule_id']==row['molecule_id'])
            if context['attempt_id']!=0 or receipt.get('retryable') is not True or receipt!=actual['receipt']:raise ValueError('ACTUAL_UNUSED_SCIENTIFIC_RETRY_NOT_BOUND')
            if any(actual['queue'][k]!=row[k] for k in actual['queue']):raise ValueError('SOURCE_CHANGED_SINCE_ACTUAL_PROBE')
            if not any(f['SCI_row']['status']=='TIMEOUT' for f in actual['failures']):raise ValueError('ACTUAL_TRANSIENT_REASON_NOT_ESTABLISHED')
        if task['node']!='compute-0-13' or task['state'] not in ('CLOSED','DEAD'):raise ValueError('ORIGINAL_TASK69_AUTHORITY_DIFFERS')
    finally:db.execute('ROLLBACK');db.close()
    plan=ROOT/'packing/node_assignment_v3/tasks.json';assignments=ROOT/'packing/molecule_assignments.parquet'
    if sha(plan)!=meta['plan_sha256'] or sha(assignments)!=meta['population_source_sha256']:raise ValueError('IMMUTABLE_PLAN_OR_ASSIGNMENT_BINDING_CHANGED')
    before_path=args.out/'production_beforeimage.json';publish(before_path,{'schema':'WP5_EXACT_TWO_RETRY_BEFOREIMAGE_V1','time':time.time(),'queue':str(ROOT/'queue/pending.sqlite'),'meta':meta,'task':task,'molecules':before,'probe':ref(args.probe),'script':ref(__file__)})
    queue=args.out/'queue.sqlite';bootstrap_metadata(queue,deadline=time.monotonic()+120)
    private=Queue(queue,deadline=time.monotonic()+120)
    try:
        def seed():
            # The frozen original full plan/assignments remain source authorities.
            # Existing seed metadata prevents Queue.seed from importing full input.
            private.db.executemany('INSERT INTO meta VALUES(?,?)',[(k,v) for k,v in meta.items() if k not in ('population_molecules','population_records','completion_sequence','smoke')]+[('population_molecules','2'),('population_records','20'),('completion_sequence','0'),('smoke','1')])
            private.db.execute("INSERT INTO tasks VALUES(?,?,?,'READY',NULL,NULL)",(task['task_id'],task['node'],task['record_directory']))
            for row in before:
                private.db.execute("INSERT INTO molecules(molecule_id,task_id,file_group,record_count,predicted_seconds,priority,state,attempt,updated) VALUES(?,?,?,?,?,?,'PENDING',1,?)",(row['molecule_id'],row['task_id'],row['file_group'],row['record_count'],row['predicted_seconds'],row['priority'],time.time()))
        private.db.transaction(seed)
        private.seed(plan,assignments,smoke=True)
        actual=[dict(r) for r in private.db.execute('SELECT * FROM molecules ORDER BY molecule_id')]
        if len(actual)!=2 or {r['molecule_id'] for r in actual}!=set(MIDS) or any(r['attempt']!=1 or r['state']!='PENDING' or r['receipt_json'] is not None for r in actual):raise ValueError('PRIVATE_EXACT_TWO_BOOTSTRAP_DIFFERS')
    finally:private.db.close()
    contract=json.loads(CONTRACT.read_text())
    command=[PYTHON,str(RUNNER),'--plan',str(plan),'--assignments',str(assignments),'--queue',str(queue),'--task-id','69','--mode','main','--workers','24','--hours','48','--admit-hours','46','--export-reserve-hours','2','--smoke','--dictionaries',str(ROOT/'dictionaries/job_4513894/dictionary_manifest.json'),'--protocol',contract['protocol']['path'],'--registry',contract['registry']['path'],'--node-authority',contract['node_authority']['path'],'--node-scope-plan',contract['node_scope_plan']['path'],'--audit-membership',contract['audit_manifest']['path'],'--reproduction-package',contract['reproduction_package']['path'],'--production-contract',str(CONTRACT)]
    prepared={'schema':'WP5_EXACT_TWO_SCIENTIFIC_RETRY_PREPARED_V1','status':'PREPARED_NO_QM_STARTED','molecules':list(MIDS),'records':20,'task_slots':240,'queue_retry_budget_before':1,'execution_attempt_required':1,'original_task_id':'69','actual_node':'compute-0-13','queue':str(queue),'beforeimage':ref(before_path),'probe':ref(args.probe),'runner':ref(RUNNER),'contract':ref(CONTRACT),'script':ref(__file__),'command':command,'run_root_parent':str(ROOT/'runtime/task_69_exact_budget1_retry_20261016'),'subset_health_metadata':'smoke only skips full-population rate extrapolation on the two-molecule private queue; it changes no scientific task, seed, parser, timeout, retention or audit selection. claim-cap remains unlimited.','original_plan':ref(plan),'original_assignments':{'path':str(assignments),'sha256':meta['population_source_sha256']},'original_record_directory':task['record_directory'],'new_QM_started':False,'production_queue_written':False,'old_SCI_or_receipt_written':False}
    publish(args.out/'prepared.json',prepared);print(json.dumps({'prepared':str(args.out/'prepared.json'),'records':20,'slots':240,'node':'compute-0-13'}))
def load_prepared(path):
    value=json.loads(path.read_text())
    if value['schema']!='WP5_EXACT_TWO_SCIENTIFIC_RETRY_PREPARED_V1' or value['molecules']!=list(MIDS) or value['execution_attempt_required']!=1:raise ValueError('EXACT_PREPARED_SCOPE_REQUIRED')
    for k in ('beforeimage','probe','runner','contract','script','original_plan'):check_ref(value[k])
    if value['script']['path']!=str(Path(__file__)) or value['runner']['sha256']!=RUNNER_SHA or value['contract']['sha256']!=CONTRACT_SHA:raise ValueError('FROZEN_EXECUTION_BINDING_CHANGED')
    return value
def launch(args):
    import subprocess
    value=load_prepared(args.prepared);job=os.environ.get('SLURM_JOB_ID');node=os.uname().nodename.split('.')[0]
    if not job or node!=value['actual_node'] or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<24:raise ValueError('ACTUAL_24CPU_TASK69_NODE13_SLURM_REQUIRED')
    db=ro(value['queue'])
    try:
        rows=[dict(r) for r in db.execute('SELECT * FROM molecules')]
        if len(rows)!=2 or {r['molecule_id'] for r in rows}!=set(MIDS):raise ValueError('PRIVATE_SCOPE_CHANGED')
        for row in rows:
            subset_row(row)
            if row['state']!='PENDING' or row['receipt_json'] is not None or row['owner'] is not None:raise ValueError('PRIVATE_RETRY_ALREADY_STARTED_OR_NOT_FRESH')
    finally:db.close()
    run_root=Path(value['run_root_parent'])/('job_'+job)
    if run_root.exists():raise FileExistsError(run_root)
    argv=value['command']+['--run-root',str(run_root)]
    publish(args.prepared.parent/'launch_receipt.json',{'job_id':job,'node':node,'uid':os.getuid(),'time':time.time(),'prepared':ref(args.prepared),'run_root':str(run_root),'argv':argv,'scientific_source_unchanged':True})
    raise SystemExit(subprocess.run(argv,cwd=PROJECT).returncode)
def validate(args):
    import pyarrow as pa,pyarrow.dataset as ds,wp5_parquet_v2 as wire
    from wp5_archive_v5 import ArchiveReader
    from wp5_acceptance_verify_v10 import execution_authorities,run_execution_binding
    if not os.environ.get('SLURM_JOB_ID') or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<24:raise ValueError('EXACT_RETRY_EXPORT_CHECK_REQUIRES_24CPU_SLURM')
    pa.set_cpu_count(24);pa.set_io_thread_count(8)
    value=load_prepared(args.prepared);launch_path=args.prepared.parent/'launch_receipt.json';launch=json.loads(launch_path.read_text())
    run_root=Path(launch['run_root']);run=json.loads((run_root/'run.json').read_text());completion=json.loads((run_root/'completion.json').read_text())
    if completion.get('error') or completion.get('status')!='WP5_JOB_CLOSED' or completion.get('global_stop') or run['options']['queue']!=value['queue'] or run['options']['task_id']!='69' or run['options']['plan']!=value['original_plan']['path'] or run['node']!='compute-0-13':raise ValueError('NEW_RUN_NOT_FRESH_OR_CLOSED')
    binding=run_execution_binding({'run_root':str(run_root),'job_id':int(launch['job_id'])},execution_authorities(CONTRACT),{})
    db=ro(value['queue'])
    try:
        rows=[dict(r) for r in db.execute('SELECT * FROM molecules ORDER BY molecule_id')];sessions=[dict(r) for r in db.execute('SELECT * FROM sessions')]
        if len(rows)!=2 or len(sessions)!=1 or sessions[0]['end'] is None or sessions[0]['mode']!='main' or sessions[0]['task_id']!='69' or sessions[0]['session_id']!=run['options']['session'] or str(sessions[0]['job_id'])!=str(launch['job_id']):raise ValueError('EXACT_PRIVATE_QUEUE_NOT_CLOSED')
        for row in rows:
            subset_row(row)
            receipt=json.loads(row['receipt_json']);ctx=receipt['context']
            if row['state']!='COMPLETE' or ctx['attempt_id']!=1 or row['owner']!=sessions[0]['session_id'] or str(ctx['job_id'])!=str(launch['job_id']) or ctx['task_id']!='69' or ctx['lane']!=row['lane'] or not ctx['execution_id'].startswith(row['owner']+':'+str(row['lane'])+':1:') or receipt['records']!=10 or receipt['requested_outcomes']!=120:raise ValueError('TRUE_BUDGET1_EXECUTION_NOT_COMPLETE')
    finally:db.close()
    source=ds.dataset(value['original_record_directory'],format='parquet',partitioning='hive').to_table(filter=ds.field('molecule_id').isin(MIDS),use_threads=True).to_pylist()
    record_ids={r['record_id']:r for r in source}
    if len(source)!=20 or len(record_ids)!=20 or collections.Counter(r['molecule_id'] for r in source)!=collections.Counter({m:10 for m in MIDS}):raise ValueError('IMMUTABLE_ORIGINAL20_RECORD_SCOPE_DIFFERS')
    contract=json.loads(CONTRACT.read_text());audit=json.loads(Path(contract['audit_manifest']['path']).read_text());check_ref(audit['selected_records'])
    audit_ids={r['record_id'] for r in ds.dataset(audit['selected_records']['path'],format='parquet').to_table(filter=ds.field('record_id').isin(list(record_ids)),columns=['record_id'],use_threads=True).to_pylist()}
    entries={entry['registry_id']:entry for entry in wire.registry(contract['registry']['path'])};expected_cells={calc:{rid for rid,entry in entries.items() if entry['task']==calc} for calc in CALCS}
    export=json.loads((run_root/'export_completion.json').read_text());refs=export['families'];archive=export['archive'];canonical_ref=export.get('canonical') or next((r for r in refs if r['family']=='canonical_record_attempts'),None)
    if canonical_ref is None:raise ValueError('NEW_CANONICAL_REFERENCE_MISSING')
    checked=[]
    for reference in refs+[archive]:
        if not Path(reference['path']).resolve().is_relative_to(run_root.resolve()):raise ValueError('NEW_EXPORT_OUTSIDE_FRESH_RUNTIME')
        check_ref(reference);checked.append(reference)
    if canonical_ref not in refs:check_ref(canonical_ref);checked.append(canonical_ref)
    canonical_rows=ds.dataset(canonical_ref['path'],format='parquet').to_table(use_threads=True).to_pylist()
    expected={(rid,calc) for rid in record_ids for calc in CALCS}
    if len(canonical_rows)!=240 or {(r['record_id'],r['calc_type']) for r in canonical_rows}!=expected:raise ValueError('NEW_CANONICAL_NOT_EXACT240')
    latest={r['molecule_id']:r for r in rows};locators={(r['record_id'],r['calc_type']):r for r in canonical_rows}
    for row in canonical_rows:
        if row['molecule_id'] not in latest or record_ids[row['record_id']]['molecule_id']!=row['molecule_id']:raise ValueError('NEW_CANONICAL_MOLECULE_SOURCE_DIFFERS')
        ctx=json.loads(latest[row['molecule_id']]['receipt_json'])['context']
        if any(row[k]!=ctx[k] for k in ('attempt_id','job_id','task_id','lane')) or row['raw_execution_id']!=ctx['execution_id'] or row['archive_path']!=archive['path'] or row['file_group']!=5:raise ValueError('NEW_CANONICAL_EXACT_EXECUTION_CONTEXT_DIFFERS')
    counts=collections.Counter();qm={};families={};metadata={}
    for reference in refs:
        family=reference['family']
        if family=='canonical_record_attempts':continue
        records=ds.dataset(reference['path'],format='parquet').to_table(use_threads=True).to_pylist()
        if len(records)!=reference['rows']:raise ValueError('NEW_FAMILY_DECLARED_ROWCOUNT_DIFFERS')
        families[family]=families.get(family,0)+len(records)
        for row in records:
            mid=row['molecule_id'];rid=row['record_id'];receipt=json.loads(latest[mid]['receipt_json']);ctx=receipt['context']
            if rid not in record_ids or record_ids[rid]['molecule_id']!=mid or any(row[k]!=ctx[k] for k in ('attempt_id','job_id','task_id','lane')):raise ValueError('NEW_FAMILY_EXECUTION_IDENTITY_DIFFERS')
            if family not in ('base_geometry','D20','D3','QC'):
                key=(rid,row['calc_type']);location=locators[key]
                if key in qm or location['family_parquet_path']!=reference['path'] or location['raw_execution_id']!=ctx['execution_id'] or location['archive_path']!=archive['path']:raise ValueError('NEW_CANONICAL_SCI_LOCATOR_DIFFERS')
                if wire.FAMILIES[row['calc_type']]!=family or row['reproduction_package_sha256']!=binding['package']['sha256'] or row['total_atoms']!=record_ids[rid]['total_atoms'] or row['status'] not in ('SUCCESS','CALCULATION_FAILED','PROPERTY_FAILED','TIMEOUT') or row['raw_audit_selected']!=(rid in audit_ids):raise ValueError('NEW_SCI_SCOPE_PACKAGE_OR_FIXED_AUDIT_DIFFERS')
                cells=[cell['registry_id'] for cell in row['values']]
                if len(cells)!=len(set(cells)) or set(cells)!=expected_cells[row['calc_type']]:raise ValueError('NEW_SCI_REGISTRY_CELL_SET_DIFFERS')
                qm[key]=row;counts[(row['calc_type'],row['status'])]+=1
            elif family=='QC':metadata[rid]=row
    if set(qm)!=expected or any(families.get(f)!=20 for f in ('base_geometry','D20','D3','QC')) or sum(n for f,n in families.items() if f not in ('base_geometry','D20','D3','QC'))!=240:raise ValueError('NEW_FAMILY_ROW_DENOMINATOR_NOT_CLOSED')
    reader=ArchiveReader(archive['path'],value['command'][value['command'].index('--dictionaries')+1]);raw_keys=set();raw_proofs=[]
    try:
        meta=dict(reader.db.execute('SELECT key,value FROM metadata'))
        if meta.get('reproduction_package_sha256')!=binding['package']['sha256'] or meta.get('audit_membership_sha256')!=binding['audit']['sha256'] or meta.get('input_bodies_saved')!='false' or meta.get('policy')!='FAILURES_PLUS_STRATIFIED_RECORD_AUDIT_NO_INPUT' or reader.db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('NEW_RAW_BINDING_OR_INTEGRITY_DIFFERS')
        for row in rows:
            receipt=json.loads(row['receipt_json']);stored=reader.completion(row['molecule_id'])
            if not stored or stored['receipt']['context']!=receipt['context'] or stored['record_count']!=10 or stored['receipt']['counts']!=receipt['counts']:raise ValueError('NEW_SCI_DURABLE_RECEIPT_DIFFERS')
            for r in reader.db.execute('SELECT record_id,calc_type,execution_id FROM records WHERE molecule_id=?',(row['molecule_id'],)):
                key=(r[0],r[1]);sci=qm[key]
                if r[2]!=receipt['context']['execution_id'] or not (sci['status']!='SUCCESS' or sci['raw_audit_selected']):raise ValueError('NEW_RAW_OUTSIDE_EXACT_FAILURE_AUDIT_POLICY')
                raw=reader.get(*r)
                if raw['input_files'] or raw['input_bodies_saved'] or raw['metadata']['context']!=receipt['context'] or raw['scope_status']!=sci['status'] or raw['input_file_sha256']!=sci['input_file_sha256'] or raw['input_bundle_sha256']!=sci['input_bundle_sha256']:raise ValueError('NEW_RAW_EXECUTION_STATUS_OR_INPUT_SHA_DIFFERS')
                raw_keys.add(key);raw_proofs.append({'record_id':r[0],'calc_type':r[1],'execution_id':r[2],'raw_sha256':raw['raw_sha256'],'outputs':raw['original_output_manifest']})
        if raw_keys!={key for key,row in qm.items() if row['status']!='SUCCESS' or row['raw_audit_selected']}:raise ValueError('NEW_REQUIRED_FAILURE_AUDIT_RAW_MISSING')
    finally:reader.close()
    for rid,qc in metadata.items():
        if len(qc['task_statuses'])!=12 or {s['calc_type']:s['status'] for s in qc['task_statuses']}!={c:qm[(rid,c)]['status'] for c in CALCS}:raise ValueError('NEW_QC_STATUS_NOT_ALL12')
    report={'schema':'WP5_EXACT_TWO_RETRY_240_SLOTS_VERIFIED_V1','status':'EXACT_TWO_BUDGET1_SCI_EXPORT_VERIFIED','prepared':ref(args.prepared),'launch':ref(launch_path),'run_root':str(run_root),'run_json':ref(run_root/'run.json'),'completion':ref(run_root/'completion.json'),'export_completion':ref(run_root/'export_completion.json'),'job_id':launch['job_id'],'records':20,'task_slots':240,'attempt_id':1,'private_rows':rows,'private_session':sessions[0],'files_verified':checked,'raw_member_proofs':raw_proofs,'status_counts':[{'calc_type':k[0],'status':k[1],'rows':v} for k,v in sorted(counts.items())],'original20_source_keys_sha256':hashlib.sha256(canonical(sorted(record_ids))).hexdigest(),'old_SCI_or_receipt_written':False,'production_queue_written':False,'script':ref(__file__)}
    report['fixed_audit_records']=sorted(audit_ids);report['fixed_audit_membership']=contract['audit_manifest'];report['all_registry_cells_extracted']=True
    publish(args.out,report);print(json.dumps({'verified':str(args.out),'status':report['status'],'records':20,'task_slots':240}))
def terminal_accounting(path,job):
    data=json.loads(path.read_text());payload=data.get('sacct',data)
    code=payload.get('returncode',payload.get('sacct_returncode'));stdout=payload.get('stdout',payload.get('sacct_stdout',''))
    if code!=0:raise ValueError('ACTUAL_SACCT_QUERY_FAILED')
    found=[]
    for line in stdout.splitlines():
        fields=[s.strip() for s in line.split('|')]
        if fields and fields[0]==str(job):found.append(fields)
    if len(found)!=1 or found[0][1]!='zixiao' or found[0][2].split()[0]!='COMPLETED' or found[0][3]!='0:0':raise ValueError('ACTUAL_RETRY_PARENT_NOT_COMPLETED_ZERO')
def adopt(args):
    value=load_prepared(args.prepared);report=json.loads(args.verified.read_text())
    if report['status']!='EXACT_TWO_BUDGET1_SCI_EXPORT_VERIFIED' or report['prepared']!=ref(args.prepared) or report['script']!=ref(__file__):raise ValueError('EXACT_NEW_SCI_VERIFICATION_REQUIRED')
    for reference in report['files_verified']+[report['run_json'],report['completion'],report['export_completion']]:check_ref(reference)
    terminal_accounting(args.terminal_accounting,report['job_id'])
    before=json.loads(Path(value['beforeimage']['path']).read_text());original={r['molecule_id']:r for r in before['molecules']};new={r['molecule_id']:r for r in report['private_rows']}
    if set(new)!=set(MIDS) or set(original)!=set(MIDS):raise ValueError('ADOPT_SCOPE_DIFFERS')
    if args.out.exists():raise FileExistsError('WRITE_ONCE_ADOPTION_REPORT_REQUIRED')
    from wp5_runner_v14 import Queue
    queue=Queue(ROOT/'queue/pending.sqlite',deadline=time.monotonic()+120)
    session=report['private_session'];session_columns=('session_id','job_id','task_id','mode','claims','start','end')
    def apply():
        for mid in MIDS:
            actual=dict(queue.db.execute('SELECT * FROM molecules WHERE molecule_id=?',(mid,)).fetchone())
            if actual!=original[mid]:raise ValueError('PRODUCTION_BEFOREIMAGE_CHANGED:'+mid)
            subset_row(new[mid])
        if queue.db.execute('SELECT 1 FROM sessions WHERE session_id=?',(session['session_id'],)).fetchone():raise ValueError('NEW_SESSION_ALREADY_ADOPTED')
        queue.db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,?)',tuple(session[c] for c in session_columns))
        for mid in MIDS:
            r=new[mid]
            queue.db.execute("UPDATE molecules SET state='COMPLETE',owner=?,lane=?,archive_path=?,receipt_json=?,counts_json=?,export_json=?,updated=? WHERE molecule_id=? AND attempt=1",(r['owner'],r['lane'],r['archive_path'],r['receipt_json'],r['counts_json'],r['export_json'],time.time(),mid))
            actual=dict(queue.db.execute('SELECT * FROM molecules WHERE molecule_id=?',(mid,)).fetchone())
            if actual['attempt']!=1 or actual['completion_rank']!=original[mid]['completion_rank'] or json.loads(actual['receipt_json'])['context']['attempt_id']!=1:raise ValueError('ADOPTION_BUDGET_OR_RANK_CHANGED')
        return [dict(queue.db.execute('SELECT * FROM molecules WHERE molecule_id=?',(mid,)).fetchone()) for mid in MIDS]
    try:after=queue.db.transaction(apply)
    finally:queue.db.close()
    publish(args.out,{'schema':'WP5_EXACT_TWO_BUDGET1_ATOMIC_ADOPTION_V1','status':'EXACT_TWO_TRUE_RETRY_ADOPTED','time':time.time(),'beforeimage':value['beforeimage'],'verified':ref(args.verified),'actual_terminal_accounting':ref(args.terminal_accounting),'after':after,'queue_budget_preserved':1,'completion_rank_preserved':True,'old_scientific_files_written':False,'new_formal_parent_job_id':report['job_id'],'script':ref(__file__)})
    print(json.dumps({'adoption':str(args.out),'status':'EXACT_TWO_TRUE_RETRY_ADOPTED'}))
def check():
    import tempfile,shutil,ast
    from wp5_runner_v14 import bootstrap_metadata,Queue
    ast.parse(Path(__file__).read_text());base=ROOT/'tests';base.mkdir(exist_ok=True);folder=Path(tempfile.mkdtemp(prefix='exact_two_retry_metadata_',dir=base))
    try:
        plan=folder/'plan.json';plan.write_text('{"tasks":[]}\n');path=folder/'queue.sqlite';bootstrap_metadata(path,deadline=time.monotonic()+120);queue=Queue(path,deadline=time.monotonic()+120)
        try:
            queue.db.executemany('INSERT INTO meta VALUES(?,?)',[('plan_sha256',sha(plan)),('population_source_sha256','fixture-source-not-opened'),('population_molecules','2'),('population_records','20'),('completion_sequence','0'),('smoke','1')])
            queue.db.execute("INSERT INTO tasks VALUES('69','compute-0-13','FIXTURE_UNOPENED','READY',NULL,NULL)")
            for i,mid in enumerate(MIDS):queue.db.execute("INSERT INTO molecules(molecule_id,task_id,file_group,record_count,predicted_seconds,priority,state,attempt,updated) VALUES(?,'69',5,10,1,?,'PENDING',1,?)",(mid,i,time.time()))
            queue.seed(plan,folder/'ASSIGNMENTS_MUST_NOT_BE_OPENED.parquet',smoke=True)
            rows=[dict(r) for r in queue.db.execute('SELECT * FROM molecules')]
            assert len(rows)==2 and all(r['attempt']==1 and r['state']=='PENDING' for r in rows)
            for row in rows:subset_row(row)
            for key,bad in [('attempt',0),('attempt',2),('molecule_id','UNAUTHORIZED'),('record_count',9),('task_id','68')]:
                invalid={**rows[0],key:bad}
                try:subset_row(invalid);raise AssertionError('Invalid retry accepted:'+key)
                except ValueError:pass
            queue.start('fixture',0,'69','main','compute-0-13')
            first=queue.claim('fixture','69','main',120,0);assert first['attempt']==1
            second=queue.claim('fixture','69','main',120,0);assert second['attempt']==1 and first['molecule_id']!=second['molecule_id']
            assert queue.claim('fixture','69','main',120,0) is None
        finally:queue.db.close()
        print(json.dumps({'status':'EXACT_TWO_RETRY_METADATA_FIXTURE_PASS','private_scope':2,'budget1_preserved':True,'original_assignments_not_opened':True,'new_QM_calls':0,'production_queue_opened':False,'fixture_cleaned':True}))
    finally:shutil.rmtree(folder)
def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='mode',required=True)
    p=sub.add_parser('prepare');p.add_argument('--probe',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p=sub.add_parser('launch');p.add_argument('--prepared',type=Path,required=True)
    p=sub.add_parser('validate');p.add_argument('--prepared',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p=sub.add_parser('adopt');p.add_argument('--prepared',type=Path,required=True);p.add_argument('--verified',type=Path,required=True);p.add_argument('--terminal-accounting',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    sub.add_parser('check');args=ap.parse_args();{'prepare':prepare,'launch':launch,'validate':validate,'adopt':adopt,'check':lambda _:check()}[args.mode](args)
if __name__=='__main__':main()
