"""Current-policy exact50 audit records, two same-environment600-task runs, parsed comparison."""
from __future__ import annotations
import argparse,ast,collections,concurrent.futures,hashlib,json,math,os,socket,struct,subprocess,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
CALCS=('pm7_B','pm7_cation','pm7_anion','pm7_water','pm7_octanol','xtb_singlepoint','xtb_vipea','xtb_vfukui','xtb_ALPB_water','xtb_ALPB_octanol','xtb_fod','xtb_perturbed_gradient')
AUTH_SHA='b368187eb93d0641c0628fc33ed447192cf0e260bcfb0e01230812c49ba72b2c'
_C={}
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8<<20),b''):h.update(block)
    return h.hexdigest()
def q(value):return "'"+str(value).replace("'","''")+"'"
def save(path,data):
    path=Path(path)
    if path.exists():raise FileExistsError(path)
    with path.open('x') as stream:json.dump(data,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
def copy(db,sql,path):
    temporary=Path(str(path)+'.pending')
    db.execute('COPY ('+sql+') TO '+q(temporary)+' (FORMAT PARQUET,COMPRESSION ZSTD,ROW_GROUP_SIZE 131072)')
    with temporary.open('rb') as stream:os.fsync(stream.fileno())
    temporary.rename(path)
def allocated(workers):
    if not os.environ.get('SLURM_JOB_ID') or workers<24 or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<workers or socket.gethostname().split('.')[0]!='compute-0-17':
        raise ValueError('50repeat requires actual same node17,24CPU/32GiB allocation')
def prepare(a):
    import duckdb,pyarrow as pa,pyarrow.parquet as pq
    allocated(a.workers)
    if not a.audit_membership or not a.reproduction_package or not a.production_contract:raise ValueError('Actual fixed audit/package/production contract required')
    if sha(a.authority)!=AUTH_SHA:raise ValueError('New user authority changed')
    audit=json.loads(a.audit_membership.read_text());package=json.loads(a.reproduction_package.read_text())
    if audit['status']!='AUDIT_MEMBERSHIP_CLOSED' or package['status']!='REPRODUCTION_PACKAGE_CLOSED':raise ValueError('Actual audit/package must close')
    if package['audit_membership']['sha256']!=sha(a.audit_membership):raise ValueError('Package audit authority differs')
    if sha(audit['selected_records']['path'])!=audit['selected_records']['sha256']:raise ValueError('Fixed audit selected records SHA changed')
    out=a.out or ROOT/'gates/reproduction50'/('plan_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
    db=duckdb.connect();db.execute('SET threads='+str(a.workers));db.execute("SET memory_limit='20GB'")
    db.execute('CREATE VIEW audit AS SELECT * FROM read_parquet('+q(audit['selected_records']['path'])+')')
    db.execute("CREATE VIEW chosen AS SELECT record_id FROM audit ORDER BY md5(record_id||'|repeat50|"+str(a.seed)+"'),record_id LIMIT50".replace('LIMIT50','LIMIT 50'))
    db.execute('CREATE VIEW formal AS SELECT * FROM read_parquet('+q(a.population)+')')
    directory=out/'record_index';directory.mkdir()
    copy(db,'SELECT f.*,TRUE AS audit_selected FROM formal f JOIN chosen USING(record_id) ORDER BY molecule_id,conformer_id,record_id',directory/'records.parquet')
    selected=pq.read_table(directory/'records.parquet').to_pylist()
    if len(selected)!=50 or len({row['record_id'] for row in selected})!=50:raise ValueError('EXACT50_PHYSICAL_RECORDS_REQUIRED')
    db.execute('CREATE VIEW costs AS SELECT * FROM read_parquet('+q(ROOT/'packing/molecule_assignments.parquet')+')')
    names=('molecule_id','records','file_group','original_total_records','planned_allocated_seconds')
    assignments=[dict(zip(names,row)) for row in db.execute('SELECT f.molecule_id,count(*),max(f.file_group),max(c.records),max(c.planned_allocated_seconds)*count(*)/max(c.records) FROM formal f JOIN chosen USING(record_id) JOIN costs c USING(molecule_id) GROUP BY f.molecule_id ORDER BY5 DESC,f.molecule_id'.replace('ORDER BY5','ORDER BY 5')).fetchall()]
    for index,row in enumerate(assignments):row.update(task_id=0,sequence_in_task=index)
    pq.write_table(pa.Table.from_pylist(assignments),out/'molecule_assignments.parquet',compression='zstd')
    save(out/'tasks.json',{'schema':'WP5_NEW_POLICY_50_RECORD_REPRODUCTION_SUBSET','tasks':[{'task_id':0,'node':'compute-0-17','record_directory':str(directory)}]})
    protocol=ROOT/'configs/protocol.json';common=[str(a.python),str(a.runner),'--plan',str(out/'tasks.json'),'--assignments',str(out/'molecule_assignments.parquet'),
      '--task-id','0','--dictionaries',str(a.dictionaries),'--node-authority',str(ROOT/'gates/wp5_node_replacement_user_approved.json'),
      '--node-scope-plan',str(ROOT/'packing/node_assignment_v3/tasks.json'),'--audit-membership',str(a.audit_membership),
      '--reproduction-package',str(a.reproduction_package),'--production-contract',str(a.production_contract),'--policy','FAILURES_PLUS_STRATIFIED_RECORD_AUDIT_NO_INPUT','--smoke','--hours','20','--workers','24']
    commands=[]
    for run in (1,2):commands.append(common+['--queue',str(out/('queue_run'+str(run)+'.sqlite')),'--run-root',str(out/('run'+str(run)))])
    plan={'schema':'WP5_REPRODUCTION50_DOUBLE_V1','status':'PREPARED_NOT_RUN','records':50,'runs':2,'tasks_per_run':600,'total_requested_tasks':1200,'selected_record_ids':[row['record_id'] for row in selected],
      'selected_molecules':len(assignments),'selection':'Independent seed uniform record hash among the lawfully fixed stratified1% audit records, no first50/minimum/molecule-biased selection','secondary_seed':a.seed,
      'record_index':str(directory/'records.parquet'),'record_index_sha256':sha(directory/'records.parquet'),'commands':commands,'actual_node':'compute-0-17',
      'input_context':'Native z/coords/SMILES/energy/source pointers and precomputed population QC from full formal index; all same-record12 methods execute. Derived vertical IP/EA/solvent differences/Fukui use the same selected record geometry/12 tasks, not other conformers. Existing whole-molecule QC/maxsize context is preserved; no recomputation from the subset.',
      'runtime_retry_scope':'No cleanup/retry expansion: exactly two independent intended600-task runs. Natural outcomes recorded; unfinished/closure failure stops this validation.',
      'bindings':{name:{'path':str(path),'sha256':sha(path)} for name,path in [('runner',a.runner),('parser',ROOT/'scripts/wp5_parser.py'),('wire',ROOT/'scripts/wp5_parquet_v2.py'),('engine',ROOT/'scripts/wp5_engine_v2.py'),('coverage',ROOT/'scripts/wp5_registry_coverage.py'),('audit',a.audit_membership),('package',a.reproduction_package),('contract',a.production_contract),('dictionaries',a.dictionaries),('authority',a.authority),('protocol',protocol)]},
      'new_QM_calls':0,'final200_waived':False}
    save(out/'plan.json',plan);db.close();print(json.dumps({'plan':str(out/'plan.json'),'records':50,'requested_tasks':1200}))
def run(a):
    allocated(a.workers);plan=json.loads(a.plan.read_text())
    if plan['records']!=50 or plan['total_requested_tasks']!=1200:raise ValueError('Exact50x2 scope required')
    for entry in plan['bindings'].values():
        if sha(entry['path'])!=entry['sha256']:raise ValueError('Frozen50 reproduction dependency changed:'+entry['path'])
    # Both invocations share this allocation/node/env; each gets a fresh private queue/scratch.
    result=[]
    for ordinal,command in enumerate(plan['commands'],1):
        started=time.monotonic();process=subprocess.run(command,stdin=subprocess.DEVNULL)
        report={'run':ordinal,'returncode':process.returncode,'seconds':time.monotonic()-started,'command':command}
        save(a.plan.parent/('run'+str(ordinal)+'_invocation.json'),report);result.append(report)
        if process.returncode:raise RuntimeError('REPRODUCTION50_RUNTIME_FAILED_NO_FORMAL')
    print(json.dumps({'plan':str(a.plan),'runs':result,'new_requested_tasks':1200}))
def bits(a,b):
    import wp5_parquet_v2 as wire
    if a is wire.MISSING or b is wire.MISSING:return a is b
    if type(a)!=type(b):return False
    if isinstance(a,dict):return a.keys()==b.keys() and all(bits(a[key],b[key]) for key in a)
    if isinstance(a,list):return len(a)==len(b) and all(bits(x,y) for x,y in zip(a,b))
    if isinstance(a,float):return struct.pack('>d',a)==struct.pack('>d',b)
    return a==b
def rounded(a,b,tol):
    if type(a)!=type(b):return False
    if isinstance(a,dict):return a.keys()==b.keys() and all(rounded(a[key],b[key],tol) for key in a)
    if isinstance(a,list):return len(a)==len(b) and all(rounded(x,y,tol) for x,y in zip(a,b))
    if isinstance(a,float):return math.isfinite(a) and math.isfinite(b) and abs(a-b)<=tol
    return a==b
def numeric_count(value):
    if isinstance(value,float):return int(math.isfinite(value))
    if isinstance(value,list):return sum(numeric_count(item) for item in value)
    if isinstance(value,dict):return sum(numeric_count(item) for item in value.values())
    return 0
def value_sha(value):
    import wp5_parquet_v2 as wire
    def encode(x):
        if x is wire.MISSING:return {'ABSENT':True}
        if isinstance(x,float):return {'f64':struct.pack('>d',x).hex()}
        if isinstance(x,list):return [encode(y) for y in x]
        if isinstance(x,dict):return {str(k):encode(v) for k,v in sorted(x.items())}
        return x
    return hashlib.sha256(json.dumps(encode(value),sort_keys=True,separators=(',',':')).encode()).hexdigest()
def reconstruct(row,entries):
    import wp5_parquet_v2 as wire
    result={'record_id':row['record_id'],'task':row['calc_type'],'status':row['status'],'values':{}}
    for cell in row['values']:
        entry=entries[cell['registry_id']];value=wire.decode(cell)
        if value is wire.MISSING:continue
        parts=entry['source_path'].strip('/').replace('/','.').split('.')
        if parts[0] in ('detail','details'):parts=parts[1:]
        elif parts[0]!='values':parts=['values']+parts
        target=result
        for part in parts[:-1]:target=target.setdefault(part,{})
        target[parts[-1]]=value
    return result
def init(options):
    global _C
    _C=dict(options)
    _C['readers']={}
    if _C.get('barrier') is not None:_C['barrier'].wait(timeout=180)
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
def output_files(run,record_id,calc_type):
    from wp5_archive_v5 import ArchiveReader
    readers=_C['readers']
    if run not in readers:readers[run]=ArchiveReader(_C['archives'][run],_C['dictionaries'])
    value=readers[run].get(record_id,calc_type)
    if value.get('input_files') or value.get('input_bodies_saved'):raise ValueError('INPUT_BYTES_SAVED_AGAINST_USER_OVERRIDE')
    files=value.get('output_files') or []
    for item in files:
        if item.get('role')=='input':raise ValueError('INPUT_MEMBER_SAVED_AGAINST_USER_OVERRIDE')
        if not isinstance(item.get('data'),bytes) or hashlib.sha256(item['data']).hexdigest()!=item.get('sha256'):raise ValueError('ARCHIVE_OUTPUT_MEMBER_READBACK_FAILED')
    return files

def compare_task(arg):
    left,right,z=arg
    files1=output_files(1,left['record_id'],left['calc_type'])
    files2=output_files(2,right['record_id'],right['calc_type'])
    import wp5_parquet_v2 as wire,wp5_engine_v2 as engine,wp5_registry_coverage as coverage,wp5_parser
    entries=_C['entries'];key=(left['record_id'],left['calc_type']);errors=[];counts=collections.Counter();fieldstats=[]
    def error(code,field,x,y,tolerance=None):
        errors.append({'record_id':key[0],'calc_type':key[1],'code':code,'field':field,'left_sha256':value_sha(x),'right_sha256':value_sha(y),'absolute_tolerance':tolerance})
    for row,files in ((left,files1),(right,files2)):
        if not files and row['status']=='SUCCESS':error('AUDIT_COMPLETE_OUTPUT_NOT_RETAINED','output_files',[],None)
    deterministic=('status','source_status','failure_code','total_atoms','software_version_id','scf_iterations','converged','input_file_sha256','input_bundle_sha256','raw_audit_selected','reproduction_package_sha256')
    for name in deterministic:
        if name not in left or name not in right:error('TRACE_FIELD_OR_STATUS_MISSING',name,left.get(name),right.get(name));continue
        if not bits(left[name],right[name]):error('TRACE_OR_STATUS_DIFF',name,left[name],right[name])
    for row in (left,right):
        if row['raw_audit_selected'] is not True:error('AUDIT_SAMPLE_LOST_SELECTION','raw_audit_selected',row['raw_audit_selected'],True)
        if row['status'] in ('PIPELINE_FAILURE','RUNNER_ERROR','Q03_SOURCE_READ_FAILED','NOT_STARTED_DEADLINE','NOT_STARTED_STOP'):error('PIPELINE_OR_UNFINISHED_OUTCOME','status',row['status'],None)
        if row.get('elapsed_seconds') is None:error('TRACE_ELAPSED_MISSING','elapsed_seconds',None,None)
        if row.get('elapsed_seconds') is not None and (not math.isfinite(row['elapsed_seconds']) or row['elapsed_seconds']<0):error('INVALID_TRACE_ELAPSED','elapsed_seconds',row['elapsed_seconds'],None)
        if row.get('scf_iterations') is not None and (type(row['scf_iterations']) is not int or row['scf_iterations']<0):error('INVALID_TRACE_SCF','scf_iterations',row['scf_iterations'],None)
        if row.get('converged') is not None and type(row['converged']) is not bool:error('INVALID_TRACE_CONVERGED','converged',row['converged'],None)
        family='mopac' if key[1].startswith('pm7_') else 'xtb'
        if row.get('software_version_id')!=_C['software_versions'][family]['software_version_id']:error('SOFTWARE_ID_PACKAGE_MISMATCH','software_version_id',row.get('software_version_id'),None)
        if row['status']!='CALCULATION_FAILED' and not row.get('input_file_sha256'):error('INPUT_TRACE_MISSING','input_file_sha256',row.get('input_file_sha256'),None)
        names=[item.get('name') for item in row.get('input_file_sha256') or []]
        if len(names)!=len(set(names)):error('DUPLICATE_INPUT_FILE_TRACE','input_file_sha256',names,None)
        if row.get('reproduction_package_sha256')!=_C['package_sha256']:error('PACKAGE_ROW_BINDING_DIFFERS','reproduction_package_sha256',row.get('reproduction_package_sha256'),_C['package_sha256'])
        for file in row.get('input_file_sha256') or []:
            if not file.get('name') or len(file.get('sha256') or '')!=64:error('INVALID_INPUT_FILE_TRACE','input_file_sha256',file,None)
    cells1={cell['registry_id']:cell for cell in left['values']};cells2={cell['registry_id']:cell for cell in right['values']}
    expected={rid for rid,entry in entries.items() if entry['task']==key[1]}
    if set(cells1)!=expected or set(cells2)!=expected or len(cells1)!=len(left['values']) or len(cells2)!=len(right['values']):error('ACTIVE_REGISTRY_ID_OMISSION_OR_DUPLICATE','values',sorted(cells1),sorted(cells2))
    precisions=[json.loads(row.get('precision_by_field_json') or '{}') for row in (left,right)]
    for rid in sorted(expected):
        if rid not in cells1 or rid not in cells2:continue
        entry=entries[rid];a=wire.decode(cells1[rid]);b=wire.decode(cells2[rid])
        kinds=(cells1[rid]['kind'],cells2[rid]['kind']);presence=tuple({0:'NULL',9:'ABSENT',10:'NONFINITE'}.get(kind,'EMPTY' if value==[] or value=={} else 'VALUE') for kind,value in zip(kinds,(a,b)))
        if kinds[0]==10 or kinds[1]==10:error('EXPLICIT_NONFINITE_OUTPUT',entry['source_path'],a,b)
        for cell in (cells1[rid],cells2[rid]):
            if cell['kind'] in (5,6,7):
                payload=cell[{5:'array_f64',6:'array_i64',7:'array_bool'}[cell['kind']]]
                if math.prod(cell['shape'])!=len(payload):error('TYPED_ARRAY_SHAPE_INVALID',entry['source_path'],cell['shape'],len(payload))
        if entry.get('classification')=='provenance':continue
        if entry['source_path']=='values.mulliken_overlap_qc':
            if isinstance(a,dict):a={name:value for name,value in a.items() if name not in ('elapsed_seconds','wall_seconds')}
            if isinstance(b,dict):b={name:value for name,value in b.items() if name not in ('elapsed_seconds','wall_seconds')}
        path=entry['source_path'];precision_key=path.removeprefix('values.');tol=None
        p1,p2=(item.get(precision_key,item.get(path)) for item in precisions)
        if type(p1) is int and type(p2) is int and 0<=p1<=18 and 0<=p2<=18:
            tol=min(.5*10.**(-p1),.5*10.**(-p2))
            if precision_key=='dipole_Debye':tol*=wp5_parser.AU_DIPOLE_TO_DEBYE
        if bits(a,b):result='MATCH_BITS'
        elif tol is not None and rounded(a,b,tol):result='DECLARED_PRECISION_MATCH'
        else:result='DIFF';error('PARSED_SCIENTIFIC_DIFF',path,a,b,tol)
        counts[result]+=1;numeric=min(numeric_count(a),numeric_count(b));counts['finite_numeric_values_compared']+=numeric
        fieldstats.append({'record_id':key[0],'calc_type':key[1],'registry_id':rid,'classification':entry['classification'],'presence_run1':presence[0],'presence_run2':presence[1],'comparison':result,'finite_numeric_values_compared':numeric,'absolute_tolerance':tol})
    details=[reconstruct(row,entries) for row in (left,right)]
    coverage_rows=[]
    for ordinal,(detail,row,files) in enumerate(zip(details,(left,right),(files1,files2)),1):
        issues=engine.validate_atomic_arrays(detail,z)
        if issues:error('ATOMIC_N_OR_FINITE_QC',str(ordinal),issues,None)
        audit=coverage.audit_task(detail,list(entries.values()),serialized_row=row,files=files)
        if audit['issues']:error('REGISTRY_EXTRACTION_COVERAGE',str(ordinal),audit['issues'],None)
        for value in audit['rows']:
            reason=value['source_reason']
            # Native star/nonnumeric/unsupported outputs are honest failed properties;
            # source token with a successful missing value is a parser gap.
            if 'SOURCE_TOKEN_PRESENT' in reason and row['status']=='SUCCESS':error('SOURCE_TOKEN_PARSER_GAP',value['source_path'],value['observed_state'],reason)
            coverage_rows.append({'record_id':key[0],'calc_type':key[1],'run':ordinal,'registry_id':value['registry_id'],'state':value['observed_state'],'source_reason':reason,'encoding_coverage':value['encoding_coverage']})
    return {'errors':errors,'counts':dict(counts),'fields':fieldstats,'coverage':coverage_rows,'worker_pid':os.getpid(),'natural_failure':left['status']!='SUCCESS','calc_type':key[1]}
def load_run(root,selected):
    import pyarrow.parquet as pq,wp5_parquet_v2 as wire
    completion=json.loads((root/'export_completion.json').read_text());rows={};families={}
    schemas={'base_geometry':wire.BASE_SCHEMA,'D20':wire.D20_SCHEMA,'D3':wire.D3_SCHEMA,'QC':wire.QC_SCHEMA}
    for ref in completion['families']:
        if sha(ref['path'])!=ref['sha256']:raise ValueError('IMMUTABLE50_PARQUET_CHANGED')
        file=pq.ParquetFile(ref['path']);schema=schemas.get(ref['family'],wire.SCHEMA)
        if not file.schema_arrow.remove_metadata().equals(schema.remove_metadata()):raise ValueError('UNKNOWN50_FAMILY_SCHEMA')
        values=file.read().to_pylist()
        for row in values:
            if row['record_id'] not in selected:raise ValueError('50_RUN_EXPANDED_RECORD_SCOPE')
            if ref['family'] in schemas:
                if row['record_id'] in families.setdefault(ref['family'],{}):raise ValueError('DUPLICATE50_NONQM_RECORD')
                families[ref['family']][row['record_id']]=row
            else:
                key=(row['record_id'],row['calc_type'])
                if key in rows:raise ValueError('DUPLICATE50_SLOT')
                rows[key]=row
    if len(rows)!=600 or set(rows)!={(rid,task) for rid in selected for task in CALCS}:raise ValueError('50_BY12_RUN_NOT_CLOSED')
    for family in schemas:
        if len(families.get(family,{}))!=50:raise ValueError('50_NONQM_FAMILY_NOT_CLOSED:'+family)
    archive=completion['archive']
    if sha(archive['path'])!=archive['sha256']:raise ValueError('ARCHIVE50_IMMUTABLE_SHA_CHANGED')
    # Output bodies are read only one task at a time inside the 24 comparison workers.
    return rows,families,completion

def nonqm_issues(family,row,n):
    issues=[]
    def finite(value):
        if isinstance(value,float):return math.isfinite(value)
        if isinstance(value,list):return all(finite(item) for item in value)
        if isinstance(value,dict):return all(finite(item) for item in value.values())
        return True
    if not finite(row):issues.append('NONFINITE_FLOAT')
    if family=='base_geometry':
        z=row.get('atomic_numbers');p=row.get('positions_A')
        if z is None or len(z)!=n or any(type(v) is not int or not 1<=v<=118 for v in z):issues.append('ATOMIC_NUMBERS')
        if p is None or len(p)!=n or any(len(v)!=3 or any(type(x) is not float or not math.isfinite(x) for x in v) for v in p):issues.append('NATIVE_N_BY_3_COORDINATES')
        pairs=row.get('bond_pairs');codes=row.get('bond_order_codes')
        if (pairs is None)!=(codes is None):issues.append('BOND_PAIR_CODE_NULL_MASK')
        if pairs is not None and (len(pairs)!=len(codes) or any(len(p)!=2 or any(type(i) is not int or not 0<=i<n for i in p) for p in pairs) or any(c not in range(1,6) for c in codes)):issues.append('BOND_PAIR_CODE_SHAPE_OR_RANGE')
        if row.get('new_PM7_HOF_valid') is True and row.get('new_PM7_HOF_kcal_mol') is None:issues.append('VALID_HOF_MISSING')
    elif family=='D20':
        values=row.get('values_float64');mask=row.get('valid_mask');names=row.get('descriptor_names')
        if values is None or mask is None or names is None or len(values)!=20 or len(mask)!=20 or len(names)!=20:issues.append('D20_REQUIRED_SIZE20')
        elif any(type(flag) is not bool or (flag and (type(v) is not float or not math.isfinite(v))) or (not flag and v is not None) for v,flag in zip(values,mask)):issues.append('D20_VALUE_VALIDITY_MASK')
        elif row.get('status')=='SUCCESS' and not all(mask):issues.append('D20_SUCCESS_WITH_MISSING_VALUES')
    elif family=='D3':
        scalars=[row.get(key) for key in ('PMI1','PMI2','PMI3','PBF_A','volume_A3','SASA_total_A2')]
        atom=row.get('SASA_atom_A2')
        complete=all(type(v) is float and math.isfinite(v) for v in scalars) and atom is not None and len(atom)==n and all(type(v) is float and math.isfinite(v) for v in atom)
        if atom is not None and len(atom)!=n:issues.append('D3_SASA_ATOM_COUNT')
        if row.get('status')=='SUCCESS' and not complete:issues.append('D3_SUCCESS_WITH_MISSING_VALUES')
    elif family=='QC':
        tasks=row.get('task_statuses') or []
        if len(tasks)!=12 or {item['calc_type'] for item in tasks}!=set(CALCS):issues.append('QC_REQUESTED12_TASK_CLOSURE')
    return issues

def compare(a):
    allocated(a.workers)
    import pyarrow as pa,pyarrow.parquet as pq,wp5_parquet_v2 as wire,wp5_registry_coverage as coverage,multiprocessing
    plan=json.loads(a.plan.read_text());package=json.loads(Path(plan['bindings']['package']['path']).read_text())
    for entry in plan['bindings'].values():
        if sha(entry['path'])!=entry['sha256']:raise ValueError('Frozen50 comparison dependency changed')
    out=a.out or a.plan.parent/'comparison';out.mkdir(parents=True,exist_ok=False)
    protocol=json.loads(Path(plan['bindings']['protocol']['path']).read_text())
    options={'entries':{entry['registry_id']:entry for entry in coverage.entries(protocol['registry']['path'])},'dictionaries':plan['bindings']['dictionaries']['path'],'software_versions':package['software_versions'],'package_sha256':plan['bindings']['package']['sha256']}
    init(options);selected=set(plan['selected_record_ids']);left,lf,lc=load_run(a.plan.parent/'run1',selected);right,rf,rc=load_run(a.plan.parent/'run2',selected)
    options['archives']={1:lc['archive']['path'],2:rc['archive']['path']}
    errors=[];fields=[];sources=[];counts=collections.Counter();status=collections.Counter();pids=set();by_method=collections.Counter()
    ctx=multiprocessing.get_context('spawn');options['barrier']=ctx.Barrier(a.workers)
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=ctx,initializer=init,initargs=(options,)) as pool:
        arguments=((left[key],right[key],lf['base_geometry'][key[0]]['atomic_numbers']) for key in sorted(left))
        for result in pool.map(compare_task,arguments,chunksize=1):
            errors.extend(result['errors']);fields.extend(result['fields']);sources.extend(result['coverage']);counts.update(result['counts']);pids.add(result['worker_pid'])
            by_method[result['calc_type']]+=result['counts'].get('finite_numeric_values_compared',0);status[(result['calc_type'],'FAILURE' if result['natural_failure'] else 'SUCCESS')]+=1
    # Base/D20/D3/QC physical values also compare; preserved full-population context is not regenerated.
    ignored={'record_id','molecule_id','file_group','attempt_id','job_id','task_id','lane','source_path','real_index','source_payload_sha256','population_QC_json'}
    for family in lf:
        for rid in selected:
            n=len(lf['base_geometry'][rid].get('atomic_numbers') or [])
            for ordinal,row in enumerate((lf[family][rid],rf[family][rid]),1):
                issues=nonqm_issues(family,row,n)
                if issues:errors.append({'record_id':rid,'calc_type':family,'code':'NONQM_SCHEMA_N_OR_FINITE','field':'run'+str(ordinal),'left_sha256':value_sha(issues),'right_sha256':None,'absolute_tolerance':None})
            for name in lf[family][rid]:
                if name in ignored:continue
                x,y=lf[family][rid][name],rf[family][rid][name]
                if family=='QC' and name=='task_statuses':
                    x=[{k:v for k,v in row.items() if k not in ('elapsed_seconds','predicted_seconds')} for row in x]
                    y=[{k:v for k,v in row.items() if k not in ('elapsed_seconds','predicted_seconds')} for row in y]
                if not bits(x,y):errors.append({'record_id':rid,'calc_type':family,'code':'NONQM_SCIENTIFIC_DIFF','field':name,'left_sha256':value_sha(x),'right_sha256':value_sha(y),'absolute_tolerance':None})
    no_numeric=[calc for calc in CALCS if by_method[calc]==0]
    precision_manifest={'schema':'WP5_REPRODUCTION50_FIELD_PRECISION_V1','parser':plan['bindings']['parser'],
      'default':'Exact float64 bit pattern and type/shape; no unrecorded field tolerance',
      'conditional_tolerance':'Both original per-field declarations required; smaller half-unit of the last declared decimal place. Only stdout-au dipole multiplies frozen AU_DIPOLE_TO_DEBYE.',
      'observations':[{'record_id':key[0],'calc_type':key[1],'run':ordinal,'precision_by_field':json.loads(row.get('precision_by_field_json') or '{}')} for key in sorted(left) for ordinal,row in enumerate((left[key],right[key]),1)]}
    save(out/'precision_manifest.json',precision_manifest)
    sourcecounts=collections.Counter((row['registry_id'],row['state'],row['source_reason']) for row in sources)
    expected_ids=set(options['entries']);observed_ids={row['registry_id'] for row in sources}
    if observed_ids!=expected_ids:errors.append({'record_id':None,'calc_type':'G5','code':'ACTIVE_REGISTRY_CATALOGUE_OMISSION','field':'registry_id','left_sha256':value_sha(sorted(observed_ids)),'right_sha256':value_sha(sorted(expected_ids)),'absolute_tolerance':None})
    g5={'schema':'WP5_CURRENT_REGISTRY_EXTRACTION_EVIDENCE_V1','expected_active_registry_fields':len(expected_ids),
      'observed_active_registry_fields':len(observed_ids),'omitted_catalogue_ids':sorted(expected_ids-observed_ids),
      'source_evidence':[{'registry_id':rid,'state':state,'source_reason':reason,'observations':number} for (rid,state,reason),number in sorted(sourcecounts.items())],
      'parser_source':plan['bindings']['parser'],'coverage_source':plan['bindings']['coverage'],
      'natural_missingness_is_not_numeric_coverage':True,'registry_coverage_parquet':str(out/'registry_coverage.parquet')}
    save(out/'G5_registry_extraction_evidence.json',g5)
    schema=pa.schema([('record_id',pa.string()),('calc_type',pa.string()),('code',pa.string()),('field',pa.string()),('left_sha256',pa.string()),('right_sha256',pa.string()),('absolute_tolerance',pa.float64())])
    pq.write_table(pa.Table.from_pylist(errors,schema=schema),out/'differences.parquet',compression='zstd')
    pq.write_table(pa.Table.from_pylist(fields),out/'field_comparisons.parquet',compression='zstd');pq.write_table(pa.Table.from_pylist(sources),out/'registry_coverage.parquet',compression='zstd')
    passed=not errors and len(pids)>=16
    report={'schema':'WP5_REPRODUCTION50_DOUBLE_VALIDATION_V1','status':'PASS' if passed else 'NOT_PASS_STOP_BEFORE_FORMAL','records':50,'runs':2,'closed_slots_per_run':600,'total_scopes':1200,'differences':len(errors),
      'comparisons':dict(counts),'numeric_evidence_by_task':dict(by_method),'tasks_without_numeric_evidence':no_numeric,'numeric_coverage_policy':'Naturally failed matching outcomes remain eligible for validation; zero numeric evidence is disclosed and is never called numeric validation. No new scientific-success threshold is imposed.',
      'natural_outcomes':[{'calc_type':task,'status':state,'records':number} for (task,state),number in status.items()],
      'missingness_policy':'NULL/ABSENT/empty equality is missingness evidence only. Natural failures keep complete outputs and comparable partial fields; no zeros or success fabricated.',
      'raw_comparison':'No raw-output SHA/text byte comparison between runs; each immutable container internal readback SHA checked independently. Input-file SHA is deterministic trace, not output text.',
      'precision':'Exact float64 bits/types/shape by default; only both actual per-field original parser declarations permit the smaller0.5*10^-dp tolerance. Stdout au dipole conversion uses frozen parser constant. No generic epsilon.',
      'effective_worker_pids':sorted(pids),'stop_before_formal':not passed,'final200_still_required':True,'plan_sha256':sha(a.plan),'package_sha256':plan['bindings']['package']['sha256'],'precision_manifest_sha256':sha(out/'precision_manifest.json'),'G5_registry_extraction_evidence_sha256':sha(out/'G5_registry_extraction_evidence.json'),'script_sha256':sha(__file__),'metadata_memory_bound':'Parent stores parsed50-record rows only;24 workers independently read two task outputs at a time, never the full1200 raw corpus.'}
    save(out/'report.json',report);print(json.dumps({'report':str(out/'report.json'),'status':report['status']}))
    if not passed:raise SystemExit(2)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=('plan','run','compare'))
    for name in ('audit-membership','reproduction-package','production-contract','dictionaries','plan','out'):p.add_argument('--'+name,type=Path)
    p.add_argument('--population',type=Path,default=ROOT/'population/formal_record_index.parquet');p.add_argument('--authority',type=Path,default=ROOT/'configs/user_raw_retention_override_20261011_v1.json')
    p.add_argument('--runner',type=Path,default=ROOT/'scripts/wp5_runner_v8.py');p.add_argument('--python',type=Path,default=Path('/share/home/zixiao/.conda/envs/chemprop/bin/python'))
    p.add_argument('--workers',type=int,default=24);p.add_argument('--seed',type=int,default=20261011);p.add_argument('--check',action='store_true');a=p.parse_args()
    if a.check:ast.parse(Path(__file__).read_text());assert len(CALCS)==12;print('REPRODUCTION50_SCOPE_AST_PASS_NO_QM_NO_DATA');return
    {'plan':prepare,'run':run,'compare':compare}[a.operation](a)
if __name__=='__main__':main()
