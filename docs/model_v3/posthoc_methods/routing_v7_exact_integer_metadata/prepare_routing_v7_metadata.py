"""Root-only CPython metadata repair: fresh routing7; no project imports or jobs."""
from __future__ import annotations
import argparse, copy, datetime, hashlib, json, os, pathlib, re, socket, stat, sys

B=pathlib.Path('/share/home/zixiao/descriptor_analysis')
N=B/'runs/model_v3_20261026'
OLD=N/'performance_remaining_Av2_20261029_routing_v6'
NEW=N/'performance_remaining_Av2_20261029_routing_v7'
HANDOFF=N/'remaining_Av2_routing_v7_CPython_metadata_handoff_v1.json'
FILES=('PLAN.json','METHODS.md','run_remaining_Av2.sbatch','Root_submit.py','source_pins.json')
CASES=('4520486','4520405','4520456','4520438','4520411','4520549')
EXPECTED_PINS='c5f9c9600a8bf15af3641bad852d73558d72934b61ab03f07bcc20ae6eafa940'
SHARED_PINS='cbb3d620f90768272abb2e135a11e928a861a896e9c51c80b5bea82ec6eca245'
META=2<<20

def need(ok,message):
    if not ok: raise ValueError(message)

def digest(raw): return hashlib.sha256(raw).hexdigest()

def encode(value,pretty=True):
    return (json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,
                       indent=2 if pretty else None,separators=None if pretty else (',',':'))+'\n').encode('utf-8')

def canonical(value): return digest(encode(value,False))

def reference(path):
    path=pathlib.Path(path).absolute(); before=path.lstat()
    need(path.resolve()==path and path.is_relative_to(B) and stat.S_ISREG(before.st_mode)
         and before.st_uid==1278 and before.st_nlink==1 and 0<before.st_size<=META,
         'Owned canonical bounded source/metadata required: '+str(path))
    raw=path.read_bytes(); after=path.lstat()
    need(all(getattr(before,key)==getattr(after,key) for key in
             ('st_dev','st_ino','st_size','st_mtime_ns','st_uid','st_nlink')),'Input changed while read')
    return dict(path=str(path),bytes=len(raw),sha256=digest(raw))

def rawref(path,raw): return dict(path=str(path),bytes=len(raw),sha256=digest(raw))

def read(path):
    before=reference(path)
    # CPython json decodes every JSON integer directly to Python int; never via float.
    value=json.loads(pathlib.Path(path).read_bytes(),parse_int=int,
                     parse_constant=lambda item:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    need(reference(path)==before,'Metadata changed while parsed')
    return value

def bound(item,parse=False):
    need(type(item) is dict and set(item)=={'path','bytes','sha256'} and type(item['bytes']) is int
         and reference(item['path'])==item,'Exact original rawref differs')
    return read(item['path']) if parse else item

def replace_exact(text,old,new,count):
    need(text.count(old)==count,'Unexpected source occurrence count: '+old)
    return text.replace(old,new)

def value_differences(before,after,path=()):
    if isinstance(before,dict) and isinstance(after,dict):
        need(set(before)==set(after),'Unexpected data-version key difference at '+'.'.join(path))
        return [item for key in before for item in value_differences(before[key],after[key],path+(key,))]
    if isinstance(before,list) and isinstance(after,list):
        need(len(before)==len(after),'Unexpected data-version list length difference')
        return [item for index,(a,b) in enumerate(zip(before,after))
                for item in value_differences(a,b,path+(str(index),))]
    return [] if before==after else [(path,before,after)]

def checks_for_case(row,original):
    candidate=bound(row['candidate_options'],True)
    return dict(candidate=original['candidate']==row['candidate'],
                reference=original['reference']==row['reference_options'],
                model=original['model']==row['model'],
                data_version=original['data_version']==row['original_data_version'],
                data_version_canonical_exact=canonical(original['data_version'])==canonical(row['original_data_version']),
                seed=original['seed']==0,input=original['input']=='native_s',
                fixed_batches=original['fixed_batches']==20,trajectory_updates=original['trajectory_updates']==500,
                candidate_options=candidate==row['candidate'],
                performance_execution_request=row['performance_execution_request'] is None,
                old500_not_reused=row['old500_reused'] is False,
                sampler=original['data_version']['sampler']['max_padded_cost']==8000000,
                workers=original['data_version']['loader']['num_workers']==8,
                global_attention=original['model']['backbone']['use_radius_mask'] is False)

def deduplicate(items):
    table={}
    for item in items:
        bound(item)
        need(item['path'] not in table or table[item['path']]==item,'Conflicting preserved rawrefs')
        table[item['path']]=copy.deepcopy(item)
    return list(table.values())

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-v6-pins-sha256',default=EXPECTED_PINS)
    parser.add_argument('--expected-failed-job',default='4524907')
    parser.add_argument('--failure-evidence',type=pathlib.Path,action='append',default=[],
                        help='Optional existing small actual Root failure/accounting JSON; copied only as a rawref')
    args=parser.parse_args()
    need(sys.implementation.name=='cpython' and os.getuid()==1278
         and socket.gethostname().split('.')[0]=='sonmi' and not os.environ.get('SLURM_JOB_ID'),
         'Actual Root login CPython metadata operation only')
    need(args.expected_v6_pins_sha256==EXPECTED_PINS and args.expected_failed_job=='4524907',
         'This finite repair is bound to frozen routing6 and actual4907')
    need(OLD.resolve()==OLD and not NEW.exists() and not HANDOFF.exists(),'Fresh canonical routing7 and handoff required')
    prior_refs=[reference(OLD/name) for name in FILES]
    old_pins_ref=prior_refs[-1]
    need(old_pins_ref['sha256']==EXPECTED_PINS,'Frozen routing6 pins differ')
    pins6=read(OLD/'source_pins.json'); plan6=read(OLD/'PLAN.json')
    need(pins6['routing_version']==plan6['routing_version']==6
         and pins6['source_directory']==plan6['source_directory']==str(OLD)
         and set(plan6['method_files'])==set(FILES) and len(plan6['method_files'])==5,
         'Exact frozen five-leaf routing6 identity required')
    for item in pins6['files']+pins6['protected_dependencies']: bound(item)
    for item in plan6['dependencies'].values(): bound(item)
    need(plan6['dependencies']['GPU_auto_memory_policy_pins']['sha256']==SHARED_PINS,
         'Shared policy must remain frozen cbb3')
    need([row['old_job_id'] for row in plan6['cases']]==list(CASES),'All six original ordered selectors required')
    failed_submission=OLD/'trials/recheck_4520405_routing_v6/control/Root_submission_actual_v1.json'
    failed_submission_ref=reference(failed_submission); failed=read(failed_submission)
    need(failed['job_id']==args.expected_failed_job and failed['source_package']==old_pins_ref,
         'Actual4907 old routing6 submission identity differs')
    failure_refs=[reference(path) for path in args.failure_evidence]
    for item in failure_refs:
        need(pathlib.Path(item['path']).suffix=='.json','Only existing small failure/accounting JSON rawrefs are accepted')

    plan7=copy.deepcopy(plan6)
    plan7['source_directory']=str(NEW)
    plan7['method_prefix']='docs/model_v3/pre_registered_methods/'+NEW.name+'/'
    plan7['routing_version']=7
    plan7['operational_only_fix']='CPython json.load/deepcopy of actual original data_version restores exact integer provenance; fresh routing7 only. Original automatic resources, science and strict worker declaration checks unchanged.'
    originals={}; original_refs=[]; repairs=[]; full_checks=[]
    for old_row,row in zip(plan6['cases'],plan7['cases']):
        need(old_row['old_job_id']==row['old_job_id'],'Original case order changed')
        # These bytes are opened on the server and decoded only by CPython stdlib.
        original=bound(row['original_configuration'],True)
        bound(row['original_supervisor']); originals[row['old_job_id']]=original
        original_refs.append(copy.deepcopy(row['original_configuration']))
        changes=value_differences(old_row['original_data_version'],original['data_version'])
        need(len(changes)==1 and changes[0][0]==('original_shard_snapshot','mtime_ns')
             and type(changes[0][1]) is int and type(changes[0][2]) is int
             and abs(changes[0][1])>2**53 and abs(changes[0][2])>2**53,
             'Refuse changes beyond the independently identified nanosecond integer provenance repair')
        # No float, JavaScript, generic external serializer, or hardcoded timestamp.
        row['original_data_version']=copy.deepcopy(original['data_version'])
        for key in ('family','control','child_output','supervisor_record'):
            row[key]=replace_exact(old_row[key],'routing_v6','routing_v7',2)
        expected_family=NEW/'trials'/('recheck_'+row['old_job_id']+'_routing_v7')
        need(row['family']==str(expected_family) and row['control']==str(expected_family/'control')
             and row['child_output']==str(expected_family/'child')
             and row['supervisor_record']==str(expected_family/'supervisor.json')
             and not expected_family.exists(),'Fresh exact routing7 runtime family required')
        checks=checks_for_case(row,original)
        need(all(checks.values()),'Complete original cohort precondition mismatch: '+row['old_job_id']+' '+str(checks))
        full_checks.append(dict(old_job_id=row['old_job_id'],original_configuration=row['original_configuration'],
                                original_data_version_sha256=canonical(original['data_version']),
                                new_data_version_sha256=canonical(row['original_data_version']),checks=checks))
        path,old_value,new_value=changes[0]
        # Decimal strings keep audit displays safe if downstream tools use IEEE754.
        repairs.append(dict(old_job_id=row['old_job_id'],path='original_data_version.'+'.'.join(path),
                            v6_integer_decimal=str(old_value),actual_original_integer_decimal=str(new_value),
                            source='actual original configuration, CPython JSON integer -> deepcopy'))

    root6=(OLD/'Root_submit.py').read_bytes().decode('utf-8')
    root7=replace_exact(root6,'routing_v6','routing_v7',4)
    root7=replace_exact(root7,"routing_version']==6","routing_version']==7",2)
    root7=replace_exact(root7,'declared_routing_version=6','declared_routing_version=7',1)
    root7=replace_exact(root7,'Exact routing-v6 plan required','Exact routing-v7 plan required',1)
    root_inverse=root7.replace('routing_v7','routing_v6').replace("routing_version']==7","routing_version']==6").replace('declared_routing_version=7','declared_routing_version=6').replace('Exact routing-v7 plan required','Exact routing-v6 plan required')
    need(root_inverse.encode('utf-8')==(OLD/'Root_submit.py').read_bytes(),'Root operational-version inverse must equal frozen routing6 bytes')
    sb6=(OLD/'run_remaining_Av2.sbatch').read_bytes().decode('utf-8')
    sb7=replace_exact(sb6,'routing_v6','routing_v7',4)
    sb7=replace_exact(sb7,"routing_version']==6","routing_version']==7",1)
    sb7=replace_exact(sb7,'routing-v6 physical','routing-v7 physical',1)
    sb_inverse=sb7.replace('routing_v7','routing_v6').replace("routing_version']==7","routing_version']==6").replace('routing-v7 physical','routing-v6 physical')
    need(sb_inverse.encode('utf-8')==(OLD/'run_remaining_Av2.sbatch').read_bytes(),'Worker operational-version inverse must equal frozen routing6 bytes')
    tail="common=plan['common']; deps=plan['dependencies']; py=row['logical_python']"
    need(sb6[sb6.index(tail):]==sb7[sb7.index(tail):],'Original scientific child/supervisor argv body must remain byte-identical')
    diagnostics=[line for line in sb7.split("<<'PY'",1)[0].splitlines() if re.search(r'\$\{[^}]+:\?',line)]
    need(len(diagnostics)==12 and all("'" not in line for line in diagnostics),'Apostrophe-free Bash diagnostics required')
    need(not re.search(r'(?m)^#SBATCH\s+--mem',sb7) and "'--mem=" not in root7
         and "key.startswith('SBATCH_')" in root7 and "for app_row in csv.reader" in root7,
         'Unchanged automatic Slurm resources and selected-case/NVML separation required')

    # Invert only the allowed provenance/version/fresh-path edits and prove all
    # scientific/resource/trust/dependency metadata remains the frozen v6 plan.
    inverse=copy.deepcopy(plan7)
    inverse['source_directory']=plan6['source_directory']; inverse['method_prefix']=plan6['method_prefix']
    inverse['routing_version']=6; inverse['operational_only_fix']=plan6['operational_only_fix']
    for row,old_row in zip(inverse['cases'],plan6['cases']):
        row['original_data_version']=copy.deepcopy(old_row['original_data_version'])
        for key in ('family','control','child_output','supervisor_record'): row[key]=old_row[key]
    need(canonical(inverse)==canonical(plan6),'No metadata/science/resource changes beyond the finite declared repair')
    plan_raw=encode(plan7)
    roundtrip=json.loads(plan_raw,parse_int=int)
    for row in roundtrip['cases']:
        original=originals[row['old_job_id']]
        need(canonical(row['original_data_version'])==canonical(original['data_version'])
             and all(checks_for_case(row,original).values()),'Serialized PLAN did not preserve all exact original cohort preconditions')

    methods=(OLD/'METHODS.md').read_bytes().decode('utf-8').replace('routing6','routing7')
    methods+='\n\n## Routing7 exact integer-provenance repair\n\nThis revision replaces each original_data_version with a CPython stdlib JSON/deepcopy read of its actual original configuration. The six identified snapshot mtime_ns values remain Python integers throughout, including values above2**53. No literal timestamp is invented. Original v6 source and actual4907 failure remain preserved. Runtime rejects mismatches exactly as before; no declaration check or scientific/resource gate is weakened. All source/runtime version and fresh namespace identities are7; scientific acceptance schema/rules remain v2. All prior automatic-resource descriptions above refer to the already frozen operation retained from v6. Copy and publish generated PLAN.json as exact raw bytes; never deserialize/re-encode it through JavaScript or a floating-number JSON writer.\n'
    bodies={'PLAN.json':plan_raw,'METHODS.md':methods.encode('utf-8'),
            'Root_submit.py':root7.encode('utf-8'),'run_remaining_Av2.sbatch':sb7.encode('utf-8')}
    generator_ref=reference(__file__)
    pins7=copy.deepcopy(pins6)
    pins7['source_directory']=str(NEW); pins7['routing_version']=7
    pins7['files']=[rawref(NEW/name,bodies[name]) for name in FILES if name!='source_pins.json']
    pins7['protected_dependencies']=deduplicate(pins6['protected_dependencies']+prior_refs+
                                                [generator_ref,failed_submission_ref]+failure_refs+original_refs)
    pins7['operational_fix']=plan7['operational_only_fix']
    pins7['v6_retained']=old_pins_ref
    pins7['CPython_metadata_generator']=generator_ref
    pins7['actual_metadata_generation']=dict(implementation=sys.implementation.name,version=sys.version,
                                             executable=sys.executable,uid=os.getuid(),hostname=socket.gethostname(),
                                             captured_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                             project_imports_or_jobs_executed=False)
    pins7['text_only_inverse_checks']=dict(Root_version_only_inverse_exact_v6=True,
        SB_version_only_inverse_exact_v6=True,plan_inverse_equal_except_exact_original_data_version_and_fresh_identity=True,
        all_six_complete_original_cohort_preconditions_verified_on_server=True,
        serialized_all_six_original_data_versions_canonical_exact=True,shared_policy_Native_max_or_v6_modified=False)
    pins7['actual_QA_history']=dict(preserved_v6_snapshot=copy.deepcopy(pins6.get('actual_QA_history')),
                                   Root_reported_failed_job='4524907',actual_v6_submission=failed_submission_ref,
                                   optional_actual_failure_rawrefs=failure_refs,actual_v7_QA_or_submission=None)
    pins_raw=encode(pins7); bodies['source_pins.json']=pins_raw
    refs=[rawref(NEW/name,bodies[name]) for name in FILES]
    handoff=dict(schema='model_v3_remaining_Av2_routing7_CPython_exact_metadata_handoff_v1',
        status='GENERATED_SOURCE_ONLY_REQUIRES_ROOT_QA_AND_REAL_PUBLICATION',generator=generator_ref,
        actual_metadata_generation=pins7['actual_metadata_generation'],source_directory=str(NEW),
        five_leaves=refs,source_pins=refs[-1],preserved_v6_five_leaves=prior_refs,
        Root_reported_failure=dict(job_id='4524907',stage='Original cohort declaration differs before supervisor/Torch/20+500',
                                  actual_old_submission=failed_submission_ref,optional_actual_failure_rawrefs=failure_refs,
                                  terminal_accounting_independently_verified_by_this_generator=False),
        exact_integer_repairs=repairs,all_six_complete_original_cohort_checks=full_checks,
        integer_transport_rule='Copy/publish exact generated raw bytes; no JavaScript JSON parse/re-encode or floating-number metadata serializer',
        inverse_proofs=dict(Root_inverse_sha256=digest(root_inverse.encode()),Root_frozen_v6_sha256=reference(OLD/'Root_submit.py')['sha256'],
                            SB_inverse_sha256=digest(sb_inverse.encode()),SB_frozen_v6_sha256=reference(OLD/'run_remaining_Av2.sbatch')['sha256'],
                            PLAN_canonical_inverse=canonical(inverse),PLAN_v6_canonical=canonical(plan6),
                            original_scientific_child_supervisor_tail_sha256=digest(sb6[sb6.index(tail):].encode()),
                            new_scientific_child_supervisor_tail_sha256=digest(sb7[sb7.index(tail):].encode())),
        unchanged=dict(shared_policy=plan7['dependencies']['GPU_auto_memory_policy_pins'],
                       scientific_source=plan7['current_source'],rules=plan7['rules'],resources=plan7['resources'],
                       data_files_modified=False,Native_v8_or_maxauto_modified=False,old_v6_family_or_failure_modified=False),
        CLI_template=[sys.executable,'-u','-B',str(NEW/'Root_submit.py'),'4520405','--method-publication',
                      'ACTUAL_NEW_ROUTING7_AND_SHARED5_PUBLICATION_REQUIRED','--method-publication-sha256',
                      'ACTUAL_NEW_PUBLICATION_RAWSHA_REQUIRED','--source-pins-sha256',refs[-1]['sha256']],
        actual_v7_QA=None,actual_v7_publication=None,actual_v7_submission=None,
        project_training_Git_Slurm_SSH_SDK_or_payload_execution=False)
    handoff_raw=encode(handoff)
    for item in prior_refs+original_refs+[failed_submission_ref]+failure_refs: bound(item)
    for name,raw in bodies.items(): need(0<len(raw)<=META,'Bounded new source leaf required: '+name)
    need(len(handoff_raw)<=META,'Bounded metadata handoff required')
    # No writes, family creation or live mutation occur until every precondition
    # and exact-int serialized roundtrip above has passed.
    NEW.mkdir(mode=0o700)
    for name in FILES:
        with (NEW/name).open('xb') as stream:
            stream.write(bodies[name]);stream.flush();os.fsync(stream.fileno())
    with HANDOFF.open('xb') as stream:
        stream.write(handoff_raw);stream.flush();os.fsync(stream.fileno())
    for item in refs+prior_refs+original_refs: bound(item)
    print(json.dumps(dict(status='ROUTING7_EXACT_METADATA_GENERATED_NO_PROJECT_EXECUTION',
                          source_pins=reference(NEW/'source_pins.json'),handoff=reference(HANDOFF),
                          cases_verified=len(full_checks),integer_repairs=len(repairs)),sort_keys=True),flush=True)

if __name__=='__main__': main()
