"""Root-only metadata materialization for two vector CPU-v2 stages; never submit.

Run from the integrated repository on sonmi:
  python -B -m workflows.data_v1_final.pprime.vector_audit.cpu_v1.materialize_vector_cpu_v2 --job-name dv1_vector_cpu_v2
The only subprocess is the central metadata request builder. Neither the stage
driver nor any test/scientific entry is executed by this helper. Root submits
the returned .bound.json with submit_cpu_pilot_v3.py after separate review.
"""
from __future__ import annotations
import argparse,copy,json,os,pathlib,re,shlex,socket,subprocess
from workflows.data_v1_final.execution.cpu_analysis_v1 import policy

ROOT=policy.ROOT
REPO=policy.REPO
PY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
CPU=REPO/'workflows/data_v1_final/pprime/vector_audit/cpu_v1'
META=REPO/'configs/data_v1/pprime/vector_prepare_cpu_v2.json'
HELPER=CPU/'materialize_vector_cpu_v2.py'
CENTRAL=REPO/'workflows/data_v1_final/execution/cpu_analysis_v1'
SCOPE='vector_prepare_1000'
NODE='compute-0-17'
PREPARED=ROOT/'artifacts/pprime/prepared_v1'
PREPARED_SHA='3fd2feb6adf9bc125c81fb8be07f97bdbe5737d7bb09f4690da115a8468dcfca'
OUTPUT=ROOT/'artifacts/vector_frame_audit/prepared_cpu_v2'
BOUNDARY_RECEIPT=ROOT/'control/vector_cpu_boundaries_v2.json'
STAGE_RECEIPT=ROOT/'control/vector_cpu_stages_v2.json'
MATERIALIZATION_RECEIPT=ROOT/'control/vector_cpu_materialized_v2.json'

# Frozen v2 pins; edits_v2.json contains the seven frozen v1 pins.
V2_PINS=(
 ('prepare_cpu_v2.py',12974,'e949179952771fa4c4a20941c74b3ca8293c21cf2e32a2ea64cbd1ca5b6c9958'),
 ('runtime_control_v2.py',3729,'da89a49c06904cd8e014e949a2baefe14735bc9dac009c8b65378ca68529a663'),
 ('edits_v2.json',11236,'28231cb7e44d6379424c455a98a4fd34cf1f7c1c2e6c8edf05d48e6cf1809968'),
 ('verify_source_delta_v2.py',5973,'69e00c003efb67a84fff20ed26549068ee7d7152d3ea26caed95e7ba7608fb2c'),
 ('test_cpu_boundary_v2.py',3043,'eac464aebacfda249fcdf2b987bb0da0d6fe0faebb28047eba0f5a83e7000d6a'),
 ('README_v2.md',4644,'9473e0990e18b448f37d6d047303e9346381f3f105fa9cffb46439c050130478'),
)
META_PIN={'path':str(META),'bytes':3625,
          'sha256':'745a4a4e94e6913fa60ab960d034df6787b82cb59282f8d8b2472a11b2bd7716'}
ENGINE_NAMES={'wp5_engine_v3.py','wp5_parser_v2.py','wp5_parquet_v2.py',
              'wp5_archive_v5.py','wp5_archive_v4.py','wp5_scf_metadata_v2.py',
              'wp5_registry_coverage_v2.py','wp5_parser.py'}
CENTRAL_REQUIRED=('run_stages_v1.py','runtime_v2.py','launch_v2.py',
                  'prepare_request_v2.py','submit_cpu_pilot_v3.py')
RUNTIME_ROOT=pathlib.Path('/share/home/zixiao/PhyChem_MFM_stage59_three_epoch_runtime')
RUNTIME_MODULES=('phychem_mfm/data/descriptor_schema.py',
                 'phychem_mfm/model/phase1_specs.py')
RUNTIME_INITS=('phychem_mfm/__init__.py','phychem_mfm/data/__init__.py',
               'phychem_mfm/model/__init__.py')


def new_destination(path):
    policy.require(path.is_absolute() and not path.exists() and not path.is_symlink(),
                   'NEW_LITERAL_DESTINATION_REQUIRED:'+str(path))
    policy.require(not any(parent.is_symlink() for parent in path.parents),
                   'DESTINATION_SYMLINK_ANCESTOR_REJECTED:'+str(path))


def write_new(path,value):
    new_destination(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write('\n');stream.flush();os.fsync(stream.fileno())
    return policy.ref(path)


def add_source(sources,pin):
    path=pathlib.Path(pin['path'] if isinstance(pin,dict) else pin)
    policy.require(path.suffix not in {'.parquet','.jsonl','.lmdb'},
                   'SCIENTIFIC_DATA_BODY_FORBIDDEN_IN_SOURCE_REFS')
    if isinstance(pin,dict) and 'bytes' in pin:
        policy.require(0<pin['bytes']<=policy.MAX_SMALL,
                       'ONLY_SMALL_SOURCE_METADATA_MAY_BE_OPENED')
    actual=policy.ref(path)
    if isinstance(pin,dict):
        policy.require(actual['path']==pin['path'] and actual['sha256']==pin['sha256']
                       and ('bytes' not in pin or actual['bytes']==pin['bytes']),
                       'DECLARED_SMALL_SOURCE_PIN_DIFFERS:'+str(path))
    policy.require(str(path) not in sources or sources[str(path)]==actual,
                   'CONFLICTING_EXACT_SOURCE_REFERENCE:'+str(path))
    sources[str(path)]=actual
    return actual


def add_data(data,pin):
    # Deliberately inspect only inherited metadata, never stat/open/hash data.
    path=pathlib.PurePosixPath(pin['path'])
    policy.require(path.is_absolute() and '..' not in path.parts and
                   isinstance(pin.get('bytes'),int) and pin['bytes']>0 and
                   re.fullmatch(r'[0-9a-f]{64}',pin.get('sha256','')) is not None,
                   'INHERITED_DATA_REFERENCE_REQUIRED')
    policy.require(pin['path'] not in data or data[pin['path']]==pin,
                   'CONFLICTING_INHERITED_DATA_REFERENCE')
    data[pin['path']]=copy.deepcopy(pin)


def bindings():
    sources={};data={}
    for name,size,sha in V2_PINS:
        add_source(sources,{'path':str(CPU/name),'bytes':size,'sha256':sha})
    add_source(sources,META_PIN)
    delta=policy.load(CPU/'edits_v2.json')
    old=delta['unchanged_v1_references']
    policy.require(len(old)==7 and len({pin['path'] for pin in old})==7,
                   'EXACT_SEVEN_FROZEN_V1_REFERENCES_REQUIRED')
    for pin in old:
        add_source(sources,pin)
    for name in CENTRAL_REQUIRED:
        add_source(sources,CENTRAL/name)
    add_source(sources,HELPER)
    cpu=policy.load(META)
    policy.require(cpu['scope_key']==SCOPE and cpu['original_molecules']==1000 and
                   cpu['original_UFF_records']==2000 and cpu['actual_QM_calls']==0 and
                   cpu['maximum_audit_molecules']==4 and
                   cpu['scientific_config_mutated'] is False and
                   cpu['production_membership'] is False,
                   'EXACT_FROZEN_READONLY_VECTOR_SCOPE_REQUIRED')
    resources=cpu['resources']
    policy.require(resources=={'central_scope_cap_bytes':8589934592,'cpus':16,
                   'memory_gib':32,'scientific_output_cap_bytes':2147483648,
                   'wall_seconds':3600,'monitor_extra_bytes':33554432},
                   'EXACT_16CPU32G1H_AND_ORIGINAL_OUTPUT_ENVELOPE_REQUIRED')
    policy.require(cpu['runtime_path']==str(CENTRAL/'runtime_v2.py'),
                   'EXACT_CENTRAL_NODE_LOCAL_RUNTIME_PATH_REQUIRED')
    for key in ('audit_config','pilot_config','prepared_manifest'):
        add_source(sources,cpu[key])
    policy.require(cpu['prepared_manifest']=={'path':str(PREPARED/'prepared.json'),
                   'bytes':4012,'sha256':PREPARED_SHA},
                   'EXACT_CLOSED_PREPARED_MANIFEST_REQUIRED')
    saved=policy.load(PREPARED/'prepared.json')
    policy.require(saved['status']=='PPRIME_PAIRS_READY_NOT_QM_EXECUTED' and
                   saved['QM_started'] is False and saved['runtime']['job_id']=='4520345'
                   and saved['molecules']==1000 and saved['conformers']==2000 and
                   saved['audit_records']==20 and saved['config']==cpu['pilot_config']
                   and saved['outputs']==cpu['prepared_data_references'],
                   'CLOSED_1000_MOLECULE2000_UFF_INPUT_BINDING_DIFFERS')
    for pin in saved['outputs']:
        add_data(data,pin)
    audit=policy.load(cpu['audit_config']['path'])
    policy.require(audit['max_output_bytes']==2147483648 and
                   audit['minimum_molecules']==2 and audit['maximum_molecules']==4
                   and audit['maximum_prepared_QM_calls']==72 and
                   audit['minimum_prepared_QM_calls']==36 and
                   audit['production_membership'] is False,
                   'ORIGINAL_VECTOR_SCIENTIFIC_AUDIT_SCOPE_REQUIRED')
    for pin in audit['parent_source_pins']:
        add_source(sources,pin)
    pilot=policy.load(cpu['pilot_config']['path'])
    for pin in pilot['small_authority_pins']:
        if pin['bytes']>policy.MAX_SMALL:
            add_data(data,pin)
        else:
            add_source(sources,pin)
    for pin in pilot['large_authority_pins']:
        add_data(data,pin)
    add_source(sources,pilot['legacy_contract'])
    add_source(sources,pilot['source_plan'])
    add_source(sources,pilot['role_manifest'])
    contract=policy.load(pilot['legacy_contract']['path'])
    for key in ('protocol','registry','reproduction_package'):
        add_source(sources,contract[key])
    selected={pathlib.Path(pin['path']).name:pin for pin in contract['sources']
              if pathlib.Path(pin['path']).name in ENGINE_NAMES}
    policy.require(set(selected)==ENGINE_NAMES,
                   'ALL_ACTUAL_ENGINE_AND_BASE_PARSER_IMPORTS_REQUIRED')
    for name in sorted(selected):
        add_source(sources,selected[name])
    protocol=policy.load(contract['protocol']['path'])
    for pin in protocol['frozen_dependencies'].values():
        add_source(sources,pin)
    policy.require(protocol['registry']['path']==contract['registry']['path'] and
                   protocol['registry']['sha256']==contract['registry']['sha256'],
                   'EXACT_ENGINE_REGISTRY_BINDING_REQUIRED')
    for relative in RUNTIME_MODULES:
        add_source(sources,RUNTIME_ROOT/relative)
    for relative in RUNTIME_INITS:
        path=RUNTIME_ROOT/relative
        if path.is_file():
            add_source(sources,path)
    return sources,data,cpu


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job-name',default='dv1_vector_cpu_v2')
    args=parser.parse_args()
    name=args.job_name
    policy.require(os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi',
                   'ROOT_METADATA_ONLY_ON_SONMI')
    policy.require(pathlib.Path(__file__).absolute()==HELPER,
                   'INTEGRATED_ROOT_HELPER_ONLY')
    policy.require(re.fullmatch(r'dv1_[A-Za-z0-9_]+',name) is not None,
                   'EXACT_NEW_DV1_JOB_NAME_REQUIRED')
    stages_path=ROOT/'control/stages'/(name+'.json')
    command_path=ROOT/'control/commands'/(name+'.json')
    generated_path=ROOT/'control/requests'/(name+'.json')
    bound_path=ROOT/'control/requests'/(name+'.bound.json')
    intent=ROOT/'control/submissions'/(name+'.intent.json')
    script_path=ROOT/'control/scripts'/(name+'.sbatch')
    future_paths=(OUTPUT,BOUNDARY_RECEIPT,STAGE_RECEIPT,MATERIALIZATION_RECEIPT,
                  stages_path,command_path,generated_path,bound_path,intent,
                  script_path,ROOT/'control/submissions'/(name+'.json'),
                  ROOT/'artifacts/cpu_analysis_guards'/name)
    for path in future_paths:
        new_destination(path)
    scope=policy.load(policy.POLICY)['scopes'][SCOPE]
    policy.require(scope['memory_gib']==32 and scope['wall_seconds']==3600 and
                   scope['output_cap_bytes']==8589934592 and
                   scope['parameters']=={'molecules':1000,'UFF_records':2000,
                                         'actual_QM_calls':0},
                   'REVIEWED_SMALL_VECTOR_SCOPE_CHANGED')
    policy.verify(scope['base_request_reference'])
    sources,data,cpu=bindings()
    stages={'schema':'FINITE_VECTOR_CPU_STAGE_SPEC_V2','scope_key':SCOPE,
            'actual_QM_calls':0,'formal_generation_authorized':False,
            'stages':[
              {'name':'three_incremental_vector_v2_boundaries',
               'argv':[PY,'-B',str(CPU/'test_cpu_boundary_v2.py'),
                       '--root-preflight',str(intent),
                       '--output',str(BOUNDARY_RECEIPT)]},
              {'name':'readonly_vector_input_preparation_1000_2000',
               'argv':[PY,'-B',str(CPU/'prepare_cpu_v2.py'),
                       '--cpu-runconfig',str(META),
                       '--config',cpu['audit_config']['path'],
                       '--pilot-config',cpu['pilot_config']['path'],
                       '--prepared-pprime',str(PREPARED),
                       '--prepared-pprime-sha256',PREPARED_SHA,
                       '--root-preflight',str(intent),'--output',str(OUTPUT)]}
            ]}
    write_new(stages_path,stages)
    add_source(sources,stages_path)
    command=[PY,'-B','-m',
             'workflows.data_v1_final.execution.cpu_analysis_v1.run_stages_v1',
             '--stages',str(stages_path),'--root-preflight',str(intent),
             '--receipt',str(STAGE_RECEIPT)]
    write_new(command_path,command)
    builder=[PY,'-B','-m',
             'workflows.data_v1_final.execution.cpu_analysis_v1.prepare_request_v2',
             '--scope',SCOPE,'--node',NODE,'--job-name',name,
             '--command-file',str(command_path)]
    for path in sorted(sources):
        builder.extend(['--source',path])
    # This is the only subprocess. It builds metadata; it never submits a job.
    subprocess.run(builder,cwd=str(REPO),stdin=subprocess.DEVNULL,check=True)
    generated_raw=policy.read_small(generated_path)
    generated_reference=policy.ref(generated_path)
    request=json.loads(generated_raw)
    policy.scope(request)
    policy.require(policy.job_name(request)==name and request['node']==NODE and
                   request['cpus']==16 and request['memory_gib']==32 and
                   request['wall_seconds']==3600 and
                   request['execution_argv']==command,
                   'CENTRAL_GENERATED_REQUEST_SCOPE_OR_ARGV_DIFFERS')
    script=policy.read_small(script_path).decode('utf-8')
    policy.require('#SBATCH --partition=cpu' in script.splitlines() and
                   shlex.join(command) in script,
                   'ACTUAL_CPU_SCRIPT_OR_STAGE_DRIVER_DIFFERS')
    actual_sources={pin['path']:pin for pin in request['source_references']}
    for path,pin in sources.items():
        policy.require(actual_sources.get(path)==pin,
                       'REQUIRED_ACTUAL_IMPORT_OR_METADATA_NOT_PINNED:'+path)
    for path in (command_path,policy.POLICY,policy.DECISION,
                 *[CENTRAL/name for name in CENTRAL_REQUIRED]):
        policy.require(actual_sources.get(str(path))==policy.ref(path),
                       'ACTUAL_CENTRAL_BUILDER_DRIVER_SUBMITTER_NOT_PINNED')
    for pin in request.get('data_references',[]):
        add_data(data,pin)
    policy.require(not set(data).intersection(actual_sources),
                   'DATA_REFERENCE_MUST_NOT_BE_A_SOURCE_BODY')
    bound=copy.deepcopy(request)
    bound['data_references']=[data[path] for path in sorted(data)]
    bound['partition']='cpu'
    changed={key for key in set(request)|set(bound)
             if request.get(key)!=bound.get(key)}
    policy.require(changed<={'partition','data_references'} and
                   bound['partition']=='cpu',
                   'ONLY_CPU_PARTITION_AND_ADDITIVE_DATA_BINDINGS_MAY_DIFFER')
    policy.require(not intent.exists() and not
                   (ROOT/'control/submissions'/(name+'.json')).exists(),
                   'BOUND_REQUEST_MUST_PRECEDE_ANY_REGISTRATION')
    policy.scope(bound)
    policy.require(policy.job_name(bound)==name,'BOUND_SCRIPT_JOB_NAME_DIFFERS')
    bound_reference=write_new(bound_path,bound)
    policy.require(policy.read_small(generated_path)==generated_raw,
                   'CENTRAL_GENERATED_REQUEST_BYTES_MUST_REMAIN_UNCHANGED')
    receipt={'schema':'VECTOR_CPU_V2_METADATA_MATERIALIZATION_V1',
             'status':'PREPARED_NOT_SUBMITTED','scope_key':SCOPE,'node':NODE,
             'resources':cpu['resources'],'helper_reference':policy.ref(HELPER),
             'central_generated_request_reference':generated_reference,
             'bound_request_reference':bound_reference,
             'central_generated_request_unchanged':True,
             'bound_request_changed_keys':sorted(changed),
             'script_reference':policy.ref(script_path),
             'stages_reference':policy.ref(stages_path),
             'command_reference':policy.ref(command_path),
             'future_stage_receipt':str(STAGE_RECEIPT),
             'future_boundary_receipt':str(BOUNDARY_RECEIPT),
             'future_prepared_output':str(OUTPUT),
             'future_intent':str(intent),'stage_command':command,
             'source_references':bound['source_references'],
             'inherited_data_references_not_opened_or_hashed':bound['data_references'],
             'scientific_modules_imported':[],
             'boundary_tests_or_scientific_stages_executed':False,
             'submission_attempted':False,'automatic_retry':False,
             'formal_generation_authorized':False,
             'next_action':'Root reviews and submits bound_request_reference with submit_cpu_pilot_v3.py; accept only actual stages, 16 TIDs, input/source hashes and successful durable v2 monitor export.'}
    receipt_reference=write_new(MATERIALIZATION_RECEIPT,receipt)
    print(json.dumps({'status':'PREPARED_NOT_SUBMITTED',
                      'request_to_submit':bound_reference,
                      'materialization_receipt':receipt_reference,
                      'central_generated_request_unchanged':True,
                      'actual_QM_calls':0},sort_keys=True))

if __name__=='__main__':
    main()
