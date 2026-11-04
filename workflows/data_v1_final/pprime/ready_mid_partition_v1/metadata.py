"""Small actual registration -> separate exact generic16 review, no DATA IO."""
import argparse,pathlib
from . import contract as C
def fresh(path):
    path=pathlib.Path(path);C.need(path.is_absolute()and C.ROOT/'control'in path.parents and not path.exists()
      and not any(p.is_symlink()for p in(path,*path.parents)),'FRESH_PURE_METADATA_DIRECTORY');path.mkdir(parents=True);return path
def draft(request_path,output):
    C.Q.on_login();r=C.Q.load(request_path);C.need(r['schema']=='ROOT_REQUESTED_PPRIME_READY_MID_PARTITION_V1'
      and r['status']=='REQUESTED_FOR_REVIEW'and r['requested_by']=='root','ROOT_EXACT_PARTITION_REQUEST')
    out=fresh(output);p={k:v for k,v in r.items()if k not in('schema','status','requested_by')}
    C.need(all(type(p.get(k))is dict for k in C.REQUIRED)and type(p.get('main190_registration'))is dict,'ACTUAL_RESOURCES_AND_FOUR_PARENT_REFS_NOT_FUTURE_PINS')
    p.update(schema='PPRIME_READY_MID_PARTITION_PLAN_V1',requested_cpus=16,wall_seconds=86400)
    p['scope_parameters']=C.parameters(p);C.validate(p);parent,b,parents,data=C.registration(p)
    sources=C.unique([*parents,*(p[k]for k in C.REQUIRED),*C.sources(),C.Q.pin(request_path)]);p.update(source_references=sources,data_references=C.unique(data))
    ref=C.Q.write_new(out/'plan.json',p);sources=C.unique([*sources,ref])
    fields={'kind':'analysis','scope_key':C.KEY,'scope_parameters':p['scope_parameters'],'pilot':False,'wall_seconds':86400,
      'estimated_peak_output_bytes':p['whole_output_cap_bytes'],'source_status_stage':'READONLY_DISJOINT_READY_MID_PARTITION',
      'execution_argv':[C.PY,'-B','-m',C.MODULE,'--plan',ref['path'],'--startup-proof','__ROOT_STARTUP_PROOF__']}
    template={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,**fields,
      'scope_mode':'BOUNDED_PERFORMANCE_BATCH','resource_authority_reference':p['resource_authority_reference'],
      'stage_output_cap_bytes':p['whole_output_cap_bytes'],'parent_evidence_references':parents,'approved_source_references':sources,
      'data_references':p['data_references'],'bounded_batch_limits_reviewed':True,'resource_current_context_reviewed':False,
      'Source3_same_parent_no_native_active_DB_or_claim_write':True}
    tr=C.Q.write_new(out/'root_review.template.json',template)
    return C.Q.write_new(out/'draft.json',{'schema':'PPRIME_READY_MID_PARTITION_DRAFT_V1','plan_reference':ref,'template_reference':tr,
      'fields':fields,'source_references':sources,'data_references':p['data_references'],'resource_authority_reference':p['resource_authority_reference']})
def finalize(path,root_review):
    C.Q.on_login();d=C.Q.load(path);r=C.Q.pin(root_review);review=C.meta(r);template=C.meta(d['template_reference'])
    C.need(r!=d['template_reference']and review['status']=='APPROVED_FOR_EXACT_STAGE'and review['reviewer']=='root'
      and review['resource_current_context_reviewed']is True,'INDEPENDENT_ROOT_EXACT_RESOURCE_REVIEW')
    for k,v in template.items():
        if k not in('status','reviewer','resource_current_context_reviewed'):C.need(review[k]==v,'EXACT_REVIEW_FIELD:'+k)
    for ref in d['source_references']:C.need(C.Q.pin(ref['path'])==ref,'CURRENT_INSTALLED_SOURCE_REGISTRATION_PIN')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
      'stage_output_cap_bytes':d['fields']['estimated_peak_output_bytes'],'source_references':d['source_references'],'data_references':d['data_references'],
      'scope':{'mode':'BOUNDED_PERFORMANCE_BATCH','parent_profile':None,'review':r}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=C.Q.read_small)
    return C.Q.write_new(pathlib.Path(path).parent/'stage_spec.json',spec)
def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('draft');p.add_argument('--request',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('finalize');p.add_argument('--draft',required=True);p.add_argument('--root-review',required=True);a=parser.parse_args()
    print(draft(a.request,a.output)if a.action=='draft'else finalize(a.draft,a.root_review))
if __name__=='__main__':main()
