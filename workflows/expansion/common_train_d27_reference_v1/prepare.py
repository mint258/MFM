"""Small plan builder; unavailable actual references produce NONEXECUTABLE only."""
import argparse
import json
from pathlib import Path
from .inventory import need,reference
REQUIRED=('source_catalog_reference','logical_group_plan_reference','canonical_index','field_map_reference',
 'diagnostic_delivery_reference','original_mask_config_reference',
 'scientific_sources','parent_transport_manifest')
RESOURCE=('runtime_profile_reference','endpoint','uid','workers','software_rss_budget_bytes',
 'minimum_node_available_bytes','output_scope_root','output_directory','output_cap_bytes',
 'other_future_reserved_bytes','minimum_free_bytes','quota_snapshot','quota_authority')


def prepare(input_path,resource_path,output):
    bindings=json.loads(Path(input_path).read_bytes());resources=json.loads(Path(resource_path).read_bytes())
    need(bindings['schema']=='PUBCHEM_FULL_COMMON_TRAIN_D27_INPUT_BINDINGS_V1','Explicit actual input bindings required')
    missing=[k for k in REQUIRED if not isinstance(bindings.get(k),dict)]
    common={k:bindings[k]for k in('common_reference_manifest','common_membership_acceptance_reference')if isinstance(bindings.get(k),dict)}
    need(len(common)<=1,'Choose one explicit Common authority branch')
    if not common:missing.append('actual_full_Common_authority')
    for key in('codec','calibration','compact','projection','owner_support'):
        if not isinstance(bindings.get('scientific_sources',{}).get(key),dict):missing.append('scientific_sources:'+key)
    missing.extend('resource:'+k for k in RESOURCE if k not in resources or resources[k]is None)
    if missing:
        result={'schema':'PUBCHEM_FULL_COMMON_TRAIN_D27_NONEXECUTABLE_V1','status':'NONEXECUTABLE_ACTUAL_INPUTS_PENDING',
            'missing':missing,'future_SHA_or_C0_invented':False,'source_input_reference':reference(input_path)}
    else:
        result={**resources,**{k:bindings[k]for k in REQUIRED},**common,'schema':'PUBCHEM_FULL_COMMON_TRAIN_D27_REFERENCE_PLAN_V1',
            'input_bindings_reference':reference(input_path),'source_resources_reference':reference(resource_path),
            'calibration_scope':'fullCommon AND effectiveTRAIN AND NOT originalD5 PM7 base; original record/atom weighting',
            'new_UFF_geometry_QM_Pprime_or_R_N_fit':False,'mask_over_one_percent_policy':'REPORT_ONLY_NO_RECORD_DELETION'}
    with Path(output).open('x',encoding='utf-8')as stream:json.dump(result,stream,sort_keys=True,separators=(',',':'));stream.write('\n')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in('inputs','resources','output'):p.add_argument('--'+key,required=True,type=Path)
    a=p.parse_args();result=prepare(a.inputs,a.resources,a.output);print(result['schema'],result.get('status','PLAN_FOR_ROOT_ACTUAL_ADMISSION'))


if __name__=='__main__':main()
