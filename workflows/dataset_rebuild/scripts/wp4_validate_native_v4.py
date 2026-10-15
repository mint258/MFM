#!/usr/bin/env python3
"""16-worker read-only existing-output and copied-fixture validation, no QM."""
from __future__ import annotations
import argparse
import concurrent.futures as futures
import hashlib
import importlib.util
import json
import multiprocessing as mp
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

sys.dont_write_bytecode=True
HERE=Path(__file__).absolute().parent
ROOT=HERE.parent
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[name]='1'


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def copied_field_change(text,field,variant):
    """Change only an already exported field body in a disposable copy."""
    pattern=re.compile(r'(?m)^[ \t]*([A-Z][A-Z0-9_:./ -]*?)(?:\[(\d+)\])?[ \t]*=[ \t]*')
    hits=list(pattern.finditer(text))
    offset=next(index for index,hit in enumerate(hits) if hit.group(1).strip()==field)
    hit=hits[offset]; end=hits[offset+1].start() if offset+1<len(hits) else len(text)
    body=text[hit.end():end]
    if variant=='extra': changed=body+'Calculation of polarizability failed (This part of MOPAC is fragile)\n'
    elif variant=='missing':
        tokens='\n'.join(line for line in body.splitlines() if not line.lstrip().startswith('#')).split()
        changed=' '.join(tokens[:-1])+'\n'
    else: raise ValueError(variant)
    return text[:hit.end()]+changed+text[end:]


def getter_case(task):
    import numpy as np
    getter=module('new_mulliken',HERE/'wp4_mulliken_pairs_v3.py')
    old_getter=module('frozen_mulliken',HERE/'wp4_mulliken_pairs_v2.py')
    parser=module('frozen_parser',HERE/'wp4_parsers.py')
    path=Path(task['input_path']); aux_path=path/'input.aux'; out_path=path/'input.out'
    before={str(p):sha(p) for p in (aux_path,out_path)}
    aux,errors=getter.read_selected_aux(aux_path)
    if errors: raise ValueError('Existing baseline unexpectedly malformed')
    symbols=aux['ATOM_EL']; reference=[row[1] for row in parser.indexed_table(out_path.read_text(),r'MULLIKEN POPULATIONS AND CHARGES',symbols,2)]
    pairs=[(i,j) for i in range(len(symbols)) for j in range(i)]
    baseline=getter.sparse_mulliken_from_aux(aux_path,symbols,pairs,reference)
    assert baseline['qc']['status']=='AVAILABLE_CHARGE_QC_PASS'
    frozen=old_getter.sparse_mulliken_from_aux(aux_path,symbols,pairs,reference)
    assert baseline['pairs']==frozen['pairs']
    assert baseline['qc']['reconstructed_charge_max_error_e']==frozen['qc']['reconstructed_charge_max_error_e']
    scratch=Path(tempfile.mkdtemp(prefix='wp4_getter_fixture_'+str(os.getuid())+'_',dir='/tmp'))
    checks={}
    try:
        raw=aux_path.read_text()
        for variant in ('extra','missing'):
            fixture=scratch/('duplicate_charge_'+variant+'.aux')
            fixture.write_text(copied_field_change(raw,'MULLIKEN_ATOM_CHARGES',variant))
            observed=getter.sparse_mulliken_from_aux(fixture,symbols,pairs,reference)
            rejected=old_getter.sparse_mulliken_from_aux(fixture,symbols,pairs,reference)
            assert observed['qc']['status']=='AVAILABLE_CHARGE_QC_PASS' and observed['pairs']==baseline['pairs']
            assert observed['qc']['nonessential_AUX_errors']==['AUX_COUNT_MISMATCH:MULLIKEN_ATOM_CHARGES']
            assert rejected['pairs'] is None
            direct=getter.sparse_mulliken_from_aux(fixture,symbols,pairs,None)
            assert direct['pairs'] is None
            checks['unused_charge_'+variant]={'new_status':observed['qc']['status'],'pairs_exactly_unchanged':True,
                                            'old_guard_rejected':True,'without_out_reference_still_rejected':True}
        for field in ('TOTAL_DENSITY_MATRIX','OVERLAP_MATRIX','AO_ATOMINDEX','ATOM_CORE'):
            fixture=scratch/(field+'.aux'); fixture.write_text(copied_field_change(raw,field,'missing'))
            observed=getter.sparse_mulliken_from_aux(fixture,symbols,pairs,reference)
            assert observed['pairs'] is None and 'AUX_COUNT_MISMATCH:'+field in observed['qc']['failure_reason']
            checks['required_'+field]='REJECTED'
    finally:
        for file in scratch.iterdir():
            if file.is_symlink() or not file.is_file() or file.stat().st_uid!=os.getuid(): raise ValueError('Fixture cleanup scope differs')
            file.unlink()
        scratch.rmdir()
    assert before=={str(p):sha(p) for p in (aux_path,out_path)}
    return {'worker_pid':os.getpid(),'molecule':task['molecule'],'task':task['task'],
            'baseline_max_charge_error_e':baseline['qc']['reconstructed_charge_max_error_e'],
            'checks':checks,'existing_inputs_unchanged':True,'fixture_directory_removed':True}


def native_text_group(item):
    engine=module('native_v4',HERE/'wp4_native_pilot_v4.py')
    archive_path,records=item
    ref=records[0]['archive']; assert sha(archive_path)==ref['sha256']
    targets={r['archive']['member_prefix']:r for r in records}; results=[]
    decoder=subprocess.Popen(['/usr/bin/zstd','-d','-c',archive_path],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=decoder.stdout,mode='r|') as files:
            for member in files:
                if not member.isfile(): continue
                prefix,name=member.name.rsplit('/',1); target=targets.get(prefix)
                if target is None or name not in ('input.out','process.out'): continue
                if target['task']!='xtb_vfukui' and name!='input.out': continue
                data=files.extractfile(member).read()
                assert hashlib.sha256(data).hexdigest()==target['archived_text'][name]['sha256']
                codes=engine.scientific_failure_codes(data.decode(errors='replace'))
                results.append({'record_id':target['record_id'],'task':target['task'],'codes':codes,'source_text_sha256':hashlib.sha256(data).hexdigest()})
    finally:
        while decoder.stdout.read(1<<20): pass
        decoder.stdout.close(); error=decoder.stderr.read(); code=decoder.wait()
    assert code==0,error
    return {'worker_pid':os.getpid(),'archive':ref,'native_diagnostics':results}


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--out',required=True); p.add_argument('--workers',type=int,default=16)
    args=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or not 16<=args.workers<=int(os.environ.get('SLURM_CPUS_PER_TASK',0)):
        raise ValueError('SLURM_16_EFFECTIVE_WORKERS_REQUIRED')
    output=Path(args.out)
    if output.exists(): raise ValueError('NEW_OUTPUT_REQUIRED')
    audit=json.loads((ROOT/'reports/mulliken_audit_v2_job_4512806/mulliken_audit.json').read_text())
    failures=json.loads((ROOT/'reports/wp4_bounded_failure_audit_job_4512826.json').read_text())
    archives={}
    for row in failures['failures']: archives.setdefault(row['archive']['path'],[]).append(row)
    tasks=[(getter_case,case) for case in audit['cases']]+[(native_text_group,item) for item in archives.items()]
    started=time.monotonic(); results=[]; errors=[]
    with futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=mp.get_context('spawn')) as pool:
        pending={pool.submit(function,argument):function.__name__ for function,argument in tasks}
        for future in futures.as_completed(pending):
            try: results.append(future.result())
            except Exception as exc: errors.append({'function':pending[future],'error':type(exc).__name__+': '+str(exc)})
    from collections import Counter
    diagnostic_records=[r for group in results for r in group.get('native_diagnostics',[])]
    summary={'status':'V4_EXISTING_OUTPUT_AND_COPIED_FIXTURES_PASS' if not errors else 'FAILED','job_id':os.environ['SLURM_JOB_ID'],
             'seed':20261010,'actual_worker_pids':sorted({r['worker_pid'] for r in results}),'workers':args.workers,
             'elapsed_seconds':time.monotonic()-started,'errors':errors,
             'real_existing_getter_cases':sum('checks' in r for r in results),
             'native_failure_code_counts':dict(Counter(code for r in diagnostic_records for code in r['codes'])),
             'native_records_without_specific_code':[r for r in diagnostic_records if not r['codes']],
             'source_sha256':{name:sha(HERE/name) for name in ('wp4_native_pilot_v4.py','wp4_mulliken_pairs_v3.py','wp4_native_v4_config.json','wp4_validate_native_v4.py')},
             'new_QM_calls':0,'LMDB_opened':False,'native_missing_AUX_recomputed':False,'results':results}
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({key:summary[key] for key in ('status','job_id','real_existing_getter_cases','native_failure_code_counts','errors')}))
    return 1 if errors else 0


if __name__=='__main__': raise SystemExit(main())
