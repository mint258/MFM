"""Recover only the taskbook's four frozen calibration cases; no QM calls."""
import collections,hashlib,importlib.util,json,pathlib,sys
import numpy as np
from rdkit import Chem
from stage0_cohort import R,O,load,save,guard
B=R/'MFM_p_data_information';SNAP=R/'runs/data_v1_20261025/control/window2_20261105/D6_node20_shared_candidate_20261108_v1/source_snapshot86'
sys.path.insert(0,str(SNAP))
from workflows.data_v1_final.export.full_physical_index_v3.read_index import locators_for_mids,iter_source_rows
ENGINE=R/'runs/phase1_wp5_20261011/scripts';sys.path.insert(0,str(ENGINE));import wp5_engine_v3 as engine

def digest(b):return hashlib.sha256(b).hexdigest()
def main():
 guard();selected=load(B/'results/p_data_information/resolution.json')['calibration_2B']['candidates'];wanted={(p['molecule_id'],rid) for p in selected for rid in [p['native_record_id_a'],p['native_record_id_b']]};mids=list(dict.fromkeys(mid for mid,rid in wanted));index='/lfshome/zixiao/data_v1_20261025/D6_full_physical_index_20261105_v3/manifest.json'
 locations=[p for p in locators_for_mids(index,mids,domains=(0,),families=('base_geometry','pm7_neutral','xtb_singlepoint')) if (p['molecule_id'],p['record_id']) in wanted];print('FROZEN_CALIBRATION_LOCATORS',len(locations),flush=True);geometries={};metadata=[];retained=[]
 def columns(loc):
  return ['atomic_numbers','positions_A','source_native_geometry_sha256','native_atom_order_sha256'] if loc['family']=='base_geometry' else ['calc_type','status','source_status','software_version_id','scf_iterations','converged','input_file_sha256','input_bundle_sha256','reproduction_package_sha256','precision_by_field_json','raw_output_locator_json']
 for loc,row in iter_source_rows(locations,columns):
  key=(loc['molecule_id'],loc['record_id'])
  if loc['family']=='base_geometry':
   if key in geometries:raise ValueError('Ambiguous original base')
   geometries[key]=row
  else:metadata.append((loc,row))
 mapping=load(R/'runs/data_v1_20261025/control/window2_20261105/known_package_protocol_map.json')['entries'];packages={v['reproduction_package_reference']['sha256']:v for v in mapping};root=O/'calibration_2B_inputs';root.mkdir(exist_ok=True);plans=[]
 for loc,meta in metadata:
  key=(loc['molecule_id'],loc['record_id']);task=meta['calc_type'];entry=packages.get(meta['reproduction_package_sha256']);result=dict(molecule_id=key[0],native_record_id=key[1],task=task,source_locator=loc,original_metadata=meta,ready=False)
  if entry is None or key not in geometries:result['reason']='Original package/base binding unavailable';plans.append(result);continue
  pr=entry['protocol_reference'];raw=pathlib.Path(pr['path']).read_bytes();assert digest(raw)==pr['sha256'];protocol=json.loads(raw);package_ref=entry['reproduction_package_reference'];raw=pathlib.Path(package_ref['path']).read_bytes();assert digest(raw)==package_ref['sha256'];package=json.loads(raw);definition=next(t for t in protocol['tasks'] if t['name']==task);base=geometries[key];symbols=[Chem.GetPeriodicTable().GetElementSymbol(int(z)) for z in base['atomic_numbers']];native=dict(symbols=symbols,coords=base['positions_A']);engine.CONFIG=protocol;rendered=engine.render_inputs(definition,native,dict(record_id=key[1]),protocol);per_file,bundle=engine.rendered_input_hashes(definition,native,dict(record_id=key[1]));version=package['software_versions'][definition['family']]
  result.update(protocol_reference=pr,reproduction_package_reference=package_ref,software=version,original_keywords=definition.get('keywords'),original_arguments=definition.get('args'),environment=protocol[definition['family']+'_environment'],reconstructed_files=per_file,reconstructed_bundle_sha256=bundle,base_source_native_geometry_sha256=base['source_native_geometry_sha256'],base_native_atom_order_sha256=base['native_atom_order_sha256'])
  exact=per_file==meta['input_file_sha256'] and bundle==meta['input_bundle_sha256'] and version['software_version_id']==meta['software_version_id'];result['original_inputs_exact_hash_match']=exact
  if not exact:result['reason']='Original input/version binding mismatch';plans.append(result);continue
  folder=root/(digest(json.dumps(key).encode())[:16]+'_'+task);folder.mkdir(exist_ok=True)
  for name,body in rendered.items():(folder/name).write_bytes(body)
  result['original_input_directory']=str(folder);result['symbols']=symbols
  if task=='pm7_B':
   keywords=definition['keywords'];assert 'SCFCRT' not in keywords.upper() and '1SCF' in keywords and 'PM7' in keywords;assert version['version']=='23.0.3';binary=pathlib.Path(version['executable']);result['binary_sha_match']=digest(binary.read_bytes())==version['sha256'];result['ready']=result['binary_sha_match'] and meta['converged'] is True and meta['status'] in ('SUCCESS','PROPERTY_FAILED');result['setting']=dict(parameter='SCFCRT',original_default=1e-4,tight=1e-5,source='https://openmopac.net/Manual/scf_test.html',only_changed_keyword='SCFCRT=0.00001');result['reason']='READY_EXACT_ORIGINAL_INPUT_AND_VERSION; original result reused' if result['ready'] else 'Original convergence or exact binary unavailable'
  else:result['reason']='No recovered independent 10x SCF-only control for this actual xTB version; --acc not substituted'
  plans.append(result);retained.append(dict(molecule_id=key[0],native_record_id=key[1],task=task,original_input_exact_hash_match=exact))
 save(O/'calibration_2B_lineage.json',dict(cases=plans,actual_QM_calls=0,source_index=index,matched_original_inputs=retained,new_geometry=False,selection='Unchanged first four frozen TRAIN-core molecules, maximum frozen-pair heavy RMSD'))
 print('CALIBRATION_LINEAGE_DONE','READY',sum(p['ready'] for p in plans),'CASES',len(plans),flush=True)
if __name__=='__main__':main()