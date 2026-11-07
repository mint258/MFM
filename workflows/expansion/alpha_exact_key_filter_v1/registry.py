"""Publish the active exact-key registry from closed producer metadata only."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import stat


def read(path):
    path=Path(path);a=path.lstat()
    if not stat.S_ISREG(a.st_mode)or path.is_symlink()or a.st_size>2<<20:raise ValueError('Small regular closed metadata required')
    raw=path.read_bytes();b=path.lstat()
    if (a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)!=(b.st_ino,b.st_size,b.st_mtime_ns,b.st_ctime_ns):raise ValueError('Metadata changed')
    return json.loads(raw),dict(path=str(path.absolute()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def build(historical,source,filtered):
    old,oldref=read(historical);inventory,inventoryref=read(source);result,resultref=read(filtered)
    policy=result['policy']
    if not(result['schema']=='PUBCHEM_EXACT_KEY_FILTERED_SHARDS_V1'and result['status']=='COMPLETE'
        and result['source_manifest_reference']==inventoryref and policy['identity_kinds']==['full','wp5']
        and all(policy[k]is False for k in ('composition_veto','lower_bound_veto','wildcard_veto'))
        and policy['removed_subdatasets']=={'moleculenet':['PDBbind']}
        and result['eligible_molecules']+result['excluded_molecules']==result['input_unique_molecules']):
        raise ValueError('Actual whole exact-key-only producer and source lineage required')
    if {s['dataset']for s in inventory['sources']}!={s['dataset']for s in old['sources']}:raise ValueError('All original source families required')
    sources=[]
    historical_fields=('acceptance','independent_Root_acceptance_reference','original_native_union_root_review_reference',
        'preserved_root_union_evidence_reference','physical_dispositions','scope_resolution','note')
    for original in inventory['sources']:
        s=copy.deepcopy(original);name=s['dataset'];disposition=result['original_identity_source_dispositions'][name]
        provenance={k:s.pop(k)for k in historical_fields if k in s}
        # These are superseded veto rules, not active source structure identities.
        s.pop('lower_bounds',None);s.pop('pending_reason',None);s.pop('global_pool_release',None)
        if provenance:s['historical_inventory_annotations_not_matching_rules']=provenance
        s['status']='ALL_PHYSICAL_ROWS_EXACT_KEYED_OR_EXPLICIT_EVALUATION_EXCLUSIONS'
        s['exact_filter_disposition']=disposition
        s['exact_index_key_counts']={kind:n for kind,dataset,n in result['exact_index_key_counts']if dataset==name}
        s['structural_veto_index_reference']=result['exact_index']
        s['unresolved_structures']='NO_STRUCTURAL_VETO_EXCLUDED_FROM_DOWNSTREAM_EVALUATION'
        s['version_basis']='FROZEN_SOURCE_LEDGER_VERSION_AND_PHYSICAL_SHA_NOT_INVENTED_CURRENT_RELEASE'
        if name=='moleculenet':
            s['required_subdatasets']=sorted(k for k in disposition['subdatasets']if k!='PDBbind')
            s['excluded_subdatasets']={'PDBbind':'USER_CONFIRMED_OUTSIDE_DOWNSTREAM_PLAN'}
        sources.append(s)
    return dict(schema='expansion_decontamination_sources_v1',version='2026-11-04-full-wp5-only-v1',
        prepared_on='2026-11-04',status='ALL_SOURCE_ROWS_ACCOUNTED_AND_FULL_POOL_FILTER_COMPLETE',
        identity_policy=dict(exact='full_inchikey',wp5='inchikey_first14+colon+last_protonation_character',
            unresolved='EXCLUDE_DOWNSTREAM_EVALUATION_NO_STRUCTURAL_VETO',composition_veto=False,
            lower_bound_veto=False,wildcard_veto=False,ranking_uses_downstream_features=False),
        required_scope='All used/planned sources and native roles; v1 TRAIN/VAL/FULL plus4900 embargo; PDBbind excluded',
        sources=sources,source_manifest_reference=inventoryref,source_transport_manifest=result['parent_transport_manifest'],
        full_pool_filter_manifest_reference=resultref,policy_authority_reference=result['policy_authority_reference'],
        eval_exclusions=result['eval_exclusions'],exact_index=result['exact_index'],
        input_unique_molecules=result['input_unique_molecules'],eligible_molecules=result['eligible_molecules'],
        excluded_molecules=result['excluded_molecules'],historical_registry_reference=oldref,
        historical_source_veto_policy_superseded=True,R_N_or_UFF_completion_claimed=False,
        future_new_downstream_dataset_requires_v2_recheck=True,no_new_per_job_Root_acceptance_required=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--historical-registry',required=True,type=Path);p.add_argument('--source-manifest',required=True,type=Path)
    p.add_argument('--filtered-manifest',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    value=build(a.historical_registry,a.source_manifest,a.filtered_manifest)
    with a.output.open('x',encoding='utf-8')as out:out.write(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    print(json.dumps(read(a.output)[1]))


if __name__=='__main__':main()
