#!/usr/bin/env python3
"""Create isolated v4: ignore only unused duplicate AUX charge count errors."""
from pathlib import Path
import ast
import hashlib
import json

here=Path(__file__).absolute().parent
getter_v2=here/'wp4_mulliken_pairs_v2.py'; getter_v4=here/'wp4_mulliken_pairs_v4.py'
getter=getter_v2.read_text()
anchor="if errors: raise ValueError(';'.join(errors))"
replacement=("nonessential_errors=[error for error in errors if reference_charges is not None and error=='AUX_COUNT_MISMATCH:MULLIKEN_ATOM_CHARGES']\n"
             "        if nonessential_errors:\n"
             "            qc['nonessential_AUX_errors']=nonessential_errors\n"
             "            qc['codes'].append('AUX_DUPLICATE_MULLIKEN_CHARGE_FIELD_UNUSED_WITH_OUT_REFERENCE')\n"
             "        required_errors=[error for error in errors if error not in nonessential_errors]\n"
             "        if required_errors: raise ValueError(';'.join(required_errors))")
assert getter.count(anchor)==1
getter=getter.replace(anchor,replacement,1)
runner=(here/'wp4_native_pilot_v3.py').read_text()
assert runner.count('wp4_mulliken_pairs_v2.py')==5
runner=runner.replace('wp4_mulliken_pairs_v2.py','wp4_mulliken_pairs_v4.py')
assert runner.count('(Path(__file__),"wp4_native_pilot_v3.py")')==1
runner=runner.replace('(Path(__file__),"wp4_native_pilot_v3.py")','(Path(__file__),"wp4_native_pilot_v4.py")',1)
assert runner.count('default=str(HERE/"wp4_native_v2_config.json")')==1
runner=runner.replace('default=str(HERE/"wp4_native_v2_config.json")','default=str(HERE/"wp4_native_v4_config.json")',1)
# The expanded diagnostic pattern recognizes an actual xTB fatal spelling.
scf_old='SCC IS NOT CONVERGED'
assert runner.count(scf_old)==1
runner=runner.replace(scf_old,'SCC IS NOT CONVERGED|SELF CONSISTENT CHARGE ITERATOR DID NOT CONVERGE',1)
property_anchor='if values.get("property_failure_lines") and result["status"]=="SUCCESS":'
assert runner.count(property_anchor)==1
runner=runner.replace(property_anchor,
    'if task["family"]=="mopac" and re.search(r"VECTOR LENGTH OF ZERO IN SURFAC",out_text,re.I):\n'
    '            values.setdefault("property_failure_lines",[]).append("VECTOR LENGTH OF ZERO IN SURFAC")\n'
    '        if task["family"]=="mopac" and task["name"]!="pm7_B" and values.get("property_failure_lines") and code==0 and values.get("normal_end") is True and not scf_failed and not timed_out:\n'
    '            result.update(status="PROPERTY_FAILED",failure_code="METHOD_PROPERTY_UNSUPPORTED")\n'
    '        '+property_anchor,1)
config=json.loads((here/'wp4_native_v2_config.json').read_text())
config['notes'].append('v4: When the actual .out Mulliken charges are the reference, an inconsistent unused duplicate AUX MULLIKEN_ATOM_CHARGES field is recorded but cannot suppress valid density/S reconstruction. Every required matrix and atom mapping remains strict; charge QC remains <=0.001e.')
config['notes'].append('Explicit ESP d-orbital refusal and VECTOR LENGTH OF ZERO IN SURFAC are property failures; POLAR failure leaves alpha missing without a STATIC fallback. The xTB Self consistent charge iterator did not converge spelling is recognized as an actual SCC failure.')
outputs=((getter_v4,getter),(here/'wp4_native_pilot_v4.py',runner),
         (here/'wp4_native_v4_config.json',json.dumps(config,indent=2,ensure_ascii=False)+'\n'))
for path,body in outputs:
    if path.exists(): raise ValueError('Do not overwrite existing v4 source:'+str(path))
    if path.suffix=='.py': ast.parse(body)
    path.write_text(body,encoding='utf-8',newline='\n')
report={'status':'V4_NEW_SOURCES_AST_PASS_NO_QM','new_source_sha256':{path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path,_ in outputs},
        'original_sources_unchanged':{name:hashlib.sha256((here/name).read_bytes()).hexdigest() for name in ('wp4_native_pilot_v2.py','wp4_native_pilot_v3.py','wp4_mulliken_pairs_v2.py','wp4_parsers.py')},
        'QM_keywords_changed':False,'coordinates_changed':False,'charge_QC_tolerance_changed':False}
(here.parent/'reports/wp4_native_v4_static_check.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
