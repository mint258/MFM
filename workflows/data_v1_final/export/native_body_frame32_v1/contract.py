"""Small immutable parents and exact DATA declarations; never open DATA here."""
from __future__ import annotations
import csv,io,pathlib,re
from workflows.data_v1_final.export.native_availability_v1 import contract as A
Q=A.Q;ROOT=A.ROOT;REPO=A.REPO;PY=A.PY;need=A.need;meta=A.meta;unique=A.unique
HERE=REPO/'workflows/data_v1_final/export/native_body_frame32_v1'
MODULE='workflows.data_v1_final.export.native_body_frame32_v1.run'
FILES=('__init__.py','contract.py','metadata.py','prepare.py','reader.py','observe.py','run.py','test_v1.py','frozen_original_sources.json','README.md')
CALCS=A.CALCS;CAPS={'prepare':128<<20,'body':2<<30};WALLS={'prepare':900,'body':1800}
RAW_CAP=8<<20;FRAME_CAP=4<<20;MEMBER_CAP=4<<20;ROW_CAP=16<<20
SCRATCH_AND_INFLIGHT_RESERVE=256<<20
WP5=A.ARCHIVE.parent;NATIVE=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010/scripts/wp4_native_pilot_v4.py')
LEGACY=NATIVE.with_name('wp4_parsers.py');VECTOR=REPO/'workflows/data_v1_final/pprime/vector_audit'


def triple(value):
    r=A.triple(value)
    need(type(r['bytes']) is int and r['bytes']>0,'POSITIVE_NONBOOL_SCIENTIFIC_DATA_REFERENCE')
    return r


def scope(mode):
    need(mode in WALLS,'EXACT_TWO_NEW_MODES');return 'native_body_frame32_'+mode+'_v1'


def resource_mode(mode):return 'BOUNDED_METADATA_PREPARATION' if mode=='prepare' else 'BOUNDED_PERFORMANCE_BATCH'


def parameters(mode):
    return {'mode':mode,'records':32,'original_calculations':12,'execution_keys':384,'workers':16,
        'original_pure_methods':3,'new_pure_methods':3,'fixtures_before_resource_observer_and_DATA':True,
        'raw_body_allowed':mode=='body','base_geometry_allowed':mode=='body','parsed_wire_pickle_allowed':False,
        'maximum_raw_bundle_per_key_bytes':RAW_CAP,'maximum_compressed_raw_frame_per_key_bytes':FRAME_CAP,
        'maximum_output_member_per_key_bytes':MEMBER_CAP,'maximum_record_evidence_bytes':ROW_CAP,
        'wall_seconds':WALLS[mode],'whole_output_cap_bytes':CAPS[mode],
        'new_QM_calls':0,'new_UFF_calls':0,'D1_joint_approval':False,'cost_overrun_action':'REPORT_AND_CONTINUE'}


def actual_closure(refs,mode,manifest_schema,status,module,expected_scope,expected_parameters):
    need(set(refs)=={'manifest','startup_proof','accounting','raw_accounting'},'EXACT_FOUR_ACTUAL_CLOSURE_REFERENCES')
    manifest=meta(refs['manifest']);proof=meta(refs['startup_proof']);account=meta(refs['accounting'])
    request=proof['request'];planref=manifest['plan_reference'];plan=meta(planref)
    need(proof['schema']=='FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1' and proof['uid']==1278
        and request['partition']=='cpu' and request['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
        and request['kind']=='analysis' and request['cpus']==16 and request['pilot'] is False,
        'MAIN_ACTUAL_CPU16_NO_MEM_PARENT')
    need(request['scope_key']==expected_scope and request['scope_parameters']==expected_parameters
        and manifest['schema']==manifest_schema and manifest['status']==status
        and manifest['mode']==mode and manifest['job_id']==str(proof['job_id'])
        and meta(proof['request_reference'])==request,'EXACT_ACTUAL_PARENT_SCOPE')
    need(request['execution_argv']==[PY,'-B','-m',module,'--plan',planref['path'],'--startup-proof',refs['startup_proof']['path']]
        and planref in request['source_references'] and plan['data_references']==request['data_references']
        and pathlib.Path(refs['manifest']['path']).parent==pathlib.Path(plan['output_directory']),
        'PARENT_PLAN_ARGV_DATA_OUTPUT_BINDING')
    need(account['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and account['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
        and account['endpoint']=='202.38.247.57:22' and account['uid']==1278 and account['query_returncode']==0
        and account['raw_sacct_reference']==refs['raw_accounting'],'ACTUAL_MAIN_ACCOUNTING_NOT_PREDICTION')
    need(Q.pin(refs['raw_accounting']['path'])==A.triple(refs['raw_accounting']),'RAW_ACCOUNTING_PIN')
    rows=[r for r in csv.DictReader(io.StringIO(pathlib.Path(refs['raw_accounting']['path']).read_text()),delimiter='|')
        if r['JobIDRaw']==str(proof['job_id'])]
    parents=[r for r in account['parents'] if str(r['job_id'])==str(proof['job_id'])]
    need(len(rows)==len(parents)==1 and rows[0]['State']=='COMPLETED' and rows[0]['ExitCode']=='0:0'
        and rows[0]['UID']=='1278' and rows[0]['AllocCPUS']=='16' and parents[0]['state']=='COMPLETED'
        and parents[0]['exit_code']=='0:0' and parents[0]['alloc_cpus']==16
        and int(rows[0]['ElapsedRaw'])==parents[0]['elapsed_raw_seconds'],'REAL_C0_PARENT_AND_EXACT_ACCOUNT_PARITY')
    observation=meta(manifest['resource_observation_reference'])
    need(observation['status']=='RESOURCE_OBSERVATION_CLOSED' and observation['job_id']==str(proof['job_id'])
        and observation['startup_proof_request_reference']==proof['request_reference']
        and observation['soft_stop_requested'] is False and observation['forced_signals_sent'] is False,
        'PARENT_RESOURCE_CLOSURE_NO_SOFT_STOP')
    return manifest,plan,unique([*refs.values(),planref,proof['request_reference'],manifest['resource_observation_reference']])


def parents(inputs):
    need(set(inputs)=={'preparation_closure_references','metadata_probe_closure_references'},'EXACT_ORIGINAL3532_AND3538_AUTHORITIES')
    prepared,refs=A.closed_preparation(inputs['preparation_closure_references'])
    probe,plan,extra=actual_closure(inputs['metadata_probe_closure_references'],'probe','NATIVE_RAW_METADATA_AVAILABILITY_V1',
        'FINITE_NATIVE_METADATA_OBSERVED_FRAME_AND_VALUES_PENDING',A.MODULE,A.scope('probe'),A.parameters('probe'))
    need(prepared['job_id']=='4523532' and probe['job_id']=='4523538'
        and plan['preparation_closure_references']==inputs['preparation_closure_references']
        and probe['input_authority_references']==prepared['input_authority_references'], 'EXACT_CLOSED3532_TO3538_LINEAGE')
    need(probe['completed_key_observations']==384 and probe['missing_raw_keys']==probe['key_errors']==0
        and probe['sqlite_opens']==probe['sqlite_closes'] and probe['scientific_BLOBs_fetched']==0
        and probe['input_bodies_read']==0 and probe['native_frame_verified'] is False,'ORIGINAL_METADATA_ONLY_COMPLETE_NOT_NATIVE_ACCEPTANCE')
    wanted={(r['record_id'],r['calc_type'],r['execution_id']) for r in prepared['execution_keys']};seen=set();workers=[]
    frozen=meta(Q.pin(HERE/'frozen_original_sources.json'))
    package_counts={r['sha256']:0 for r in frozen['package_references']}
    for r in probe['worker_reports']:
        w=meta(r['report']);need(w['errors']==[],'ORIGINAL_METADATA_WORKER_NO_ERRORS');workers.append(r['report'])
        for row in w['rows']:
            key=tuple(row['key'][k] for k in ('record_id','calc_type','execution_id'))
            need(key not in seen and row['status']=='RAW_ROW_PRESENT_METADATA_VERIFIED','ORIGINAL_EXACT_UNIQUE_VERIFIED_METADATA_ROW');seen.add(key)
            package=row['reproduction_package_sha256'];need(package in package_counts,'EXACT_ORIGINAL_PER_KEY_PACKAGE');package_counts[package]+=1
    need(len(workers)==16 and seen==wanted,'COMPLETE_ORIGINAL384_MATRIX')
    need(package_counts==frozen['observed_original_package_key_counts'],'EXACT_ORIGINAL_FOUR_PACKAGE_CENSUS_3538')
    return prepared,probe,unique([*refs,*extra,*workers])


def recipe_sources(prepared):
    source=meta(prepared['input_authority_references']['source_prepared']);protocolref=source['sources']['protocol']
    protocol=meta(protocolref);frozen=meta(Q.pin(HERE/'frozen_original_sources.json'))
    paths=[WP5/'wp5_engine_v3.py',WP5/'wp5_parser_v2.py',WP5/'wp5_parser.py',NATIVE,LEGACY]
    refs=[protocolref]
    for package_ref in frozen['package_references']:
        package=meta(package_ref);refs.append(package_ref)
        need(package['status']=='REPRODUCTION_PACKAGE_CLOSED' and package['protocol']['path']==protocolref['path']
            and package['protocol']['sha256']==protocolref['sha256'],'EACH_ORIGINAL_PACKAGE_PROTOCOL_BINDING')
        for path in paths:
            options=[r for r in package['assets'] if r.get('source_path')==str(path)]
            pin=Q.pin(path)
            need(bool(options) and all(r['sha256']==pin['sha256'] and r['bytes']==pin['bytes'] for r in options),
                'EACH_ORIGINAL_PACKAGED_SCIENTIFIC_SOURCE_SHA:'+path.name)
            refs.extend([pin,Q.pin(options[0]['path'])])
            need(refs[-1]['bytes']==pin['bytes'] and refs[-1]['sha256']==pin['sha256'],'PACKAGED_AND_ORIGINAL_FULL_SOURCE_BYTES')
    need(protocol['seed']==20261010 and protocol['perturb_sigma_A']==0.1 and protocol['pair_cutoff_A']==4.0
        and protocol['expected_versions']=={'xtb':'6.7.1','mopac':'23.0.3'},'ORIGINAL_RECIPE_SEED_VERSION_NO_CHANGE')
    need(frozen['schema']=='NATIVE_BODY32_ACTUAL_ORIGINAL_SOURCE_PINS_V1','EXACT_FROZEN_ORIGINAL_SOURCE_BINDINGS')
    for ref in frozen['source_references']:
        need(Q.pin(ref['path'])==A.triple(ref),'FROZEN_ORIGINAL_SOURCE_BYTES_CHANGED');refs.append(ref)
    return protocolref,unique(refs)


def preparation_data(prepared):
    source=meta(prepared['input_authority_references']['source_prepared'])
    return unique([*A.expected_probe_data(prepared),triple(source['authority_locators']['catalog'])])


def prepared_body(refs,inputs):
    prior,plan,extra=actual_closure(refs,'prepare','NATIVE_BODY_FRAME32_LOCATORS_V1','EXACT_BASE_GEOMETRY_LOCATORS_NOT_OPENED',
        MODULE,scope('prepare'),parameters('prepare'))
    need(prior['input_authority_references']==inputs and plan['input_authority_references']==inputs
        and prior['base_geometry_files_opened']==0 and prior['new_QM_calls']==prior['new_UFF_calls']==0,
        'ACTUAL_NEW_PREPARATION_NOT_FUTURE_OR_SCIENCE')
    prepared,_,_=parents(inputs);keys=prepared['execution_keys'];rows=prior['geometry_locators']
    need(len(rows)==32 and {r['record_id'] for r in rows}=={r['record_id'] for r in prepared['selected_records']},'EXACT32_GEOMETRY_LOCATORS')
    need(all(len(r['execution_metadata'])==12 and set(r['execution_metadata'])==set(CALCS) for r in rows),'EXACT32_BY12_METADATA_FOR_GEOMETRY')
    data=unique([*A.expected_probe_data(prepared),*(triple(r['base_reference']) for r in rows)])
    return prior,data,extra


def derivation(plan):
    prepared,probe,refs=parents(plan['input_authority_references'])
    if plan['mode']=='prepare':return prepared,probe,None,preparation_data(prepared),refs
    prior,data,extra=prepared_body(plan['locator_preparation_closure_references'],plan['input_authority_references'])
    return prepared,probe,prior,data,unique([*refs,*extra])


def key(item):return tuple(item[k] for k in ('record_id','calc_type','execution_id'))


def source_paths():
    from workflows.data_v1_final.export.native_availability_v1.metadata import source_files
    paths=[*source_files(),*(HERE/n for n in FILES),NATIVE,LEGACY]
    paths += [WP5/n for n in ('wp5_engine_v3.py','wp5_parser_v2.py','wp5_parser.py','wp5_scf_metadata_v2.py','wp5_registry_coverage_v2.py')]
    paths += [VECTOR/n for n in ('read_outputs_v1.py','math_v1.py')]
    paths += [REPO/'workflows/data_v1_final/labels/lossless_projection_pilot_v1/projection.py']
    need(all(p.exists() for p in paths),'ALL_ACTUAL_NEW_AND_REUSED_SOURCE_FILES_REQUIRED')
    return list(dict.fromkeys(paths))
