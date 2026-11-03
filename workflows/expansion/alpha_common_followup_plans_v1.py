"""Metadata-only Root followups from an accepted actual Alpha Common manifest.

Writes fresh templates and sbatch text; never submits or manufactures acceptance.
"""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import shlex
import sys

A=Path('/gfshome/alpha/codex_data_v1_20261026')
D=A/'control/pubchem_completion_environment_20261103'
B=A/'control/pubchem_expansion_runtime_20261103'
BASE=A/'code/pubchem_completion_20261103_497c584'
PACK='workflows.expansion.exact_nn_cached_v1.pack_reference'
BINDER='workflows.expansion.regression_common_scope_v1.run'
FIELDS=('path','bytes','sha256')


def need(value,message):
    if not value:raise ValueError(message)


def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def pin(path):
    path=Path(path).absolute();before=path.stat();raw=path.read_bytes();after=path.stat()
    frame=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    need(frame(before)==frame(after) and not path.is_symlink(),'Stable regular metadata/source required')
    need(path.is_file(),'Regular metadata/source required')
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def triple(ref):return {k:ref[k] for k in FIELDS}


def verify(ref):
    need(pin(ref['path'])==triple(ref),'Current metadata/source bytes differ from declared pin')
    return Path(ref['path'])


def union(*groups):
    result={}
    for refs in groups:
        for ref in refs:
            ref=triple(ref)
            need(ref['path'] not in result or result[ref['path']]==ref,'Conflicting source pins')
            result[ref['path']]=ref
    return list(result.values())


def actual_common_parent(manifest):
    if manifest.get('producer_schema')=='ALPHA_COMMON_GENERIC_REPRESENTATION_REPAIR_COMPLETION_PRODUCER_V1':
        from workflows.expansion.exact_nn_cached_v1.alpha_common_repaired import validate_manifest
        validate_manifest(manifest)
        review=load(verify(manifest['final_Root_graph_review_reference']))
        return review['actual_parent']
    need(manifest.get('status')=='COMPLETE_ALPHA_FULL_COMMON_REFERENCE'
      and manifest.get('producer_schema')=='ALPHA_COMMON_GRAPH_CONTINUATION_PRODUCER_V1'
      and manifest.get('common_molecules')==1196122 and manifest.get('Main_parent_C0_claimed') is False,
      'Accepted actual full Common required; running/source-only is not an input')
    review=load(verify(manifest['final_Root_graph_review_reference']))
    need(review.get('schema')=='ROOT_ALPHA_FULL_COMMON_GRAPH_ACTUAL_ACCEPTANCE_V1'
      and review.get('status')=='APPROVED_EXACT_FULL_COMMON_REFERENCE' and review.get('reviewer')=='root'
      and review.get('producer_receipt')==manifest['actual_full_receipt_reference'], 'Existing independent Root acceptance required')
    parent=review['actual_parent']
    need(parent.get('endpoint')=='218.192.171.238:22' and parent.get('uid')==1264
      and parent.get('State')=='COMPLETED' and parent.get('ExitCode')=='0:0', 'Actual Alpha C0 required')
    account=load(verify(review['actual_accounting_reference']))
    need(parent in account['actual_parents'],'Existing actual accounting must contain the accepted parent')
    return parent


def original_regression(transport):
    need(transport.get('schema')=='PUBCHEM_PARENT_TRANSPORT_MANIFEST_V1'
      and transport.get('status')=='VERIFIED_REPLICAS_CLOSED'
      and transport.get('actual_transport_hash_verification') is True
      and transport.get('destination')==dict(endpoint='218.192.171.238:22',uid=1264), 'Closed real Alpha transport required')
    rows=transport['replicas'];need(len(rows)==9,'All nine original regression replicas required')
    by_name={Path(row['replica_reference']['path']).name:row for row in rows}
    need(len(by_name)==9,'Unambiguous original replica names required')
    for row in rows:
        need(row['origin_endpoint']=='202.38.247.57:22' and row['origin_uid']==1278
          and all(row['source_reference'][k]==row['replica_reference'][k] for k in ('bytes','sha256')),
          'Main UID1278 origin must remain exact; no Alpha impersonation')
    oldrow=by_name['original_full_v3_receipt.json'];accountrow=by_name['4520414_actual_accounting.json']
    old=load(verify(oldrow['replica_reference']));account=load(verify(accountrow['replica_reference']))
    need(old['uid']==1278 and str(old['job_id'])=='4520414'
      and old['status']=='FULL_X_RULE_PASS_COMMON_SCOPE_PENDING'
      and old['full_v1_selection_regression_passed'] is False and old['common_population_scope_bound'] is False,
      'Immutable original regression remains pending Common binding')
    parents=account.get('actual_parents') or [account.get('actual_parent',{})]
    matches=[p for p in parents if str(p.get('JobIDRaw',p.get('job_id')))=='4520414']
    need(len(matches)==1 and matches[0].get('State',matches[0].get('state'))=='COMPLETED'
      and matches[0].get('ExitCode',matches[0].get('exit_code'))=='0:0','Actual original Main C0 required')
    # Large Parquets are intentionally not rehashed on the metadata host. The
    # admitted SQL producer opens and hashes all actual data via its held FD.
    return triple(oldrow['source_reference']),triple(accountrow['source_reference'])


def launcher_argv(python,launcher,base,entry,module,tag,control,template,rpc):
    need(module in (PACK,BINDER),'Fixed scientific stage module required')
    need(tag and '/' not in tag and '..' not in tag,'Simple separate stage tag required')
    return [str(python),'-I','-B',str(launcher),'--template',str(template),
      '--base-root',str(base),'--entry',str(entry),'--module',module,'--tag',tag,
      '--control-root',str(control),'--gluster-rpc-program',str(rpc)]


def sbatch(argv,base,control,tag):
    return '\n'.join(['#!/bin/bash','#SBATCH --partition=cpu','#SBATCH --nodelist=compute-0-1',
      '#SBATCH --nodes=1','#SBATCH --ntasks=1','#SBATCH --cpus-per-task=16',
      '#SBATCH --time=0','#SBATCH --job-name='+tag,
      '#SBATCH --output='+str(control/(tag+'_%j.out')),'set -euo pipefail',
      'unset SBATCH_MEM_PER_NODE SBATCH_MEM_PER_CPU SBATCH_MEM_PER_GPU',
      'export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1',
      'cd '+shlex.quote(str(base)),'exec '+shlex.join(argv),''])


def save(path,value):
    with Path(path).open('x',encoding='utf-8') as stream:
        json.dump(value,stream,sort_keys=True,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    return pin(path)


def build(args):
    need(os.getuid()==1264 and sys.flags.isolated,'Run isolated metadata builder on actual Alpha UID1264')
    manifest=load(args.common_manifest)
    exact=load(args.exact_deployment);reg=load(args.regression_deployment);resource=load(args.resource_template)
    need(exact['base_code_root']==str(args.base),'Exact deployed clean base required')
    exact_refs=exact['code_references'];reg_refs=reg['code_references']
    for ref in union(exact_refs,reg_refs,resource['code_references']):verify(ref)
    # Reuse the existing metadata consumer checks, including all1196122 census,
    # source/spawn proof,4 readbacks and immutable Main STOPPED provenance.
    exact_entry=Path(verify(exact.get('entry_reference') or next(r for r in exact_refs if Path(r['path']).name=='layer_entry.py')))
    reg_entry=verify(reg['entry_reference'])
    sys.path[:0]=[str(exact_entry.parent),str(args.base)]
    importlib.invalidate_caches()
    parent=actual_common_parent(manifest)
    if manifest.get('producer_schema')=='ALPHA_COMMON_GENERIC_REPRESENTATION_REPAIR_COMPLETION_PRODUCER_V1':
        from workflows.expansion.exact_nn_cached_v1.alpha_common_repaired import validate_manifest
    else:
        from workflows.expansion.exact_nn_cached_v1.alpha_common import validate_manifest
    validate_manifest(manifest)
    common_ref=pin(args.common_manifest);transport=load(args.regression_transport)
    old_ref,account_ref=original_regression(transport)
    transport_ref=pin(args.regression_transport)
    keep=('runtime_profile_reference','quota_snapshot','quota_authority','minimum_free_bytes',
      'minimum_node_available_bytes','output_scope_root','output_cap_bytes','other_future_reserved_bytes',
      'other_future_closed_scope_credit_reference')
    resources={k:resource[k] for k in keep if k in resource}
    need(resources['output_cap_bytes']==300000000000 and resources['other_future_reserved_bytes']==986736873472
      and resources['minimum_free_bytes']==200000000000 and resources['minimum_node_available_bytes']==24<<30,
      'Use reviewed conservative shared exact scope reservations without invented credit')
    verify(resources['runtime_profile_reference'])
    resources['quota_authority']=dict(resources['quota_authority']);resources['quota_authority'].pop('publisher',None)
    resources['workers']=16
    common_sources=union(resource['code_references'],exact_refs,reg_refs,
      [pin(args.launcher),pin(args.rpc_program),pin(__file__)])
    for ref in resource.get('scientific_source_references',[]):verify(ref)
    lineage=dict(common_reference_manifest=common_ref,accepted_Alpha_Common_parent=parent,
      Main_origin_parent_C0_claimed=False,source_template_reference=pin(args.resource_template),
      exact_source_deployment_reference=pin(args.exact_deployment),regression_source_deployment_reference=pin(args.regression_deployment),
      scientific_source_references=resource.get('scientific_source_references',[]),code_references=common_sources)
    pack={**resources,**lineage,'schema':'PUBCHEM_EXACT_REFERENCE_PACK_PLAN_V1','scope_key':'reference_before_pack_v1',
      'reference_role':'before','input_manifest':common_ref,'parent_rss_cap_bytes':8<<30,
      'software_rss_budget_bytes':8<<30,'sqlite_cache_bytes':1<<30}
    binder={**resources,**lineage,'schema':'ALPHA_COMMON_SELECTION_REGRESSION_BIND_PLAN_V1',
      'scope_key':'regression_common_scope_v1','original_full_regression_reference':old_ref,
      'original_regression_accounting_reference':account_ref,'parent_transport_manifest':transport_ref,
      'software_rss_budget_bytes':48<<30,'duckdb_memory_bytes':32<<30}
    need(not args.output_directory.exists(),'Fresh builder output required; preserve all earlier plans')
    args.output_directory.mkdir(parents=True)
    outputs=[]
    for label,plan,module,entry in [('reference_before',pack,PACK,exact_entry),('regression_common',binder,BINDER,reg_entry)]:
        tag=args.tag_prefix+'_'+label;template=args.output_directory/(label+'_plan_template.json')
        plan['output_directory']=str(Path(plan['output_scope_root'])/(tag+'_LAUNCHER_ASSIGN_REAL_JOB_ID'))
        plan_ref=save(template,plan)
        argv=launcher_argv(A/'software/pubchem_completion_20261103_venv/bin/python',args.launcher,args.base,entry,module,tag,args.control_root,template,args.rpc_program)
        batch=args.output_directory/(label+'.sbatch')
        with batch.open('x',encoding='utf-8',newline='\n') as stream:stream.write(sbatch(argv,args.base,args.control_root,tag))
        outputs.append(dict(template=plan_ref,sbatch=pin(batch),launcher_argv=argv,module=module,tag=tag,
          expected_actual_control_directory=str(args.control_root/(tag+'_job_<actual-job-id>')),
          expected_actual_output_directory=str(Path(plan['output_scope_root'])/(tag+'_job_<actual-job-id>'))))
    return save(args.output_directory/'build_receipt.json',dict(schema='ALPHA_ACCEPTED_COMMON_FOLLOWUP_PLAN_BUILD_V1',
      status='TEMPLATES_PREPARED_NOT_SUBMITTED',builder_reference=pin(__file__),uid=os.getuid(),
      common_manifest=common_ref,accepted_Alpha_parent=parent,original_Main_regression_uid=1278,
      original_Main_regression_reference=old_ref,metadata_only=True,production_started=False,outputs=outputs))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--common-manifest',required=True,type=Path)
    p.add_argument('--output-directory',required=True,type=Path)
    p.add_argument('--tag-prefix',default='common_followup')
    p.add_argument('--resource-template',type=Path,default=B/'common_graph_grouped_node_plan_template.json')
    p.add_argument('--exact-deployment',type=Path,default=D/'audit_exact_06a5bfd_actual_deployment.json')
    p.add_argument('--regression-deployment',type=Path,default=D/'regression_common_bc4669c_actual_deployment.json')
    p.add_argument('--regression-transport',type=Path,default=A/'inputs/regression_full_v3_original_replicas_20261103/source_transport.json')
    p.add_argument('--base',type=Path,default=BASE)
    p.add_argument('--launcher',type=Path,default=D/'node_launcher_rpc_v3_resume.py')
    p.add_argument('--rpc-program',type=Path,default=D/'gluster_readonly_rpc.py')
    p.add_argument('--control-root',type=Path,default=B/'node_epochs')
    args=p.parse_args();print(json.dumps(build(args),sort_keys=True))


if __name__=='__main__':main()
