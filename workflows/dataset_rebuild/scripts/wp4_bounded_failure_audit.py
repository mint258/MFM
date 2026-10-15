#!/usr/bin/env python3
"""Read existing native failures and selected archived text; no QM/LMDB."""
from __future__ import annotations
import argparse
import concurrent.futures as futures
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import time

sys.dont_write_bytecode=True
HERE=Path(__file__).absolute().parent
for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[name]='1'
TARGET_TASKS={'pm7_B','pm7_ESP','xtb_vfukui'}
DIAGNOSTIC=re.compile(r'error|fail|not work|not available|unsupported|not converg|no convergence|warning|ALPHA AT|NFREQ|IBET|IGAM|STOP|polariz|population',re.I)


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''): digest.update(block)
    return digest.hexdigest()


def aux_counts(text):
    header=re.compile(r'^[ \t]*([A-Z][A-Z0-9_:./ -]*?)(?:\[(\d+)\])?[ \t]*=[ \t]*(.*)$')
    selected={'ATOM_CORE','AO_ATOMINDEX','ATOM_SYMTYPE','OVERLAP_MATRIX','TOTAL_DENSITY_MATRIX','MULLIKEN_ATOM_CHARGES'}
    observations=[]; active=None; expected=None; tokens=[]
    def finish():
        if active is not None:
            observations.append({'field':active,'declared_count':expected,'actual_tokens':len(tokens),
                                 'tail_tokens':tokens[-12:] if expected!=len(tokens) else []})
    for line in text.splitlines():
        match=header.match(line)
        if match:
            finish(); name=match.group(1).strip(); active=name if name in selected else None
            expected=int(match.group(2)) if match.group(2) else None
            tokens=match.group(3).split() if active else []
        elif active and not line.lstrip().startswith('#'): tokens.extend(line.split())
    finish()
    return observations


def worker(receipt_path):
    import pyarrow.parquet as pq
    receipt_path=Path(receipt_path); receipt=json.loads(receipt_path.read_text())
    parquet=receipt['parquet']; path=Path(parquet['path'])
    if sha(path)!=parquet['sha256']: raise ValueError('PARQUET_SOURCE_SHA_DIFFERS')
    records=[]; archives={}
    for row in pq.read_table(path,columns=['record_id','molecule_id','task','status','details_json'],use_threads=False).to_pylist():
        if row['task'] not in TARGET_TASKS or row['status']=='SUCCESS': continue
        detail=json.loads(row['details_json']); values=detail.get('values',{})
        item={key:row[key] for key in ('record_id','molecule_id','task','status')}
        item.update(failure_code=detail.get('failure_code'),failure_reason=detail.get('failure_reason'),
                    returncode=detail.get('returncode'),diagnostic_lines=detail.get('diagnostic_lines'),
                    property_failure_lines=values.get('property_failure_lines'),
                    missing_properties=detail.get('missing_properties'),mulliken_qc=values.get('mulliken_overlap_qc'),
                    normal_end=values.get('normal_end'),B_base_success=detail.get('B_base_success'),
                    software_version_lines=detail.get('software_version_lines'),aux_archived=detail.get('aux_archived'),
                    archive=detail.get('archive'),archived_text={})
        records.append(item)
        ref=detail.get('archive')
        if ref: archives.setdefault(ref['path'],{'ref':ref,'targets':{}})['targets'][ref['member_prefix']]=item
    for archive_path,archive in archives.items():
        if sha(archive_path)!=archive['ref']['sha256']: raise ValueError('ARCHIVE_SOURCE_SHA_DIFFERS')
        decoder=subprocess.Popen(['/usr/bin/zstd','-d','-c',archive_path],stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            with tarfile.open(fileobj=decoder.stdout,mode='r|') as files:
                for member in files:
                    if not member.isfile(): continue
                    prefix=member.name.rsplit('/',1)[0]
                    target=archive['targets'].get(prefix)
                    if target is None: continue
                    data=files.extractfile(member).read(); text=data.decode(errors='replace')
                    lines=text.splitlines(); suffix=member.name.rsplit('/',1)[-1]
                    evidence={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
                              'diagnostic_lines':[{'line':i+1,'text':line} for i,line in enumerate(lines) if DIAGNOSTIC.search(line)][:100]}
                    if suffix.endswith('.aux'): evidence['selected_AUX_count_observations']=aux_counts(text)
                    if target['task']=='xtb_vfukui': evidence['last_45_lines']=lines[-45:]
                    target['archived_text'][suffix]=evidence
        finally:
            while decoder.stdout.read(1<<20): pass
            decoder.stdout.close(); stderr=decoder.stderr.read(); code=decoder.wait()
        if code: raise RuntimeError('ARCHIVE_DECODE_FAILED:'+stderr.decode(errors='replace'))
    return {'worker_pid':os.getpid(),'molecule_id':receipt['molecule_id'],'failures':records,
            'parquet_reference':parquet,'receipt_sha256':sha(receipt_path),'QM_calls':0,'LMDB_opened':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pilot-root',required=True); parser.add_argument('--out',required=True)
    parser.add_argument('--workers',type=int,default=16); args=parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or not 16<=args.workers<=int(os.environ.get('SLURM_CPUS_PER_TASK',0)):
        raise ValueError('SLURM_16_PARALLEL_WORKERS_REQUIRED')
    root=Path(args.pilot_root); paths=sorted((root/'molecules').glob('*/receipt.json'))
    output=Path(args.out)
    if output.exists(): raise ValueError('NEW_FAILURE_AUDIT_OUTPUT_REQUIRED')
    output.parent.mkdir(parents=True,exist_ok=True)
    started=time.monotonic(); results=[]; errors=[]
    with futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=mp.get_context('spawn')) as pool:
        pending={pool.submit(worker,path):str(path) for path in paths}
        for future in futures.as_completed(pending):
            try: results.append(future.result())
            except Exception as exc: errors.append({'receipt':pending[future],'error':type(exc).__name__+': '+str(exc)})
    from collections import Counter
    failures=[row for result in results for row in result['failures']]
    report={'scope':'READ_ONLY_EXISTING_BOUNDED_FAILURE_TEXT_NOT_NEW_QM','job_id':os.environ['SLURM_JOB_ID'],
            'seed':20261010,'script_sha256':sha(__file__),'pilot_metadata_sha256':sha(root/'metadata.json'),
            'workers':args.workers,'actual_worker_pids':sorted({r['worker_pid'] for r in results}),
            'elapsed_seconds':time.monotonic()-started,'molecules':len(results),'errors':errors,
            'failure_counts_by_task':dict(Counter(r['task'] for r in failures)),
            'failures':sorted(failures,key=lambda r:(r['task'],r['molecule_id'],r['record_id'])),
            'molecule_input_references':[{k:r[k] for k in ('molecule_id','parquet_reference','receipt_sha256')} for r in results],
            'QM_calls':0,'LMDB_opened':False}
    output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({k:report[k] for k in ('job_id','molecules','failure_counts_by_task','errors','elapsed_seconds')}))
    return 1 if errors else 0


if __name__=='__main__': raise SystemExit(main())
