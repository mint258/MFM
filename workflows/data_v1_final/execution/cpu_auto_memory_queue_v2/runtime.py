"""Producer startup API for new unspecified-memory authority, never old proofs.

No memory environment value, 64GiB allocation or declaration-percentage test is
assumed. Producers own their explicit STOP/soft-budget/natural-drain monitoring.
"""
import os,sys,time
from pathlib import Path
from .shared import REPO,load,pin,read_small
from .contract import (PY,MEMORY_POLICY,need,validate_request,validate_bound_request,
                       validate_fresh_startup_proof,same)


def primary_binding(request,main_file,argv_tail):
    path=Path(main_file).absolute();code=str(path)
    args=list(request['execution_argv']);need(args and args[0]==PY,'LITERAL_PYTHON_PRIMARY_REQUIRED')
    tail=args[1:]
    while tail and tail[0] in ('-B','-u'):tail=tail[1:]
    if tail and tail[0]=='-m':
        need(len(tail)>=2 and REPO in path.parents,'ROOT_MODULE_PRIMARY_REQUIRED')
        module='.'.join(path.relative_to(REPO).with_suffix('').parts)
        need(tail[1]==module,'ACTUAL_PRIMARY_MODULE_DIFFERS')
        actual_tail=tail[2:]
    else:
        need(tail and tail[0]==code,'ACTUAL_PRIMARY_SCRIPT_DIFFERS')
        actual_tail=tail[1:]
    need(actual_tail==list(argv_tail),'ACTUAL_ALL_PRIMARY_OPTIONS_DIFFERS')
    return code


def require_startup(proof_path,*,expected_scope_key=None,expected_scope_parameters=None,
                    expected_execution_argv=None,expected_source=None,expected_kind=None,
                    required_references=()):
    proof_path=Path(proof_path).absolute();proof=load(proof_path);request=proof['request']
    need(proof_path==Path(request['startup_proof_path']) and
         proof['request_reference']==pin(proof['request_reference']['path']) and
         load(proof['request_reference']['path'])==request,'ACTUAL_NEW_REQUEST_AND_PROOF_PATH_REQUIRED')
    validate_request(request,read_small=read_small,
                     script_text=read_small(request['script_reference']['path']).decode())
    validate_bound_request(request,read_small=read_small)
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    import socket
    need(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID')==str(proof['job_id'])
         and socket.gethostname().split('.')[0]==request['node']
         and os.environ.get('SLURM_JOB_PARTITION')=='cpu'
         and os.environ.get('SLURM_CPUS_PER_TASK')=='16'
         and os.environ.get('CUDA_VISIBLE_DEVICES')=='','ACTUAL_CPU16_OWN_NODE_ALLOCATION_REQUIRED')
    validate_fresh_startup_proof(proof,request,now_unix=time.time(),uid=os.getuid(),boot_id=boot,max_age_seconds=120)
    if expected_kind is not None:need(request['kind']==expected_kind,'EXACT_PRODUCER_KIND_REQUIRED')
    if expected_scope_key is not None:need(request.get('scope_key')==expected_scope_key,'EXACT_PRODUCER_SCOPE_KEY_REQUIRED')
    if expected_scope_parameters is not None:
        need(same(request.get('scope_parameters'),expected_scope_parameters),'EXACT_PRODUCER_SCOPE_PARAMETERS_REQUIRED')
    if expected_execution_argv is not None:
        need(request['execution_argv']==list(expected_execution_argv),'EXACT_EXPECTED_EXECUTION_ARGV_REQUIRED')
    main=Path(sys.modules['__main__'].__file__).absolute()
    primary_binding(request,main,sys.argv[1:])
    sources={p['path']:p for p in request['source_references']}
    need(pin(main) in request['source_references'],'ACTUAL_PRIMARY_CODE_MUST_BE_PINNED')
    if expected_source is not None:
        wanted=expected_source if isinstance(expected_source,dict) else pin(Path(expected_source).absolute())
        need(wanted['path']==str(main) and sources.get(wanted['path'])==wanted and pin(main)==wanted,
             'EXPECTED_PRIMARY_CODE_PATH_OR_PIN_DIFFERS')
    for path in Path(__file__).parent.glob('*.py'):
        need(sources.get(str(path.absolute()))==pin(path.absolute()),'ACTUAL_CENTRAL_STARTUP_SOURCE_NOT_PINNED')
    bodies={p['path']:p for p in request.get('data_references',[])}
    for reference in required_references:
        need(isinstance(reference,dict) and
             (sources.get(reference['path'])==reference or bodies.get(reference['path'])==reference),
             'EXACT_PRODUCER_PLAN_OR_INPUT_NOT_AUTHORIZED')
        if reference['path'] in sources:need(pin(reference['path'])==reference,'ACTUAL_SMALL_INPUT_PIN_CHANGED')
    return proof
