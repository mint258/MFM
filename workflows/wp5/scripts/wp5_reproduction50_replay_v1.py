"""Offline replay of the SAME real50 double runs: native HB delta and corrected source coverage. No QM."""
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
    # Only100 affected B calls are decoded. Other source evidence is the immutable
    # actual registry_coverage from the original full1200-output verification.
    if calc_type!='pm7_B':return None
    cache=_C.setdefault('files_cache',{})
    key=(run,record_id,calc_type)
    if key in cache:return cache[key]
    from wp5_archive_v5 import ArchiveReader
    readers=_C['readers']
    if run not in readers:readers[run]=ArchiveReader(_C['archives'][run],_C['dictionaries'])
    value=readers[run].get(record_id,calc_type)
    if value.get('input_files') or value.get('input_bodies_saved'):raise ValueError('INPUT_BYTES_SAVED_AGAINST_USER_OVERRIDE')
    files=value.get('output_files') or []
    for item in files:
        if item.get('role')=='input':raise ValueError('INPUT_MEMBER_SAVED_AGAINST_USER_OVERRIDE')
        if not isinstance(item.get('data'),bytes) or hashlib.sha256(item['data']).hexdigest()!=item.get('sha256'):raise ValueError('ARCHIVE_OUTPUT_MEMBER_READBACK_FAILED')
    cache[key]=files
    return files

def compare_task(arg):
    left,right,z=arg
    files1=output_files(1,left['record_id'],left['calc_type'])
    files2=output_files(2,right['record_id'],right['calc_type'])
    import wp5_parquet_v2 as wire,wp5_engine_v3 as engine,wp5_registry_coverage_v2 as coverage,wp5_parser
    entries=_C['entries'];key=(left['record_id'],left['calc_type']);errors=[];counts=collections.Counter();fieldstats=[]
    def error(code,field,x,y,tolerance=None):
        errors.append({'record_id':key[0],'calc_type':key[1],'code':code,'field':field,'left_sha256':value_sha(x),'right_sha256':value_sha(y),'absolute_tolerance':tolerance})
    for row,files in ((left,files1),(right,files2)):
        if key[1]=='pm7_B' and not files and row['status']=='SUCCESS':error('AUDIT_COMPLETE_OUTPUT_NOT_RETAINED','output_files',[],None)
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
            prior=_C['prior_source'][(ordinal,key[0],key[1],value['registry_id'])]
            source_key=value['source_path'].removeprefix('values.')
            corrected=(source_key=='fukui' and key[1]=='xtb_vfukui') or (source_key in coverage.B_ONLY_MULLIKEN_FIELDS and key[1]!='pm7_B') or (source_key=='hydrogen_bond_energy_kcal_mol' and key[1]=='pm7_B')
            if not corrected:
                if value['observed_state']!=prior['state']:error('UNCHANGED_SOURCE_STATE_DIFF',value['source_path'],value['observed_state'],prior['state'])
                reason=prior['source_reason']
            value['source_reason']=reason
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


PROCESSING_SHAS={
 'wp5_parser_v2.py':'33d5cb65429f6f969d8739c2f244cf8249f35d23792dca4e73cd52ffe4eaaf6f',
 'wp5_engine_v3.py':'53c09b68938ead8449f0da2ec7a03337df3125826080ece58fabe107cdd9f26b',
 'wp5_registry_coverage_v2.py':'b8aecd11f64097e046519cb26ef5a64099a61583de0547a4955b0a405600914c',
 'wp5_parquet_v2.py':'2864d129336d597ac224d494547143fac35591b6cdcaff6b4520a094fef6c6cd',
 'wp5_archive_v5.py':'3ef37935402fffc9a5111f0dd6b942b279f42581cdea9aeea1a358169d766477'}
HB='values.hydrogen_bond_energy_kcal_mol'
def processing_bindings():
    refs=[]
    for name,expected in PROCESSING_SHAS.items():
        path=Path(__file__).with_name(name)
        if sha(path)!=expected:raise ValueError('PROCESSING_SOURCE_CHANGED:'+name)
        refs.append({'path':str(path),'sha256':expected})
    return refs

def replay_record(arg):
    import copy,wp5_parquet_v2 as wire,wp5_engine_v3 as engine
    rid,left,right,z,prior=arg
    if time.time()>=_C['deadline']:raise TimeoutError('OFFLINE_INTERNAL46H_BOUND')
    _C['prior_source']={(r['run'],r['record_id'],r['calc_type'],r['registry_id']):r for r in prior}
    _C['files_cache']={}
    updated=[];proofs=[];unchanged=0
    for ordinal,rows in enumerate((left,right),1):
        details=[reconstruct(row,_C['entries']) for row in rows]
        b=next(d for d in details if d['task']=='pm7_B')
        files=output_files(ordinal,rid,'pm7_B')
        outputs=[f for f in files if Path(f['name']).name=='input.out']
        if len(outputs)!=1:raise ValueError('EXACT_B_OUTPUT_REQUIRED:'+rid)
        new,proof=engine.reparse_hydrogen_bond_output(b,outputs[0]['data'])
        details=[new if d['task']=='pm7_B' else d for d in details]
        engine.derived_quantities(details)
        by={d['task']:d for d in details};newrows=[]
        for row in rows:
            detail=by[row['calc_type']]
            serialized=wire.task_row(row['record_id'],row['molecule_id'],row['calc_type'],detail,list(_C['entries'].values()),row['total_atoms'])
            oldcells={c['registry_id']:c for c in row['values']}
            for cell in serialized['values']:
                entry=_C['entries'][cell['registry_id']]
                if not (entry['source_path']==HB and row['calc_type']=='pm7_B'):
                    if not bits(oldcells[cell['registry_id']],cell):raise ValueError('NON_HB_CELL_OR_F64_BITS_CHANGED:'+rid+':'+str(cell['registry_id']))
                    unchanged+=1
            newrow=copy.deepcopy(row);newrow['values']=serialized['values']
            if row['calc_type']=='pm7_B':
                precision=json.loads(row.get('precision_by_field_json') or '{}')
                if proof['rounding_decimal_places'] is not None:precision['hydrogen_bond_energy_kcal_mol']=proof['rounding_decimal_places']
                newrow['precision_by_field_json']=json.dumps(precision,sort_keys=True,separators=(',',':'))
            # Preserve true execution provenance, elapsed/SCF/input SHA/package and raw locator.
            for name in row:
                if name not in ('values','precision_by_field_json') and not bits(newrow[name],row[name]):raise ValueError('OLD_EXECUTION_PROVENANCE_CHANGED:'+name)
            newrows.append(newrow)
        proofs.append({'record_id':rid,'run':ordinal,'input_out_sha256':outputs[0]['sha256'],
           'original_execution_package_sha256':_C['package_sha256'],'proof':proof,
           'old_value':b['values'].get('hydrogen_bond_energy_kcal_mol'),
           'new_value':new['values'].get('hydrogen_bond_energy_kcal_mol')})
        updated.append(newrows)
    rightby={row['calc_type']:row for row in updated[1]}
    results=[compare_task((row,rightby[row['calc_type']],z)) for row in updated[0]]
    return {'results':results,'updated_rows':updated,'proofs':proofs,'non_HB_cells_exact_original':unchanged,'pid':os.getpid()}

def replay(a):
    allocated(a.workers);processing=processing_bindings()
    import pyarrow as pa,pyarrow.parquet as pq,wp5_parquet_v2 as wire,wp5_registry_coverage_v2 as coverage,multiprocessing
    plan=json.loads(a.plan.read_text());package=json.loads(Path(plan['bindings']['package']['path']).read_text())
    for entry in plan['bindings'].values():
        if sha(entry['path'])!=entry['sha256']:raise ValueError('ORIGINAL_EXECUTION_DEPENDENCY_CHANGED:'+entry['path'])
    if len(plan['selected_record_ids'])!=50 or len(set(plan['selected_record_ids']))!=50:raise ValueError('ORIGINAL_EXACT50_SCOPE_CHANGED')
    out=a.out or ROOT/'gates/reproduction50_replay'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
    protocol=json.loads(Path(plan['bindings']['protocol']['path']).read_text())
    options={'entries':{e['registry_id']:e for e in coverage.entries(protocol['registry']['path'])},
      'dictionaries':plan['bindings']['dictionaries']['path'],'software_versions':package['software_versions'],
      'package_sha256':plan['bindings']['package']['sha256'],'deadline':time.time()+46*3600}
    init(options);selected=set(plan['selected_record_ids'])
    left,lf,lc=load_run(a.plan.parent/'run1',selected);right,rf,rc=load_run(a.plan.parent/'run2',selected)
    options['archives']={1:lc['archive']['path'],2:rc['archive']['path']}
    old_report=a.plan.parent/'comparison/report.json';old_coverage=a.plan.parent/'comparison/registry_coverage.parquet'
    original_report=json.loads(old_report.read_text())
    if original_report['closed_slots_per_run']!=600 or original_report['records']!=50:raise ValueError('ORIGINAL_COMPARISON_SCOPE_NOT_CLOSED')
    prior=pq.read_table(old_coverage).to_pylist();priorby=collections.defaultdict(list)
    for r in prior:priorby[r['record_id']].append(r)
    keys={(r['run'],r['record_id'],r['calc_type'],r['registry_id']) for r in prior}
    expected={(run,rid,e['task'],e['registry_id']) for run in (1,2) for rid in selected for e in options['entries'].values()}
    if keys!=expected or len(keys)!=len(prior):raise ValueError('ORIGINAL_FULL_SOURCE_EVIDENCE_SCOPE_NOT_CLOSED')
    errors=[];fields=[];sources=[];counts=collections.Counter();status=collections.Counter();pids=set();by_method=collections.Counter()
    newrows={1:[],2:[]};proofs=[];preserved=0
    ctx=multiprocessing.get_context('spawn');options['barrier']=ctx.Barrier(a.workers)
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=ctx,initializer=init,initargs=(options,)) as pool:
        args=((rid,[left[(rid,c)] for c in CALCS],[right[(rid,c)] for c in CALCS],lf['base_geometry'][rid]['atomic_numbers'],priorby[rid]) for rid in sorted(selected))
        for item in pool.map(replay_record,args,chunksize=1):
            pids.add(item['pid']);preserved+=item['non_HB_cells_exact_original'];proofs.extend(item['proofs'])
            for run in (1,2):newrows[run].extend(item['updated_rows'][run-1])
            for r in item['results']:
                errors.extend(r['errors']);fields.extend(r['fields']);sources.extend(r['coverage']);counts.update(r['counts'])
                by_method[r['calc_type']]+=r['counts'].get('finite_numeric_values_compared',0)
                status[(r['calc_type'],'FAILURE' if r['natural_failure'] else 'SUCCESS')]+=1
    ignored={'record_id','molecule_id','file_group','attempt_id','job_id','task_id','lane','source_path','real_index','source_payload_sha256','population_QC_json'}
    for family in lf:
        for rid in selected:
            n=len(lf['base_geometry'][rid].get('atomic_numbers') or [])
            for ordinal,row in enumerate((lf[family][rid],rf[family][rid]),1):
                issues=nonqm_issues(family,row,n)
                if issues:errors.append({'record_id':rid,'calc_type':family,'code':'NONQM_SCHEMA_N_OR_FINITE','field':str(ordinal),'left_sha256':value_sha(issues),'right_sha256':None,'absolute_tolerance':None})
            for name in lf[family][rid]:
                if name in ignored:continue
                x,y=lf[family][rid][name],rf[family][rid][name]
                if family=='QC' and name=='task_statuses':
                    x=[{k:v for k,v in r.items() if k not in ('elapsed_seconds','predicted_seconds')} for r in x]
                    y=[{k:v for k,v in r.items() if k not in ('elapsed_seconds','predicted_seconds')} for r in y]
                if not bits(x,y):errors.append({'record_id':rid,'calc_type':family,'code':'NONQM_SCIENTIFIC_DIFF','field':name,'left_sha256':value_sha(x),'right_sha256':value_sha(y),'absolute_tolerance':None})
    refs=[]
    for run in (1,2):
        rows=sorted(newrows[run],key=lambda r:(r['record_id'],r['calc_type']))
        if len(rows)!=600:raise ValueError('REPLAY_SERIALIZED600_NOT_CLOSED')
        path=out/('run'+str(run)+'_reprocessed_tasks.parquet')
        ref=wire.write_rows(rows,path,metadata={'processing_script_sha256':sha(__file__),'original_plan_sha256':sha(a.plan),'QM_started':False})
        read=pq.read_table(path).to_pylist()
        if not bits(rows,read):raise ValueError('REPLAY_PARQUET_LOSSLESS_F64_READBACK_FAILED')
        refs.append(ref)
    eschema=pa.schema([('record_id',pa.string()),('calc_type',pa.string()),('code',pa.string()),('field',pa.string()),('left_sha256',pa.string()),('right_sha256',pa.string()),('absolute_tolerance',pa.float64())])
    pq.write_table(pa.Table.from_pylist(errors,schema=eschema),out/'differences.parquet',compression='zstd')
    pq.write_table(pa.Table.from_pylist(fields),out/'field_comparisons.parquet',compression='zstd')
    pq.write_table(pa.Table.from_pylist(sources),out/'registry_coverage.parquet',compression='zstd')
    save(out/'HB_delta_proofs.json',{'rows':proofs,'only_changed_physical_field':HB,'non_HB_cells_exact_original':preserved})
    expected_ids=set(options['entries']);observed={r['registry_id'] for r in sources}
    if observed!=expected_ids:raise ValueError('ALL_ACTIVE_REGISTRY_SOURCE_COVERAGE_NOT_CLOSED')
    sourcecounts=collections.Counter((r['registry_id'],r['state'],r['source_reason']) for r in sources)
    save(out/'G5_registry_extraction_evidence.json',{'expected_active_registry_fields':len(expected_ids),'observed_active_registry_fields':len(observed),'omitted_catalogue_ids':sorted(expected_ids-observed),
      'source_evidence':[{'registry_id':rid,'state':state,'source_reason':reason,'observations':number} for (rid,state,reason),number in sorted(sourcecounts.items())],
      'original_all1200_raw_verification':{'path':str(old_coverage),'sha256':sha(old_coverage),'report_path':str(old_report),'report_sha256':sha(old_report)},
      'replayed_source_scope':'100 PM7-B output calls; unchanged original source evidence retained, corrected applicability/Fukui mapping reaudited by production coverage2',
      'natural_missingness_is_not_numeric_coverage':True})
    save(out/'precision_manifest.json',{'default':'Strict Float64 bits/types/shape; no generic epsilon',
      'conditional_tolerance':'Only both original field declarations, smaller half-unit decimal place; HB uses actual native output precision',
      'processing_sources':processing,'observations':[{'record_id':r['record_id'],'calc_type':r['calc_type'],'run':run,'precision_by_field':json.loads(r.get('precision_by_field_json') or '{}')} for run,rows in newrows.items() for r in rows]})
    passed=not errors and len(pids)>=16 and len(observed)==622
    report={'schema':'WP5_REPRODUCTION50_OFFLINE_REPLAY_V1','status':'PASS' if passed else 'NOT_PASS_STOP_BEFORE_FORMAL',
      'QM_started':False,'records':50,'original_real_runs':2,'original_actual_scientific_calls':1200,'reprocessed_B_output_calls':100,
      'closed_slots_per_run':600,'differences':len(errors),'comparisons':dict(counts),
      'numeric_evidence_by_task':dict(by_method),'tasks_without_numeric_evidence':[c for c in CALCS if by_method[c]==0],
      'natural_outcomes':[{'calc_type':c,'status':s,'records':n} for (c,s),n in status.items()],
      'effective_worker_pids':sorted(pids),'non_HB_cells_exact_original':preserved,'only_changed_physical_field':HB,
      'native_HB_values_newly_extracted':sum(p['proof']['fallback_applied'] for p in proofs),
      'original_execution_plan':{'path':str(a.plan),'sha256':sha(a.plan)},
      'original_execution_package_sha256':plan['bindings']['package']['sha256'],
      'original_run_exports':[{'path':str(a.plan.parent/('run'+str(run))/'export_completion.json'),'sha256':sha(a.plan.parent/('run'+str(run))/'export_completion.json')} for run in (1,2)],
      'processing_sources':processing,'processing_script_sha256':sha(__file__),'reprocessed_parquets':refs,
      'precision_manifest_sha256':sha(out/'precision_manifest.json'),'G5_registry_extraction_evidence_sha256':sha(out/'G5_registry_extraction_evidence.json'),
      'execution_provenance_policy':'Original status/elapsed/SCF/input SHAs/software ID/execution package retained; processing source changes are separately bound. No claim of new QM execution.',
      'stop_before_formal':not passed,'final200_still_required':True}
    save(out/'report.json',report);print(json.dumps({'report':str(out/'report.json'),'status':report['status']}))
    if not passed:raise SystemExit(2)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path);p.add_argument('--out',type=Path);p.add_argument('--workers',type=int,default=24);p.add_argument('--check',action='store_true');a=p.parse_args()
    if a.check:
        ast.parse(Path(__file__).read_text());processing_bindings();assert len(CALCS)==12
        print('OFFLINE_REPLAY_SOURCE_SCOPE_AST_PASS_NO_QM');return
    if not a.plan:p.error('--plan required')
    replay(a)
if __name__=='__main__':main()
