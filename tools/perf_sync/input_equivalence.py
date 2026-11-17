"""Reuse PR8's real 1000-batch sequence/RNG and 20-batch tensor comparison."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from regression import REPO, SCRATCH, capacity


def child(flag, tensor_only=False):
    sys.path.insert(0,str(REPO/'tools/model_v3'))
    import step_overhead as reference
    from phychem_mfm.phase1 import p_recipe_input
    configuration = json.loads((REPO/'configs/perf_sync/M2.json').read_text())
    options = configuration['step_overhead']
    original_model = reference.model_for
    def model_for(c, selected, device='cpu'):
        return original_model(c,dict(options,**selected),device=device)
    reference.model_for = model_for
    original_metadata = p_recipe_input.reader_metadata
    def reader_metadata(model, fields):
        return original_metadata(model,fields,sync_free=flag=='S1',async_transfer=flag=='S5')
    p_recipe_input.reader_metadata = reader_metadata
    original_equal = reference.equal_tensors
    def equal_tensors(left, right):
        # CPU layout metadata is intentionally new; model input keys stay strict.
        if isinstance(left,dict) and isinstance(right,dict) and 'perf_sync_layout' in right and 'perf_sync_layout' not in left:
            right = {name:value for name,value in right.items() if name!='perf_sync_layout'}
        return original_equal(left,right)
    reference.equal_tensors = equal_tensors
    if tensor_only:
        from itertools import islice
        original_batches = p_recipe_input.ordered_prepared_batches
        def first_twenty(*args,**kwargs):
            yield from islice(original_batches(*args,**kwargs),20)
        p_recipe_input.ordered_prepared_batches = first_twenty
    suffix = '_tensor' if tensor_only else ''
    output = SCRATCH/('input_'+flag+suffix)
    output.mkdir(parents=True,exist_ok=False)
    reference.verify_input(configuration,output)
    original = json.loads((output/'input_equivalence.json').read_text())
    summary = {key:value for key,value in original.items() if key!='records'}
    summary.update(flag=flag,tool='PR8 tools/model_v3/step_overhead.py verify_input',
        readers=configuration['workers'],gpu_used=False,
        raw_result=str(output/'input_equivalence.json'))
    summary['excluded_new_layout_metadata_keys'] = ['perf_sync_layout']
    if tensor_only:
        valid = len(original['records'])==20 and original['tensor_batches']==20 and not original['violations']
        summary.update(status='PASS' if valid else 'FAIL',scope='20-batch tensor correction only',
                       raw_full_tool_status=original['status'])
    (REPO/'results/perf_sync'/('input_'+flag+suffix+'_summary.json')).write_text(json.dumps(summary,indent=2)+'\n')
    if summary['status']!='PASS':raise RuntimeError('Real input sequence/RNG/tensor comparison failed')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--child',choices=('S1','S5'))
    parser.add_argument('--flag',choices=('S1','S5'))
    parser.add_argument('--tensor-only',action='store_true')
    args=parser.parse_args()
    if args.child:
        child(args.child,args.tensor_only)
        return
    capacity()
    SCRATCH.mkdir(mode=0o700,parents=True,exist_ok=True)
    sys.path.insert(0,str(REPO.parent/'MFM_p_recipe/tools/model_v3'))
    import v2_diagnosis_disk as disk
    def guard():
        capacity()
        # Anonymous torch IPC storage is physically allocated in this tmpfs.
        disk.m.require_capacity(disk.m.filesystem_status('/dev/shm'),2*1024**3,10000)
    for flag in ((args.flag,) if args.flag else ('S1',) if args.tensor_only else ('S1','S5')):
        suffix='_tensor' if args.tensor_only else ''
        summary=REPO/'results/perf_sync'/('input_'+flag+suffix+'_summary.json')
        if summary.exists():
            result=json.loads(summary.read_text())
            if result.get('status')=='PASS':
                print('RETAIN_PASS',flag,flush=True)
                continue
            raise RuntimeError('Preserve a failed input test; inspect before another attempt')
        guard()
        with (REPO/'results/perf_sync'/('input_'+flag+suffix+'.log')).open('x') as log:
            command=[sys.executable,'-B','-u',str(Path(__file__).resolve()),'--child',flag]
            if args.tensor_only:command.append('--tensor-only')
            process=subprocess.Popen(command,
                cwd=REPO,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                while process.poll() is None:
                    guard()
                    time.sleep(5)
            except BaseException:
                if process.poll() is None:
                    import signal
                    os.killpg(process.pid,signal.SIGTERM);process.wait()
                raise
        if process.returncode:
            raise RuntimeError(f'{flag} real input comparison failed; inspect preserved log')
        print('INPUT_PASS',flag,flush=True)


if __name__=='__main__':
    main()
