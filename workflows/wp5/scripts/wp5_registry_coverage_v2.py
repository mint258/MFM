#!/usr/bin/env python3
"""Complete active registry source catalogue and per-task extraction/encoding audit.

This describes implementation coverage separately from native values. A NULL or
missing value is never evidence that a parser is implemented, nor a fabricated
zero. Historical missing raw is an approved exception, not a regression PASS.
V2 corrects source evidence and existing task applicability only: real MOPAC
hydrogen-bond summary energies, B-only sparse Mulliken getter, and native xTB
Fukui table. Parser numerical values and registry cells are not modified.
No calculations, source changes, or archive mutation.
"""
from __future__ import annotations
import argparse,ast,collections,hashlib,json,math,re
from pathlib import Path
TASKS={'pm7_B','pm7_anion','pm7_cation','pm7_water','pm7_octanol',
 'xtb_singlepoint','xtb_vipea','xtb_vfukui','xtb_ALPB_water',
 'xtb_ALPB_octanol','xtb_fod','xtb_perturbed_gradient'}
DELETED=('polar_blocks','static_polar_block','static_finite_field_tensors')
MISSING=object()
FLOAT_TOKEN=r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[DEde][+-]?\d+)?'
B_ONLY_MULLIKEN_FIELDS={
 'mulliken_overlap_population_pairs',
 'mulliken_reconstruction_charge_max_error_e',
 'mulliken_overlap_qc'}
HYDROGEN_NUMERIC_PATTERNS=[
 r'\bHYDROGEN BOND(?:ING)? ENERGY\s*=\s*('+FLOAT_TOKEN+r')(?=\s|$)',
 r'\bTotal contribution from hydrogen bonds:\s*('+FLOAT_TOKEN+
 r')\s+disp\.\s*:\s*('+FLOAT_TOKEN+r')\s+Tot\s*:\s*('+FLOAT_TOKEN+r')\s+kcal/mol\b']
OUT_MARKERS={
 'heat_of_formation_kcal_mol':'FINAL HEAT OF FORMATION',
 'gradient_norm_kcal_mol_A':'GRADIENT NORM','total_energy_eV':'TOTAL ENERGY',
 'electronic_energy_eV':'ELECTRONIC ENERGY','core_core_repulsion_eV':'CORE-CORE REPULSION',
 'dispersion_energy_kcal_mol':'DISPERSION ENERGY','hydrogen_bond_energy_kcal_mol':'HYDROGEN BOND ENERGY',
 'dielectric_energy_eV':'DIELECTRIC ENERGY','cosmo_area_A2':'COSMO AREA',
 'cosmo_volume_A3':'COSMO VOLUME','spin_Sz':'(SZ)','spin_S2':'(S**2)',
 'net_charges_e':'NET ATOMIC CHARGES','mulliken_charges_e':'MULLIKEN POPULATIONS AND CHARGES',
 'sigma_pi_entries':'SIGMA','enpart_one_center_eV':'ATOM      E-E',
 'enpart_pairs_eV':'TWO-CENTER TERMS','super_heavy_atom_rows':'Dn(r)'}
AUX_KEYS={'dipole_Debye':['DIP_VEC:DEBYE'],'gradient_kcal_mol_A':['GRADIENTS:KCAL/MOL/ANGSTROM'],
 'valences':['BOND_ORDERS'],'bond_orders':['BOND_ORDERS'],
 'atomic_shell_population_e':['AO_CHARGES','AO_ATOMINDEX','ATOM_SYMTYPE'],
 'mulliken_overlap_population_pairs':['OVERLAP_MATRIX','EIGENVECTORS','MOLECULAR_ORBITAL_OCCUPANCIES','AO_ATOMINDEX'],
 'mulliken_reconstruction_charge_max_error_e':['OVERLAP_MATRIX','EIGENVECTORS','MOLECULAR_ORBITAL_OCCUPANCIES','AO_ATOMINDEX'],
 'mulliken_overlap_qc':['OVERLAP_MATRIX','EIGENVECTORS','MOLECULAR_ORBITAL_OCCUPANCIES','AO_ATOMINDEX']}
DETAIL_KEYS={'B_base_success','Q01_gradient_norm_kcal_mol_A','Q02_delta_HOF_kcal_mol',
 'archive','archived_files','argv','arguments','aux_archived','aux_bytes','conformer_id',
 'diagnostic_lines','elapsed_seconds','failure_code','failure_reason','family','heavy_atoms',
 'job_id','keywords','missing_properties','molecule_id','native_atom_order_sha256',
 'native_coordinates_sha256','natoms','qc_codes','qm_child_cpu_seconds','raw_total_bytes',
 'record_id','returncode','scratch_bytes_removed','size_stratum','software_version_lines',
 'source_payload_sha256','split','status','stdout_bytes','stored_HOF_kcal_mol','task',
 'worker_pid','xyz_roundtrip_max_error_A','qm_termination'}
XTB_SOURCES={
 'energy_Eh':('process.out','TOTAL ENERGY'),'dipole_Debye':('xtbout.json|process.out','dipole'),
 'charges_e':('xtbout.json','partial charges'),'D4_atomic_C6_au':('process.out','C6AA'),
 'D4_atomic_alpha_bohr3':('process.out','alpha(0)'),
 'molecular_quadrupole_traceless_au':('process.out','molecular quadrupole (traceless)'),
 'wiberg_pairs':('wbo',None),'homo_eV':('xtbout.json|process.out','HOMO'),
 'lumo_eV':('xtbout.json|process.out','LUMO'),'IP_eV':('process.out','delta SCC IP'),
 'EA_eV':('process.out','delta SCC EA'),'Gsolv_Eh':('process.out','Gsolv'),
 'NFOD_e':('process.out','NFOD'),'FOD_atom_e':('fod',None),
 'gradient_Eh_bohr':('gradient',None),'forces_eV_A':('gradient',None),
 'method':('xtbout.json|process.out','method'),'version':('xtbout.json|process.out','version'),
 'warnings':('process.out',None),'fukui':('process.out','Fukui functions:')}
def active(entry):
    return entry['task'] in TASKS and not any(s in entry['source_path'].lower() for s in DELETED)
def entries(path):
    raw=json.loads(Path(path).read_text());all_entries=raw['entries']
    chosen=[e for e in all_entries if active(e)]
    ids=[e['registry_id'] for e in chosen]
    if len(ids)!=len(set(ids)):raise ValueError('REGISTRY_IDS_NOT_UNIQUE')
    return chosen
def lookup(detail,path):
    parts=str(path).strip('/').replace('/','.').split('.')
    if parts and parts[0] in ('detail','details'):parts=parts[1:]
    value=detail
    for part in parts:
        if not isinstance(value,dict) or part not in value:return MISSING
        value=value[part]
    return value
def source_spec(entry):
    path=entry['source_path'];task=entry['task']
    if path.startswith('detail.'):
        key=path.split('.')[1]
        return {'producer':'native_engine_and_runtime_context','artifacts':[],'markers':[],
          'implementation_rule_known':key in DETAIL_KEYS,
          'value_semantics':'PROVENANCE_OR_QC; CONDITIONAL_FIELDS_MAY_BE_ABSENT',
          'scope_note':'archive fields follow current no-input failures+record-audit retention policy; no raw means explicit no-retention context'}
    key=path.split('.')[1] if path.startswith('values.') else path
    if key=='derived_from_same_geometry_charged_states':
        return {'producer':'engine.derived_quantities','artifacts':[],'markers':[],
          'implementation_rule_known':True,'value_semantics':'DEPENDENT_SUCCESS_STATES_SAME_GEOMETRY',
          'scope_note':'missing dependent charged/solvent label is a native/derivation input gap; never synthesize missing derived values'}
    if task.startswith('pm7_'):
        if key=='hydrogen_bond_energy_kcal_mol':
            return {'producer':'parser.parse_mopac','artifacts':['input.out'],
              'markers':['HYDROGEN BOND ENERGY','HYDROGEN BONDING ENERGY','Total contribution from hydrogen bonds:'],
              'numeric_patterns':HYDROGEN_NUMERIC_PATTERNS,
              'implementation_rule_known':True,'value_semantics':'NATIVE_HYDROGEN_BOND_ENERGY_CONTRIBUTION_KCAL_MOL',
              'scope_note':'Exact old ENERGY assignment or confirmed DISP summary first numeric component; disp. and Tot are distinct. Keyword/help text alone is not numeric evidence; no finite native numeric component remains NULL.'}
        if key in AUX_KEYS:
            return {'producer':'native_engine.atomic_shell_population' if key=='atomic_shell_population_e' else ('wp4_mulliken_pairs_v3.sparse_mulliken_from_aux' if key.startswith('mulliken_overlap') or key.startswith('mulliken_reconstruction') else 'parser.parse_mopac'),
              'artifacts':['input.aux'],'markers':AUX_KEYS[key],
              'implementation_rule_known':True,'value_semantics':'ATOMIC_OR_SPARSE_TYPED_VALUE',
              'applicable':key not in B_ONLY_MULLIKEN_FIELDS or task=='pm7_B',
              'scope_note':'Mulliken overlap reconstruction requested on pm7_B only; other task legacy NULL remains NULL' if key in B_ONLY_MULLIKEN_FIELDS else ''}
        if key in OUT_MARKERS:return {'producer':'parser.parse_mopac','artifacts':['input.out'],'markers':[OUT_MARKERS[key]],'implementation_rule_known':True,'value_semantics':'NATIVE_OUTPUT'}
        if key in {'homo_eV','lumo_eV'}:
            return {'producer':'parser.parse_mopac','artifacts':['input.aux','input.out'],'markers':[],
              'implementation_rule_known':True,'value_semantics':'AUX_OCCUPATION_AND_EIGENVALUES_OR_SUPER_TEXT'}
        if key=='esp_charges_e':
            return {'producer':'parser.parse_mopac.indexed_table','artifacts':['input.out'],'markers':['ELECTROSTATIC POTENTIAL CHARGES'],
              'implementation_rule_known':True,'value_semantics':'NOT_EMITTED_WITHOUT_ESP; OLD_EXPLICIT_NULL_PRESERVED',
              'scope_note':'ESP task/keyword removed by user; no new ESP calculation'}
        if key in {'normal_end','parse_errors','property_failure_lines'}:
            return {'producer':'parser.parse_mopac','artifacts':['input.out','input.aux'],'markers':[],
              'implementation_rule_known':True,'value_semantics':'QC_REPRESENTS_REAL_ERRORS_OR_EMPTY_ERRORS'}
    if task.startswith('xtb_'):
        if key in XTB_SOURCES:
            artifact,marker=XTB_SOURCES[key]
            return {'producer':'parser.parse_xtb_or_project_values','artifacts':artifact.split('|'),
              'markers':[marker] if marker else [],'implementation_rule_known':True,'value_semantics':'TASK_SPECIFIC_NATIVE_VALUE'}
        if key in {'positions_A','elements','perturb_seed','perturb_sigma_A'}:
            return {'producer':'native_engine.perturbed_geometry_context','artifacts':[],'markers':[],
              'implementation_rule_known':True,'value_semantics':'ACTUAL_PERTURBED_GEOMETRY_NOT_NATIVE_GEOMETRY'}
    return {'producer':None,'artifacts':[],'markers':[],'implementation_rule_known':False,
      'value_semantics':'UNMAPPED_IMPLEMENTATION_REQUIRES_FIX'}
def _inventory(files):
    bodies={}
    for f in files or []:
        data=f.get('data')
        if isinstance(data,bytes):bodies[Path(f['name']).name]=data.decode('utf-8',errors='replace')
    return bodies
def numeric_source_present(spec,bodies,present):
    patterns=spec.get('numeric_patterns')
    if patterns:
        for artifact in present:
            for pattern in patterns:
                for hit in re.finditer(pattern,bodies[artifact],re.I|re.M):
                    try:
                        finite=all(math.isfinite(float(t.replace('D','E').replace('d','e'))) for t in hit.groups())
                    except (TypeError,ValueError,OverflowError):finite=False
                    if finite:return True
        return False
    return bool(spec['markers']) and any(all(m.lower() in bodies[p].lower() for m in spec['markers']) for p in present)
def audit_task(detail,registry_entries,serialized_row=None,files=None):
    """Audit every active entry. Run after same-record derived enrichment.

    No artifact corpus means source verification UNAVAILABLE, not native absent.
    Marker presence with NULL/ABSENT calls for parsing/QC review; a marker alone
    does not prove its numeric contents are valid.
    """
    task=detail['task'];selected=[e for e in registry_entries if active(e) and e['task']==task]
    expected={int(e['registry_id']) for e in selected};cell_ids=[]
    if serialized_row is not None:cell_ids=[int(c['registry_id']) for c in serialized_row.get('values',[])]
    bodies=_inventory(files);rows=[];counts=collections.Counter()
    for e in selected:
        value=lookup(detail,e['source_path']);spec=source_spec(e)
        state='ABSENT' if value is MISSING else ('NULL' if value is None else ('EMPTY' if isinstance(value,(list,dict)) and not value else 'VALUE'))
        artifact_names=spec['artifacts'];present=[p for p in artifact_names if p in bodies]
        token=numeric_source_present(spec,bodies,present)
        if not spec['implementation_rule_known']:reason='IMPLEMENTATION_RULE_UNMAPPED'
        elif state=='VALUE' or state=='EMPTY':reason='EXTRACTED_VALUE_OR_EXPLICIT_EMPTY'
        elif spec.get('applicable') is False:reason='NOT_APPLICABLE_TO_THIS_TASK_B_ONLY_SPARSE_MULLIKEN_GETTER'
        elif not artifact_names:reason='GENERATED_CONTEXT_CONDITIONAL_OR_DERIVATION_INPUT_MISSING'
        elif files is None:reason='RAW_SOURCE_VERIFICATION_UNAVAILABLE'
        elif not present:reason='NATIVE_ARTIFACT_UNAVAILABLE'
        elif token:reason='SOURCE_TOKEN_PRESENT_NULL_OR_ABSENT_REQUIRES_PARSER_OR_NATIVE_QC_REVIEW'
        else:reason='NATIVE_FIELD_NOT_EMITTED_OR_SOURCE_FORMAT_REVIEW'
        encoding='NOT_CHECKED' if serialized_row is None else ('ENCODED' if int(e['registry_id']) in cell_ids else 'SERIALIZER_OMISSION')
        row={'registry_id':int(e['registry_id']),'source_path':e['source_path'],'classification':e['classification'],
             'observed_state':state,'source_reason':reason,'encoding_coverage':encoding,'source_spec':spec}
        rows.append(row);counts[state]+=1;counts[reason]+=1
    issues=[]
    if serialized_row is not None:
        if set(cell_ids)!=expected:issues.append({'code':'SERIALIZER_REGISTRY_ID_SET_MISMATCH','missing_ids':sorted(expected-set(cell_ids)),'unexpected_ids':sorted(set(cell_ids)-expected)})
        if len(cell_ids)!=len(set(cell_ids)):issues.append({'code':'SERIALIZER_DUPLICATE_REGISTRY_ID'})
    unknown=[r['registry_id'] for r in rows if not r['source_spec']['implementation_rule_known']]
    if unknown:issues.append({'code':'UNMAPPED_PARSER_OR_PRODUCER_FIELDS','registry_ids':unknown})
    return {'task':task,'record_id':detail.get('record_id'),'expected_active_registry_fields':len(selected),
      'rows':rows,'counts':dict(counts),'issues':issues,
      'status':'IMPLEMENTATION_AND_CELL_SET_COVERED_VALUES_SEPARATELY_AUDITED' if not issues else 'IMPLEMENTATION_COVERAGE_FAILED',
      'scientific_regression_pass_not_inferred':True}
def catalogue(registry_path,source_paths):
    all_entries=json.loads(Path(registry_path).read_text())['entries'];chosen=entries(registry_path)
    proof=[]
    for path in source_paths or []:
        p=Path(path);proof.append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
    rows=[{'registry_id':e['registry_id'],'task':e['task'],'source_path':e['source_path'],
           'classification':e['classification'],'source_spec':source_spec(e)} for e in chosen]
    unknown=[r for r in rows if not r['source_spec']['implementation_rule_known']]
    return {'schema':'WP5_REGISTRY_EXTRACTION_COVERAGE_SOURCE_CATALOG_V1',
      'status':'SOURCE_CATALOG_COMPLETE_PENDING_ACTUAL_PER_FIELD_REGRESSION' if not unknown else 'SOURCE_CATALOG_IMPLEMENTATION_GAPS',
      'registry':{'path':str(registry_path),'sha256':hashlib.sha256(Path(registry_path).read_bytes()).hexdigest()},
      'registry_total_entries':len(all_entries),'active_entries':len(chosen),'excluded_entries':len(all_entries)-len(chosen),
      'active_by_task':dict(collections.Counter(e['task'] for e in chosen)),
      'source_bindings':proof,'entries':rows,'unmapped_entries':unknown,
      'scope':'All active fields incl physical/QC/provenance/derived/dedup IDs. POLAR response subtree/ESP/Hess removed; static source mapping is not numeric regression PASS.'}
def check():
    ast.parse(Path(__file__).read_text())
    e={'task':'pm7_B','source_path':'values.heat_of_formation_kcal_mol','registry_id':1,'classification':'physical_label'}
    a=audit_task({'task':'pm7_B','record_id':'r','values':{'heat_of_formation_kcal_mol':0.0}},[e],{'values':[{'registry_id':1}]},[])
    assert a['rows'][0]['observed_state']=='VALUE' and not a['issues']
    a=audit_task({'task':'pm7_B','values':{'heat_of_formation_kcal_mol':None}},[e],{'values':[]},[{'name':'input.out','data':b'FINAL HEAT OF FORMATION = *****'}])
    assert a['rows'][0]['observed_state']=='NULL' and a['issues']
    assert 'REQUIRES' in a['rows'][0]['source_reason']
    h={'task':'pm7_B','source_path':'values.hydrogen_bond_energy_kcal_mol','registry_id':62,'classification':'physical_label'}
    detail={'task':'pm7_B','values':{'hydrogen_bond_energy_kcal_mol':None}}
    cell={'values':[{'registry_id':62}]}
    help_line=b' * DISP - PRINT DISPERSION AND HYDROGEN BOND ENERGIES'
    a=audit_task(detail,[h],cell,[{'name':'input.out','data':help_line}])
    assert a['rows'][0]['source_reason']=='NATIVE_FIELD_NOT_EMITTED_OR_SOURCE_FORMAT_REVIEW'
    for text in (b'HYDROGEN BOND ENERGY = -1.234 KCAL/MOL',
                 b'HYDROGEN BONDING ENERGY = 0.000',
                 b'Total contribution from hydrogen bonds: 0.000 disp.: -6.169 Tot: -6.169 kcal/mol'):
        a=audit_task(detail,[h],cell,[{'name':'input.out','data':text}])
        assert a['rows'][0]['source_reason']=='SOURCE_TOKEN_PRESENT_NULL_OR_ABSENT_REQUIRES_PARSER_OR_NATIVE_QC_REVIEW'
    for text in (b'Total contribution from hydrogen bonds: ***** disp.: -6.169 Tot: -6.169 kcal/mol',
                 b'Total contribution from hydrogen bonds: 1.0E999 disp.: -6.169 Tot: -6.169 kcal/mol',
                 b'Total contribution from hydrogen bonds: 0.000'):
        assert not numeric_source_present(source_spec(h),{'input.out':text.decode()},['input.out'])
    a=audit_task({'task':'pm7_B','values':{'hydrogen_bond_energy_kcal_mol':0.0}},[h],cell,[{'name':'input.out','data':help_line}])
    assert a['rows'][0]['observed_state']=='VALUE'
    aux=b'OVERLAP_MATRIX EIGENVECTORS MOLECULAR_ORBITAL_OCCUPANCIES AO_ATOMINDEX'
    for task in ('pm7_anion','pm7_cation','pm7_water','pm7_octanol'):
        for key in B_ONLY_MULLIKEN_FIELDS:
            e={'task':task,'source_path':'values.'+key,'registry_id':1,'classification':'physical_label'}
            a=audit_task({'task':task,'values':{key:None}},[e],{'values':[{'registry_id':1}]},[{'name':'input.aux','data':aux}])
            assert not a['issues'] and a['rows'][0]['observed_state']=='NULL'
            assert a['rows'][0]['source_reason']=='NOT_APPLICABLE_TO_THIS_TASK_B_ONLY_SPARSE_MULLIKEN_GETTER'
    e={'task':'pm7_B','source_path':'values.mulliken_overlap_population_pairs','registry_id':1,'classification':'physical_label'}
    a=audit_task({'task':'pm7_B','values':{'mulliken_overlap_population_pairs':None}},[e],{'values':[{'registry_id':1}]},[{'name':'input.aux','data':aux}])
    assert a['rows'][0]['source_reason']=='SOURCE_TOKEN_PRESENT_NULL_OR_ABSENT_REQUIRES_PARSER_OR_NATIVE_QC_REVIEW'
    e={'task':'xtb_vfukui','source_path':'values.fukui','registry_id':712,'classification':'physical_label'}
    assert source_spec(e)['implementation_rule_known'] and source_spec(e)['artifacts']==['process.out']
    a=audit_task({'task':'xtb_vfukui','values':{'fukui':[[0.0,0.0,0.0]]}},[e],{'values':[{'registry_id':712}]},[])
    assert not a['issues'] and a['rows'][0]['observed_state']=='VALUE'
    print('REGISTRY_COVERAGE_V2_SOURCE_APPLICABILITY_CHECK_PASS')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true')
    p.add_argument('--registry');p.add_argument('--source-paths',nargs='*',default=[]);p.add_argument('--output');a=p.parse_args()
    if a.check:check()
    else:
        if not a.registry or not a.output:p.error('--registry --output required')
        out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
        with out.open('x') as h:json.dump(catalogue(a.registry,a.source_paths),h,indent=2,allow_nan=False);h.write('\n')
