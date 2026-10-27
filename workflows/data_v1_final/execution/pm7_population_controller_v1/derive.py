"""Materialize only exact Root range-delegated versions of frozen candidates."""
from __future__ import annotations
import argparse,pathlib
from . import contract as C
from workflows.data_v1_final.conformers.pm7_population_cache_v1 import metadata as M,contract as P


def delegation(review_ref,launch_ref):
    return {'mode':C.POLICY,'root_range_review_reference':review_ref,'actual_materializer_launch_reference':launch_ref,
        'individual_human_job_review_claimed':False,'new_scientific_authority_created':False}


def build(root,batch,row,review,review_ref,launch_ref,wall):
    directory=root/'stages'/batch;C.need(not directory.exists(),'EXISTING_STAGE_METADATA_NO_AUTOMATIC_REGENERATION')
    directory.mkdir(parents=True,mode=0o700);candidate=directory/'candidate';candidate.mkdir()
    args=argparse.Namespace(file_group=row['file_group'],shard_index=row['shard_index'],offset=0,limit=row['molecules'],
        quota_reuse_review=pathlib.Path(review['resource_template_review_reference']['path']),previous_parent_accounting=[],previous_submission=[])
    M.candidate(args,candidate)
    plan=M.load(candidate/'plan_candidate.json');quota=M.load(candidate/'quota_candidate.json')
    C.need(plan['selection']==dict(file_group=row['file_group'],shard_index=row['shard_index'],offset=0,limit=row['molecules'])
        and quota['preserved_previous_reserve_bytes']==review['non_PM7_future_output_reserve_bytes']+C.CAP
        and quota['whole_wave_output_reserve_bytes']==review['non_PM7_future_output_reserve_bytes']+C.POOL,'EXACT_ROOT_POOL_TEMPLATE_ARITHMETIC')
    stamp=delegation(review_ref,launch_ref)
    # The actual Root range approval explicitly authorizes only these status /
    # provenance changes. This is not a child signing a new human approval.
    plan.update(status=P.STATUS,reviewer='root',approval_derivation=stamp)
    plan['metadata_source_references']=M.unique([*plan['metadata_source_references'],*review['source_references'],review_ref,launch_ref])
    quota.update(status='APPROVED_RESOURCE_FACT_REUSE_ONLY',reviewer='root',approval_derivation=stamp,
        runtime_pool_reserve_policy='BASE_PLUS_TWO64GIB_SLOTS_NOT247',reserved_pool_slots=2,
        reserved_slots_are_not_job_allocations=True)
    plan_ref=M.write(directory/'plan.json',plan);quota_ref=M.write(directory/'quota_review.json',quota)
    output=P.BASE/'full247_v1'/batch/'run_v1'
    draft=directory/'draft';draft.mkdir()
    stage=argparse.Namespace(plan=pathlib.Path(plan_ref['path']),quota_reuse_review=pathlib.Path(quota_ref['path']),
        stage_output=output,wall_seconds=wall,scope_review=None)
    M.stage(stage,draft);scope=M.load(draft/'scope_candidate.json')
    C.need(scope['scope_key']==P.SCOPE and scope['scope_parameters']==P.scope(plan['selection'])
        and scope['stage_output_cap_bytes']==C.CAP and scope['wall_seconds']==wall,'FROZEN_SCOPE_ONLY')
    scope.update(status='APPROVED_FOR_EXACT_STAGE',reviewer='root',root_review_reason=review['root_reason'],approval_derivation=stamp)
    scope_ref=M.write(directory/'scope_review.json',scope)
    final=directory/'final';final.mkdir();stage.scope_review=pathlib.Path(scope_ref['path']);M.stage(stage,final)
    return M.pin(final/'stage_spec.json'),str(output),stamp
