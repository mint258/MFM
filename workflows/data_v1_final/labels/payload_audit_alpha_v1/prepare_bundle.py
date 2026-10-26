"""Stdlib small-metadata packaging only; never reads/hashes scientific bodies."""
from __future__ import annotations
import argparse,copy,hashlib,json
from pathlib import Path
ROOT=Path('/gfshome/alpha/codex_data_v1_20261026')
MAIN=Path('/share/home/zixiao/descriptor_analysis')

def read(path):
    p=Path(path)
    if p.stat().st_size>2<<20:raise ValueError('SMALL_METADATA_ONLY')
    return p.read_bytes()

def triple(path):
    raw=read(path);return {'path':str(Path(path).absolute()),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def save(path,value):
    with Path(path).open('x',encoding='utf-8') as stream:json.dump(value,stream,sort_keys=True,indent=2);stream.write('\n')
    return triple(path)

def target(reference,path):return dict(reference,path=str(path))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inventory',required=True)
    p.add_argument('--streaming-config',required=True);p.add_argument('--output-directory',required=True);a=p.parse_args()
    inventory=json.loads(read(a.inventory));entries=[]
    if inventory['data_files']!=227 or inventory['small_files']!=54:raise ValueError('EXACT_ORIGINAL_INVENTORY')
    for row in [*inventory['data'],*inventory['small']]:
        entries.append({'kind':row['kind'],'origin_reference':row['origin_reference'],
          'target_reference':{k:row['target_locator'][k] for k in ('path','bytes','sha256')}})
    by_source={e['origin_reference']['path']:e['target_reference'] for e in entries}
    # This frozen metadata is in the original54; streaming_v1.json itself is not.
    manifest_main=str(MAIN/'runs/data_v1_20261025/artifacts/labels/source_status_v1/auto_memory_v1/prepared/manifest.json')
    authority_row=next(r for r in inventory['small'] if r['origin_reference']['path']==manifest_main)
    authority_origin=authority_row['origin_reference']
    authority_path=Path(authority_origin['path'])
    if not authority_path.is_file():authority_path=Path(authority_row['target_locator']['path'])
    authority_observed=triple(authority_path)
    if any(authority_observed[k]!=authority_origin[k] for k in ('bytes','sha256')):
        raise ValueError('FROZEN_PREPARED_MANIFEST_METADATA_SHA_DIFFERS')
    full_prepared=json.loads(read(authority_path));streaming_origin=full_prepared['sources']['streaming_config_baseline']
    expected_main_path=str(MAIN/'runs/data_v1_20261025/repository/configs/data_v1/labels/streaming_v1.json')
    if streaming_origin['path']!=expected_main_path:raise ValueError('EXACT_MAIN_STREAMING_CONFIG_ORIGIN_REQUIRED')
    original_bytes=read(a.streaming_config);original_observed=triple(a.streaming_config)
    if any(original_observed[k]!=streaming_origin[k] for k in ('bytes','sha256')):
        raise ValueError('STREAMING_CONFIG_COPY_DIFFERS_FROM_FROZEN_MAIN_REFERENCE')
    original=json.loads(original_bytes);auxiliary=copy.deepcopy(original)
    auxiliary['adapter_source_pins']=[by_source[p['path']] for p in original['adapter_source_pins']]
    if len(auxiliary['adapter_source_pins'])!=4:raise ValueError('EXACT_FOUR_FROZEN_CODE_ADAPTERS')
    out=Path(a.output_directory);out.mkdir(parents=True,exist_ok=False)
    map_local=save(out/'relocation_map.json',{'schema':'LABEL_PAYLOAD512_READONLY_RELOCATION_MAP_V1',
      'origin_inventory_reference':target(triple(a.inventory),ROOT/'code/payload_audit_alpha_v1/transfer_inventory_v1.json'),
      'status':'EXPECTED_LOCATORS_ONLY_BODY_SHA_PENDING_IN_ALPHA_ALLOCATION','entries':entries,
      'target_body_SHA_verified_by_packager':False,'source_body_read_or_hashed_by_packager':False})
    with (out/'streaming_v1_original.json').open('xb') as stream:stream.write(original_bytes)
    original_local=triple(out/'streaming_v1_original.json');original_target=target(original_local,ROOT/'metadata/labels_payload512_v1/streaming_v1_original.json')
    auxiliary_local=save(out/'streaming_v1_fixture_auxiliary.json',auxiliary)
    auxiliary_target=target(auxiliary_local,ROOT/'code/labels_payload512_frozen_v1/configs/data_v1/labels/streaming_v1.json')
    transform_local=save(out/'fixture_auxiliary_transform.json',{'schema':'LABEL_PAYLOAD512_FIXTURE_FOUR_CODE_PATHS_ONLY_V1',
      'origin_main_reference':streaming_origin,'origin_reference_authority':authority_origin,
      'origin_authority_observed_reference':authority_observed,'original_input_observed_reference':original_observed,
      'original_alpha_reference':original_target,
      'auxiliary_alpha_reference':auxiliary_target,'changed_fields':['adapter_source_pins['+str(i)+'].path' for i in range(4)],
      'original_scientific_parameters_changed':False,'original_six_test_method_bodies_changed':False,
      'original_adapter_source_pins':original['adapter_source_pins'],'auxiliary_adapter_source_pins':auxiliary['adapter_source_pins']})
    transfers=[{'local_reference':map_local,'target_locator':target(map_local,ROOT/'metadata/labels_payload512_v1/relocation_map.json')},
      {'local_reference':original_local,'target_locator':original_target},{'local_reference':auxiliary_local,'target_locator':auxiliary_target},
      {'local_reference':transform_local,'target_locator':target(transform_local,ROOT/'metadata/labels_payload512_v1/fixture_auxiliary_transform.json')}]
    save(out/'package_receipt.json',{'schema':'LABEL_PAYLOAD512_ALPHA_SMALL_METADATA_PACKAGE_V1','status':'PREPARED_NOT_INSTALLED',
      'source_expected_inventory':triple(a.inventory),'fixed_original_entries':281,'install_small_files':transfers,
      'target_files_read_or_stat':False,'large_scientific_source_read_or_hash':False,'actual_CPU_job_or_Slurm_executed':False})
    print(json.dumps({'status':'SMALL_PACKAGE_READY_NOT_INSTALLED','receipt':triple(out/'package_receipt.json')}))
if __name__=='__main__':main()