#!/usr/bin/env python3
"""Targeted G5 dipole print-precision diagnosis; immutable pilot, no QM."""
from __future__ import annotations
import argparse,collections,concurrent.futures,json,multiprocessing,os
from pathlib import Path
import re,shutil,stat,sys,tempfile,time
sys.dont_write_bytecode=True
HERE=Path(__file__).absolute().parent;sys.path.insert(0,str(HERE))
import wp5_parser_semantic_review as REVIEW
ENGINE,G5=REVIEW.ENGINE,REVIEW.G5

def scan(indices):
    import pyarrow.parquet as pq
    source=pq.ParquetFile(REVIEW.FIELD_FILE);selected=[];controls=[]
    for index in indices:
        rows=source.read_row_group(index,columns=['record_id','molecule_id','calc_type','registry_id','source_path','comparison','reason','expected_sha256','reparsed_sha256','expected_summary','reparsed_summary','rounding_tolerance']).to_pylist()
        for row in rows:
            if row['calc_type']!='xtb_singlepoint' or row['source_path']!='values.dipole_Debye':continue
            if row['comparison']=='DIFF':selected.append(row)
            elif row['comparison'] in ('MATCH_BITS','ROUNDING_MATCH') and len(controls)<3:controls.append(row)
    return {'pid':os.getpid(),'selected':selected+controls,'diff_count':len(selected),'controls':len(controls)}

def minimum_decimal_grid(value):
    for digits in range(15):
        if abs(value-round(value,digits))<=2e-12:return digits
    return None

def inspect(item):
    import pyarrow.parquet as pq
    receipt_path,comparisons=item;receipt=json.loads(Path(receipt_path).read_text());ref=receipt['parquet'];source=Path(ref['path'])
    if source.stat().st_size!=ref['bytes'] or ENGINE.sha(source)!=ref['sha256']:raise ValueError('PILOT_PARQUET_CHANGED')
    ids=sorted({row['record_id'] for row in comparisons})
    details=[json.loads(row['details_json']) for row in pq.read_table(source,columns=['details_json'],filters=[('record_id','in',ids),('task','=','xtb_singlepoint')]).to_pylist()]
    by={row['record_id']:row for row in details};temp=Path(tempfile.mkdtemp(prefix=f'wp5dipole_{os.getuid()}_{os.environ["SLURM_JOB_ID"]}_{os.getpid()}_',dir='/tmp'));results=[]
    try:
        dirs=G5.extract_retained(receipt,details,temp)
        for comparison in comparisons:
            old=by[comparison['record_id']];directory=dirs[(comparison['record_id'],'xtb_singlepoint')];text=(directory/'process.out').read_text(errors='replace')
            expected=old['values']['dipole_Debye']
            if G5.value_sha(expected)!=comparison['expected_sha256']:raise ValueError('PILOT_DIPOLE_REFERENCE_SHA_DIFFERS')
            part=text.split('molecular dipole:')[-1]
            match=re.search(r'full:\s*('+ENGINE.PARSER.FLOAT+r')\s+('+ENGINE.PARSER.FLOAT+r')\s+('+ENGINE.PARSER.FLOAT+r')',part)
            result=dict(comparison);result.update(source_receipt=str(receipt_path),source_archive=receipt['archive']['path'],member_prefix=old['archive']['member_prefix'],expected_Debye=expected,worker_pid=os.getpid())
            if not match:result.update(category='STDOUT_FULL_DIPOLE_ABSENT');results.append(result);continue
            tokens=list(match.groups());printed=[ENGINE.PARSER.f(token) for token in tokens];reparsed=[value*ENGINE.PARSER.AU_DIPOLE_TO_DEBYE for value in printed]
            if G5.value_sha(reparsed)!=comparison['reparsed_sha256']:raise ValueError('REPARSED_DIPOLE_SHA_DIFFERS')
            precision=[ENGINE.PARSER.decimal_places(token) for token in tokens];allow_au=[.5*10**(-digits) for digits in precision]
            pilot_au=[value/ENGINE.PARSER.AU_DIPOLE_TO_DEBYE for value in expected];delta_au=[abs(a-b) for a,b in zip(pilot_au,printed)]
            old_grid=[minimum_decimal_grid(value) for value in pilot_au]
            ratios=[delta/bound for delta,bound in zip(delta_au,allow_au)]
            g5_bound=comparison['rounding_tolerance'];max_delta_D=max(abs(a-b) for a,b in zip(expected,reparsed))
            if max(ratios)<=1+1e-9:category='WITHIN_COMPONENT_STDOUT_ROUNDING'
            elif all(grid is not None for grid in old_grid) and all(delta<=bound+.5*10**(-grid)+1e-12 for delta,bound,grid in zip(delta_au,allow_au,old_grid)):category='WITHIN_COMBINED_PRINT_AND_PILOT_GRID_ROUNDING'
            else:category='EXCEEDS_IDENTIFIED_PRINT_PRECISION_REQUIRES_SOURCE_SEMANTICS'
            result.update(category=category,stdout_tokens=tokens,stdout_line=part[match.start():].splitlines()[0],stdout_decimal_places=precision,pilot_au=pilot_au,pilot_minimum_decimal_grid=old_grid,
                component_abs_delta_au=delta_au,component_stdout_halfstep_au=allow_au,component_error_to_stdout_halfstep=ratios,max_abs_delta_Debye=max_delta_D,
                max_component_ratio=max(ratios),reparsed_Debye=reparsed,g5_bound_Debye=g5_bound,
                g5_bound_at_least_component_print_bound=g5_bound is not None and g5_bound>=max(allow_au)*ENGINE.PARSER.AU_DIPOLE_TO_DEBYE*(1-1e-9),
                note='Minimum decimal grid is inferred from the immutable pilot value; it is not proof of an original JSON formatter precision. Preserve separate source-precision uncertainty.')
            results.append(result)
        return results
    finally:
        if temp.parent!=Path('/tmp') or not temp.name.startswith(f'wp5dipole_{os.getuid()}_'):raise ValueError('LOCAL_DIPOLE_CLEANUP_TARGET')
        for path in [temp,*temp.rglob('*')]:
            info=path.lstat()
            if info.st_uid!=os.getuid() or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):raise ValueError('LOCAL_DIPOLE_CLEANUP_OWNER')
        shutil.rmtree(temp)

def distribution(values):
    import numpy as np
    values=np.asarray(list(values),dtype=np.float64)
    return {'n':len(values),'min':float(values.min()),'p50':float(np.median(values)),'p90':float(np.quantile(values,.9)),'p99':float(np.quantile(values,.99)),'max':float(values.max())} if len(values) else {'n':0}

def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--workers',type=int,default=24);p.add_argument('--input-report');p.add_argument('--output');p.add_argument('--config',default=str(HERE.parent/'configs/protocol.json'));p.add_argument('--source-plan',default=str(G5.AUDIT/'plan.json'));a=p.parse_args()
    if a.check:
        import ast;ast.parse(Path(__file__).read_text());assert minimum_decimal_grid(.1234)==4;print('DIPOLE_REVIEW_AST_PASS_NO_QM_DATA');return 0
    if not a.input_report:p.error('--input-report required')
    if not os.environ.get('SLURM_JOB_ID') or not 16<=a.workers<=int(os.environ.get('SLURM_CPUS_PER_TASK','0')):raise ValueError('SLURM_AT_LEAST_16_EFFECTIVE_WORKERS_REQUIRED')
    import pyarrow as pa,pyarrow.parquet as pq
    report=json.loads(Path(a.input_report).read_text());field_file=report['files']['field_regression.parquet']['path']
    if ENGINE.sha(field_file)!=report['files']['field_regression.parquet']['sha256']:raise ValueError('REGRESSION_FIELDS_SHA_CHANGED')
    if ENGINE.sha(HERE/'wp5_parser.py')!=report['binding']['parser_sha256'] or ENGINE.sha(a.config)!=report['binding']['protocol_sha256']:raise ValueError('G5_FROZEN_BINDING_DIFFERS')
    panel=pq.read_table(G5.OLD/'wp4_native_panel/pilot_panel.parquet').to_pylist();groups=pq.ParquetFile(field_file).num_row_groups
    context=multiprocessing.get_context('fork');barrier=context.Barrier(a.workers);started=time.monotonic();pids=set();selected=[];diffs=0;controls=0
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=context,initializer=REVIEW.initialize,initargs=(field_file,panel,a.config,a.source_plan,barrier)) as pool:
        for result in pool.map(scan,[list(range(lane,groups,a.workers)) for lane in range(a.workers)]):pids.add(result['pid']);selected.extend(result['selected']);diffs+=result['diff_count'];controls+=result['controls']
        receipt_by_molecule={json.loads(path.read_text())['molecule_id']:str(path) for path in G5.iter_pilot_molecules(G5.OLD/'wp4_native_full_v4')}
        by_molecule=collections.defaultdict(list)
        for row in selected:by_molecule[row['molecule_id']].append(row)
        results=[]
        for items in pool.map(inspect,[(receipt_by_molecule[mid],rows) for mid,rows in sorted(by_molecule.items())]):results.extend(items)
        cleanup=[future.result() for future in [pool.submit(REVIEW.close_lane) for _ in range(a.workers)]]
    output=Path(a.output or HERE.parent/'gates/G5_dipole_review'/('job_'+os.environ['SLURM_JOB_ID']));output.mkdir(parents=True,exist_ok=False)
    schema=pa.schema([('record_id',pa.string()),('molecule_id',pa.string()),('source_comparison',pa.string()),('category',pa.string()),('max_abs_delta_Debye',pa.float64()),('max_component_ratio',pa.float64()),('evidence_json',pa.large_string())])
    pq.write_table(pa.Table.from_pylist([{'record_id':row['record_id'],'molecule_id':row['molecule_id'],'source_comparison':row['comparison'],'category':row['category'],'max_abs_delta_Debye':row.get('max_abs_delta_Debye'),'max_component_ratio':row.get('max_component_ratio'),'evidence_json':json.dumps(row,ensure_ascii=False,sort_keys=True,allow_nan=False)} for row in results],schema=schema),output/'case_evidence.parquet',compression='zstd')
    failed=[row for row in results if row['comparison']=='DIFF'];ok=[row for row in results if row['comparison']!='DIFF'];counts=collections.Counter(row['category'] for row in failed)
    final={'status':'TARGETED_DIPOLE_PRINT_DIAGNOSIS_COMPLETE_NOT_GATE_OVERRIDE','all_actual_G5_dipole_DIFF':diffs,'audited_DIFF':len(failed),'control_cases':len(ok),'actual_workers':len(pids),'worker_pids':sorted(pids),'category_counts_DIFF':dict(counts),
       'delta_Debye_DIFF':distribution(row['max_abs_delta_Debye'] for row in failed if 'max_abs_delta_Debye' in row),'error_to_stdout_halfstep_DIFF':distribution(row['max_component_ratio'] for row in failed if 'max_component_ratio' in row),
       'stdout_precision_counter':dict(collections.Counter(','.join(map(str,row.get('stdout_decimal_places',[]))) for row in failed)),
       'pilot_decimal_grid_counter':dict(collections.Counter(','.join(map(str,row.get('pilot_minimum_decimal_grid',[]))) for row in failed)),
       'g5_bound_too_small_for_printed_precision':sum(not row.get('g5_bound_at_least_component_print_bound',True) for row in failed),
       'evidence_samples':failed[:12],'control_samples':ok[:5],'cleanup':cleanup,'source_report':str(a.input_report),'source_report_sha256':ENGINE.sha(a.input_report),'case_evidence':{'path':str(output/'case_evidence.parquet'),'sha256':ENGINE.sha(output/'case_evidence.parquet')},
       'elapsed_seconds':time.monotonic()-started,'seed':ENGINE.load_protocol(a.config)['seed'],'job_id':os.environ['SLURM_JOB_ID'],'script_sha256':ENGINE.sha(__file__),'semantic_helper_sha256':ENGINE.sha(HERE/'wp5_parser_semantic_review.py'),'parser_sha256':ENGINE.sha(HERE/'wp5_parser.py'),'engine_sha256':ENGINE.sha(HERE/'wp5_engine.py'),'protocol_sha256':ENGINE.sha(a.config),'python':sys.version,'pyarrow':pa.__version__,
       'interpretation':'A stored-value decimal grid gives a possible combined-rounding bound, not conclusive JSON formatter provenance. No physical mismatch is dismissed without raw evidence, and absent JSON remains a historical gap.'}
    (output/'report.json').write_text(json.dumps(final,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(json.dumps({'diffs':diffs,'categories':dict(counts),'output':str(output)}));return 0
if __name__=='__main__':raise SystemExit(main())
