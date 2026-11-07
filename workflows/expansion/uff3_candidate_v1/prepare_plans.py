"""Concrete metadata-only pilot/full plans; future scientific parents stay null."""
import argparse
from pathlib import Path
from . import store as S


def prepare(storage_path,policy_path,proposed_quality_path,output):
    storage=S.read_json(storage_path)
    if storage['schema']=='PUBCHEM_LUSTRE_ROOT_STORAGE_ADMISSION_V1':quota=storage['quota_plan']
    elif storage['schema']=='PUBCHEM_QUOTA_DELIVERY_EPOCH_V2':quota=storage['services']['lustre']
    else:raise RuntimeError('ACTUAL_ROOT_LUSTRE_AUTHORITY_SCHEMA_REQUIRED')
    if quota['quota_authority']['kind']!='lustre':
        raise RuntimeError('ACTUAL_ROOT_LUSTRE_STORAGE_ADMISSION_REQUIRED')
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    root=Path('/lfshome/zixiao/pubchem_completion_20261103/uff_candidate')
    common={'schema':'PUBCHEM_UFF3_ALLOCATION_PLAN_V1',
        'status':'NONEXECUTABLE_MISSING_FROZEN_ORDERED_SOURCE_AND_ROOT_QUALITY_REVIEW',
        'user_policy':S.reference(policy_path),'source_manifest':None,'output_directory':str(root),
        'workers':32,'allowed_nodes':['compute-0-21'],'maximum_conformers':3,'no_fill':True,'no_retry':True,
        'shard_index':0,'shard_count':1,'family_batch_molecules':64,
        'worker_rss_soft_cap_bytes':8<<30,'maximum_molecule_output_bytes':64<<20,
        'parent_family_reserved_bytes':128<<20,'minimum_node_available_bytes':4<<30,
        'quota_snapshot':quota['quota_snapshot'],'quota_authority':quota['quota_authority'],
        'output_cap_bytes':700000000000,'other_future_reserved_bytes':800000000000,
        'minimum_free_bytes':200000000000,'quality_reference_review':None,
        'proposed_quality_review_for_Root':S.reference(proposed_quality_path),
        'actual_storage_admission_reference':S.reference(storage_path),
        'memory_limits_are_software_guards_not_scheduler_reservations':True,
        'whole_tree_memory_review':'Root must review actual pilot process-tree RSS and node reserve before full; per-worker soft caps are not a physical allocation guarantee',
        'pending_actual_dependencies':['Complete true Common reference and exact full-pool novelty',
            'Full original-input regression and all11 all-split decontaminated typed pool',
            'Frozen10M disjoint R5M/N5M queues and exact2.5M first batch',
            'Closed all2.5M ordered source JSONL/manifest with PubChem version and actual parent pins',
            'Independent Root approval of proposed original50000-TRAIN provisional reference application'],
        'source_immutability':'Same all2.5M manifest for pilot/full; exact once cache and family batches reused',
        'science':'Fixed30 internal original UFF candidates; export actual up-to3; nofill,noretry,D20once,D3peractual,noPprime/QM/training',
        'operational':'No application wall timeout or failure-count stop; actual scheduler/resource protections retained',
        'parent_submission':'Root only; recheck idleCPU preference, actual node memory and fresh Lustre controller before submit'}
    pilot={**common,'mode':'pilot','selected_molecules':10000,'selected_molecules_by_stream':{'R':5000,'N':5000},
        'selection':'One Random(20261025); sample5000 R ranks then5000 N ranks from1..1250000',
        'requested_native_new_optimizations_upper_bound':300000,
        'maximum_exported_D20_rows':10000,'maximum_exported_D3_rows':30000,
        'full_cap_is_also_reserved_during_pilot':True}
    full={**common,'mode':'full','selected_molecules':2500000,'selected_molecules_by_stream':{'R':1250000,'N':1250000},
        'selection':'All frozen first-batch source ordinals; one full allocation; no1024-parent partition',
        'requested_native_new_optimizations_upper_bound':75000000,
        'maximum_exported_D20_rows':2500000,'maximum_exported_D3_rows':7500000,
        'same_output_directory_reuses_actual_pilot_packets':True,
        'additional_pending_actual_dependencies':['Actual10k terminal receipt/accounting and measured cost/storage/shortage/mask report',
            'Root review of native parity,actual resource budget and full production projection']}
    S.write_new(out/'pilot.json',pilot);S.write_new(out/'full.json',full)
    return pilot,full


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('storage','policy','proposed-quality','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();prepare(a.storage,a.policy,a.proposed_quality,a.output)


if __name__=='__main__':main()
