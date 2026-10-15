#!/usr/bin/env python3
"""Create new native-v2 sources only, then perform lightweight static checks."""
from pathlib import Path
import ast
import hashlib
import importlib.util
import json
import sys

sys.dont_write_bytecode=True
here=Path(__file__).absolute().parent
root=here.parent
v1=here/'wp4_native_pilot.py'
frozen_parser=here/'wp4_parsers.py'
before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (v1,frozen_parser)}
runner=v1.read_text()
def replace_once(old,new):
    global runner
    if runner.count(old)!=1: raise ValueError('Expected unique v1 source anchor: '+old[:100])
    runner=runner.replace(old,new,1)

replace_once('WP4: read-only native-geometry pilot, with resumable molecule checkpoints.',
             'WP4 native v2: read-only original geometries, sparse Mulliken pairs and resumable molecule checkpoints.')
replace_once('HERE = Path(__file__).absolute().parent',
             'sys.dont_write_bytecode = True\nHERE = Path(__file__).absolute().parent')
replace_once('HANDLES, SOURCES, CONFIG, PARSER, OUTPUT, DEADLINE, STOP_EVENT = {}, None, None, None, None, None, None',
             'HANDLES, SOURCES, CONFIG, PARSER, OUTPUT, DEADLINE, STOP_EVENT, MULLIKEN = {}, None, None, None, None, None, None, None')
replace_once('global SOURCES,CONFIG,OUTPUT,PARSER,DEADLINE,STOP_EVENT',
             'global SOURCES,CONFIG,OUTPUT,PARSER,DEADLINE,STOP_EVENT,MULLIKEN')
replace_once('PARSER=importlib.util.module_from_spec(spec); spec.loader.exec_module(PARSER)',
             'PARSER=importlib.util.module_from_spec(spec); spec.loader.exec_module(PARSER)\n'
             '    pair_spec=importlib.util.spec_from_file_location("wp4_pinned_mulliken_pairs",OUTPUT/"source_snapshot"/"wp4_mulliken_pairs_v2.py")\n'
             '    MULLIKEN=importlib.util.module_from_spec(pair_spec); pair_spec.loader.exec_module(MULLIKEN)')
replace_once('values=PARSER.parse_mopac(scratch,symbols,pair_indices=native["pairs"],reconstruct_mulliken=False)',
             'values=PARSER.parse_mopac(scratch,symbols,pair_indices=native["pairs"],reconstruct_mulliken=False)\n'
             '            if task["name"]=="pm7_B":\n'
             '                overlap=MULLIKEN.sparse_mulliken_from_aux(scratch/"input.aux",symbols,native["pairs"],\n'
             '                    reference_charges=values.get("mulliken_charges_e"),\n'
             '                    charge_tolerance_e=CONFIG["mulliken_overlap_charge_tolerance_e"],\n'
             '                    min_absolute_eigenvalue=CONFIG["mulliken_minimum_absolute_eigenvalue"])\n'
             '                values["mulliken_overlap_population_pairs"]=overlap["pairs"]\n'
             '                values["mulliken_overlap_qc"]=overlap["qc"]\n'
             '                values["mulliken_reconstruction_charge_max_error_e"]=overlap["qc"].get("reconstructed_charge_max_error_e")')
replace_once('result["qc_codes"].append("MULLIKEN_OVERLAP_RECONSTRUCTION_NOT_VALIDATED")',
             'result["qc_codes"].extend(values.get("mulliken_overlap_qc",{}).get("codes",[]))')
replace_once('default=str(HERE/"wp4_native_config.json")',
             'default=str(HERE/"wp4_native_v2_config.json")')
replace_once('ast.parse(Path(__file__).read_text()); ast.parse((HERE/"wp4_parsers.py").read_text())',
             'ast.parse(Path(__file__).read_text()); ast.parse((HERE/"wp4_parsers.py").read_text())\n'
             '        getter_path=HERE/"wp4_mulliken_pairs_v2.py"; ast.parse(getter_path.read_text())\n'
             '        spec=importlib.util.spec_from_file_location("static_mulliken_check",getter_path)\n'
             '        getter=importlib.util.module_from_spec(spec); spec.loader.exec_module(getter)\n'
             '        parameter_check=getter.validate_official_parameters(config["mulliken_official_references"]["parameters"]["path"])\n'
             '        assert set(parameter_check["elements"])=={"H","B","C","N","O","F","Si","P","S","Cl","Se","Br","I"}\n'
             '        assert "mulliken_overlap_population_pairs" in config["tasks"][0]["required_values"]\n'
             '        for reference in config["mulliken_official_references"].values():\n'
             '            assert sha(reference["path"])==reference["sha256"]')
replace_once('"runner_sha256":source_sha,"parser_sha256":parser_sha,"config_sha256":sha(args.config),',
             '"runner_sha256":source_sha,"parser_sha256":parser_sha,"config_sha256":sha(args.config),\n'
             '             "mulliken_getter_sha256":sha(HERE/"wp4_mulliken_pairs_v2.py"),\n'
             '             "mulliken_official_references":config["mulliken_official_references"],')
replace_once('((Path(__file__),"wp4_native_pilot.py"),(HERE/"wp4_parsers.py","wp4_parsers.py"),(Path(args.config),"config.json"))',
             '((Path(__file__),"wp4_native_pilot_v2.py"),(HERE/"wp4_parsers.py","wp4_parsers.py"),\n'
             '                         (HERE/"wp4_mulliken_pairs_v2.py","wp4_mulliken_pairs_v2.py"),(Path(args.config),"config.json"))')
replace_once('"units":config["units"],"pair_storage":',
             '"mulliken_pair_method":config["mulliken_pair_method"],"coverage_cost_notes":config["coverage_cost_notes"],\n'
             '                  "units":config["units"],"pair_storage":')
replace_once('config=json.loads(Path(args.config).read_text())',
             'config=json.loads(Path(args.config).read_text())\n'
             '    for reference in config["mulliken_official_references"].values():\n'
             '        if sha(reference["path"])!=reference["sha256"]: raise ValueError("MULLIKEN_OFFICIAL_SOURCE_BINDING_DIFFERS")')

spec=importlib.util.spec_from_file_location('build_mulliken_parameters',here/'wp4_mulliken_pairs_v2.py')
getter=importlib.util.module_from_spec(spec); spec.loader.exec_module(getter)
references={}
for key,name in (('parameters','parameters_for_PM7_C.F90'),('mullik','mullik.F90'),('aux_export','to_screen.F90')):
    path=root/'software/mopac_reference/native_v2'/name
    references[key]={'path':str(path),'bytes':path.stat().st_size,
                     'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source_URL':getter.SOURCE_URLS[key]}
official_check=getter.validate_official_parameters(references['parameters']['path'])
config=json.loads((here/'wp4_native_config.json').read_text())
config.update(mulliken_overlap_charge_tolerance_e=0.001,mulliken_minimum_absolute_eigenvalue=1e-10,
              mulliken_official_references=references,mulliken_pair_method=getter.METHOD,
              coverage_cost_notes={
                  'current_measured_recipe':'All native records use B with static POLAR. The B timing includes core PM7 properties, POLAR, and auxiliary density/overlap export; getter wall time is separately recorded.',
                  'hessian_scope':'Exactly the marked lowest original-energy retained conformer per molecule; no finite original energy means no Hessian.',
                  'low_coverage_C_D_polar':'For a later scheme computing POLAR only on lowest conformers, use the same B keywords without POLAR(E=(0.0),BETA=0,GAMMA=0) on other records, and remove static_polar_block from their required-values list. No extra B SCF is required.',
                  'cost_estimation_limit':'Full-B measured timing cannot be exactly split into PM7 core and POLAR cost from this pilot; do not claim an exact C/D counterfactual saving.'})
config['units']['Mulliken_overlap_population']='electrons; 2*sum(P_nonorthogonal[AO_i,AO_j]*S_MULLIK[AO_i,AO_j]), sparse selected unordered pairs'
config['notes']=[note for note in config['notes'] if not note.startswith('Mulliken overlap reconstruction is currently')]
config['notes'].append('Mulliken pairs use full AUX total density, exact v23.0.3 beta_p-for-d correction, official abs-eigenvalue inverse root, and per-case charge agreement <=0.001e; disagreement leaves pairs null with explicit QC.')
config['tasks'][0]['required_values'].append('mulliken_overlap_population_pairs')
for path,body in ((here/'wp4_native_pilot_v2.py',runner),
                  (here/'wp4_native_v2_config.json',json.dumps(config,indent=2,ensure_ascii=False)+'\n')):
    if path.exists(): raise ValueError('Do not replace an existing v2 source: '+str(path))
    path.write_text(body,encoding='utf-8',newline='\n')
    if path.suffix=='.py': ast.parse(body)
after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (v1,frozen_parser)}
assert after==before
report={'status':'NEW_V2_SOURCES_AST_PASS_NO_QM_NO_LMDB','official_parameter_check':official_check,
        'frozen_v1_and_parser_sha256':before,
        'new_source_sha256':{name:hashlib.sha256((here/name).read_bytes()).hexdigest() for name in
            ('wp4_native_pilot_v2.py','wp4_mulliken_pairs_v2.py','wp4_native_v2_config.json')},
        'audit_source':str(root/'reports/mulliken_audit_v2_job_4512806/mulliken_audit.json')}
(root/'reports/wp4_native_v2_static_check.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
