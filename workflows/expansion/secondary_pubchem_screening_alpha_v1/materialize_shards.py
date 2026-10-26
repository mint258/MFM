"""Pure partition validation plus immutable single-manifest ordinal claims; no submit."""
import os
from . import contracts as C,source
from secondary_cpu_queue_v1 import common as Q

def proposed(parts,index_reference,inventory_reference,parts_per_shard=1):
    Q.need(type(parts_per_shard) is int and 1<=parts_per_shard<=C.PARTS,'FINITE_PARTS_PER_SHARD_REQUIRED')
    rows=[]
    for first in range(0,len(parts),parts_per_shard):
        last=min(len(parts)-1,first+parts_per_shard-1)
        rows.append({'shard_index':len(rows),'first_part':first,'last_part':last,
            'first_ordinal':parts[first]['first_ordinal'],'last_ordinal':parts[last]['last_ordinal']})
    value={'schema':'ALPHA_PUBCHEM_EXCLUSIVE_ORDINAL_MANIFEST_V1','status':'PROPOSED_NOT_ROOT_FROZEN',
        'source_raw_sha256':C.RAW_SHA,'source_index_reference':index_reference,'alpha_inventory_receipt_reference':inventory_reference,
        'population_N':C.N,'part_count':C.PARTS,'shards':rows,'profile_receipt_reference':None,'pool_release_authorized':False}
    validate(value);return value

def validate(value):
    Q.need(value['schema']=='ALPHA_PUBCHEM_EXCLUSIVE_ORDINAL_MANIFEST_V1' and value['source_raw_sha256']==C.RAW_SHA
        and value['population_N']==C.N and value['part_count']==C.PARTS and value['pool_release_authorized'] is False,'EXACT_FULL_PHYSICAL_SOURCE_PARTITION')
    next_part=0;next_ordinal=1
    for index,row in enumerate(value['shards']):
        Q.need(row['shard_index']==index and row['first_part']==next_part and row['first_ordinal']==next_ordinal
            and row['first_part']<=row['last_part']<C.PARTS and row['first_ordinal']<=row['last_ordinal']<=C.N,
            'NONOVERLAPPING_CONTIGUOUS_COMPLETE_ORDINAL_AND_PART_RANGES')
        next_part=row['last_part']+1;next_ordinal=row['last_ordinal']+1
    Q.need(next_part==C.PARTS and next_ordinal==C.N+1,'NO_HOLE_OR_OMITTED_RAW_ROW_IN_FULL_PARTITION')
    return value

def freeze_metadata(proposed_value,actual_profile_reference,budget_reference):
    import copy
    value=copy.deepcopy(validate(proposed_value));value.update(status='ROOT_FROZEN_EXCLUSIVE_SUBMISSION_MANIFEST',
        profile_receipt_reference=actual_profile_reference,profile_output_budget_reference=budget_reference)
    return value

def claim(plan,proof):
    manifest=validate(Q.load_ref(plan['full_shard_manifest_reference']))
    Q.need(manifest['status']=='ROOT_FROZEN_EXCLUSIVE_SUBMISSION_MANIFEST'
        and manifest['profile_receipt_reference']==plan['accepted_profile_receipt_reference']
        and manifest['profile_output_budget_reference']==plan['profile_output_budget_reference'],'ACTUAL_PROFILE_BOUND_ROOT_FROZEN_PARTITION_REQUIRED')
    matches=[row for row in manifest['shards'] if row['shard_index']==plan['shard_index']]
    Q.need(len(matches)==1 and all(matches[0][key]==plan[key] for key in ('first_part','last_part','first_ordinal','last_ordinal')),'EXACT_SELECTED_SHARD_MEMBER')
    base=C.ROOT/'control/pubchem_ordinal_claims'/C.RAW_SHA;base.mkdir(parents=True,exist_ok=True)
    global_path=base/'frozen_manifest_claim.json'
    try:Q.write_new(global_path,{'manifest_reference':plan['full_shard_manifest_reference'],'raw_sha256':C.RAW_SHA})
    except FileExistsError:Q.need(Q.load(global_path)['manifest_reference']==plan['full_shard_manifest_reference'],'OTHER_PARTITION_MANIFEST_ALREADY_CLAIMED')
    path=base/('shard_%06d.json'%plan['shard_index'])
    return Q.write_new(path,{'manifest_reference':plan['full_shard_manifest_reference'],'plan_reference':proof['plan_reference'],
        'job_id':str(proof['job_id']),'node':proof['node'],'uid':1264,'range':matches[0],
        'automatic_retry_or_release':False,'partial_jobs_require_independent_Root_recovery':True})
