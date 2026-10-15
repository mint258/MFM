"""G6: pure export repair, original four pending molecules, at most one cleanup.
V7 records the user-approved 15-to12/16-to13 execution substitution and preserves the originally designed cohort seed; science and accounting transport unchanged. No wrapper process signals; original outcomes and attempts are retained.
"""
from __future__ import annotations
import argparse,collections,concurrent.futures,hashlib,importlib,json,multiprocessing,os,socket,sqlite3,subprocess,sys,time,traceback
from pathlib import Path
from urllib.parse import quote
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
SCREEN=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011')
CALCS=('pm7_B','pm7_water','pm7_octanol','pm7_cation','pm7_anion','xtb_singlepoint','xtb_vipea','xtb_vfukui','xtb_ALPB_water','xtb_ALPB_octanol','xtb_fod','xtb_perturbed_gradient')
FAMILY={'pm7_B':'pm7_neutral','pm7_water':'pm7_solvents','pm7_octanol':'pm7_solvents','pm7_cation':'pm7_ions','pm7_anion':'pm7_ions','xtb_singlepoint':'xtb_singlepoint','xtb_vipea':'xtb_vipea','xtb_vfukui':'xtb_vfukui','xtb_ALPB_water':'xtb_alpb','xtb_ALPB_octanol':'xtb_alpb','xtb_fod':'xtb_fod','xtb_perturbed_gradient':'perturbed'}
_BARRIER=None
NODE_AUTHORITY_SHA='32b0ba7355603c697ac0b2083d090d60fe924eb4d23f7128f451735cf6909d3f'
NODE_SCOPE_PLAN_SHA='dd195e994628c75b710de6e267f99556df59e918b875117907753693af638f3b'
ACTUAL_NODES={'compute-0-'+str(i) for i in (12,13,14,17,18,19)}
DESIGNED_BY_ACTUAL={'compute-0-12':'compute-0-15','compute-0-13':'compute-0-16'}
def designed_node(actual,requested=None):
    if actual not in ACTUAL_NODES:raise ValueError('ACTUAL_NODE_OUTSIDE_USER_APPROVED_SCOPE')
    expected=DESIGNED_BY_ACTUAL.get(actual,actual)
    if requested is not None and requested!=expected:raise ValueError('ORIGINAL_DESIGNED_NODE_MAPPING_MISMATCH')
    return expected

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8<<20),b''):h.update(block)
    return h.hexdigest()

def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.'+str(os.getpid())+'.pending')
    with tmp.open('w') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)

def readonly(path):
    db=sqlite3.connect('file:'+quote(str(Path(path).absolute()))+'?mode=ro',uri=True);db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON');return db

def snapshot(path):
    db=readonly(path)
    try:return {'molecules':[dict(r) for r in db.execute('SELECT molecule_id,state,attempt,record_count,archive_path,receipt_json,export_json FROM molecules ORDER BY molecule_id')],
                'tasks':[dict(r) for r in db.execute('SELECT * FROM tasks')],'sessions':[dict(r) for r in db.execute('SELECT * FROM sessions ORDER BY start')]}
    finally:db.close()

def terminal(job):
    from wp5_accounting_v2 import run_sacct
    proc=run_sacct(['-X','-n','-P','-j',str(job),'--format=JobID,User,State'],timeout=60)
    states=[]
    for line in proc.stdout.splitlines():
        f=[part.strip() for part in line.split('|')]
        if len(f)>=3 and f[0]==str(job) and f[1]=='zixiao':states.append(f[2].split()[0])
    if proc.returncode or len(states)!=1 or states[0] not in {'COMPLETED','FAILED','CANCELLED','NODE_FAIL','OUT_OF_MEMORY','TIMEOUT','BOOT_FAIL','DEADLINE','PREEMPTED'}:
        raise ValueError('SOURCE_JOB_NOT_CONFIRMED_TERMINAL:'+json.dumps({'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr,'accounting_evidence_path':proc.evidence_path}))
    return {'job_id':str(job),'state':states[0],'accounting_evidence_path':proc.evidence_path,'accounting':proc.evidence}

def refs(root):
    items=json.loads((Path(root)/'family_exports.json').read_text())['references'];canonical=Path(root)/'canonical_record_attempts.parquet'
    if canonical.exists():items+=[{'path':str(canonical),'bytes':canonical.stat().st_size,'sha256':digest(canonical),'family':'canonical_record_attempts'}]
    return items

def verify(items):
    for ref in items:
        path=Path(ref['path'])
        if not path.is_file() or path.stat().st_size!=ref['bytes'] or digest(path)!=ref['sha256']:raise ValueError('IMMUTABLE_PERMANENT_REFERENCE_CHANGED:'+str(path))

def clean(info):
    if info.get('error') or not info['scratch_clean'] or any(r['error_count'] for r in info['workers']):raise ValueError('G6_RUNTIME_CHAIN_ERROR:'+str(info.get('error')))
    if any(not r['cleanup']['work_root_removed'] or not r['cleanup']['LMDB_handles_closed'] for r in info['workers']):raise ValueError('EXPLICIT_WORKER_CLEANUP_FAILED')

def run_phase(a,out,queue,plan,assignments,label,mode,cap,deadline):
    left=(deadline-time.monotonic())/3600
    if left<.6:return None
    path=out/label
    argv=[sys.executable,str(a.runner),'--plan',str(plan),'--assignments',str(assignments),'--queue',str(queue),'--task-id','0',
          '--mode',mode,'--run-root',str(path),'--dictionaries',str(a.dictionaries),'--protocol',str(a.protocol),'--policy','ALL',
          '--node-authority',str(a.node_authority),'--node-scope-plan',str(a.node_scope_plan),
          '--workers','24','--hours',str(left),'--admit-hours',str(left-.6),'--export-reserve-hours','0.5','--claim-cap',str(cap),'--smoke']
    started=time.monotonic()
    # QM lifecycle owns its timeouts. The harness never kills this process.
    proc=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True)
    save(out/(label+'_command.json'),{'argv':argv,'returncode':proc.returncode,'seconds':time.monotonic()-started,'stdout':proc.stdout,'stderr':proc.stderr})
    if proc.returncode:raise RuntimeError('RUNNER_NONZERO:'+label+':'+proc.stderr[-2000:])
    info=json.loads((path/'completion.json').read_text());clean(info)
    return {'root':str(path),'completion':info,'archive':info['archive'],'families':info['families']}

def bind(barrier):
    global _BARRIER
    _BARRIER=barrier

def put_path(detail,path,value):
    parts=path.split('.')
    if parts[0] in ('detail','details'):parts=parts[1:]
    current=detail
    for part in parts[:-1]:current=current.setdefault(part,{})
    if parts:current[parts[-1]]=value

def concurrency(receipts):
    active=set();peak=0;events=[]
    for r in receipts:events.extend([(r['molecule_started_epoch'],1,r['worker_pid']),(r['completed_epoch'],-1,r['worker_pid'])])
    for _,change,pid in sorted(events):
        if change>0:active.add(pid)
        else:active.discard(pid)
        peak=max(peak,len(active))
    return {'worker_pids':sorted({r['worker_pid'] for r in receipts}),'peak_active_whole_molecule_workers':peak}

def create_cohort(out,node,original_designed_node=None):
    cohort_seed_node=designed_node(node,original_designed_node)
    import duckdb,pyarrow as pa,pyarrow.parquet as pq
    db=duckdb.connect();db.execute("SET threads=24");db.execute("SET memory_limit='20GB'")
    def q(path):return "'"+str(path).replace("'","''")+"'"
    molpath=ROOT/"population/molecule_index.parquet"
    pilot=SCREEN/"c_engineering/xyz/analysis_geometry.parquet"
    db.execute("CREATE VIEW eligible AS SELECT m.* FROM read_parquet("+q(molpath)+") m "
               "WHERE molecule_id IN (SELECT DISTINCT molecule_id FROM read_parquet("+q(pilot)+"))")
    # Twenty whole molecules in one test cover all formal size strata, five
    # file groups and the pilot-eligible largest total-atom representative.
    # Node-specific ordering gives additional samples; the largest is shared.
    chosen=[];selected_info={}
    columns="molecule_id,records,max_heavy_atoms,max_total_atoms,file_group"
    def add(row):
        if row[0] not in selected_info:chosen.append((row[0],));selected_info[row[0]]=row
    def pick(condition,params=()):
        clause=" AND molecule_id NOT IN ("+",".join(q(molecule) for molecule in selected_info)+")" if selected_info else ""
        row=db.execute("SELECT "+columns+" FROM eligible WHERE "+condition+clause+
                       " ORDER BY CASE WHEN records>=4 THEN 0 ELSE 1 END,md5(molecule_id || ?) LIMIT 1",tuple(params)+(cohort_seed_node,)).fetchone()
        if row is None:raise ValueError("G6_REQUIRED_COHORT_HAS_NO_ELIGIBLE_WHOLE_MOLECULE")
        add(row)
    largest=db.execute("SELECT "+columns+" FROM eligible ORDER BY max_total_atoms DESC,max_heavy_atoms DESC,molecule_id LIMIT 1").fetchone()
    if largest is None:raise ValueError("G6_PILOT_ELIGIBLE_FRAME_EMPTY")
    add(largest)
    ranges=[(0,10),(11,20),(21,30),(31,50),(51,75),(76,100),(101,1000000)]
    for lower,upper in ranges:
        if not any(lower<=row[2]<=upper for row in selected_info.values()):
            pick("max_heavy_atoms BETWEEN ? AND ?",(lower,upper))
    for group in range(1,6):
        if not any(row[4]==group for row in selected_info.values()):pick("file_group=?",(group,))
    while len(chosen)<20:
        group=min(range(1,6),key=lambda value:(sum(row[4]==value for row in selected_info.values()),value))
        pick("file_group=?",(group,))
    ids=[row[0] for row in chosen]
    if len(ids)!=20 or len(set(ids))!=20:raise ValueError("G6_WHOLE_MOLECULE_SELECTION_NOT20")
    save(out/"selected_molecules.json",{"selection":"all7strata/all5filegroups/piloteligible largest; node-specific deterministic ordering",
        "node":node,"actual_node":node,"original_designed_node":cohort_seed_node,"cohort_selection_seed_node":cohort_seed_node,"source_pilot_geometry_sha256":digest(pilot),"largest_pilot_eligible_molecule":largest[0],
        "largest_total_atoms":largest[3],"molecules":[dict(zip(columns.split(","),row)) for row in selected_info.values()]})
    db.register("selected",pa.table({"molecule_id":ids}))
    directory=out/"record_index";directory.mkdir()
    db.execute("COPY (SELECT p.* FROM read_parquet("+q(ROOT/"population/formal_record_index.parquet")+
               ") p JOIN selected s USING(molecule_id) ORDER BY p.molecule_id,p.conformer_id,p.record_id) TO "+
               q(directory/"records.parquet")+" (FORMAT PARQUET, COMPRESSION ZSTD)")
    stats=db.execute("SELECT molecule_id,records,max_heavy_atoms,max_total_atoms,file_group FROM eligible JOIN selected USING(molecule_id)").fetchall()
    measured=db.execute("SELECT a.molecule_id,a.planned_allocated_seconds FROM read_parquet("+
                        q(ROOT/"packing/molecule_assignments.parquet")+") a JOIN selected s USING(molecule_id)").fetchall()
    costs=dict(measured)
    if len(costs)!=20 or any(not isinstance(value,(int,float)) or value<=0 for value in costs.values()):
        raise ValueError("G6_REAL_PACKING_COSTS_NOT_CLOSED")
    stats.sort(key=lambda row:(-costs[row[0]],row[0]))
    assignments=[{"molecule_id":mol,"records":records,"file_group":group,"task_id":0,
                  "sequence_in_task":i,"planned_allocated_seconds":costs[mol]}
                 for i,(mol,records,heavy,natoms,group) in enumerate(stats)]
    pq.write_table(pa.Table.from_pylist(assignments),out/"assignments.parquet",compression="zstd")
    save(out/"tasks.json",{"tasks":[{"task_id":0,"node":node,"record_directory":str(directory)}]})
    expected_records=sum(r[1] for r in stats);db.close()
    return json.loads((out/'selected_molecules.json').read_text()),out/'queue.sqlite',out/'tasks.json',out/'assignments.parquet'

def audit_molecule(item):
    import pyarrow.parquet as pq
    from wp5_archive_v4 import ArchiveReader
    from wp5_parquet import decode
    from wp5_engine import validate_atomic_arrays,render_inputs,stable_sha
    from rdkit import Chem
    row=item['queue_row'];exp=json.loads(row['export_json']);records=item['records'];ids={r['record_id'] for r in records}
    entries={int(e['registry_id']):e for e in json.loads(Path(item['registry']).read_text())['entries']}
    protocol=json.loads(Path(item['protocol']).read_text());tasks={t['name']:t for t in protocol['tasks']}
    base={};issues=[];counts=collections.Counter();scope=[];compression=[];details={};minimum_flags=set()
    for ref in exp['families']:
        if ref.get('file_group')!=int(records[0]['file_group']) or ref['family'] not in set(FAMILY.values())|{'base_geometry'}:continue
        if digest(ref['path'])!=ref['sha256']:raise ValueError('IMMUTABLE_FAMILY_SHA_MISMATCH')
        for batch in pq.ParquetFile(ref['path']).iter_batches(batch_size=64):
            for target in batch.to_pylist():
                if target['molecule_id']!=row['molecule_id']:continue
                rid=target['record_id']
                if rid not in ids:issues.append('UNEXPECTED_RECORD:'+rid);continue
                if ref['family']=='base_geometry':
                    if rid in base:issues.append('DUPLICATE_BASE:'+rid)
                    base[rid]=target;continue
                calc=target['calc_type'];key=(rid,calc)
                if key in details:issues.append('DUPLICATE_TARGET:'+str(key))
                detail={'values':{}}
                for cell in target['values']:
                    if cell['kind']==9:continue
                    e=entries.get(int(cell['registry_id']))
                    if e is None or e['task']!=calc:issues.append('UNREGISTERED_OR_TASK_MISMATCH:'+str(cell['registry_id']));continue
                    put_path(detail,e['source_path'],decode(cell))
                details[key]=(target,detail)
    reader=ArchiveReader(row['archive_path'],item['dictionaries'])
    try:
        completion=reader.completion(row['molecule_id'])
        if not completion or completion['record_count']!=len(records) or completion['raw_calls']!=12*len(records):issues.append('COMPLETION_RECEIPT_SLOT_COUNT')
        keys=set(tuple(r) for r in reader.db.execute('SELECT record_id,calc_type FROM records WHERE molecule_id=?',(row['molecule_id'],)))
        expected={(rid,calc) for rid in ids for calc in CALCS}
        if keys!=expected or set(details)!=expected:issues.append('LATEST_RECORD_TIMES12_NOT_CLOSED')
        for source in records:
            rid=source['record_id'];geom=base.get(rid)
            if geom is None:issues.append('BASE_MISSING:'+rid);continue
            z=geom['atomic_numbers'];coords=geom['positions_A']
            if geom['source_payload_sha256']!=source['record_payload_sha256']:issues.append('BASE_SOURCE_PAYLOAD_SHA:'+rid)
            if z is not None and (len(z)!=source['total_atoms'] or len(coords)!=len(z)):issues.append('BASE_ATOM_COUNT:'+rid)
            for calc in CALCS:
                key=(rid,calc)
                if key not in keys or key not in details:continue
                raw=reader.get(rid,calc);target,detail=details[key];status=target['status'];counts[calc+'|'+status]+=1
                meta=raw['metadata'];task=tasks[calc]
                if meta.get('is_minimum'):minimum_flags.add(rid)
                if raw['scope_status']!=status or raw['source_status']!=target['source_status']:issues.append('SOURCE_SCOPE_STATUS:'+str(key))
                if meta.get('source_payload_sha256')!=source['record_payload_sha256']:issues.append('RAW_SOURCE_PAYLOAD_SHA:'+str(key))
                keywords=task['keywords']+' THREADS=1' if task['family']=='mopac' else task['args']
                if meta.get('keywords')!=keywords or meta.get('keywordSHA')!=stable_sha(keywords):issues.append('KEYWORDS_CHANGED:'+str(key))
                if meta.get('software',{}).get('version')!=protocol['expected_versions'][task['family']]:issues.append('SOFTWARE_VERSION_CHANGED:'+str(key))
                inputs={f['name']:f['data'] for f in raw['input_files']};outputs={f['name']:f['data'] for f in raw['output_files'] or []}
                if z is not None:
                    native={'symbols':[Chem.GetPeriodicTable().GetElementSymbol(int(a)) for a in z],'coords':coords}
                    for name,data in render_inputs(task,native,source,protocol).items():
                        if inputs.get(name)!=data:issues.append('ORIGINAL_INPUT_OR_NATIVE_ATOM_ORDER:'+str(key)+':'+name)
                elif not meta.get('input_missing_reason'):issues.append('SOURCE_FAILED_WITHOUT_REASON:'+str(key))
                if raw['original_output_manifest'] and not raw['output_retained']:issues.append('ALL_POLICY_OUTPUT_LOST:'+str(key))
                atomic=validate_atomic_arrays(detail,z if z is not None else int(source['total_atoms']))
                if status=='SUCCESS':
                    if atomic or target.get('numeric_issues'):issues.append('SUCCESS_NUMERIC_OR_SHAPE:'+str(key)+':'+str(atomic or target['numeric_issues']))
                    need=['process.out']+(['input.out','input.aux'] if task['family']=='mopac' else ['xtbout.json'])
                    need+={'xtb_singlepoint':['wbo'],'xtb_fod':['fod'],'xtb_perturbed_gradient':['gradient']}.get(calc,[])
                    for name in need:
                        if name not in outputs:issues.append('SUCCESS_RAW_ARTIFACT_MISSING:'+str(key)+':'+name)
                    for name in task.get('required_values',[]):
                        value=detail.get('values',{}).get(name)
                        if value is None or value==[] or value=={}:issues.append('SUCCESS_REQUESTED_VALUE_MISSING:'+str(key)+':'+name)
                elif status in {'RUNNER_ERROR','PIPELINE_FAILURE','RESOURCE_LIMIT_FAILED'}:issues.append('TECHNICAL_TASK_FAILURE:'+str(key)+':'+status)
                for role,files in [('input',raw['input_files']),('output',raw['original_output_manifest'])]:
                    for f in files:scope.append({'record_id':rid,'molecule_id':row['molecule_id'],'calc_type':calc,'size_stratum':item['size_stratum'],
                         'attempt_id':row['attempt'],'name':f['name'],'role':role,'bytes':f.get('byte_count',f.get('bytes')),'sha256':f.get('sha256')})
                packed=reader.db.execute('SELECT input_bytes,raw_bytes,metadata_bytes,length(input_frame),length(raw_frame),length(metadata_frame) FROM records WHERE record_id=? AND calc_type=?',key).fetchone()
                compression.append({'record_id':rid,'molecule_id':row['molecule_id'],'calc_type':calc,'size_stratum':item['size_stratum'],'attempt_id':row['attempt'],
                   'logical_input_bundle_bytes':packed[0],'logical_output_bundle_bytes':packed[1],'logical_metadata_bytes':packed[2],
                   'input_frame_bytes':packed[3],'raw_frame_bytes':packed[4],'metadata_frame_bytes':packed[5],
                   'source_status':raw['source_status'],'scope_status':raw['scope_status'],'output_retained':raw['output_retained'],
                   'source_directory_total_bytes':sum(f['byte_count'] for f in raw['input_files'])+sum(f['bytes'] for f in raw['original_output_manifest']) if raw['input_files'] or raw['original_output_manifest'] else None,
                   'directory_total_definition':'complete post-QM directory capture, not intra-process highwater','scope_unknown_reason':meta.get('input_missing_reason')})
    finally:reader.close()
    return {'molecule_id':row['molecule_id'],'attempt_id':row['attempt'],'records':len(records),'raw_calc_rows':len(keys),'issues':issues,
       'counts':dict(counts),'receipt':completion['receipt'] if completion else None,'minimum_flag_record_ids':sorted(minimum_flags),
       'raw_scope':scope,'compression':compression,'pid':os.getpid()}

def audit_lane(items):
    _BARRIER.wait(timeout=120)
    return {'pid':os.getpid(),'molecules':[audit_molecule(item) for item in items]}

def check():
    import ast;ast.parse(Path(__file__).read_text())
    assert designed_node('compute-0-12')=='compute-0-15' and designed_node('compute-0-13')=='compute-0-16' and designed_node('compute-0-17')=='compute-0-17'
    assert set(FAMILY)==set(CALCS) and len(CALCS)==12
    assert concurrency([{'molecule_started_epoch':0.,'completed_epoch':2.,'worker_pid':1},{'molecule_started_epoch':1.,'completed_epoch':3.,'worker_pid':2}])['peak_active_whole_molecule_workers']==2
    print('AST_CLOSURE_AND_CONCURRENCY_PASS_NO_QM_NO_DATA')

def main():
    p=argparse.ArgumentParser();p.add_argument('--source-run',type=Path);p.add_argument('--runner',type=Path,default=ROOT/'scripts/wp5_runner_v7.py')
    p.add_argument('--designed-node');p.add_argument('--node-authority',type=Path);p.add_argument('--node-scope-plan',type=Path,default=ROOT/'packing/node_assignment_v3/tasks.json')
    p.add_argument('--dictionaries',type=Path);p.add_argument('--protocol',type=Path,default=ROOT/'configs/protocol.json');p.add_argument('--registry',type=Path)
    p.add_argument('--retry-diagnosis',type=Path);p.add_argument('--output',type=Path);p.add_argument('--hours',type=float,default=48);p.add_argument('--check',action='store_true');a=p.parse_args()
    if a.check:check();return
    node=socket.gethostname().split('.')[0];job=os.environ.get('SLURM_JOB_ID')
    if not job or node not in ACTUAL_NODES or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<24:raise ValueError('G6_ACTUAL24CPU_AUTHORIZED_12_13_14_17_18_19_REQUIRED')
    original_designed_node=designed_node(node,a.designed_node)
    if a.node_authority is None or not a.node_authority.is_file():raise ValueError('ACTUAL_NODE_AUTHORITY_RECEIPT_REQUIRED')
    if digest(a.node_authority)!=NODE_AUTHORITY_SHA or digest(a.node_scope_plan)!=NODE_SCOPE_PLAN_SHA:raise ValueError('FROZEN_NODE_AUTHORITY_OR_PLAN_SHA_CHANGED')
    authority=json.loads(a.node_authority.read_text())
    if authority.get('schema')!='WP5_NODE_REPLACEMENT_USER_APPROVAL_V1' or authority.get('status')!='USER_APPROVED' or authority.get('scientific_configuration_changed') is not False or set(authority.get('authorized_node_slots',{}))!=ACTUAL_NODES:raise ValueError('NODE_AUTHORITY_CONTENT_MISMATCH')
    scope_plan=json.loads(a.node_scope_plan.read_text())
    if {task['node'] for task in scope_plan['tasks']}!=ACTUAL_NODES:raise ValueError('NODE_ASSIGNMENT_V3_SCOPE_MISMATCH')
    node_scope={'actual_node':node,'original_designed_node':original_designed_node,
        'authority_path':str(a.node_authority),'authority_sha256':digest(a.node_authority),
        'plan_path':str(a.node_scope_plan),'plan_sha256':digest(a.node_scope_plan),'science_recipe_unchanged':True}
    if not a.dictionaries:raise ValueError('FROZEN_DICTIONARIES_REQUIRED')
    a.registry=a.registry or Path(json.loads(a.protocol.read_text())['registry']['path'])
    out=a.output or ROOT/'gates/g6_recovery'/node/('job_'+job)
    if not out.resolve().is_relative_to(ROOT):raise ValueError('ONLY_NEW_WP5_OUTPUT_ROOT')
    out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();deadline=started+min(46.,a.hours-2)*3600;phases=[];permanent=[];proof=[];original=None;cleanup_allowed=set()
    bindings=[{'path':str(path),'sha256':digest(path)} for path in [Path(__file__),a.runner,Path(__file__).with_name('wp5_accounting_v2.py'),Path(__file__).with_name('wp5_archive_v4.py'),a.protocol,a.registry,a.dictionaries,Path(__file__).with_name('wp5_engine.py'),Path(__file__).with_name('wp5_parser.py'),Path(__file__).with_name('wp5_g6_v3.py'),a.node_authority,a.node_scope_plan]]
    if a.retry_diagnosis:bindings.append({'path':str(a.retry_diagnosis),'sha256':digest(a.retry_diagnosis)})
    save(out/'metadata.json',{'node':node,'actual_node':node,'original_designed_node':original_designed_node,'node_scope':node_scope,'job_id':job,'source_run':str(a.source_run) if a.source_run else None,'source_bindings':bindings,
       'allocation_hours':a.hours,'internal_deadline_hours':min(46.,a.hours-2),'workers':24,'science_recipe_unchanged':True,
       'signal_cleanup_rule':'one cleanup for an actual signal/TIMEOUT; no claim of deterministic SCC without raw evidence; attempt1 failure remains final recorded outcome',
       'original_data_written':False,'lmdb_created':False})
    try:
        if a.source_run:
            old=a.source_run.resolve();cohort=old;selection=json.loads((old/'selected_molecules.json').read_text())
            oldrun=json.loads((old/'phase_0/run.json').read_text());options=oldrun['options'];oldcompletion=json.loads((old/'phase_0/completion.json').read_text())
            if selection['node']!=node or oldrun['node']!=node:raise ValueError('RECOVERY_MUST_USE_ORIGINAL_NODE')
            stateproof=terminal(options['job_id']);queue=Path(options['queue']);plan=old/'tasks.json';assignments=old/'assignments.parquet';original=snapshot(queue)
            durable=[r for r in original['molecules'] if r['receipt_json']]
            if len(durable)!=16 or sum(r['state']=='PENDING' for r in original['molecules'])!=4:raise ValueError('ORIGINAL_CUTOFF_NOT16_DURABLE_PLUS4_UNLAUNCHED')
            if any(r['error_count'] for r in oldcompletion['workers']) or not oldcompletion['scratch_clean']:raise ValueError('ORIGINAL_WORKER_OR_SCRATCH_ERROR')
            for key in ('dictionaries','protocol','registry'):
                if digest(options[key])!=digest(getattr(a,key)):raise ValueError('RECOVERY_FROZEN_DEPENDENCY_CHANGED:'+key)
            permanent=refs(old/'phase_0');verify(permanent);proof=[json.loads(r['receipt_json']) for r in durable]
            runner=importlib.import_module(a.runner.stem)
            # Pure finalizer: no source geometry read, minimum reset, new claims or QM.
            exported=runner.finalize_run(options);verify(permanent)
            permanent.append(exported['archive']);verify(permanent)
            phases.append({'root':str(old/'phase_0'),'completion':oldcompletion,'archive':exported['archive'],'families':exported['families'],'repair_only':True})
            save(out/'phase0_export_repair.json',{'status':'DURABLE16_REEXPORTED_WITHOUT_QM','original_job':stateproof,
                'original_run_sha256':digest(old/'phase_0/run.json'),'original_completion_sha256':digest(old/'phase_0/completion.json'),
                'original_error_preserved':oldcompletion['error'],'permanent_refs':permanent,'export':exported,'new_QM':False})
        else:
            selection,queue,plan,assignments=create_cohort(out,node,original_designed_node);cohort=out
            first=run_phase(a,out,queue,plan,assignments,'phase_0','main',16,deadline)
            if first is None:raise ValueError('NO_BUDGET_FOR_INITIAL_CUTOFF')
            phases.append(first);original=snapshot(queue);durable=[r for r in original['molecules'] if r['receipt_json']]
            if len(durable)!=16 or sum(r['state']=='PENDING' for r in original['molecules'])!=4:raise ValueError('INITIAL_CUTOFF_NOT16_DURABLE_PLUS4_UNLAUNCHED')
            proof=[json.loads(r['receipt_json']) for r in durable];permanent=refs(out/'phase_0')+[first['archive']];verify(permanent)
        save(out/'queue_before_resume.json',original)
        if a.retry_diagnosis:
            diagnosis=json.loads(a.retry_diagnosis.read_text())
            relevant=[c for c in diagnosis['cases'] if c['source_run']==str(cohort)]
            save(out/'prior_retry_raw_evidence.json',{'source_report':str(a.retry_diagnosis),'sha256':digest(a.retry_diagnosis),'cases':relevant,
                  'interpretation':'SIGSEGV is preserved as a signal failure, not renamed SCF; one cleanup is authorized. No extra diagnostic QM.'})
            deterministic={c['molecule_id'] for c in relevant if c['classification']['classification']=='DETERMINISTIC_METHOD_FAILURE'}
            if deterministic:raise ValueError('EVIDENCED_METHOD_FAILURE_REQUIRES_QUEUE_CLASSIFICATION_NOT_SIGNAL_RETRY')
        second=run_phase(a,out,queue,plan,assignments,'phase_main','main',0,deadline)
        if second:phases.append(second)
        verify(permanent);before=snapshot(queue);save(out/'queue_before_cleanup.json',before)
        unlaunched=[r for r in before['molecules'] if r['state']=='PENDING']
        retry=[r for r in before['molecules'] if r['state']=='RETRY_PENDING']
        cleanup_allowed={r['molecule_id'] for r in retry}
        if any(r['attempt']!=0 or not r['receipt_json'] for r in retry):raise ValueError('RETRY_WITHOUT_ATTEMPT0_DURABLE_RECEIPT')
        # main only claims the original four pending molecules. Cleanup has its
        # own session/attempt, and never claims a COMPLETE molecule.
        if not unlaunched and retry:
            cleaned=run_phase(a,out,queue,plan,assignments,'phase_cleanup','cleanup',0,deadline)
            if cleaned:phases.append(cleaned)
        final=snapshot(queue);save(out/'queue_after_resume.json',final);verify(permanent)
        by_id={r['molecule_id']:r for r in final['molecules']};original_ids={r['molecule_id'] for r in original['molecules']}
        if len(original_ids)!=20 or set(by_id)!=original_ids:raise ValueError('ORIGINAL20_MOLECULE_POPULATION_CHANGED')
        for row in original['molecules']:
            current=by_id[row['molecule_id']]
            if current['attempt']>1:raise ValueError('MORE_THAN_ONE_CLEANUP_ATTEMPT')
            if row['receipt_json'] and current['receipt_json']!=row['receipt_json'] and row['molecule_id'] not in cleanup_allowed:
                raise ValueError('DURABLE_FIRST16_RECOMPUTED_WITHOUT_TRANSIENT_EVIDENCE')
            if row['receipt_json'] and row['molecule_id'] not in cleanup_allowed and current['attempt']!=row['attempt']:raise ValueError('ORDINARY_DURABLE_ATTEMPT_CHANGED')
        remaining=[{'molecule_id':r['molecule_id'],'state':r['state'],'attempt':r['attempt']} for r in final['molecules'] if r['state']!='COMPLETE']
        if remaining:
            save(out/'report.json',{'status':'G6_RECORDED_INCOMPLETE_REQUIRES_RESUME','remaining':remaining,'node':node,'actual_node':node,'original_designed_node':original_designed_node,'node_scope':node_scope,'source_run':str(cohort),'queue':str(queue),
                 'phases':[phase['root'] for phase in phases],'permanent_first_phase_unchanged':True,'elapsed_seconds':time.monotonic()-started,'source_bindings':bindings})
            print(json.dumps({'report':str(out/'report.json'),'status':'G6_RECORDED_INCOMPLETE'}));return
        import pyarrow as pa,pyarrow.parquet as pq
        population=pq.read_table(cohort/'record_index/records.parquet').to_pylist();records=collections.defaultdict(list)
        for row in population:records[row['molecule_id']].append(row)
        if set(records)!=original_ids or len(population)!=sum(row['records'] for row in selection['molecules']):raise ValueError('COHORT_RECORD_POPULATION_CHANGED')
        heavy={row['molecule_id']:row['max_heavy_atoms'] for row in selection['molecules']}
        def stratum(h):return next(label for limit,label in [(10,'0_10'),(20,'11_20'),(30,'21_30'),(50,'31_50'),(75,'51_75'),(100,'76_100'),(10**9,'above_100')] if h<=limit)
        items=[{'queue_row':row,'records':records[row['molecule_id']],'registry':str(a.registry),'protocol':str(a.protocol),
           'dictionaries':str(a.dictionaries),'size_stratum':stratum(heavy[row['molecule_id']])} for row in final['molecules']]
        context=multiprocessing.get_context('spawn');barrier=context.Barrier(24)
        with concurrent.futures.ProcessPoolExecutor(max_workers=24,mp_context=context,initializer=bind,initargs=(barrier,)) as pool:
            audits_by_lane=list(pool.map(audit_lane,[items[i::24] for i in range(24)]))
        audits=[mol for lane in audits_by_lane for mol in lane['molecules']];issues=[{'molecule_id':mol['molecule_id'],'issue':issue} for mol in audits for issue in mol['issues']]
        measured=concurrency(proof)
        if len(measured['worker_pids'])<16 or measured['peak_active_whole_molecule_workers']<16:issues.append({'issue':'FIRST_PHASE_ACTUAL_CONCURRENCY_BELOW16'})
        verify(permanent)
        for field,name in [('raw_scope','raw_scope_members.parquet'),('compression','raw_compression_by_record.parquet')]:
            rows=[row for mol in audits for row in mol[field]]
            if rows:pq.write_table(pa.Table.from_pylist(rows),out/name,compression='zstd')
        counts=collections.Counter()
        for mol in audits:counts.update(mol['counts'])
        report={'status':'G6_FULL_CHAIN_PASSED_WITH_RECORDED_SCIENTIFIC_OUTCOMES' if not issues else 'G6_CHAIN_NOT_PASS','node':node,'actual_node':node,'original_designed_node':original_designed_node,'node_scope':node_scope,'job_id':job,
           'molecules':len(audits),'records':len(population),'latest_raw_calc_rows':sum(mol['raw_calc_rows'] for mol in audits),'expected_latest_raw_calc_rows':12*len(population),
           'latest_attempt_selection':'queue latest completed receipt/export; previous attempt archive and permanent Parquet retained separately',
           'task_status_counts':dict(counts),'issues':issues,'reader_worker_pids':sorted({lane['pid'] for lane in audits_by_lane}),
           'first_phase_concurrency':measured,'artificial_cutoff_completed':16,'resume_originally_unlaunched':4,'cleanup_molecules':sorted(cleanup_allowed),
           'permanent_first_phase_unchanged':True,'source_bindings':bindings,'scientific_failures_are_chain_failures':False,
           'phases':[{'root':phase['root'],'archive':phase['archive'],'completion_path':str(Path(phase['root'])/'completion.json'),'repaired_without_QM':phase.get('repair_only',False)} for phase in phases],
           'historical_attempts':[{'molecule_id':r['molecule_id'],'attempt':r['attempt'],'original_receipt_sha256':hashlib.sha256(r['receipt_json'].encode()).hexdigest()} for r in original['molecules'] if r['receipt_json']],
           'raw_minimum_flags_by_molecule':{mol['molecule_id']:mol['minimum_flag_record_ids'] for mol in audits},
           'minimum_flag_context':('Original recovery metadata stays ALL-retained; new claims use the fixed minimum rule' if a.source_run else 'Fresh replacement cohort uses fixed minimum rule for all20 molecules; original designed seed retained; no history mutation'),
           'resource_peaks':[phase['completion'].get('resource_peaks') for phase in phases],'elapsed_seconds':time.monotonic()-started,
           'five_file_groups':sorted({r['file_group'] for r in selection['molecules']}),'seven_size_strata':sorted({stratum(r['max_heavy_atoms']) for r in selection['molecules']}),
           'largest_pilot_eligible_molecule':selection['largest_pilot_eligible_molecule'],'largest_pilot_eligible_total_atoms':selection['largest_total_atoms'],
           'queue':str(queue),'source_run':str(cohort),'wrapper_process_signals':False,'original_data_written':False,'lmdb_created':False}
        save(out/'report.json',report);print(json.dumps({'report':str(out/'report.json'),'status':report['status'],'issues':len(issues)}))
    except BaseException:
        save(out/'harness_error.json',{'status':'G6_HARNESS_RECORDED_ERROR','traceback':traceback.format_exc(),'queue_preserved':True,'phases':[phase['root'] for phase in phases],'elapsed_seconds':time.monotonic()-started});raise
if __name__=='__main__':main()
