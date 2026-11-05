"""Read only the fixed retained calls; evidence can remain UNKNOWN, never new PASS."""
from __future__ import annotations
import hashlib,importlib,json,math,os,pathlib,re,struct,sys
from . import contract as C
from . import frozen_scf as SCF
WORK={}


def need(ok,message):
    if not ok:raise ValueError(message)


def choose_cases(report,original,summary):
    need(report.get('schema')=='PPRIME_NATIVE72_READONLY_ALPHA_DIAGNOSIS_V2' and report['runtime']['job_id']=='1884773'
        and report['all72_inputs_closed'] is True and report['actual_cases_read']==72 and report['case_read_errors']==[]
        and report['synthetic_test_receipt']['status']=='PASS' and report['synthetic_test_receipt']['tests_run']==4,
        'ACTUAL1884773_CLOSED72_ORIGINAL_FOUR_FIXTURES_REQUIRED')
    need(report['original_failures']==original['contradictions']==C.EXPECTED_FAILURES
        and [row['original_failure'] for row in summary['per_original_failure_invariant_summary']]==C.EXPECTED_FAILURES
        and len(C.EXPECTED_FAILURES)==15 and summary['original15FAIL_preserved'] is True,'EXACT_ORIGINAL15_FAILURE_AUTHORITY_REQUIRED')
    links={}
    for orbit in report['geometry_orbits']:
        for arm,key in (('base','base_case'),('rotated','variant_case')):
            group=tuple(orbit['group']);identity=(*group,arm);case_id=orbit[key]
            need(identity not in links,'UNIQUE_RECORDED_GROUP_ARM_REQUIRED');links[identity]=case_id
    selected=[]
    for mid,geometry in C.PM7_GROUPS:
        for arm in ('base','rotated'):selected.append((mid,geometry,'pm7_B',arm))
    for mid,geometry in C.NOISY_GROUPS:
        for condition in ('xtb_perturbed_gradient','xtb_singlepoint_noisy_companion'):
            for arm in ('base','rotated'):selected.append((mid,geometry,condition,arm))
    checks={row['case_id']:row for row in report['input_checks']}
    need(len(selected)==len(set(selected))==24 and len(checks)==len(report['input_checks'])==72,'EXACT_FIXED24_CASES_AND72_BINDINGS_REQUIRED')
    rows=[]
    for identity in selected:
        need(identity in links,'FIXED_RETAINED_CASE_NOT_IDENTIFIED');case_id=links[identity];check=checks[case_id]
        need(check['all_actual_input_bindings_and_target_verified'] is True,'ORIGINAL_ACTUAL_INPUT_BINDING_REQUIRED')
        rows.append({'case_id':case_id,'identity':list(identity),'input_check':check})
    need(len({row['case_id'] for row in rows})==24,'NO_DUPLICATED_RETAINED_CALLS_ALLOWED')
    return rows


def terminal_evidence(calc_type,files):
    texts={item['name']:item['data'] for item in files}
    name='process.out' if calc_type.startswith('xtb_') else ('input.out' if 'input.out' in texts else 'process.out')
    data=texts.get(name)
    if data is None:return {'status':'UNKNOWN_OUTPUT_FILE_ABSENT','normal_marker':None,'failure_markers':[],'cause_proven':False}
    text=data.decode('utf-8',errors='replace');sha=hashlib.sha256(data).hexdigest();xtb=calc_type.startswith('xtb_')
    normal='normal termination of xtb' if xtb else 'JOB ENDED NORMALLY'
    failure=SCF.XTB_FAIL if xtb else SCF.MOPAC_FAIL;events=[];normal_count=bad_count=0
    candidates=[];versions=[];energies=[]
    energy=re.compile(r'\bTOTAL ENERGY\s+('+r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?'+r')\s+Eh') if xtb else re.compile(r'FINAL HEAT OF FORMATION\s*=\s*('+r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?'+r')\s*KCAL')
    for number,line in enumerate(text.splitlines(),1):
        good=normal in (line.lower() if xtb else line);bad=bool(failure.search(line))
        entry={'file':name,'line_1_based':number,'file_sha256':sha,'text':line[:C.SCOPE['maximum_line_characters']],
            'source_line_characters':len(line),'line_shortened':len(line)>C.SCOPE['maximum_line_characters']}
        normal_count+=good;bad_count+=bad
        if good or bad:events.append(dict(entry,normal_termination_marker=good,explicit_electronic_failure_marker=bad))
        if re.search(r'MOPAC v\d|xtb version',line,re.I):versions.append(entry)
        if re.search(r'CARTESIAN COORDINATES|final structure|\$coord|ATOM_X_OPT',line,re.I):candidates.append(entry)
        hit=energy.search(line)
        if hit:energies.append(dict(entry,token=hit[1],field='energy_Eh' if xtb else 'heat_of_formation_kcal_mol',
            units='Eh' if xtb else 'kcal/mol',interpretation='NATIVE_TOKEN_EVIDENCE_ONLY_NO_NEW_ENERGY_TOLERANCE'))
    cap=C.SCOPE['maximum_marker_evidence_lines']
    return {'status':'CONFLICTING_TERMINAL_MARKERS' if normal_count and bad_count else 'EXPLICIT_ELECTRONIC_FAILURE_MARKER_OBSERVED' if bad_count else
        'NORMAL_TERMINATION_MARKER_OBSERVED' if normal_count else 'UNKNOWN_NO_EXPLICIT_TERMINATION_MARKER',
        'source_file':name,'source_file_sha256':sha,'utf8_replacement_characters':text.count('\ufffd'),
        'normal_marker_literal':normal,'normal_marker_count':normal_count,'electronic_failure_marker_count':bad_count,
        'events':events[:cap],'events_not_listed':max(0,len(events)-cap),'version_lines':versions[:cap],
        'energy_tokens':energies[:cap],'energy_tokens_not_listed':max(0,len(energies)-cap),
        'unparsed_coordinate_candidate_lines':candidates[:cap],'coordinate_candidates_not_listed':max(0,len(candidates)-cap),
        'unparsed_coordinate_lines_certify_frame':False,'normal_termination_implies_SCF_convergence':False,'cause_proven':False}


def helpers():
    sys.path.insert(0,str(C.OLD))
    modules={name:importlib.import_module(name) for name in ('relocation','raw_reader','read_outputs_v1','math_v1')}
    for name,module in modules.items():need(pathlib.Path(module.__file__).absolute()==C.OLD/(name+'.py'),'EXACT_FROZEN_HELPER_LOCATION_REQUIRED')
    return modules


def init_worker(plan):
    modules=helpers();resolver=modules['relocation'].activate(plan['relocation_map_reference']['path'])
    pilot=resolver.json(modules['relocation'].REPO+'/configs/data_v1/pprime/pilot_v1.json')
    engine,contract,protocol=modules['relocation'].metadata_engine(pilot)
    config=resolver.json(modules['relocation'].REPO+'/configs/data_v1/pprime/vector_frame_audit_root_v1.json')
    WORK.update(modules=modules,resolver=resolver,archive=engine.OUTPUT_ARCHIVE,protocol=protocol,config=config)


def frame_info(calc_type,files,symbols,coordinates,modules,config):
    source={row['name']:row['data'] for row in files};reader=modules['read_outputs_v1'];mathmod=modules['math_v1']
    if calc_type=='pm7_B' and 'input.aux' in source:
        aux=reader.aux_arrays(source['input.aux'].decode('utf-8',errors='strict'),len(symbols))
        xyz=aux.get('ATOM_X_OPT:ANGSTROMS');elements=aux.get('ATOM_EL',{}).get('values')
        if xyz is None:return {'status':'UNKNOWN_NO_OWN_AUX_COORDINATES','companion_frame_borrowed':False}
        if elements is None or [value.capitalize() for value in elements]!=symbols:
            return {'status':'UNKNOWN_OWN_AUX_ATOM_ORDER_NOT_PROVEN','companion_frame_borrowed':False}
        result=mathmod.output_frame(coordinates,xyz['values'],config['coordinate_atol_A']['mopac'])
        return dict(result,own_output_artifact='input.aux:ATOM_X_OPT:ANGSTROMS',own_file_sha256=hashlib.sha256(source['input.aux']).hexdigest(),
            atom_order_matches=True,frozen_coordinate_atol_A=config['coordinate_atol_A']['mopac'],
            companion_frame_borrowed=False,physical_cause_proven=False)
    if calc_type.startswith('xtb_') and 'gradient' in source:
        value=reader.xtb_gradient(source['gradient'].decode('utf-8',errors='strict'),symbols)
        fits={name:mathmod.output_frame(coordinates,xyz,config['coordinate_atol_A']['xtb'])
            for name,xyz in value['coordinate_conversion_hypotheses_A'].items()}
        return {'status':'OWN_GRADIENT_COORDINATES_FIT_WITH_UNCHANGED_CONVERSION_HYPOTHESES',
            'own_output_artifact':'gradient:$grad coordinates','own_file_sha256':hashlib.sha256(source['gradient']).hexdigest(),
            'atom_order_matches':value['symbols']==symbols,'fits':fits,'frozen_coordinate_atol_A':config['coordinate_atol_A']['xtb'],
            'force_label_conversion_changed':False,'companion_frame_borrowed':False,'physical_cause_proven':False}
    return {'status':'UNKNOWN_NO_IDENTIFIED_OWN_OUTPUT_COORDINATE_ARTIFACT','companion_frame_borrowed':False,
        'same_geometry_companion_is_not_own_frame_evidence':True,'physical_cause_proven':False}


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
    need(all(re.fullmatch(WORK['modules']['math_v1'].FLOAT,value) for _,row in rows for value in row),'EXACT_INPUT_COORDINATE_TOKEN_REQUIRED')
    need(all(math.isfinite(value) for row in coords for value in row),'FINITE_ACTUAL_INPUT_COORDINATES_REQUIRED')
    return coords


def frame(stat):return (stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_uid)


def read_pin(pin,limit,kind):
    resolver=WORK['resolver'];row=resolver.row(pin['path']);need(row['kind']==kind,'EXACT_MAPPED_BODY_KIND_REQUIRED')
    path=resolver.require(pin,full_hash=False)
    need(0<pin['bytes']<=limit,'BOUNDED_PIN_BYTES_REQUIRED')
    with path.open('rb') as stream:
        before=os.fstat(stream.fileno());need(before.st_uid==1264 and before.st_size==pin['bytes'],'OWNED_EXACT_BODY_BYTES_REQUIRED')
        data=stream.read(limit+1);after=os.fstat(stream.fileno())
    need(frame(before)==frame(after)==frame(path.stat()) and len(data)==pin['bytes'] and hashlib.sha256(data).hexdigest()==pin['sha256'],
        'BOUNDED_BODY_SHA_FSTAT_OR_LINK_CHANGED')
    return data


def read_staging(data):
    def hook(value):
        if set(value)=={'__pprime_nonfinite_float64__'}:return struct.unpack('<d',bytes.fromhex(value['__pprime_nonfinite_float64__']))[0]
        return value
    return json.loads(data,object_hook=hook)


def diagnose(item):
    resolver=WORK['resolver'];check=item['input_check'];record=read_staging(read_pin(check['result'],C.SCOPE['maximum_result_bytes_per_call'],'pinned_case_result_metadata'))
    case=record['case'];identity=[case['molecule_id'],case['geometry_source'],case['condition'],case['arm']]
    need(case['case_id']==record['case_id']==item['case_id'] and identity==item['identity'] and record['QM_call_attempted'] is True,'EXACT_SELECTED_RETAINED_CALL_IDENTITY_REQUIRED')
    symbols=case['symbols'];need(0<len(symbols)<=80,'ORIGINAL_ATOM_CAP_REQUIRED');raw=record['raw_reference']
    need(raw['output_retained'] is True and raw['raw_call_durable'] is True and raw['input_bodies_saved'] is False
        and raw['calc_type']==case['calc_type'] and raw['raw_sha256']==check['raw_call_sha256'],'DURABLE_ORIGINAL_OUTPUT_ONLY_RAW_REFERENCE_REQUIRED')
    row=resolver.row(raw['container_path']);need(row['kind']=='raw_sqlite_locator_no_main_SHA' and row['origin'].get('sha256') is None,'NO_INVENTED_MAIN_DATABASE_SHA')
    path=resolver.path(raw['container_path']);expected=check['raw_container']['actual_alpha_reference']
    need(expected['path']==str(path) and expected['bytes']==row['origin']['bytes']<=C.SCOPE['maximum_database_locator_bytes'],'EXACT_PRIOR_ALPHA_DATABASE_LOCATOR_REQUIRED')
    before=path.stat();need(before.st_uid==1264,'OWNED_RETAINED_DATABASE_REQUIRED');digest=hashlib.sha256();total=0
    with path.open('rb') as stream:
        opened=os.fstat(stream.fileno());need(frame(opened)==frame(before),'EXACT_DATABASE_OPEN_IDENTITY_REQUIRED')
        while total<=expected['bytes']:
            block=stream.read(min(1<<20,expected['bytes']+1-total))
            if not block:break
            total+=len(block);digest.update(block)
        ended=os.fstat(stream.fileno())
    need(total==expected['bytes'] and frame(opened)==frame(ended)==frame(path.stat()),'BOUNDED_DATABASE_SHA_FSTAT_OR_BYTES_CHANGED')
    observed={'path':str(path),'bytes':total,'sha256':digest.hexdigest()}
    need(observed==expected,'PRIOR_ACTUAL_ALPHA_DATABASE_SHA_CHANGED')
    reader=WORK['modules']['raw_reader'].BoundedRawReader(path,WORK['archive'],C.SCOPE['maximum_raw_bytes_per_call'],C.SCOPE['maximum_result_bytes_per_call'])
    try:retained=reader.get(raw['record_id'],raw['calc_type'],raw['execution_id'],raw['raw_sha256'],raw['raw_bytes'])
    finally:reader.close()
    need(frame(before)==frame(path.stat()),'READONLY_DATABASE_CHANGED_DURING_SNAPSHOT')
    files=retained['output_files']
    need(all(pathlib.PurePosixPath(row['name']).name==row['name'] for row in files),'ONLY_SAFE_NATIVE_OUTPUT_MEMBER_NAMES')
    input_name='input.mop' if case['calc_type']=='pm7_B' else 'input.xyz'
    inputs=[row for row in record['actual_postcall_input_references'] if pathlib.Path(row['path']).name==input_name]
    need(len(inputs)==1,'ONE_ACTUAL_PROGRAM_INPUT_REQUIRED');pin=inputs[0]
    need(any(all(row[key]==pin[key] for key in ('path','bytes','sha256')) for row in check['inputs']),'SAME_PRIOR_ACTUAL_INPUT_PIN_REQUIRED')
    coordinates=actual_input(read_pin(pin,C.SCOPE['maximum_actual_input_bytes_per_call'],'actual_input_stat_locator'),input_name,symbols)
    scf=SCF.extract_scf(case['calc_type'],files);stored=record.get('parsed_wp5_result',{});provenance=stored.get('provenance',{})
    cap=C.SCOPE['maximum_marker_evidence_lines'];stage_count=len(scf['stages']);event_count=len(scf['evidence'])
    bounded=dict(scf,stages=scf['stages'][:cap],evidence=scf['evidence'][:cap],stages_not_listed=max(0,stage_count-cap),evidence_not_listed=max(0,event_count-cap))
    try:output_frame=frame_info(case['calc_type'],files,symbols,coordinates,WORK['modules'],WORK['config'])
    except Exception as exc:output_frame={'status':'UNKNOWN_OWN_OUTPUT_COORDINATE_PARSE_OR_FIT','error':type(exc).__name__+': '+str(exc)[:1600],
        'companion_frame_borrowed':False,'physical_cause_proven':False}
    terminal=terminal_evidence(case['calc_type'],files)
    return {'case_id':item['case_id'],'identity':identity,'actual_worker_pid':os.getpid(),
        'result_reference':check['result'],'raw_SQLite_key':{key:raw[key] for key in ('record_id','calc_type','execution_id')},
        'raw_call_sha256':raw['raw_sha256'],'raw_call_bytes':raw['raw_bytes'],'actual_database_reference':observed,
        'Main_database_whole_SHA_claimed':False,'archive_manifest_and_member_SHA_verified':True,'gzip_EOF_CRC_verified':True,
        'output_members':[{'name':row['name'],'bytes':len(row['data']),'sha256':row['sha256']} for row in files],
        'actual_program_input_reference':{key:pin[key] for key in ('path','bytes','sha256')},'own_output_frame':output_frame,
        'frozen_SCF_metadata':bounded,'SCF_stage_count':stage_count,'SCF_evidence_count':event_count,
        'stored_native_result':{key:stored.get(key) for key in ('status','source_status','scope_status','failure_code','returncode','argv','keywords','arguments','software_version_lines','diagnostic_lines')},
        'stored_SCF_provenance':{key:provenance.get(key) for key in ('software_version_id','converged','scf_iterations')},
        'fresh_SCF_matches_recorded':scf['converged']==provenance.get('converged') and scf['scf_iterations']==provenance.get('scf_iterations'),
        'termination':terminal,'causal_status':'UNKNOWN_NO_UNIQUE_CAUSAL_EXPLANATION',
        'explicit_SCF_failure_observed':scf['converged'] is False,'SCF_converged_does_not_certify_covariance':True,
        'original15FAIL_retained':True,'original_tolerances_changed':False,'physical_cause_proven':False,'full_or2000_release':'HOLD'}
