#!/usr/bin/env python3
"""Independent post-terminal G5 semantic review, no new QM and no old edits."""
from __future__ import annotations
import argparse,collections,concurrent.futures,hashlib,json,math,multiprocessing,os
from pathlib import Path
import re,shutil,sys,tempfile,time
sys.dont_write_bytecode=True
HERE=Path(__file__).absolute().parent
sys.path.insert(0,str(HERE))
import wp5_engine as ENGINE
import wp5_parser_regression as G5
FIELD_FILE=ROWS=BARRIER=None
EMPTY_SHA=hashlib.sha256(b'[]').hexdigest()
AUX_MISSING_SHA=hashlib.sha256(b'["AUX_MISSING"]').hexdigest()

def initialize(field_file,panel,protocol,plan,barrier):
    global FIELD_FILE,ROWS,BARRIER
    FIELD_FILE=field_file;ROWS={row['record_id']:row for row in panel};BARRIER=barrier
    ENGINE.initialize_worker(plan,protocol,'/tmp',deadline=time.time()+6*3600)
    BARRIER.wait(timeout=180)

def preliminary(row):
    status=row['comparison'];path=row['source_path']
    if status=='DIFF' and path=='values.parse_errors' and row['reparsed_sha256']==AUX_MISSING_SHA:
        return 'QC_REPARSE_AUX_NOT_RETAINED'
    if status=='AUTHORIZED_D4_CORRECTION':return 'D4_REQUIRES_CASE_EVIDENCE'
    if status=='SOURCE_NOT_ARCHIVED' and path=='values.molecular_quadrupole_traceless_au':return 'QUADRUPOLE_SOURCE_REASON_REQUIRES_REVIEW'
    if status in ('DIFF','SOURCE_NOT_ARCHIVED') and path in ('values.homo_eV','values.lumo_eV'):return 'ORBITAL_SOURCE_OR_INDEX_REQUIRES_REVIEW'
    if status=='SOURCE_NOT_ARCHIVED':return 'HISTORICAL_RAW_GAP'
    if status=='DIFF':return 'UNRESOLVED_PHYSICAL_OR_STRUCTURAL_DIFF'
    return status

def scan_partition(indices):
    import pyarrow.parquet as pq
    source=pq.ParquetFile(FIELD_FILE);stats={};cases={};records={};selected=[];samples={};original_records={};original_cases={}
    keep={'DIFF','SOURCE_NOT_ARCHIVED','AUTHORIZED_D4_CORRECTION','NEW_FIELD_PRESENT'}
    for index in indices:
        for row in source.read_row_group(index).to_pylist():
            if row['comparison'] not in keep:continue
            original_records.setdefault(row['comparison'],set()).add(row['record_id']);original_cases.setdefault(row['comparison'],set()).add((row['record_id'],row['calc_type']))
            category=preliminary(row);key=(row['calc_type'],row['registry_id'],row['source_path'],category,row.get('reason'))
            stats[key]=stats.get(key,0)+1;cases.setdefault(key,set()).add((row['record_id'],row['calc_type']));records.setdefault(key,set()).add(row['record_id'])
            if len(samples.setdefault(key,[]))<3:samples[key].append(row)
            if category in ('D4_REQUIRES_CASE_EVIDENCE','QUADRUPOLE_SOURCE_REASON_REQUIRES_REVIEW','ORBITAL_SOURCE_OR_INDEX_REQUIRES_REVIEW'):selected.append(row)
    return {'pid':os.getpid(),'stats':stats,'cases':cases,'records':records,'samples':samples,'selected':selected,'original_records':original_records,'original_cases':original_cases}

def orbital_rows(text):
    rows=[]
    for line in text.splitlines():
        match=re.search(r'\((HOMO|LUMO)\)',line);marker=match.group(1) if match else None
        tokens=re.sub(r'\((?:HOMO|LUMO)\)','',line).split()
        if len(tokens) not in (3,4) or not tokens[0].isdigit() or not all(re.fullmatch(ENGINE.PARSER.FLOAT,token) for token in tokens):continue
        numbers=[ENGINE.PARSER.f(token) for token in tokens]
        # Orbital rows have Eh and eV in their final two numeric columns.
        if abs(numbers[-1]-numbers[-2]*ENGINE.PARSER.EH_TO_EV)>.01:continue
        rows.append({'index_1based':int(numbers[0]),'occupation_printed':numbers[1] if len(numbers)==4 else None,'energy_Eh_printed':numbers[-2],'energy_eV_printed':numbers[-1],
          'energy_eV_decimal_places':ENGINE.PARSER.decimal_places(tokens[-1]),'marker':marker,'line':line.strip()})
    return rows

def inspect_molecule(item):
    receipt_path,comparisons=item
    receipt=json.loads(Path(receipt_path).read_text())
    import pyarrow.parquet as pq
    binding=receipt['parquet'];parquet=Path(binding['path'])
    if parquet.stat().st_size!=binding['bytes'] or ENGINE.sha(parquet)!=binding['sha256']:raise ValueError('PILOT_PARQUET_CHANGED')
    ids=sorted({row['record_id'] for row in comparisons});tasks=sorted({row['calc_type'] for row in comparisons})
    original_rows=pq.read_table(parquet,columns=['details_json'],filters=[('record_id','in',ids),('task','in',tasks)]).to_pylist()
    details=[json.loads(row['details_json']) for row in original_rows];by={(row['record_id'],row['task']):row for row in details}
    temp=Path(tempfile.mkdtemp(prefix=f'wp5g5semantic_{os.getuid()}_{os.environ["SLURM_JOB_ID"]}_{os.getpid()}_',dir='/tmp'));evidence=[]
    try:
        dirs=G5.extract_retained(receipt,details,temp)
        native_cache={};parsed={}
        for row in comparisons:
            key=(row['record_id'],row['calc_type']);old=by[key];directory=dirs.get(key);path=row['source_path'];item=dict(row)
            item.update(source_receipt=str(receipt_path),source_archive=receipt.get('archive',{}).get('path'),member_prefix=old.get('archive',{}).get('member_prefix'),worker_pid=os.getpid())
            if directory is None:
                item.update(semantic_category='HISTORICAL_RAW_GAP',proof='No archived call output for this historical outcome');evidence.append(item);continue
            if row['record_id'] not in native_cache:native_cache[row['record_id']]=ENGINE.NATIVE.read_native(ROWS[row['record_id']])
            native=native_cache[row['record_id']];stdout_path=directory/'process.out';text=stdout_path.read_text(errors='replace') if stdout_path.exists() else ''
            if key not in parsed:
                values=ENGINE.PARSER.parse_xtb(directory,native['symbols']);parsed[key]=(values,ENGINE.PARSER.context())
            values,context=parsed[key];field=path.removeprefix('values.');expected=old['values'].get(field);actual=values.get(field)
            if G5.value_sha(expected)!=row['expected_sha256'] or G5.value_sha(actual)!=row['reparsed_sha256']:raise ValueError('FROZEN_COMPARISON_VALUE_SHA_DIFFERS')
            item['expected_value']=expected;item['reparsed_value']=actual;item['retained_files']=sorted(p.name for p in directory.iterdir())
            if field in ('D4_atomic_C6_au','D4_atomic_alpha_bohr3'):
                legacy=ENGINE.PARSER._LEGACY.parse_xtb(directory,native['symbols']).get(field)
                extrema=[]
                for line in text.splitlines():
                    tokens=line.split()
                    if len(tokens)==8 and tokens[0].isdigit() and tokens[1].isdigit() and tokens[2] in native['symbols'] and tokens[-1] in ('(max)','(min)'):extrema.append(line.strip())
                proof=G5.exact(expected,legacy) and bool(extrema) and context.get('D4_complete_tables',0)>0 and G5.value_sha(actual)==row['reparsed_sha256']
                item.update(semantic_category='D4_EXTREMA_PARTIAL_APPEND_FIX_PROVEN' if proof else 'D4_UNPROVEN_DIFFERENCE',old_legacy_value=legacy,extrema_lines=extrema,D4_complete_tables=context.get('D4_complete_tables',0))
            elif field=='molecular_quadrupole_traceless_au':
                marker='molecular quadrupole (traceless):';quad_match=None
                if marker in text:quad_match=re.search(r'full:\s*('+ENGINE.PARSER.FLOAT+r')\s+('+ENGINE.PARSER.FLOAT+r')\s+('+ENGINE.PARSER.FLOAT+r')\s+('+ENGINE.PARSER.FLOAT+r')\s+('+ENGINE.PARSER.FLOAT+r')\s+('+ENGINE.PARSER.FLOAT+r')',text.split(marker)[-1])
                tolerance=.5*10**(-min(ENGINE.PARSER.decimal_places(token) for token in quad_match.groups())) if quad_match else None
                if G5.exact(expected,actual):category='STDOUT_QUADRUPOLE_MATCH_BITS'
                elif tolerance is not None and G5.numeric_round_match(expected,actual,tolerance*(1+1e-9)):category='STDOUT_QUADRUPOLE_ROUNDING_MATCH'
                elif quad_match:category='STDOUT_QUADRUPOLE_TRUE_DIFF'
                else:category='QUADRUPOLE_STDOUT_FIELD_NOT_RETAINED'
                item.update(semantic_category=category,stdout_quad_marker=marker in text,stdout_full_quad_tokens=list(quad_match.groups()) if quad_match else None,rounding_tolerance=tolerance,
                    proof='Legacy quadrupole is parsed from stdout, not JSON. JSON absence alone is not a source-gap explanation.')
            else:
                table=orbital_rows(text);marker='HOMO' if field=='homo_eV' else 'LUMO';tagged=[orb for orb in table if orb['marker']==marker]
                matches=[orb for orb in table if isinstance(expected,(int,float)) and abs(expected-orb['energy_eV_printed'])<=.5*10**(-orb['energy_eV_decimal_places'])*(1+1e-9)]
                if tagged and G5.numeric_round_match(expected,tagged[-1]['energy_eV_printed'],.5*10**(-tagged[-1]['energy_eV_decimal_places'])*(1+1e-9)):
                    tolerance=.5*10**(-tagged[-1]['energy_eV_decimal_places']);category='ORBITAL_PRINTED_ROUNDING_MATCH' if G5.numeric_round_match(expected,actual,tolerance*(1+1e-9)) else 'ORBITAL_FALLBACK_COLUMN_OR_UNIT_ERROR'
                elif tagged and matches and all(orb['index_1based']!=tagged[-1]['index_1based'] for orb in matches):category='ORBITAL_OCCUPATION_INDEX_SEMANTICS_DIFFER'
                elif not any(p.name.endswith('.json') for p in directory.iterdir()):category='JSON_OCCUPATION_PRECISION_NOT_RETAINED'
                else:category='ORBITAL_UNRESOLVED_NUMERICAL_DIFF'
                item.update(semantic_category=category,stdout_marked_orbital=tagged[-1] if tagged else None,rows_matching_pilot_energy=matches,orbital_rows_near_markers=[orb for orb in table if orb['marker']],
                    source_index_rule='Pilot JSON: highest fractional occupation >1e-6; old JSON is not reconstructed from rounded printed occupations.',proof='Compare original pilot scalar with retained stdout rows and tag/index before assigning source-gap or real physical change.')
            evidence.append(item)
        return evidence
    finally:
        import stat
        if temp.parent!=Path('/tmp') or not temp.name.startswith(f'wp5g5semantic_{os.getuid()}_'):raise ValueError('SEMANTIC_LOCAL_CLEANUP_TARGET')
        for path in [temp,*temp.rglob('*')]:
            info=path.lstat()
            if info.st_uid!=os.getuid() or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):raise ValueError('SEMANTIC_LOCAL_CLEANUP_OWNER_TYPE')
        shutil.rmtree(temp)

def close_lane():
    BARRIER.wait(timeout=180);result=ENGINE.close_worker();BARRIER.wait(timeout=180);return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--input-report',required=False);p.add_argument('--workers',type=int,default=24);p.add_argument('--output')
    p.add_argument('--source-plan',default=str(G5.AUDIT/'plan.json'));p.add_argument('--config',default=str(HERE.parent/'configs/protocol.json'));args=p.parse_args()
    if args.check:
        import ast;ast.parse(Path(__file__).read_text());assert preliminary({'comparison':'DIFF','source_path':'values.parse_errors','reparsed_sha256':AUX_MISSING_SHA})=='QC_REPARSE_AUX_NOT_RETAINED'
        print('G5_SEMANTIC_REVIEW_AST_RULE_PASS_NO_DATA_QM');return 0
    if not args.input_report:p.error('--input-report required')
    if not os.environ.get('SLURM_JOB_ID') or not 16<=args.workers<=int(os.environ.get('SLURM_CPUS_PER_TASK','0')):raise ValueError('SLURM_AT_LEAST_16_EFFECTIVE_WORKERS_REQUIRED')
    import pyarrow as pa,pyarrow.parquet as pq
    source_report=json.loads(Path(args.input_report).read_text());field_file=source_report['files']['field_regression.parquet']['path'];config=ENGINE.load_protocol(args.config)
    if ENGINE.sha(field_file)!=source_report['files']['field_regression.parquet']['sha256']:raise ValueError('G5_COMPARISON_PARQUET_CHANGED')
    if source_report['binding']['parser_sha256']!=ENGINE.sha(HERE/'wp5_parser.py') or source_report['binding']['engine_sha256']!=ENGINE.sha(HERE/'wp5_engine.py') or source_report['binding']['protocol_sha256']!=ENGINE.sha(args.config):raise ValueError('G5_BINDING_CHANGED')
    panel=pq.read_table(G5.OLD/'wp4_native_panel/pilot_panel.parquet').to_pylist()
    output=Path(args.output or HERE.parent/'gates/G5_semantic_review'/('job_'+os.environ['SLURM_JOB_ID']));output.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();numgroups=pq.ParquetFile(field_file).num_row_groups;context=multiprocessing.get_context('fork');barrier=context.Barrier(args.workers)
    totals=collections.Counter();cases=collections.defaultdict(set);records=collections.defaultdict(set);fieldstats=collections.Counter();samples={};selected=[];pids=set();original_records=collections.defaultdict(set);original_cases=collections.defaultdict(set)
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=context,initializer=initialize,initargs=(field_file,panel,args.config,args.source_plan,barrier)) as pool:
        for result in pool.map(scan_partition,[list(range(lane,numgroups,args.workers)) for lane in range(args.workers)]):
            pids.add(result['pid']);selected.extend(result['selected'])
            for key,value in result['original_records'].items():original_records[key].update(value)
            for key,value in result['original_cases'].items():original_cases[key].update(value)
            for key,count in result['stats'].items():
                category=key[3];totals[category]+=count;fieldstats[key]+=count;cases[category].update(result['cases'][key]);records[category].update(result['records'][key])
                samples.setdefault(key,[]).extend(result['samples'][key][:max(0,3-len(samples.get(key,[])))])
        receipt_by_molecule={}
        if selected:
            for path in G5.iter_pilot_molecules(G5.OLD/'wp4_native_full_v4'):receipt_by_molecule[json.loads(path.read_text())['molecule_id']]=str(path)
        groups=collections.defaultdict(list)
        for row in selected:groups[row['molecule_id']].append(row)
        evidence=[]
        for rows in pool.map(inspect_molecule,[(receipt_by_molecule[mid],rows) for mid,rows in sorted(groups.items())]):evidence.extend(rows)
        cleanup=[future.result() for future in [pool.submit(close_lane) for _ in range(args.workers)]]
    schema=pa.schema([('record_id',pa.string()),('molecule_id',pa.string()),('calc_type',pa.string()),('registry_id',pa.int16()),('source_path',pa.string()),('source_comparison',pa.string()),('semantic_category',pa.string()),('evidence_json',pa.large_string())])
    table=pa.Table.from_pylist([{'record_id':row['record_id'],'molecule_id':row['molecule_id'],'calc_type':row['calc_type'],'registry_id':row['registry_id'],'source_path':row['source_path'],'source_comparison':row['comparison'],'semantic_category':row['semantic_category'],'evidence_json':json.dumps(row,sort_keys=True,ensure_ascii=False,allow_nan=False)} for row in evidence],schema=schema)
    pq.write_table(table,output/'case_evidence.parquet',compression='zstd')
    evidence_counts=collections.Counter(row['semantic_category'] for row in evidence)
    # This report diagnoses the failed gate; it never changes old G5 statuses
    # or promotes absent raw to a successful regression.
    report={'status':'POST_TERMINAL_G5_DIAGNOSIS_COMPLETE_NOT_A_GATE_OVERRIDE','source_G5_status':source_report['status'],'source_report':str(args.input_report),'source_report_sha256':ENGINE.sha(args.input_report),
      'source_comparison_counts':source_report['comparison_counts'],'source_comparison_distinct_records':{key:len(value) for key,value in original_records.items()},'source_comparison_distinct_record_task_cases':{key:len(value) for key,value in original_cases.items()},'questionable_field_count':sum(totals.values()),'category_counts':dict(totals),'category_distinct_records':{key:len(value) for key,value in records.items()},'category_distinct_record_task_cases':{key:len(value) for key,value in cases.items()},
      'field_counts':[{'task':task,'registry_id':rid,'source_path':path,'category':category,'reason':reason,'fields':count,'samples':samples[key]} for key,count in sorted(fieldstats.items(),key=lambda item:tuple(str(value) for value in item[0])) for task,rid,path,category,reason in [key]],
      'targeted_raw_audited_fields':len(evidence),'targeted_raw_categories':dict(evidence_counts),'raw_evidence_samples':evidence[:20],
      'historical_gap_policy':'QC AUX_MISSING from absent files is distinct from changed physical numbers; unreconstructible raw fields remain unmet G5 verification, never PASS.',
      'available_alternatives':['User-approved substitution: full pilot parsed-value typed float64 bit-exact readback plus all retained-raw field matches, retained AUX subset checks and G6 fresh full-raw validation. This requires an explicit G5 acceptance decision.','Strict original G5 requires unavailable historical raw to be recovered from an existing backup or separately authorized QM regeneration; do not claim reconstruction from old parsed values is raw reparse.'],
      'worker_pids':sorted(pids),'actual_workers':len(pids),'workers_requested':args.workers,'cleanup':cleanup,'elapsed_seconds':time.monotonic()-started,'job_id':os.environ['SLURM_JOB_ID'],'seed':config['seed'],
      'script_sha256':ENGINE.sha(__file__),'python':sys.version,'pyarrow':pa.__version__,'engine_sha256':ENGINE.sha(HERE/'wp5_engine.py'),'parser_sha256':ENGINE.sha(HERE/'wp5_parser.py'),'protocol_sha256':ENGINE.sha(args.config),
      'case_evidence':{'path':str(output/'case_evidence.parquet'),'sha256':ENGINE.sha(output/'case_evidence.parquet'),'rows':len(evidence)}}
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    (output/'report.md').write_text('G5 独立语义诊断已闭合，保留原回归证据且不改门槛。\n\n分类字段数：'+json.dumps(dict(totals),ensure_ascii=False)+'\n\n原子/物理差异、AUX_MISSING 新离线诊断、轨道索引与四极矩/D4 来源按字段列于 report.json；逐疑例原始归档路径和数值见 case_evidence.parquet。未保存 raw 仍是不可独立回归的缺口。无 QM 重算。\n')
    print(json.dumps({'actual_workers':len(pids),'category_counts':dict(totals),'targeted_raw_categories':dict(evidence_counts),'output':str(output)}));return 0
if __name__=='__main__':raise SystemExit(main())
