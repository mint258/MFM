"""Source-full IO/once metadata adapters; original scientific helpers retained."""
from __future__ import annotations
import argparse,ast,hashlib,json,os,pathlib,socket,sys,time,unittest
from . import contract as C
from workflows.data_v1_final.conformers.n1_pprime2_pilot_v4 import io as V,quota_provider as Q
HERE=pathlib.Path(__file__).absolute().parent
ROOT=V.ROOT;BASE=ROOT/'artifacts/conformers/n1_pprime2_source_full_v1'
LEDGER=V.LEDGER;CAP=V.CAP;PACKET_CAP=V.PACKET_CAP;TASK_CAP=V.TASK_CAP;ADMIN_RESERVE=V.ADMIN_RESERVE
FILES=('__init__.py','contract.py','core.py','frozen_sources.json','test_core.py','io.py','prepare_cpu.py','run_batch.py','reduce.py','planning.py','test_full.py','README.md')
ref=V.ref;read=V.read;request_ref=V.request_ref;authorized=V.authorized;usage=V.usage;source_check=V.source_check
terminal_c0=V.terminal_c0;reserve_task=V.reserve_task;active_parent_continuation=V.active_parent_continuation;Budget=V.Budget

def small_ref(path):
    C.need(pathlib.Path(path).stat().st_size<=1<<20,'SMALL_METADATA_ONLY_BEFORE_HASH')
    return ref(path)

def fsync_directory(path):
    fd=os.open(path,os.O_DIRECTORY|os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)

def write(path,body,roots,reserve=ADMIN_RESERVE):
    result=V.write(path,body,roots,reserve);fsync_directory(pathlib.Path(path).parent);return result

def json_new(path,value,roots):return write(path,C.canonical(value)+b'\n',roots)

def new_output(path):
    path=pathlib.Path(path);C.need(path.is_absolute() and BASE in path.parents and path!=LEDGER and LEDGER not in path.parents
        and '..' not in path.parts and not path.exists() and not any(item.is_symlink() for item in (path,*path.parents)),'NEW_OWN_SOURCE_FULL_OUTPUT_REQUIRED')
    path.mkdir(parents=True,mode=0o700,exist_ok=False);fsync_directory(path.parent);return path

def packet_new(out,task,packet,ledger):
    result=V.packet_new(out,task,packet,ledger);fsync_directory(out/'packets');return result

def claim(task,ledger,out,proof):
    ledger=pathlib.Path(ledger);C.need(ledger==LEDGER and not any(path.is_symlink() for path in (ledger,*ledger.parents)),'EXACT_SHARED_N1_ONCE_LEDGER_REQUIRED')
    ledger.mkdir(parents=True,exist_ok=True,mode=0o700);key=task['task_key']
    C.need(key==C.task_key(task['meta']['molecule_id']),'N1_GENERATION_ONCE_KEY_DIFFERS')
    row={'schema':'N1_PPRIME2_ONCE_ATTEMPT_STARTED_V2','task_key':key,'molecule_id':task['meta']['molecule_id'],
        'job_id':str(proof['job_id']),'uid':os.getuid(),'pid':os.getpid(),
        'pid_start_ticks':int(pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),
        'boot_id':proof['boot_id'],'node':socket.gethostname(),'started_unix':time.time(),'output_root':str(out),
        'core_reference':ref(HERE/'core.py'),'seed':C.proposed_seed(task['meta']['molecule_id']),
        'automatic_retry':False,'common':False,'pilot_membership':False}
    return json_new(ledger/(key+'.json'),row,[out,ledger])



def event_checkpoint(out,task,name,value):
    out=pathlib.Path(out);C.need(BASE in out.parents and out.exists(),'ACTUAL_OWN_EVENT_OUTPUT_REQUIRED')
    directory=out/'events'/task['task_key']
    C.need(not any(path.is_symlink() for path in (directory,*directory.parents)),'NO_EVENT_SYMLINK_ANCESTOR')
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    C.need(not any(path.is_symlink() for path in (directory,*directory.parents)),'NO_EVENT_SYMLINKS')
    return json_new(directory/(name+'.json'),{'schema':'N1_ACTUAL_EVENT_CHECKPOINT_V2','task_key':task['task_key'],
        'molecule_id':task['meta']['molecule_id'],'job_id':os.environ['SLURM_JOB_ID'],'pid':os.getpid(),'uid':os.getuid(),
        'start_ticks':int(pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),
        'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'node':socket.gethostname(),
        'observed_unix':time.time(),
        'value':value,'common':False,'pilot_membership':False},[out,LEDGER])


class EmbeddingJournal(list):
    """Instrument the unchanged helper's list protocol, with no new native call."""
    def __init__(self,out,task):super().__init__();self.out=out;self.task=task;self.closed=set()
    def append(self,event):
        self.flush_last();super().append(event)
        event_checkpoint(self.out,self.task,'embedding_%02d_started'%len(self),event)
    def flush_last(self):
        if self and len(self) not in self.closed:
            event_checkpoint(self.out,self.task,'embedding_%02d_observed'%len(self),self[-1]);self.closed.add(len(self))


def science_ast_proof():
    old=V.science_ast_proof();before=(C.V4/'core.py').read_bytes().decode('utf-8');after=(HERE/'core.py').read_bytes().decode('utf-8')
    inverse=after.replace("proof['request']['pilot'] is False and proof['request']['scope']['mode']=='FULL_SOURCE_AFTER_PROFILE'",
        "proof['request']['pilot'] is True and proof['request']['scope']['mode']=='BOUNDED_PERFORMANCE_BATCH'")
    inverse=inverse.replace('ONLY_ROOT_REVIEWED_BOUNDED_SOURCE_WAVE_ADMITTED_NOT_PILOT_OR_FIXTURE','ONLY_EXACT32_REAL_SCIENCE_PILOT_ADMITTED_NOT_FORMAL_OR_FIXTURE')
    inverse=inverse.replace('for name in I.FILES:',"for name in ('__init__.py','contract.py','core.py','frozen_sources.json','test_core.py','README.md','io.py','prepare_cpu.py','run32.py'):")
    inverse=inverse.replace("Initializer for Root's central-v2 admitted finite source-wave parent runner.","Initializer for Root's single central-v2 admitted32 parent runner.")
    C.need(inverse.encode()==before.encode(),'CORE_INVERSE_ONLY_SCOPE_SOURCE_BINDINGS_MUST_EQUAL_V4')
    def functions(text):return {node.name:node for node in ast.parse(text).body if isinstance(node,ast.FunctionDef)}
    a=functions(before);b=functions(after)
    def body(text,node):return ''.join(text.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    for name in ('_add_conformer','_raw_number','_embedding','process_task'):
        C.need(body(before,a[name])==body(after,b[name]) and ast.dump(a[name],include_attributes=False)==ast.dump(b[name],include_attributes=False),'FULL_SOURCE_SCIENCE_FUNCTION_CHANGED:'+name)
    old_contract=(C.V4/'contract.py').read_bytes().decode('utf-8');new_contract=(HERE/'contract.py').read_bytes().decode('utf-8')
    for name,node in functions(old_contract).items():
        other=functions(new_contract)[name]
        C.need(body(old_contract,node)==body(new_contract,other) and ast.dump(node,include_attributes=False)==ast.dump(other,include_attributes=False),'ORIGINAL_CONTRACT_FUNCTION_CHANGED:'+name)
    old_prepare=(C.V4/'prepare_cpu.py').read_bytes().decode('utf-8');new_prepare=(HERE/'prepare_cpu.py').read_bytes().decode('utf-8')
    for name in ('q','init_validation','validate_original','mother_aggregation'):
        a=functions(old_prepare)[name];b=functions(new_prepare)[name]
        C.need(body(old_prepare,a)==body(new_prepare,b) and ast.dump(a,include_attributes=False)==ast.dump(b,include_attributes=False),'ORIGINAL_PREPARATION_SCIENCE_CHANGED:'+name)
    anchor='    config=I.read(formal_ref)'
    old_segment=old_prepare[old_prepare.index(anchor):old_prepare.index("        selection=C.module_from_pin('_n1_prepare_selection'")]
    new_segment=new_prepare[new_prepare.index(anchor):new_prepare.index("        picked={'tasks':sorted(valid")]
    C.need(old_segment==new_segment,'ORIGINAL_ALL_MOTHER_CENSUS_ELIGIBILITY_AND_PHYSICAL_VALIDATION_PATH_CHANGED')
    C.need((HERE/'frozen_sources.json').read_bytes()==(C.V4/'frozen_sources.json').read_bytes()
        and (HERE/'test_core.py').read_bytes()==(C.V4/'test_core.py').read_bytes(),'ORIGINAL_CATALOG_OR_TEN_FIXTURE_BYTES_CHANGED')
    result=dict(old,source_full_core_inverse_bytes_and_AST_equal=True,full_process_task_source_bytes_equal=True,
        original_v4_core_reference=ref(C.V4/'core.py'),new_full_core_reference=ref(HERE/'core.py'),
        scope_source_binding_only_edits=4,source_census_and_physical_validation_segment_bytes_equal=True,scientific_parameters_changed=False)
    return result


def test10():
    inheritance=science_ast_proof();result=V.test10()
    from .test_full import SourceFullBoundaries
    boundary=unittest.TestResult();suite=unittest.defaultTestLoader.loadTestsFromTestCase(SourceFullBoundaries);suite.run(boundary)
    extra={'tests_run':boundary.testsRun,'failures':[str(row) for row in boundary.failures],'errors':[str(row) for row in boundary.errors],
        'skips':[str(row) for row in boundary.skipped],'expected_failures':[str(row) for row in boundary.expectedFailures],
        'unexpected_successes':[str(row) for row in boundary.unexpectedSuccesses]}
    good=boundary.testsRun==6 and boundary.wasSuccessful() and not(boundary.skipped or boundary.expectedFailures or boundary.unexpectedSuccesses)
    result.update(status='PASS' if result['status']=='PASS' and good else 'FAIL',source_full_scientific_inheritance=inheritance,
        source_full_boundary_tests=extra,new_UFF_calls=0,new_QM_calls=0)
    return result


def admit(script,args,options,scope_key,scope,kind,required,*,execution_argv=None):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import PY
    script=pathlib.Path(script).absolute();argv=[PY,'-B',str(script)]
    C.need(pathlib.Path(sys.modules['__main__'].__file__).absolute()==script and pathlib.Path(sys.argv[0]).absolute()==script,'ACTUAL_SOURCE_FULL_PRIMARY')
    for name in options:
        value=getattr(args,name.replace('-','_'));C.need(value.is_absolute() and '..' not in value.parts,'LITERAL_SOURCE_FULL_CLI');argv.extend(['--'+name,str(value)])
    if execution_argv is not None:
        C.need(execution_argv==[PY,'-B',str(script),*sys.argv[1:]],'ACTUAL_COMPLETE_REPEATABLE_SOURCE_CLI')
        argv=list(execution_argv)
    catalog_ref=ref(HERE/'frozen_sources.json');catalog=C.load_catalog(catalog_ref)
    provider_review_reference=request_ref(args.root_preflight,args.quota_provider_review);provider_references=Q.references(provider_review_reference)
    local=[ref(HERE/name) for name in FILES];v4=[ref(C.V4/name) for name in V.FILES]
    proof=runtime.require_startup(args.root_preflight,expected_scope_key=scope_key,expected_scope_parameters=scope,
        expected_execution_argv=argv,expected_source=script,expected_kind=kind,
        required_references=(*required,*local,*v4,*catalog['references'].values(),*catalog['inherited_v1_sources'],
            *catalog['inherited_v2_sources'],*catalog['inherited_v3_sources'],*C.count_evidence_references(catalog),
            *catalog['usability_semantics_provenance'],*provider_references))
    C.need(proof['request']['pilot'] is False and proof['request']['estimated_peak_output_bytes']>=CAP,'HONEST_NONPILOT_SOURCE_STAGE_AND_WHOLE8GIB_CAP')
    C.need(proof['request']['node']=='compute-0-13','ACTUALLY_REVIEWED_FRESH_SAME_STORAGE_QUOTA_NODE13')
    mode='FULL_SOURCE_AFTER_PROFILE' if kind=='conformer' else 'BOUNDED_METADATA_PREPARATION'
    C.need(proof['request']['scope']['mode']==mode,'ACTUAL_SOURCE_STAGE_CENTRAL_MODE')
    os.environ.update({key:'1' for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')})
    return proof,catalog,{'proof_path':str(args.root_preflight),'runner_source':ref(script),'execution_argv':argv,
        'proof_reference':ref(args.root_preflight),'output_root':str(args.output),'validated_parent_pid':os.getpid(),
        'validated_parent_start_ticks':int(pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),
        'count_evidence_references':C.count_evidence_references(catalog),'usability_semantics_provenance':catalog['usability_semantics_provenance'],
        'quota_provider_review_reference':provider_review_reference,'quota_provider_references':provider_references}


def prepare_input_references(formal_path,quota_provider_review_path,pilot_review_path):
    for path in (formal_path,quota_provider_review_path,pilot_review_path):C.need(pathlib.Path(path).stat().st_size<=1<<20,'SMALL_METADATA_HELPER_INPUT_ONLY')
    result=V.prepare_input_references(formal_path,quota_provider_review_path);review_ref=small_ref(pilot_review_path);review=C.source_review(review_ref)
    prepared=read(review['prepared_reference']);pilot=read(review['pilot_receipt_reference']);account=read(review['terminal_all_known_accounting_reference'])
    extra=[review_ref,review['prepared_reference'],review['pilot_receipt_reference'],review['terminal_all_known_accounting_reference'],account['raw_sacct_reference'],
        prepared['source_population_authority'],prepared['role_status_usable_audit'],prepared['metadata_aggregation_before_validation'],
        review['original_ten_science_fixture_reference'],*prepared['tasks'],*prepared['baseline_packets'],
        *[row['reference'] for row in pilot['packets']],*[row['start_reference'] for row in pilot['claims']]]
    inputs={row['path']:row for row in [*result['input_references'],*extra]}
    sources={row['path']:row for row in [*result['source_references'],*[ref(HERE/name) for name in FILES]]}
    result.update(schema='N1_SOURCE_FULL_PREPARE_INPUT_LOCATORS_ONLY_V1',input_references=list(inputs.values()),source_references=list(sources.values()),
        actual_parent32_import_required=True,source_mother=5105,eligible_source=4631,imported_once=32,new_attempt_roster=4599,
        no_scientific_body_read_by_metadata_helper=True,common=False,pilot_membership=False,production_membership=False)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Small metadata references only; no source payload/body or new UFF')
    for name in ('formal-config','quota-provider-review','pilot-review'):parser.add_argument('--'+name,type=pathlib.Path,required=True)
    a=parser.parse_args();print(json.dumps(prepare_input_references(a.formal_config,a.quota_provider_review,a.pilot_review),allow_nan=False))


