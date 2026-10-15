"""Schema metadata correction only: stable registry IDs and payloads unchanged."""
import hashlib,json
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011')
source=ROOT/'reports/label_registry.json';raw=source.read_bytes();registry=json.loads(raw);changed=[]
for entry in registry['entries']:
    task,path=entry['task'],entry['source_path'];before={key:entry[key] for key in ('canonical_target','level','unit')}
    geometry='seeded_sigma0.1A_perturbed_PM7' if task=='xtb_perturbed_gradient' else 'native_original_PM7'
    property_name=path.removeprefix('values.').removeprefix('detail.')
    if '.fukui_Coulson.' in path:entry['level']='atom'
    electronic='5000K_FOD' if task=='xtb_fod' else 'ground_state'
    entry['geometry_context']=geometry;entry['electronic_context']=electronic
    entry['canonical_target']='|'.join([entry['method'],'charge'+str(entry['charge']),entry['context'],geometry,electronic,property_name])
    if path.endswith('D4_atomic_C6_au'):entry['unit']='Eh bohr^6'
    if path.endswith('molecular_quadrupole_traceless_au'):entry['unit']='e bohr^2; xx,xy,yy,xz,yz,zz'
    if path.endswith('positions_A'):entry['unit']='Angstrom'
    if path.endswith('perturb_sigma_A'):entry['unit']='Angstrom'
    if path.endswith('perturb_seed'):entry['unit']='integer seed'
    changed.append({'registry_id':entry['registry_id'],'task':task,'source_path':path,'before':before,'after':{key:entry[key] for key in ('canonical_target','level','unit')}})
registry.update(schema_revision='V2_EXPLICIT_GEOMETRY_AND_FUKUI_ATOM_LEVEL',source_registry_sha256=hashlib.sha256(raw).hexdigest(),stable_entry_order_and_ids=True,payload_values_changed=False)
(root_path:=ROOT/'reports/label_registry_v2.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n')
review={'status':'REGISTRY_METADATA_V2_CORRECTED','source_sha256':hashlib.sha256(raw).hexdigest(),'v2_sha256':hashlib.sha256(root_path.read_bytes()).hexdigest(),'entries':len(registry['entries']),'stable_ids':True,'changed_fields':changed,'serialization_note':'Registry-indexed P stores integer IDs and original numeric values. Entry order/IDs and inclusion rules unchanged, so per-record serialized numeric bytes unchanged; only shared registry metadata bytes differ. C4 v1 snapshot retained for measured wire provenance.'}
(ROOT/'reports/label_registry_v2_changes.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':review['status'],'entries':review['entries'],'shared_registry_byte_delta':root_path.stat().st_size-len(raw)}))
