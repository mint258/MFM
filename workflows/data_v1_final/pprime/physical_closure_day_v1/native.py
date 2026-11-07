"""384 retained lossless observations and pinned official SOURCE facts only."""
import collections,concurrent.futures as cf,hashlib,pathlib,re
from workflows.data_v1_final.export.native_frame_summary32_v1.reader import decode_evidence
from . import contract as C,io as I

# These are source locators, not a new parser/physical formula or binary-build assertion.
SOURCE_WITNESSES=(
 ('mopac','src/output/to_screen.F90',r'DIP_VEC:DEBYE|GRADIENTS:KCAL/MOL/ANGSTROM|ATOM_X_OPT:ANGSTROMS','AUX_explicit_unit_labels'),
 ('mopac','src/input/readmo.F90',r'loc\(|lopt\(|numat','Cartesian_variable_order_source'),
 ('mopac','src/output/writmo.F90',r'GRADIENT|grad\(|loc\(','indexed_gradient_print_source'),
 ('mopac','src/properties/dipole.F90',r'TOTAL ATOMIC CHARGES|coord\(|dipvec|chargd|center','dipole_charge_coordinate_and_charged_origin_source'),
 ('mopac','src/output/denrot.F90',r'coord\(|SIGMA|isp\(|coe','pair_local_channel_source'),
 ('xtb','src/type/molecule.f90',r'Cartesian coordinates in bohr','molecule_internal_coordinate_unit'),
 ('xtb','src/io/reader.f90',r'read_structure|struc%xyz|mol%xyz','structure_to_molecule_coordinate_transfer'),
 ('xtb','src/prog/main.F90',r'readMolecule|do_cma_trafo|axis3','conditional_origin_axes_path_not_actual_branch_proof'),
 ('xtb','src/setparam.f90',r'do_cma_trafo','source_CMA_default_without_runtime_override_claim'),
 ('xtb','src/aespot.f90',r'subroutine molmom|dipm|q\(i\).*xyz|autod|quadrupole|full:','multipole_definition_and_column_units'),
 ('xtb','src/main/json.F90',r'dipole / a.u.|sccres%dipole|partial charges|atomic dipole','JSON_moment_scope_writer'),
 ('xtb','src/io/writer/turbomole.f90',r'dE/dxyz|gradient\(1,i\)|xyz\(1,i\)|mol%xyz','same_index_coordinate_and_derivative_writer'),
 ('xtb','src/mctc/convert.f90',r'autoaa|aatoau|autod|autoev','source_unit_constants'),
 ('xtb','src/scc_core.f90',r'charge|dipole|molmom|q\(','electronic_charge_population_context'),
 ('xtb','subprojects/mctc-lib.wrap',r'url|revision','dependency_revision_is_not_binary_build_proof'))

def official(catalog):
    rows={(r['program'],r['source_path']):r for r in catalog['files']};facts=[]
    C.need(len(rows)==len(catalog['files']) and set(rows)=={(x[0],x[1]) for x in SOURCE_WITNESSES},'EXACT15_PRIMARY_SOURCE_FILES_NOT_ARBITRARY_CODE')
    for program,path,pattern,role in SOURCE_WITNESSES:
        row=rows[(program,path)];ref=C.P.triple(row['reference']);p=pathlib.Path(ref['path'])
        C.need(C.Q.pin(p)==ref and p.is_relative_to(C.ROOT/'control/pprime_physical_closure_official_sources_v1'),'EXACT_OFFICIAL_SOURCE_DEPLOYED_BYTES')
        data=p.read_bytes();blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        C.need(blob==row['git_blob_sha1'],'OFFICIAL_FULL_SOURCE_GIT_BLOB_MATCH')
        text=data.decode('utf-8','strict');lines=text.splitlines();hits=[]
        for i,line in enumerate(lines):
            if re.search(pattern,line,re.I):hits.append({'line':i+1,'text':line,'context':lines[max(0,i-1):min(len(lines),i+2)]})
        facts.append({'program':program,'source_path':path,'source_reference':ref,'official_url':row['official_url'],
            'commit':row['commit'],'role':role,'matching_source_lines':hits[:32],'total_matching_lines':len(hits),
            'source_fact_state':'LOCATED_FOR_EXACT_DEFINITION_REVIEW' if hits else 'UNKNOWN_EXPECTED_SOURCE_WITNESS_NOT_LOCATED',
            'binary_rebuild_or_conformance_claimed':False})
    return {'schema':'PPRIME_PHYSICAL_OFFICIAL_SOURCE_FACTS_V1','source_facts':facts,
        'xtb_actual_print_prefix':'edcfbbe','prefix_resolution_commit':catalog['xtb_observed_prefix_resolved_commit'],
        'mctc_lib_wrap_revision_head_is_not_frozen_build_dependency':True,
        'official_definition_and_actual_control_must_be_reviewed_together':True,
        'Root_units_or_scientific_acceptance_signed_here':False}

def frame(value,config,math):
    g=value['geometry'];calc=value['key']['calc_type'];input=value['input_binding'];raw=g.get('original_reader_output')
    if raw is None:return {'state':'UNKNOWN_NO_INDEPENDENT_NATIVE_COORDINATE_BLOCK','original_state':g['state'],
        'input_binding_is_not_own_property_axis_proof':True}
    if calc.startswith('pm7'):
        output=raw.get('ATOM_X_OPT:ANGSTROMS',{}).get('values');elements=raw.get('ATOM_EL',{}).get('values')
        atoms=elements is not None and [str(z).capitalize() for z in elements]==input['symbols'];tol=config['coordinate_atol_A']['mopac']
    else:
        output=raw.get('coordinates_A');atoms=raw.get('symbols')==input['symbols'];tol=config['coordinate_atol_A']['xtb']
    if output is None:return {'state':'UNKNOWN_ORIGINAL_OUTPUT_COORDINATE_FIELD_MISSING','original_state':g['state']}
    primary=math.output_frame(input['program_coordinates_A'],output,tol);check=primary;hypotheses={};selected=None
    if not calc.startswith('pm7'):
        hypotheses={name:math.output_frame(input['program_coordinates_A'],coords,tol)
            for name,coords in raw.get('coordinate_conversion_hypotheses_A',{}).items()}
        matching=[name for name,value in hypotheses.items() if value['supports_input_axes']]
        selected=matching[0] if matching else 'WP5_parser_0.529177210903'
        check=hypotheses.get(selected,primary)
    return {'state':'PASS_ORIGINAL_COORDINATE_AND_ATOM_ORDER_GATE' if check['supports_input_axes'] and atoms else 'FAIL_ORIGINAL_COORDINATE_OR_ATOM_ORDER_GATE',
        'original_output_frame_check':check,'original_primary_WP5_conversion_check':primary,
        'original_predeclared_conversion_hypotheses':hypotheses,'original_measurement_selection_rule_result':selected,
        'no_label_or_force_conversion_constant_changed':True,'conversion_choice_not_physical_truth_by_fit':True,
        'atom_order_matches':atoms,'original_coordinate_atol_A':tol,
        'printed_float64_exact_is_not_the_tolerance_gate':g.get('float64_coordinates_exactly_equal'),
        'property_axes_not_inferred_from_coordinate_agreement_alone':True}

def run(plan,authority,config,math,store,out,check):
    roots=[C.ROOT/'artifacts/labels/source_status_v1/native_frame_summary32_v1',C.ROOT/'artifacts/labels/source_status_v1/native_body_frame32_v1'];items=authority['native_keys']
    def one(row):
        check();ref=row['scientific_DATA_reference'];b=I.body(ref,roots,plan['data_references'],32<<20);v=decode_evidence(b)
        C.need(v['schema']=='NATIVE_FRAME32_PER_KEY_SUMMARY_DATA_V1' and v['position']==row['position']
            and v['key']['calc_type']==row['calc_type'] and v['original_parser_and_projection_exact_to_B'] is True,'SAME_3953_LOSSLESS_KEY_AND_PARSER')
        C.need(v['retained_B_evidence_reference']==row['B_evidence_reference'],'SUMMARY_EXACT_ORIGINAL_B_PRODUCER_REFERENCE')
        prior=decode_evidence(I.body(row['B_evidence_reference'],roots,plan['data_references'],32<<20))
        C.need(prior['key']==v['key'] and prior['D1_jointly_frozen'] is False and prior['new_QM_calls']==prior['new_UFF_calls']==0,'SAME_B_KEY_SOFTWARE_AND_RAW_METADATA_NOT_NATIVE_RERUN')
        geometry=frame(v,config,math);q=v['r674'];tensor=None
        if v['key']['calc_type']=='xtb_singlepoint':
            observed=q.get('original_vector_audit_result')
            tensor=math.tensor_checks(observed['six_components_au'],observed['rounding_halfwidth_au']) if observed else {'state':'UNKNOWN_ORIGINAL_QUADRUPOLE_BLOCK_MISSING'}
        fields=[{k:f.get(k) for k in ('field_key','registry_id','source_path','component','status','unit','geometry_context')} for f in v['related_registry_fields']]
        parsed=v['fresh_original_parser_values'];version={k:parsed[k] for k in ('version','method','normal_end','mopac_version') if k in parsed}
        aux=v['geometry'].get('original_reader_output') or {}
        explicit_headers=[name for name in aux if any(unit in name for unit in (':DEBYE',':ANGSTROMS',':KCAL/MOL/ANGSTROM',':EV',':KCAL/MOL'))]
        detail={'schema':'PPRIME_PHYSICAL_RETAINED_NATIVE_KEY_V1','position':row['position'],'key':v['key'],'source_reference':ref,
            'native_parser_and_input_binding_exact_already_observed':True,'own_coordinate_gate':geometry,'registry_declared_fields_not_source_proof':fields,
            'native_version_fields_actually_present':version,'r73_state':v['r73']['state'],
            'original_raw_metadata_reference':row['B_evidence_reference'],
            'actual_original_software':prior['original_raw_metadata'].get('software'),
            'actual_original_keywords':prior['original_raw_metadata'].get('keywords'),
            'actual_original_keywordSHA':prior['original_raw_metadata'].get('keywordSHA'),
            'actual_original_output_file_manifest':prior['original_raw_metadata'].get('output_file_manifest'),
            'native_explicit_unit_header_labels_observed':explicit_headers,
            'unit_header_labels_are_separate_from_registry_declared_units':True,
            'original_B_input_render_seed_and_base_geometry_binding':prior['native_evidence']['input_binding'],
            'r73_channel_onsite_duplicate_and_ordinal_domain_preserved':True,'r674_original_evidence':q,'r674_original_trace_gate':tensor,
            'unit_sign_axis_accepted_false_in_old_source_was_fixed_pending_flag_not_numeric_FAIL':True,
            'definition_review_state':'SEE_PINNED_OFFICIAL_SOURCE_AND_NATIVE_TOKENS_NO_AUTOMATIC_SIGNOFF',
            'old_return_states_masks_tolerances_or_values_changed':False}
        target=store.json(out/('native_%04d.DATA.json'%row['position']),detail)
        return {'position':row['position'],'condition':row['calc_type'],'DATA_reference':target,
            'coordinate_gate_state':geometry['state'],'r73_state':v['r73']['state'],
            'r674_trace_state':'PASS_ORIGINAL_PRINTING_BOUND' if tensor and tensor.get('trace_within_rounding') is True else
                'FAIL_ORIGINAL_PRINTING_BOUND' if tensor and tensor.get('trace_within_rounding') is False else 'NOT_APPLICABLE_OR_UNKNOWN'}
    reports=[]
    # Executor.map buffers references only; exactly384 existing small evidence files.
    with cf.ThreadPoolExecutor(max_workers=16) as pool:
        pending={};iterator=iter(items)
        while True:
            while len(pending)<32:
                try:row=next(iterator)
                except StopIteration:break
                check();pending[pool.submit(one,row)]=row['position']
            if not pending:break
            done,_=cf.wait(pending,return_when=cf.FIRST_COMPLETED)
            for future in done:reports.append(future.result());del pending[future]
    C.need(len(reports)==384 and {r['position'] for r in reports}==set(range(384)),'EXACT384_NO_MISSING_OR_DUPLICATE')
    counts=[]
    for condition in C.N.CALCS:
        group=[r for r in reports if r['condition']==condition];C.need(len(group)==32,'EXACT32_NATIVE_PER_CONDITION')
        counts.append({'condition':condition,'records':32,'coordinate_gate_counts':dict(collections.Counter(r['coordinate_gate_state'] for r in group)),
            'r73_states':dict(collections.Counter(r['r73_state'] for r in group)),
            'r674_trace_counts':dict(collections.Counter(r['r674_trace_state'] for r in group))})
    return {'completed_keys':384,'per_condition':counts,'per_key_DATA_references':sorted(reports,key=lambda x:x['position']),
        'full20k_or_all_population_native_audit':False,'D1_jointly_frozen':False}
