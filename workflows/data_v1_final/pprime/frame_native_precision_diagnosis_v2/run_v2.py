"""Four synthetic tests, then bounded retained72 read-only geometry/print diagnosis."""
from __future__ import annotations
import argparse,ast,concurrent.futures as cf,contextlib,hashlib,importlib.util,io,json,multiprocessing as mp,os,pathlib,re,resource,socket,sys,tempfile,time,traceback,unittest
from precision import need,flatten,same_numbers,token_values,propagate_native,geometry_orbit
from tokens import select_field
from raw_reader import BoundedRawReader
import precision as diagnostic_precision
import tokens as diagnostic_tokens
import raw_reader as diagnostic_raw_reader
sys.dont_write_bytecode=True
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
REPO=ROOT/'repository';HERE=pathlib.Path(__file__).absolute().parent
PPRIME=REPO/'workflows/data_v1_final/pprime';VECTOR=PPRIME/'vector_audit'
sys.path[:0]=[str(VECTOR),str(PPRIME),str(REPO)]
from common import reference,require_pin,read_staging,load_engine
from prepare_v1 import load_audit
import evaluate_v1 as frozen_eval
import read_outputs_v1 as frozen_read
import math_v1 as frozen_math
SCOPE_KEY='pprime_frame_native_precision72_v2'
SCOPE={'original_job_id':'4521124','retained_cases':72,'original_covariance_failures':15,'new_QM_calls':0,
    'synthetic_test_methods':4,'all4_tests_must_pass_before_raw_reads':True,'pilot':False,'production_membership':False,
    'native_raw_read_only':True,'bounded_gzip_decompression':True,'precision_arithmetic':'EXACT_FRACTION',
    'maximum_report_bytes':2097152,'algorithm_rss_soft_cap_bytes':8589934592,'minimum_mem_available_bytes':4294967296}
WORKER={}


def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def frozen_sources():
    expected=json.loads((HERE/'frozen_sources.json').read_text())
    for item in expected['references']:require_pin(item)
    return expected


def init_worker(config_path,pilot_path):
    global WORKER
    sources=frozen_sources();config=load_audit(config_path)
    need(reference(pilot_path)==config['pilot_config'],'FROZEN_PILOT_METADATA_REFERENCE_REQUIRED')
    pilot=json.loads(pathlib.Path(pilot_path).read_text())
    engine,contract,protocol=load_engine(pilot)
    parser_ref=next(ref for ref in contract['sources'] if pathlib.Path(ref['path']).name=='wp5_parser_v2.py')
    parser=load_module('_diagnosis_frozen_parser2',require_pin(parser_ref))
    native_ref=protocol['frozen_dependencies']['native_lifecycle'];native_path=require_pin(native_ref)
    text=native_path.read_text();tree=ast.parse(text);names={'native_aux_labels','sparse_sigma_pi'}
    nodes=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
    need({node.name for node in nodes}==names,'EXACT_FROZEN_NATIVE_PARSER_HOOKS_REQUIRED')
    namespace={'Path':pathlib.Path,'PARSER':parser,'re':re}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(native_path)+'[exact parser hooks]','exec'),namespace)
    parser.read_aux=namespace['native_aux_labels']
    WORKER={'config':config,'pilot':pilot,'engine':engine,'contract':contract,'protocol':protocol,'parser':parser,
        'hooks':namespace,'parser_reference':reference(parser_ref['path']),'native_hook_reference':reference(native_path),
        'hook_AST_source_sha256':{node.name:hashlib.sha256(ast.get_source_segment(text,node).encode()).hexdigest() for node in nodes},
        'frozen_source_bindings':sources}


def actual_input(data,name,symbols):
    text=data.decode('utf-8','strict');lines=text.splitlines();rows=[]
    if name=='input.xyz':
        need(len(lines)>=2 and int(lines[0].strip())==len(symbols),'XYZ_DECLARED_COUNT_MISMATCH')
        source_rows=lines[2:];offset=3
        for line in source_rows:
            if line.strip():
                tokens=line.split();need(len(tokens)==4,'EXACT_XYZ_ROW_REQUIRED');rows.append((tokens[0],tokens[1:]))
    else:
        need(name=='input.mop' and len(lines)>=3,'MOPAC_INPUT_REQUIRED');source_rows=lines[3:];offset=4
        for line in source_rows:
            if line.strip():
                tokens=line.split();need(len(tokens)==7 and tokens[2::2]==['1','1','1'],'EXACT_MOPAC_XYZ_FLAGS_REQUIRED')
                rows.append((tokens[0],[tokens[1],tokens[3],tokens[5]]))
    need([symbol for symbol,_ in rows]==symbols,'ACTUAL_INPUT_ATOM_ORDER_OR_COUNT_MISMATCH')
    coords=[[float(value.replace('D','E').replace('d','e')) for value in row] for _,row in rows]
    need(all(re.fullmatch(frozen_math.FLOAT,value) for _,row in rows for value in row),'EXACT_INPUT_COORDINATE_TOKEN_REQUIRED')
    return coords


def bounded_pin_bytes(ref,limit):
    need(type(ref.get('bytes')) is int and 0<ref['bytes']<=limit,'PINNED_BODY_BYTES_EXCEED_FROZEN_LIMIT')
    path=require_pin(ref,full_hash=False)
    with path.open('rb') as stream:data=stream.read(limit+1)
    need(len(data)==ref['bytes'] and hashlib.sha256(data).hexdigest()==ref['sha256'],'PINNED_BOUNDED_BODY_CHANGED')
    return data


def result_record(ref,config):
    record=read_staging(bounded_pin_bytes(ref,config['max_result_bytes_per_case']))
    case=record['case'];raw=record['raw_reference']
    need(record['case_id']==case['case_id'] and record['QM_call_attempted'] is True,'ACTUAL_RETAINED_CASE_REQUIRED')
    need(type(raw['raw_bytes']) is int and 0<raw['raw_bytes']<=config['max_raw_bytes_per_case'],
        'PINNED_RAW_BYTES_EXCEED_FROZEN_CASE_CAP')
    need(isinstance(raw['raw_sha256'],str) and re.fullmatch('[0-9a-f]{64}',raw['raw_sha256']),'EXACT_RAW_SHA_REQUIRED')
    need(raw['output_retained'] is True and raw['raw_call_durable'] is True and raw['input_bodies_saved'] is False,
        'ORIGINAL_DURABLE_OUTPUT_ONLY_RAW_REFERENCE_REQUIRED')
    need(isinstance(case['symbols'],list) and 0<len(case['symbols'])<=config['maximum_atoms'],'FROZEN_CASE_ATOM_CAP_REQUIRED')
    for refs in (record['actual_postcall_input_references'],case['input_files']):
        need(isinstance(refs,list) and refs,'ACTUAL_AND_PREPARED_INPUT_REFERENCES_REQUIRED')
        need(all(type(item.get('bytes')) is int and item['bytes']>0 for item in refs)
            and sum(item['bytes'] for item in refs)<=config['max_input_bytes_per_case'],'FROZEN_CASE_INPUT_BYTES_CAP_REQUIRED')
        names=[pathlib.Path(item['path']).name for item in refs]
        need(len(names)==len(set(names)),'DUPLICATE_INPUT_MEMBER_NAME')
    return record


def preflight_cases(result_refs,original,config):
    """Read only bounded result metadata; never open a raw SQLite container here."""
    rows=[];errors=[];paths=set();ids=set();groups=set();raw_keys=set()
    need(isinstance(result_refs,list) and len(result_refs)==72,'EXACT72_RESULT_REFERENCES_REQUIRED')
    for ref in result_refs:
        try:
            need(ref['path'] not in paths,'DUPLICATE_RESULT_REFERENCE');paths.add(ref['path'])
            record=result_record(ref,config);case=record['case'];raw=record['raw_reference']
            need(case['case_id'] not in ids,'DUPLICATE_RETAINED_CASE_ID');ids.add(case['case_id'])
            group=(case['molecule_id'],case['geometry_source'],case['condition'])
            arm_key=group+(case['arm'],)
            need(arm_key not in groups,'DUPLICATE_RETAINED_GROUP_ARM');groups.add(arm_key)
            raw_key=(raw['container_path'],raw['record_id'],raw['calc_type'],raw['execution_id'])
            need(raw_key not in raw_keys,'DUPLICATE_RETAINED_RAW_KEY');raw_keys.add(raw_key)
            need(pathlib.Path(raw['container_path']).is_absolute(),'ABSOLUTE_ORIGINAL_RAW_CONTAINER_REQUIRED')
            need(raw['calc_type']==case['calc_type'],'CASE_AND_RAW_CALC_TYPE_DIFFER')
            rows.append({'result':ref,'case_id':case['case_id'],'group':list(group),
                'arm':case['arm'],'raw_bytes':raw['raw_bytes'],'raw_sha256':raw['raw_sha256']})
        except Exception as exc:
            errors.append({'result':ref,'error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc()})
    expected=set(original['measurements'])
    if len(expected)!=72 or ids!=expected:
        errors.append({'error':'ORIGINAL_EVALUATION_AND_RETAINED72_CASE_IDS_DIFFER',
            'missing_case_ids':sorted(expected-ids),'unexpected_case_ids':sorted(ids-expected)})
    return {'status':'PASS_METADATA_ONLY' if not errors and len(rows)==72 else 'FAIL_METADATA_ONLY_NO_RAW_READS',
        'raw_container_bodies_read':0,'maximum_raw_bytes_per_case':config['max_raw_bytes_per_case'],
        'maximum_result_bytes_per_case':config['max_result_bytes_per_case'],
        'maximum_input_bytes_per_case':config['max_input_bytes_per_case'],
        'case_count_checked':len(result_refs),'cases':rows,'errors':errors}


def run_synthetic_tests():
    """An actual in-allocation four-method receipt; no subprocess/science entry."""
    wanted={'test_scientific_E_D_halfstep_and_unique_native_token_selection',
        'test_large_component_quantization_propagates_into_small_rotated_component',
        'test_reperturbed_lab_geometry_is_not_same_orbit_and_P_must_be_explicit',
        'test_fraction_large_exponent_cancellation_and_small_component_boundary'}
    receipt={'schema':'PPRIME_NATIVE_PRECISION_SYNTHETIC4_ACTUAL_RECEIPT_V2','status':'FAIL',
        'tests_required':4,'tests_run':0,'successful_test_ids':[],'failures':[],'errors':[],
        'skipped':[],'expected_failures':[],'unexpected_successes':[],
        'retained_raw_or_input_bodies_read':0,'QM_or_UFF_calls':0,'source':reference(HERE/'test_v2.py')}
    started=time.monotonic();out=io.StringIO();err=io.StringIO()
    class RecordingResult(unittest.TestResult):
        def addSuccess(self,test):
            super().addSuccess(test);receipt['successful_test_ids'].append(test.id())
    try:
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            module=load_module('_native_precision_v2_synthetic4',HERE/'test_v2.py')
            fixture=module.NativePrecisionFixtures
            names=unittest.defaultTestLoader.getTestCaseNames(fixture)
            need(set(names)==wanted and len(names)==4,'EXACT_FROZEN3_PLUS_FRACTION1_METHODS_REQUIRED')
            suite=unittest.defaultTestLoader.loadTestsFromTestCase(fixture);result=RecordingResult();suite.run(result)
            receipt.update(tests_run=result.testsRun,
                failures=[{'test_id':test.id(),'traceback':detail} for test,detail in result.failures],
                errors=[{'test_id':test.id(),'traceback':detail} for test,detail in result.errors],
                skipped=[{'test_id':test.id(),'reason':reason} for test,reason in result.skipped],
                expected_failures=[{'test_id':test.id(),'traceback':detail} for test,detail in result.expectedFailures],
                unexpected_successes=[test.id() for test in result.unexpectedSuccesses])
            if result.testsRun==4 and len(receipt['successful_test_ids'])==4 and result.wasSuccessful() and not (
                result.skipped or result.expectedFailures or result.unexpectedSuccesses):receipt['status']='PASS'
    except Exception as exc:
        receipt['errors'].append({'error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc()})
    receipt.update(stdout=out.getvalue(),stderr=err.getvalue(),wall_seconds_observed=time.monotonic()-started)
    return receipt


def read_case(result_ref,failure_fields):
    import numpy as np
    record=result_record(result_ref,WORKER['config']);case=record['case'];symbols=case['symbols'];task=case['calc_type']
    raw_ref=record['raw_reference'];reader=BoundedRawReader(raw_ref['container_path'],WORKER['engine'].OUTPUT_ARCHIVE,
        WORKER['config']['max_raw_bytes_per_case'],WORKER['config']['max_result_bytes_per_case'])
    try:
        key=(raw_ref['record_id'],raw_ref['calc_type'],raw_ref['execution_id'])
        retained=reader.get(*key,expected_raw_sha256=raw_ref['raw_sha256'],expected_raw_bytes=raw_ref['raw_bytes'])
    finally:reader.close()
    files=retained['output_files'];raw_source=reference(raw_ref['container_path'])
    inputs={pathlib.Path(ref['path']).name:(ref,bounded_pin_bytes(ref,WORKER['config']['max_input_bytes_per_case']))
        for ref in record['actual_postcall_input_references']}
    prepared={pathlib.Path(ref['path']).name:ref for ref in case['input_files']}
    recipe=next(item for item in WORKER['protocol']['tasks'] if item['name']==task)
    rendered=WORKER['engine'].render_inputs(recipe,{'symbols':symbols,'coords':np.asarray(case['native_coordinates_A'],float)},case['row'],WORKER['protocol'])
    need(set(inputs)==set(rendered)==set(prepared),'EXACT_PREPARED_AND_ACTUAL_INPUT_MEMBER_SET_REQUIRED')
    input_byte_checks=[]
    for name,(ref,data) in inputs.items():
        require_pin(prepared[name]);input_byte_checks.append({'name':name,'actual_equals_frozen_render_bytes':data==rendered[name],
            'actual_SHA_equals_prepared_SHA':ref['sha256']==prepared[name]['sha256']})
    program_name='input.mop' if recipe['family']=='mopac' else 'input.xyz'
    coords=actual_input(inputs[program_name][1],program_name,symbols)
    xyz=actual_input(inputs['input.xyz'][1],'input.xyz',symbols)
    actual=np.asarray(coords);xyz_error=float(np.max(np.abs(actual-np.asarray(xyz))))
    target_error=float(np.max(np.abs(actual-np.asarray(case['expected_actual_coordinates_A']))))
    recorded_error=float(np.max(np.abs(actual-np.asarray(case['actual_rendered_coordinates_A']))))
    geometry_matches_target=max(xyz_error,target_error,recorded_error)<=WORKER['config']['rendered_coordinate_atol_A']
    input_binding_verified=geometry_matches_target and all(row['actual_equals_frozen_render_bytes'] and
        row['actual_SHA_equals_prepared_SHA'] for row in input_byte_checks)
    independent=frozen_read.parse_outputs(files,task,symbols)
    reread_record=dict(record,independent_raw_readback=independent)
    measured=frozen_eval.measurement(reread_record,WORKER['config'])
    # Copy output bodies only into this node-local temporary directory. Original raw is opened read-only.
    with tempfile.TemporaryDirectory(prefix='pva_precision_'+str(os.getuid())+'_',dir='/tmp') as scratch:
        folder=pathlib.Path(scratch)
        for item in files:
            name=item['name'];need(pathlib.PurePosixPath(name).name==name and name not in {'input.xyz','input.mop','native.inp'},'SAFE_OUTPUT_ONLY_MEMBER_NAME_REQUIRED')
            with (folder/name).open('xb') as stream:stream.write(item['data'])
        parser=WORKER['parser'];pairs=[tuple(pair) for pair in case['pairs']]
        parser.sigma_pi_entries=lambda body:WORKER['hooks']['sparse_sigma_pi'](body,pairs)
        full_values=parser.parse_mopac(folder,symbols,pair_indices=pairs,reconstruct_mulliken=False) if recipe['family']=='mopac' else parser.parse_xtb(folder,symbols)
    fields={}
    for field in failure_fields:
        selection=select_field(files,field,symbols,parser);item={'native_selection':selection}
        if selection['status']=='UNIQUE_NATIVE_TOKEN_SELECTION':
            try:
                key=selection['parser_field'];factor=selection['factor_from_frozen_parser']
                converted,details=token_values(selection['entries'],factor,parser.f)
                parsed=full_values.get(key);audit=measured['vectors'].get(field,{}).get('values')
                original=record['parsed_wp5_result'].get('values',{}).get(key)
                projected=parser.project_values(task,full_values)
                no_label=key not in projected and original is None
                checks={'native_tokens_match_fresh_frozen_parser_bitwise':same_numbers(converted,parsed),
                    'fresh_frozen_parser_matches_independent_audit_vector_bitwise':same_numbers(parsed,audit),
                    'fresh_parser_matches_original_label_bitwise':same_numbers(parsed,original) if original is not None else None,
                    'original_label_absence':'INTENTIONALLY_EXCLUDED_BY_FROZEN_TASK_PROJECTION' if no_label else None,
                    'fresh_independent_audit_matches_original_readback_bitwise':same_numbers(audit,
                        frozen_eval.measurement(record,WORKER['config'])['vectors'].get(field,{}).get('values'))}
                known=checks['native_tokens_match_fresh_frozen_parser_bitwise'] and checks['fresh_frozen_parser_matches_independent_audit_vector_bitwise'] and checks['fresh_independent_audit_matches_original_readback_bitwise']
                known=known and (checks['fresh_parser_matches_original_label_bitwise'] is True or no_label)
                item.update(status='EXACT_NATIVE_VALUES_AND_UNITS_VERIFIED' if known else 'UNKNOWN',value_checks=checks,
                    native_token_details=details,fresh_parser_values=parsed,audit_vector=measured['vectors'].get(field),
                    no_precision_inferred_from_float_repr_or_dtype=True)
            except Exception as exc:item.update(status='UNKNOWN',error=type(exc).__name__+': '+str(exc))
        else:item['status']='UNKNOWN'
        fields[field]=item
    return {'case_id':case['case_id'],'group':[case['molecule_id'],case['geometry_source'],case['condition']],
        'arm':case['arm'],'symbols':symbols,'actual_program_coordinates_A':coords,
        'source_clean_coordinates_A':case['source_clean_coordinates_A'],'rotation_matrix':case.get('rotation_matrix'),
        'translation_A':case.get('translation_A'),'perturb_seed':case.get('perturb_seed'),
        'case_perturbation_metadata':{'native_coordinates_A':case['native_coordinates_A'],'noisy_singlepoint_companion':case.get('noisy_singlepoint_companion'),
            'noise_precompensation_is_audit_only':case.get('noise_precompensation_is_audit_only')},
        'input_validation':{'case_id':case['case_id'],'program_input':program_name,'inputs':list(ref for ref,_ in inputs.values()),
            'input_member_byte_checks':input_byte_checks,'actual_program_geometry_matches_frozen_target':geometry_matches_target,
            'all_actual_input_bindings_and_target_verified':input_binding_verified,
            'original_software_version_id':record['parsed_wp5_result'].get('provenance',{}).get('software_version_id'),
            'frozen_task_recipe':recipe,'input_mop_vs_xyz_max_abs_A':xyz_error,
            'actual_vs_expected_target_max_abs_A':target_error,'actual_vs_recorded_rendered_max_abs_A':recorded_error,
            'raw_container':raw_source,'raw_call_sha256':raw_ref['raw_sha256'],'result':result_ref},
        'fields':fields,'parser_sources':{'parser':WORKER['parser_reference'],'native_hooks':WORKER['native_hook_reference'],
            'hook_AST_source_sha256':WORKER['hook_AST_source_sha256']}}


def memory_sample(processes):
    available=next(int(line.split()[1])*1024 for line in pathlib.Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
    pids=[os.getpid()]+[process.pid for process in processes if process.pid and process.is_alive()];rss=0
    for pid in pids:
        try:rss+=int(pathlib.Path('/proc',str(pid),'statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
        except FileNotFoundError:continue
    return {'unix_seconds':time.time(),'parent_plus_live_worker_RSS_bytes':rss,'MemAvailable_bytes':available,'pids':pids}


def geometry_diagnostics(cases,config):
    import numpy as np
    groups={};orbits={};noise=[];translations=[]
    for item in cases:groups.setdefault(tuple(item['group']),{})[item['arm']]=item
    for key,arms in groups.items():
        if set(arms)>={'base','rotated'}:
            base,variant=arms['base'],arms['rotated'];rotation=variant['rotation_matrix']
            need(rotation==config['rotation_matrix'],'FROZEN_DECLARED_ROTATION_MATRIX_REQUIRED')
            check=geometry_orbit(base['actual_program_coordinates_A'],variant['actual_program_coordinates_A'],rotation,atol=config['rendered_coordinate_atol_A'])
            check.update(group=list(key),base_case=base['case_id'],variant_case=variant['case_id'])
            orbits[key]=check
    for mid,geom in sorted({key[:2] for key in groups}):
        clean=groups.get((mid,geom,'xtb_singlepoint'),{})
        for condition in ('xtb_perturbed_gradient','xtb_singlepoint_noisy_companion'):
            noisy=groups.get((mid,geom,condition),{})
            if not set(clean)>={'base','rotated'} or not set(noisy)>={'base','rotated'}:continue
            nb=np.asarray(noisy['base']['actual_program_coordinates_A'])-np.asarray(clean['base']['actual_program_coordinates_A'])
            nv=np.asarray(noisy['rotated']['actual_program_coordinates_A'])-np.asarray(clean['rotated']['actual_program_coordinates_A'])
            rotated=geometry_orbit(nb,nv,config['rotation_matrix'],atol=config['rendered_coordinate_atol_A'])
            lab=geometry_orbit(nb,nv,np.eye(3).tolist(),atol=config['rendered_coordinate_atol_A'])
            noise.append({'molecule_id':mid,'geometry_source':geom,'condition':condition,
                'observed_noise_follows_rotation':rotated,'observed_same_lab_frame_noise':lab,
                'interpretation':'ROTATED_NOISE_SUPPORTED' if rotated['same_geometry_orbit_within_predeclared_coordinate_atol'] and not lab['same_geometry_orbit_within_predeclared_coordinate_atol'] else 'AMBIGUOUS_OR_NOT_ROTATED_NOISE',
                'comparison_uses_actual_native_program_input_coordinates':True})
        translated=groups.get((mid,geom,'xtb_singlepoint_origin_translation'),{}).get('translated')
        if clean.get('base') and translated:
            check=geometry_orbit(clean['base']['actual_program_coordinates_A'],translated['actual_program_coordinates_A'],np.eye(3).tolist(),translated['translation_A'],atol=config['rendered_coordinate_atol_A'])
            check['declared_translation_matches_frozen_config']=translated['translation_A']==config['origin_translation_A']
            check['diagnostic_binding_status']='VERIFIED' if check['declared_translation_matches_frozen_config'] else 'UNKNOWN_DECLARED_TRANSLATION_DIFFERS_FROM_FROZEN_CONFIG'
            translations.append(dict(check,molecule_id=mid,geometry_source=geom,base_case=clean['base']['case_id'],variant_case=translated['case_id']))
    return groups,orbits,noise,translations


def public_endpoint(value):
    result={key:item for key,item in value.items() if key not in {'fresh_parser_values','audit_vector','native_selection'}}
    result['native_selection']={key:item for key,item in value['native_selection'].items() if key!='entries'}
    return result


def failure_diagnostics(original,groups,orbits,config):
    rows=[]
    old_checks={(row['molecule_id'],row['geometry_source'],row['condition']):row for row in original['rotation_comparisons']}
    for failure in original['contradictions']:
        key=tuple(failure['group']);field=failure['field'];arms=groups.get(key,{})
        item={'original_failure':failure,'original_failure_retained':True,'original_predeclared_tolerance':config['vector_tolerances'][field],
            'original_check':old_checks[key]['vector_covariance'][field],'geometry_orbit':orbits.get(key),'field':field}
        try:
            need(set(arms)>={'base','rotated'},'SOURCE_ARMS_UNAVAILABLE')
            b,v=arms['base']['fields'][field],arms['rotated']['fields'][field]
            item.update(base_case=arms['base']['case_id'],variant_case=arms['rotated']['case_id'],base=public_endpoint(b),variant=public_endpoint(v))
            need(b['status']==v['status']=='EXACT_NATIVE_VALUES_AND_UNITS_VERIFIED','UNIQUE_NATIVE_TOKENS_VALUES_OR_UNITS_UNAVAILABLE')
            need(b['native_selection']['factor_from_frozen_parser']==v['native_selection']['factor_from_frozen_parser'],'UNIT_CONVERSION_MISMATCH')
            bv,vv=b['audit_vector'],v['audit_vector']
            fresh=frozen_math.covariance(bv['values'],vv['values'],bv['rounding_halfwidth'],vv['rounding_halfwidth'],config['vector_tolerances'][field])
            item['frozen_evaluator_check_on_retained_raw']=fresh
            item['original_frozen_check_reproduced']=fresh==item['original_check']
            components=propagate_native(b['native_selection']['entries'],v['native_selection']['entries'],
                b['native_selection']['factor_from_frozen_parser'],config['rotation_matrix'],b['fresh_parser_values'],v['fresh_parser_values'])
            item['componentwise_native_print_checks']=components
            orbit=orbits[key]['same_geometry_orbit_within_predeclared_coordinate_atol']
            all_native=all(row['native_centers_within_print_bound'] for row in components)
            all_parser=all(row['parser_float_centers_within_print_bound'] for row in components)
            input_binding=all(arms[arm]['input_validation']['all_actual_input_bindings_and_target_verified'] for arm in ('base','rotated'))
            item['both_actual_input_bindings_and_targets_verified']=input_binding
            item['all_components_within_native_print_propagation_only']=all_native and all_parser
            item['diagnosis_status']='UNKNOWN_ACTUAL_INPUT_BINDING_OR_TARGET_MISMATCH' if not input_binding else 'DIFFERENT_GEOMETRIES_NOT_A_COVARIANCE_COMPARISON' if not orbit else 'UNKNOWN_OLD_CHECK_NOT_REPRODUCED' if not item['original_frozen_check_reproduced'] else 'RESIDUAL_WITHIN_NATIVE_PRINT_PROPAGATION_ONLY_ORIGINAL_FAILURE_PRESERVED' if all_native and all_parser else 'RESIDUAL_NOT_EXPLAINED_BY_NATIVE_PRINT_PROPAGATION'
            item['still_unexplained_under_native_print_hypothesis']=not input_binding or not orbit or not item['original_frozen_check_reproduced'] or not(all_native and all_parser)
        except Exception as exc:item.update(diagnosis_status='UNKNOWN',still_unexplained_under_native_print_hypothesis=True,diagnostic_error=type(exc).__name__+': '+str(exc))
        rows.append(item)
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    option_names=('evaluation','run-closed','config','pilot-config','root-preflight','output')
    for name in option_names:p.add_argument('--'+name,type=pathlib.Path,required=True)
    a=p.parse_args();need(pathlib.Path(sys.modules['__main__'].__file__).absolute()==HERE/'run_v2.py' and pathlib.Path(sys.argv[0]).absolute()==HERE/'run_v2.py','ACTUAL_PRIMARY_ENTRY_REQUIRED')
    need(all(getattr(a,name.replace('-','_')).is_absolute() for name in option_names),'ALL_PRIMARY_PATH_OPTIONS_MUST_BE_ABSOLUTE')
    for module,name in ((diagnostic_precision,'precision.py'),(diagnostic_tokens,'tokens.py'),(diagnostic_raw_reader,'raw_reader.py')):
        need(pathlib.Path(module.__file__).absolute()==HERE/name,'ACTUAL_DIAGNOSTIC_HELPER_SOURCE_LOCATION_REQUIRED')
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import PY
    expected_argv=[PY,'-B',str(HERE/'run_v2.py')]
    for name in option_names:expected_argv.extend(['--'+name,str(getattr(a,name.replace('-','_')))])
    local_refs=[reference(HERE/name) for name in ('README.md','frozen_sources.json','precision.py','raw_reader.py','run_v2.py','test_v2.py','tokens.py')]
    bindings=json.loads((HERE/'frozen_sources.json').read_text())
    required=[reference(a.evaluation),reference(a.run_closed),reference(a.config),reference(a.pilot_config)]
    proof=runtime.require_startup(a.root_preflight,expected_scope_key=SCOPE_KEY,expected_scope_parameters=SCOPE,
        expected_execution_argv=expected_argv,expected_source=pathlib.Path(__file__).absolute(),expected_kind='analysis',
        required_references=required+local_refs+bindings['references'])
    need(proof['request']['pilot'] is False,'RETAINED72_DIAGNOSIS_IS_NOT_A_NEW_PILOT')
    started=time.monotonic()
    dispatch_stop_seconds=max(0,min(3000,proof['request']['wall_seconds']-600))
    os.environ.update({key:'1' for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')})
    frozen_sources();original=json.loads(require_pin(required[0]).read_text());closed=json.loads(require_pin(required[1]).read_text())
    config=load_audit(a.config);need(original['config']==required[2] and original['run']==required[1] and config['pilot_config']==required[3],'ORIGINAL_REPORT_RUN_AND_CONFIG_BINDINGS_REQUIRED')
    need(original['status']=='ACTUAL_FRAME_CONTRADICTION_REPORT_ROOT' and len(original['contradictions'])==15 and len(closed['results'])==72
        and all(row.get('reason')=='VECTOR_NOT_COVARIANT' for row in original['contradictions']),'EXACT_EXISTING72_AND15_FAILURE_SCOPE_REQUIRED')
    need(a.output.is_absolute() and '..' not in a.output.parts and ROOT/'artifacts' in a.output.parents and not a.output.exists()
        and not any(path.is_symlink() for path in (a.output,*a.output.parents)),'NEW_SEPARATE_DIAGNOSTIC_REPORT_ONLY')
    synthetic=run_synthetic_tests()
    preflight={'status':'NOT_RUN_SYNTHETIC4_DID_NOT_PASS','raw_container_bodies_read':0,'cases':[],'errors':[]}
    if synthetic['status']=='PASS':
        try:preflight=preflight_cases(closed['results'],original,config)
        except Exception as exc:preflight={'status':'FAIL_METADATA_ONLY_NO_RAW_READS','raw_container_bodies_read':0,'cases':[],
            'errors':[{'error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc()}]}
    by_group={}
    for failure in original['contradictions']:by_group.setdefault(tuple(failure['group']),set()).add(failure['field'])
    ready=synthetic['status']=='PASS' and preflight['status']=='PASS_METADATA_ONLY'
    dispatch_rows=preflight['cases'] if ready else []
    index=0;active={};cases=[];errors=[];samples=[];soft_stop=None
    # Fixed72, at most16 active read/parser tasks. Existing tasks drain naturally on STOP.
    if ready:
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=init_worker,initargs=(str(a.config),str(a.pilot_config))) as pool:
            while active or index<len(dispatch_rows):
                try:
                    row=memory_sample(list(pool._processes.values()))
                    if len(samples)<4096:samples.append(row)
                    if row['parent_plus_live_worker_RSS_bytes']>SCOPE['algorithm_rss_soft_cap_bytes'] or row['MemAvailable_bytes']<SCOPE['minimum_mem_available_bytes']:soft_stop='ACTUAL_MEMORY_SOFT_STOP_NEW_READS_ONLY'
                    if time.monotonic()-started>=dispatch_stop_seconds:soft_stop='FINITE_WALL_RESERVE_STOP_NEW_READS_ONLY'
                except Exception as exc:soft_stop='MEMORY_OBSERVATION_UNAVAILABLE:'+str(exc)
                while soft_stop is None and index<len(dispatch_rows) and len(active)<16:
                    row=dispatch_rows[index];ref=row['result'];key=tuple(row['group'])
                    try:active[pool.submit(read_case,ref,sorted(by_group.get(key,set())))]=ref;index+=1
                    except Exception as exc:
                        errors.append({'stage':'dispatch','result':ref,'error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc()})
                        soft_stop='PARSER_DISPATCH_FAILED_STOP_NEW_READS_ONLY';break
                if not active:break
                done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
                for future in done:
                    source=active.pop(future)
                    try:cases.append(future.result())
                    except Exception as exc:errors.append({'stage':'read_or_parse','result':source,'error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc()})
    try:groups,orbits,noise,translations=geometry_diagnostics(cases,config)
    except Exception as exc:
        errors.append({'stage':'geometry_diagnostics','error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc()})
        groups={};orbits={};noise=[];translations=[]
    failures=failure_diagnostics(original,groups,orbits,config)
    counts={}
    for row in failures:counts[row['field']]=counts.get(row['field'],0)+1
    all72=ready and len(cases)==72 and len({case['case_id'] for case in cases})==72 and not errors
    report={'schema':'PPRIME_RETAINED_NATIVE_PRECISION_DIAGNOSIS_V2',
        'status':'READ_ONLY_DIAGNOSIS_NOT_GATE_REVISION' if all72 else 'INCOMPLETE_READ_ONLY_DIAGNOSIS_NOT_GATE_REVISION',
        'runtime':{'job_id':os.environ['SLURM_JOB_ID'],'node':socket.gethostname().split('.')[0],'uid':os.getuid(),'allocated_cpus':16,
            'parser_worker_limit':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','memory_requested':False,'signals_sent':False},
        'startup_proof':reference(a.root_preflight),'original_evaluation':required[0],'original_run_closed':required[1],
        'config':required[2],'pilot_config':required[3],'frozen_sources':reference(HERE/'frozen_sources.json'),
        'new_sources':local_refs,'original_status':original['status'],
        'original_failures':original['contradictions'],'original_field_failure_counts':counts,
        'original_all_predeclared_vector_tolerances':config['vector_tolerances'],
        'frozen_parser_and_native_hook_sources':cases[0]['parser_sources'] if cases else None,
        'native_token_interval_rule':'DIAGNOSTIC ROUND-TO-NEAREST-DECIMAL HYPOTHESIS: exponent-derived last printed step/2; |R|epsilon_base+epsilon_variant; frozen parser field conversion; not a certified binary print-error bound.',
        'precision_arithmetic':'Exact Fraction from original Decimal token, exact binary64 R/factor/parser value; all interval propagation, residuals and comparisons exact; terminating decimal serialization by integer arithmetic.',
        'printed_halfwidth_is_diagnostic_hypothesis_only':True,
        'original_rounding_and_numeric_criteria_revised':False,'SCF_failure_or_cause_inferred':False,'automatic_PASS_or_QM_release':False,
        'synthetic_test_receipt':synthetic,'retained72_metadata_preflight':preflight,
        'raw_dispatch_gate':{'synthetic4_actual_passed':synthetic['status']=='PASS',
            'all72_metadata_actual_passed':preflight['status']=='PASS_METADATA_ONLY','parser_tasks_submitted':index},
        'all72_inputs_closed':all72,'actual_cases_read':len(cases),'case_read_errors':errors,
        'input_checks':[case['input_validation'] for case in sorted(cases,key=lambda item:item['case_id'])],
        'geometry_orbits':list(orbits.values()),'translation_orbits':translations,'noise_order_checks':noise,
        'observed_arms':sorted({case['arm'] for case in cases}),'permutation_control_status':'NOT_PRESENT_IN_THIS_RETAINED72_NO_INFERRED_MAPPING',
        'failures':failures,'soft_stop_new_reads':soft_stop,'actual_memory_samples':samples,
        'dispatch_stop_after_driver_seconds':dispatch_stop_seconds,'wall_reserve_seconds':600,
        'raw_reader_bounds':{'max_decompressed_body_bytes':config['max_raw_bytes_per_case'],
            'one_byte_over_cap_detection':True,'EOF_and_CRC_required_for_allowed_stream':True,
            'max_compressed_frame_bytes':config['max_raw_bytes_per_case']+(1<<20),
            'max_raw_metadata_bytes':config['max_result_bytes_per_case'],
            'max_concurrent_node_local_output_body_bytes':16*config['max_raw_bytes_per_case'],
            'these_are_not_total_python_RSS_bounds':True,'original_archive_unbundle_retained':True},
        'wall_seconds_observed':time.monotonic()-started,'self_user_seconds':resource.getrusage(resource.RUSAGE_SELF).ru_utime,
        'self_system_seconds':resource.getrusage(resource.RUSAGE_SELF).ru_stime,
        'actual_parent_allocated_core_seconds':None,'actual_terminal_sacct_cost_closure_required':True,
        'QM_or_UFF_calls':0,'raw_input_or_old_report_modified':False,'node_local_output_copies_only':True}
    raw=(json.dumps(report,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()
    need(len(raw)<=SCOPE['maximum_report_bytes'],'BOUNDED_DIAGNOSTIC_REPORT_LIMIT_REACHED_NO_TRUNCATION_OR_FAKE_PASS')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    print(json.dumps({'status':report['status'],'report':reference(a.output),'original_failure_count':15,'QM_calls':0,'all72_inputs_closed':report['all72_inputs_closed']}))
    return 0 if report['all72_inputs_closed'] else 3
if __name__=='__main__':sys.exit(main())
