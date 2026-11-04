"""Root draft/finalize for an actual CPU component export; no scientific read."""
import argparse,copy,pathlib
from . import contract as C
Q=C.Q;M=C.M

def draft(path,out):
    Q.on_login();root=Q.load(path)
    C.need(root['schema']=='ROOT_REQUESTED_PPRIME_ALPHA_PORTABLE_MAIN_EXPORT_V1'
      and root['status']=='REQUESTED_FOR_REVIEW' and root['requested_by']=='root','EXPLICIT_ROOT_PORTABLE_EXPORT_REQUEST')
    p={k:root[k] for k in (*C.REQUIRED,'node','maximum_molecules','output_cap_bytes')}
    p.update(schema='PPRIME_ALPHA_PORTABLE_MAIN_EXPORT_PLAN_V1',wall_seconds=C.WALL,
      output_directory=str(M.fresh(root['output_directory'],'artifacts')))
    b=C.bootstrap(p);cp=b['component_plan'];p['prepared_shard_header_reference']=b['component_header_reference']
    p['additional_runtime_source_references']=b['additional_runtime_source_references']
    for k in ('original_protocol_reference','source_context_reference','retention_policy_reference'):
        p[k]=cp[k]
    p['scope_parameters']=C.parameters(p);p['data_references']=b['data']
    M.validate_authority(p['resource_authority_reference'],read_small=Q.read_small)
    M.carveout(C.meta(p['root_carveout_review_reference']),{'scope_key':C.KEY,'node':p['node'],
      'resource_authority_reference':p['resource_authority_reference'],'estimated_peak_output_bytes':p['output_cap_bytes']})
    out=M.fresh(out);out.mkdir(parents=True,mode=0o700)
    fields={'kind':'analysis','scope_key':C.KEY,'scope_parameters':p['scope_parameters'],'pilot':False,'wall_seconds':C.WALL,
      'estimated_peak_output_bytes':p['output_cap_bytes'],'source_status_stage':'CLOSED_COMPONENT_PORTABLE_ORIGINAL12_INPUT_EXPORT',
      'execution_argv':[Q.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    p['source_references']=C.unique([*C.sources(p),*b['refs'],*[p[k] for k in C.REQUIRED],Q.pin(path)])
    pr=Q.write_new(out/'plan.json',p);refs=C.unique([*p['source_references'],pr])
    template={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
      **copy.deepcopy(fields),'scope_mode':'BOUNDED_PERFORMANCE_BATCH','bounded_batch_limits_reviewed':True,
      'resource_authority_reference':p['resource_authority_reference'],'stage_output_cap_bytes':p['output_cap_bytes'],
      'parent_evidence_references':b['refs'],'approved_source_references':refs,'data_references':p['data_references'],
      'portable_original12_export_authorized':True,'native_invocations_authorized':False,'preclaim_authorized':False,
      'PREP_parent_C0_claimed':False,'external_assignment_reference':p['external_assignment_reference']}
    tr=Q.write_new(out/'root_review.template.json',template)
    return Q.write_new(out/'draft_receipt.json',{'schema':'PPRIME_ALPHA_PORTABLE_MAIN_EXPORT_DRAFT_V1','plan_reference':pr,
      'template_reference':tr,'stage_fields':fields,'source_references':refs,'data_references':p['data_references'],
      'resource_authority_reference':p['resource_authority_reference'],'scientific_DATA_opened_on_login':False})

def finalize(path,review):
    Q.on_login();d=Q.load(path);C.need(d['schema']=='PPRIME_ALPHA_PORTABLE_MAIN_EXPORT_DRAFT_V1','EXACT_PORTABLE_EXPORT_DRAFT')
    rr=M.approved(d['template_reference'],review);p=C.meta(d['plan_reference']);b=C.bootstrap(p)
    C.need(b['data']==p['data_references']==d['data_references'],'EXACT_DECLARED_CLOSED_COMPONENT_INPUTS')
    for ref in d['source_references']:C.need(Q.pin(ref['path'])==ref,'FROZEN_EXPORT_SOURCES_AND_METADATA')
    return Q.write_new(M.fresh(pathlib.Path(path).parent/'stage_spec.json'),{'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',
      **d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
      'stage_output_cap_bytes':p['output_cap_bytes'],'source_references':d['source_references'],'data_references':d['data_references'],
      'scope':{'mode':'BOUNDED_PERFORMANCE_BATCH','parent_profile':None,'review':rr}})

def close(parent_registration,output):
    """Root post-C0 metadata only; the producer cannot self-sign this wrapper."""
    Q.on_login();entry=Q.load(parent_registration)
    r,p,proof,actual=C.Small.closed_parent(entry,C.KEY,C.MODULE,'PPRIME_ALPHA_PORTABLE_MAIN_EXPORT_RECEIPT_V1')
    manifest=C.small(r['portable_manifest_reference'])
    C.need(r['native_invokes']==r['global_once_claims_created']==0 and r['scientific_PASS'] is False
      and manifest['schema']=='PPRIME_ALPHA_ORIGINAL12_PORTABLE_INPUTS_V1'
      and manifest['prepared_header_reference']==p['prepared_shard_header_reference']
      and manifest['external_assignment_reference']==p['external_assignment_reference']
      and manifest['records']==r['records'] and manifest['MIDs']==r['MIDs'],
      'ACTUAL_EXPORT_C0_COUNTS_AND_SOURCE_NOT_NATIVE_OR_COMMON_RELEASE')
    return Q.write_new(M.fresh(output),{'schema':'ROOT_ACTUAL_PPRIME_ALPHA_PORTABLE_EXPORT_CLOSURE_V1',
      'status':'ACTUAL_CPU_C0_PORTABLE_PACKET_SOURCE_ONLY','reviewer':'root','parent':entry,
      'portable_manifest_reference':r['portable_manifest_reference'],'actual_parent':actual,
      'PREP_parent_C0_claimed':False,'scientific_PASS':False})

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    d=s.add_parser('draft');d.add_argument('--request',required=True);d.add_argument('--output',required=True)
    f=s.add_parser('finalize');f.add_argument('--draft',required=True);f.add_argument('--root-review',required=True)
    c=s.add_parser('close');c.add_argument('--parent-registration',required=True);c.add_argument('--output',required=True)
    a=p.parse_args()
    if a.action=='draft':result=draft(a.request,a.output)
    elif a.action=='finalize':result=finalize(a.draft,a.root_review)
    else:result=close(a.parent_registration,a.output)
    print(result)

if __name__=='__main__':main()
