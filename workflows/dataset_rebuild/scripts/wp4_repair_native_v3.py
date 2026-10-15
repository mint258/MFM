#!/usr/bin/env python3
"""Archive-only migration of native-v2 outputs into a new v3 directory.

Completed molecule Parquet is reused byte-for-byte. Every missing receipt must
already have all requested final task slots in its v2 state files; otherwise
this repair refuses that molecule. The v3 engine's invoke is replaced by an
unconditional error and its source reader returns an unused empty mapping.
Consequently this command runs no QM and opens no source LMDB.
"""
from __future__ import annotations
import argparse
import concurrent.futures as futures
import copy
import hashlib
import importlib.util
import json
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time

sys.dont_write_bytecode=True
HERE=Path(__file__).absolute().parent
ENGINE=None
SOURCE_OUTPUT=None


def load_engine(path):
    spec=importlib.util.spec_from_file_location('wp4_archive_only_engine',path)
    engine=importlib.util.module_from_spec(spec); spec.loader.exec_module(engine)
    return engine


def forbidden_QM(*args,**kwargs):
    raise RuntimeError('ARCHIVE_ONLY_REPAIR_FORBIDS_ANY_NEW_QM')


def initialize(sources,config,output,source_output,stop_event):
    global ENGINE,SOURCE_OUTPUT
    output=Path(output); SOURCE_OUTPUT=Path(source_output)
    ENGINE=load_engine(output/'source_snapshot/wp4_native_pilot_v3.py')
    ENGINE.initialize(sources,config,str(output),str(output/'source_snapshot/wp4_parsers.py'),time.time()+86400,stop_event)
    ENGINE.invoke=forbidden_QM
    # All final slots are validated before molecule_worker; no new task uses it.
    ENGINE.read_native=lambda row:{}


def file_reference(path):
    path=Path(path)
    return {'path':str(path),'bytes':path.stat().st_size,'sha256':ENGINE.sha(path)}


def verify_reference(ref):
    path=Path(ref['path'])
    if path.stat().st_size!=ref['bytes'] or ENGINE.sha(path)!=ref['sha256']:
        raise ValueError('V2_INPUT_REFERENCE_DIFFERS:'+str(path))


def decoder_evidence(reference):
    """One existing leaf, both close policies, in the allocated repair worker."""
    observations=[]
    for drain in (False,True):
        process=subprocess.Popen([ENGINE.CONFIG['zstd_executable'],'-d','-c',reference['path']],
                                 stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        members=[]; trailing_bytes=0
        with tarfile.open(fileobj=process.stdout,mode='r|') as archive:
            for member in archive:
                members.append({'name':member.name,'bytes':member.size})
                if member.isfile():
                    stream=archive.extractfile(member)
                    while stream.read(1<<20): pass
        if drain:
            while True:
                block=process.stdout.read(1<<20)
                if not block: break
                trailing_bytes+=len(block)
        process.stdout.close()
        stderr=process.stderr.read(); code=process.wait(timeout=60)
        observations.append({'drained_to_EOF':drain,'decoder_returncode':code,
                             'stderr':stderr.decode(errors='replace'),'members':members,
                             'trailing_decoded_bytes_drained':trailing_bytes})
    return {'existing_leaf_reference':reference,'observations':observations,
            'no_new_QM':True,'source_unchanged':ENGINE.sha(reference['path'])==reference['sha256']}


def worker(item):
    molecule,rows=item
    key=hashlib.sha256(molecule.encode()).hexdigest()[:24]
    source=SOURCE_OUTPUT/'molecules'/key; target=ENGINE.OUTPUT/'molecules'/key
    target.mkdir(parents=True,exist_ok=True)
    migration_path=target/'migration_receipt.json'
    if migration_path.exists():
        migration=json.loads(migration_path.read_text())
        for ref in migration['v2_input_references']: verify_reference(ref)
        receipt=ENGINE.molecule_worker(item)
        return {**receipt,'migration_mode':migration['mode'],'new_QM_calls':0,'LMDB_opened':False}
    receipt_source=source/'receipt.json'
    input_refs=[]; archive_evidence=None
    if receipt_source.is_file():
        input_refs.append(file_reference(receipt_source))
        original=json.loads(receipt_source.read_text())
        expected=ENGINE.stable_sha([(r['record_id'],r['record_payload_sha256']) for r in rows])
        if original['input_identity_sha256']!=expected: raise ValueError('V2_COMPLETED_MOLECULE_IDENTITY_DIFFERS')
        for name in ('parquet','archive'):
            ref=original.get(name)
            if ref: verify_reference(ref); input_refs.append(ref)
        copied=target/'results.parquet'
        shutil.copyfile(original['parquet']['path'],copied)
        receipt=copy.deepcopy(original)
        receipt['parquet']={**original['parquet'],'path':str(copied)}
        receipt.update(reused_v2_receipt_sha256=input_refs[0]['sha256'],
                       reused_v2_job_id=original['job_id'],new_QM_calls=0,LMDB_opened=False)
        # The reused archive reference stays on immutable v2; no redundant copy.
        ENGINE.save_json(target/'receipt.json',receipt)
        receipt=ENGINE.molecule_worker(item)
        mode='REUSED_COMPLETE_V2_MOLECULE_PARQUET_BYTE_IDENTICAL'
    else:
        states=[]
        for row in rows:
            state_path=source/'states'/(hashlib.sha256(row['record_id'].encode()).hexdigest()[:24]+'.json')
            input_refs.append(file_reference(state_path))
            state=json.loads(state_path.read_text())
            if state.get('record_id')!=row['record_id'] or state.get('payload_sha256')!=row['record_payload_sha256']:
                raise ValueError('V2_STATE_SOURCE_PAYLOAD_DIFFERS')
            final={result['task']:result for result in state['attempts'] if result['status'] not in ENGINE.UNFINISHED}
            requested=[*ENGINE.CONFIG['tasks']]
            if row.get('molecule_lowest_energy_conformer') is True: requested.append(ENGINE.CONFIG['hessian_task'])
            if set(final)!=set(task['name'] for task in requested):
                raise ValueError('ARCHIVE_ONLY_REPAIR_REQUIRES_ALL_FINAL_TASK_SLOTS:'+row['record_id'])
            for result in state['attempts']:
                if result.get('record_id')!=row['record_id'] or result.get('source_payload_sha256')!=row['record_payload_sha256']:
                    raise ValueError('V2_ATTEMPT_SOURCE_IDENTITY_DIFFERS')
                task=next(task for task in requested if task['name']==result['task'])
                if result.get('argv'):
                    if task['family']=='mopac':
                        if result.get('keywords')!=(task['keywords']+' THREADS=1'): raise ValueError('V2_ATTEMPT_KEYWORDS_DIFFERS')
                    elif result.get('arguments')!=task['args']: raise ValueError('V2_ATTEMPT_ARGUMENTS_DIFFERS')
                if result.get('archive'):
                    verify_reference(result['archive']); input_refs.append(result['archive'])
            states.append((state_path.name,state))
        state_dir=target/'states'; state_dir.mkdir(exist_ok=True)
        for name,state in states: ENGINE.save_json(state_dir/name,state)
        archives=[r for r in input_refs if r['path'].endswith('.tar.zst')]
        if archives: archive_evidence=decoder_evidence(max(archives,key=lambda ref:ref['bytes']))
        # invoke is forbidden; all task slots above are closed. Only derived
        # values, decoder-drained archive compaction and Parquet commit remain.
        receipt=ENGINE.molecule_worker(item)
        receipt.update(new_QM_calls=0,LMDB_opened=False,recovered_v2_job_id=rows[0].get('job_id','4512821'),
                       recovery_mode='V2_FINAL_ATTEMPTS_ARCHIVE_PARQUET_ONLY',resumed_without_QM=True)
        ENGINE.save_json(target/'receipt.json',receipt)
        mode='REPAIRED_V2_FINAL_ATTEMPTS_ARCHIVE_AND_PARQUET_ONLY'
    for ref in input_refs: verify_reference(ref)
    ENGINE.save_json(migration_path,{'mode':mode,'molecule_id':molecule,'v2_input_references':input_refs,
                    'v2_input_unchanged_after_repair':True,'new_QM_calls':0,'LMDB_opened':False,
                    'decoder_policy_evidence':archive_evidence,
                    'repair_job_id':os.environ['SLURM_JOB_ID'],'repair_worker_pid':os.getpid(),
                    'v3_receipt_sha256':ENGINE.sha(target/'receipt.json')})
    return {**receipt,'migration_mode':mode,'new_QM_calls':0,'LMDB_opened':False,
            'repair_worker_pid':os.getpid()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-output'); parser.add_argument('--output'); parser.add_argument('--panel')
    parser.add_argument('--record-index'); parser.add_argument('--workers',type=int,default=16)
    parser.add_argument('--engine',default=str(HERE/'wp4_native_pilot_v3.py'))
    parser.add_argument('--check',action='store_true'); args=parser.parse_args()
    engine=load_engine(args.engine)
    if args.check:
        import ast
        ast.parse(Path(__file__).read_text()); ast.parse(Path(args.engine).read_text())
        assert 'while decoder.stdout.read(1<<20): pass' in Path(args.engine).read_text()
        print(json.dumps({'status':'ARCHIVE_ONLY_REPAIR_AST_PASS','QM_started':False,'LMDB_opened':False})); return 0
    if not all((args.source_output,args.output,args.panel,args.record_index)): parser.error('source-output/output/panel/record-index required')
    allocated=int(os.environ.get('SLURM_CPUS_PER_TASK',0))
    if not os.environ.get('SLURM_JOB_ID') or not 16<=args.workers<=allocated: raise ValueError('SLURM_16_PARALLEL_WORKERS_REQUIRED')
    source=Path(args.source_output).absolute(); output=Path(args.output).absolute()
    root=engine.PROJECT/'runs/phase1_dataset_rebuild_20261010'
    if output==source or output==root or not output.is_relative_to(root): raise ValueError('USE_DISTINCT_NEW_PHASE_V3_OUTPUT')
    source_meta=source/'metadata.json'; original=json.loads(source_meta.read_text())
    config=copy.deepcopy(original['config']); old_binding=original['input_and_implementation_binding']
    if engine.sha(args.panel)!=old_binding['panel_sha256'] or str(Path(args.record_index).absolute())!=old_binding['record_index_path']:
        raise ValueError('V2_REPAIR_PANEL_OR_INDEX_DIFFERS')
    frozen_v2=source/'source_snapshot/wp4_native_pilot_v2.py'
    if engine.sha(frozen_v2)!=old_binding['runner_sha256']: raise ValueError('ACTUAL_V2_SNAPSHOT_DIFFERS')
    patched=frozen_v2.read_text().replace('decoder.stdout.close(); error=decoder.stderr.read(); code=decoder.wait()',
        'while decoder.stdout.read(1<<20): pass\n                        decoder.stdout.close(); error=decoder.stderr.read(); code=decoder.wait()',1).replace(
        '(Path(__file__),"wp4_native_pilot_v2.py")','(Path(__file__),"wp4_native_pilot_v3.py")',1)
    if patched!=Path(args.engine).read_text(): raise ValueError('V3_HAS_CHANGES_BEYOND_APPROVED_ARCHIVE_PATCH')
    groups=engine.load_panel(args.panel,args.record_index,args.workers)
    groups=sorted((item for item in groups if int(hashlib.sha256(item[0].encode()).hexdigest()[:16],16)%old_binding['bucket_count']==old_binding['bucket']),
                  key=lambda item:hashlib.sha256((str(config['seed'])+'|'+item[0]).encode()).hexdigest())
    if old_binding['max_molecules']: groups=groups[:old_binding['max_molecules']]
    previous_summary=json.loads((source/'job_4512821_summary.json').read_text())
    if len(groups)!=previous_summary['planned_molecules'] or sum(len(rows) for _,rows in groups)!=previous_summary['planned_records']:
        raise ValueError('V2_REPAIR_SELECTION_COUNTS_DIFFER')
    sources=json.loads(engine.DEFAULT_PLAN.read_text())['sources']
    binding={'v2_output':str(source),'v2_metadata_sha256':engine.sha(source_meta),
             'v2_summary_sha256':engine.sha(source/'job_4512821_summary.json'),
             'v2_actual_runner_sha256':old_binding['runner_sha256'],'v3_engine_sha256':engine.sha(args.engine),
             'repair_script_sha256':engine.sha(__file__),'panel_sha256':old_binding['panel_sha256']}
    output.mkdir(parents=True,exist_ok=True)
    metadata_path=output/'metadata.json'
    if metadata_path.exists():
        if json.loads(metadata_path.read_text()).get('repair_binding')!=binding: raise ValueError('REPAIR_RESUME_BINDING_DIFFERS')
    else:
        snapshot=output/'source_snapshot'; snapshot.mkdir()
        for name in ('wp4_parsers.py','wp4_mulliken_pairs_v2.py','config.json','wp4_native_pilot_v2.py'):
            shutil.copyfile(source/'source_snapshot'/name,snapshot/name)
        shutil.copyfile(args.engine,snapshot/'wp4_native_pilot_v3.py')
        shutil.copyfile(__file__,snapshot/'wp4_repair_native_v3.py')
        metadata=copy.deepcopy(original)
        metadata.update(scope='WP4_NATIVE_V3_ARCHIVE_ONLY_MIGRATION_NO_NEW_QM_NO_LMDB_OPEN',repair_binding=binding,
                        reuse_policy='29 completed molecule Parquet copied identically; failed molecule final state slots reused; v2 remains unchanged.',
                        repair_job_id=os.environ['SLURM_JOB_ID'],no_new_QM_guard='engine.invoke raises unconditionally; all final task slots prevalidated')
        metadata['input_and_implementation_binding']={**old_binding,'runner_sha256':engine.sha(args.engine)}
        engine.save_json(metadata_path,metadata)
    context=mp.get_context('spawn'); stop_event=context.Event(); receipts=[]; errors=[]; started=time.monotonic()
    with futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=context,
            initializer=initialize,initargs=(sources,config,str(output),str(source),stop_event)) as pool:
        pending={pool.submit(worker,item):item[0] for item in groups}
        for future in futures.as_completed(pending):
            try: receipts.append(future.result())
            except Exception as exc: errors.append({'molecule_id':pending[future],'error':type(exc).__name__+': '+str(exc)})
    summary={'status':'ARCHIVE_ONLY_REPAIR_COMPLETE' if len(receipts)==len(groups) and not errors else 'REPAIR_INCOMPLETE',
             'job_id':os.environ['SLURM_JOB_ID'],'planned_molecules':len(groups),'planned_records':sum(len(rows) for _,rows in groups),
             'completed_molecules':len(receipts),'receipts':receipts,'failures':errors,
             'actual_repair_worker_pids':sorted({r.get('repair_worker_pid',r.get('resumed_worker_pid',r['worker_pid'])) for r in receipts}),
             'new_QM_calls':0,'LMDB_opened':False,'LMDB_written':False,'v2_metadata_unchanged':engine.sha(source_meta)==binding['v2_metadata_sha256'],
             'elapsed_seconds':time.monotonic()-started,'pilot_report_complete':False}
    engine.save_json(output/('job_'+os.environ['SLURM_JOB_ID']+'_summary.json'),summary)
    print(json.dumps({k:summary[k] for k in ('status','job_id','completed_molecules','new_QM_calls','LMDB_opened')}))
    return 1 if errors else 0


if __name__=='__main__': raise SystemExit(main())
