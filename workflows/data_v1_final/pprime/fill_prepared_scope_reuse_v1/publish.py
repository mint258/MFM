"""Publish only newly closed prepared files; no old payload/scope copies or pool."""
import os,pathlib,uuid
from . import io_adapter as A
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v2 import publication as Original
P=pathlib.Path


def publish(prepared,closures,component_ref,scope_ref,plan,proof,local,persistent,budget):
    local=P(local);persistent=P(persistent);h=A.meta(prepared['header'])
    refs=[prepared['index'],prepared['source_audit'],h['consumed_prior_reference'],h['audit_membership_reference'],prepared['header']]
    audit=A.meta(prepared['audit']);refs.append(A.triple(audit['selected_records']))
    refs.extend(v['reference']for v in closures);refs=A.unique(refs)
    n=sum(r['bytes']for r in refs);budget.check()
    A.need(n<=plan['persistent_cap_bytes'],'ACTUAL_NEW_CLOSED_COMPONENT_WITHIN_ROOT_CANDIDATE_CAP')
    name='component_%05d'%A.meta(component_ref)['component_index'];final=persistent/name;temp=persistent/('.partial_'+name+'_'+uuid.uuid4().hex)
    A.need(not final.exists(),'FRESH_PERSISTENT_PREPARED_COMPONENT');temp.mkdir();mapping=[]
    for ref in refs:
        relative=P(ref['path']).relative_to(local);target=temp/relative
        # Exact original same-FD/hash/copy/reopen function. Only the destination
        # is new Lustre instead of the former Main32G PREP pool.
        copied=Original.copy_ref(ref,target)
        mapping.append(dict(origin_reference=ref,target_reference=dict(copied,path=str(final/relative))))
        budget.check()
    def remote(ref):return Original.relocated(A.triple(ref),mapping)
    metadata=dict(schema='PPRIME_CLOSED_DEVSHM_TO_LUSTRE_COMPONENT_V1',status='BYTE_IDENTICAL_CLOSED_NEW_PREPARATION_OUTPUTS',
      actual_preparation_job_id=str(proof['job_id']),actual_node=plan['node'],source_scope_reference=scope_ref,
      generation_component_reference=component_ref,local_origin_root=str(local),entries=mapping,all_file_SHA_bytes_equal=True,
      original_scientific_bytes_rewritten=False,old_scope_or_dataset_payload_copied=False,new_QM_calls=0,uses_Main_PREP_pool=False)
    store=A.Store(temp,4<<20,budget);store.json(temp/'publication_manifest.json',metadata)
    for directory in sorted({temp,*[p.parent for p in temp.rglob('*')]},key=lambda p:len(p.parts),reverse=True):
        fd=os.open(directory,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
    os.rename(temp,final);fd=os.open(persistent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    pub=Original.I.pin(final/'publication_manifest.json',[persistent])
    # Audit metadata is rebased explicitly; its selected rows remain same bytes.
    selected_remote=remote(audit['selected_records'])
    audit['selected_records']=dict(selected_remote,rows=audit['selected_records']['rows'])
    small=A.Store(persistent,16<<20,budget);audit_ref=small.json(persistent/(name+'_audit_membership.json'),audit)
    header=dict(schema='PPRIME_CPU_CLOSED_ASSIGNED_PAIRS_HEADER_V2',records=prepared['records'],MIDs=prepared['MIDs'],
      index_reference=remote(prepared['index']),source_audit_reference=remote(prepared['source_audit']),
      audit_selected_reference=selected_remote,audit_membership_reference=audit_ref,
      pilot_reuse_reference=prepared['reuse'],publication_manifest_reference=pub,source_context_reference=plan['source_context_reference'],
      original_protocol_reference=plan['original_protocol_reference'],generation_shard_header_reference=component_ref,
      generation_partition_QA_reference=scope_ref,shared_prepare_plan_reference=A.pin_small(plan['plan_path']),
      shared_prepare_proof_reference=A.pin_small(plan['proof_path']),native_invokes=0,production_once_written=False,
      native_physical_IDs_and_original_first2_input_hashes_verified=True,final_Common_or_training_admission=False,
      preparation_storage='DEVSHM_WORK_LUSTRE_PERSISTENT_NO_MAIN_POOL',direct_Lustre_publication=True,
      operational_consumed_records_not_retried=h['additional_consumed_physical_records_not_retried'],
      original_parent_4525659_upgraded=False)
    return small.json(persistent/(name+'_prepared_header.json'),header)