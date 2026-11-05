"""Standalone Alpha metadata builder: actual D27 bindings/templates, never DATA or sbatch."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shlex
import stat
import sys

MODULE='workflows.expansion.common_train_d27_reference_v1.run'
ALPHA='218.192.171.238:22'
FIELDS=('path','bytes','sha256')
BUDGET_SHA='bce95fa0d4d7a24dbfb806a14c54e11e56195aa3083ad98b489fafea28df1c7a'
DEPLOYMENT_SHA='d3b33ce07e5892bc84757723ca97557be4193a5f731ef95c034c3ddecc9da8a9'
COMMON_SHA='bb249520721976617361806e4724df5f1079a93108ab5cb0c3f27d711cbe44b7'
INVENTORY_SHA='98dd3af0eb61032da66de0ae2f5561ee20614bbaf70312f0891c9268f3c7ad0d'
BINDINGS=('source_catalog_reference','canonical_index','logical_group_plan_reference','field_map_reference',
    'diagnostic_delivery_reference','original_mask_config_reference')
SCIENCE=('codec','calibration','compact','projection','owner_support')


def need(ok,message):
    if not ok:raise ValueError(message)


def triple(ref):return {k:ref[k]for k in FIELDS}


def pin(path):
    path=Path(path).absolute();before=path.lstat()
    need(stat.S_ISREG(before.st_mode)and before.st_uid==1264 and before.st_size<=32<<20,'Own small regular Alpha metadata/source only')
    raw=path.read_bytes();after=path.lstat()
    attrs=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    need(attrs(before)==attrs(after),'Closed metadata/source changed')
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def verify(ref):
    need(pin(ref['path'])==triple(ref),'Exact current metadata/source pin required:'+ref['path'])
    return Path(ref['path'])


def load(path):return json.loads(Path(path).read_bytes())


def read(ref):return load(verify(ref))


def save(path,body):
    with Path(path).open('x',encoding='utf-8')as stream:
        json.dump(body,stream,sort_keys=True,separators=(',',':'),allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    return pin(path)


def parent_job(parent):return str(parent.get('JobIDRaw',parent.get('job_id','')))


def actual_c0(review,job):
    need(review.get('reviewer')=='root','Independent actual Root review required')
    parent=review['actual_parent'];account=read(review['actual_accounting_reference'])
    need(parent.get('endpoint',account.get('endpoint'))==ALPHA and str(parent.get('uid',parent.get('UID')))=='1264'
        and parent_job(parent)==str(job)and parent.get('State')=='COMPLETED'and parent.get('ExitCode')=='0:0'
        and parent in account['actual_parents'],'Actual Alpha C0/accounting required, never placeholder or Main parent')
    verify(account['raw_sacct_reference']);return parent


def closed_transport(review_path,inventory_path):
    review_ref=pin(review_path);review=load(review_path)
    need(review.get('schema')=='ROOT_PUBCHEM_D27_ALPHA_TRANSPORT_ACTUAL_ACCEPTANCE_V1'
        and review.get('status')=='APPROVED_EXACT_D27_INPUT_REPLICAS','Actual Root-accepted closed transport required')
    receipt_ref=review['producer_receipt_reference'];receipt=read(receipt_ref)
    need(receipt['schema']=='PUBCHEM_D27_ALPHA_TRANSPORT_ACTUAL_CLOSE_V1'
        and receipt['status']=='WHOLE_REPLICAS_VERIFIED_PENDING_ACTUAL_PARENT_C0_AND_ROOT_REVIEW',
        'Real native transport close producer required')
    parent=actual_c0(review,receipt['actual_parent']['JobIDRaw'])
    need(receipt['actual_parent']['endpoint']==ALPHA and receipt['actual_parent']['uid']==1264,
        'Preserve actual Alpha native transport identity')
    transport_ref=review['transport_manifest_reference'];transport=read(transport_ref)
    inventory_ref=pin(inventory_path);inventory=load(inventory_path)
    need(inventory_ref['bytes']==9787915 and inventory_ref['sha256']==INVENTORY_SHA,'Actual frozen original transfer inventory required')
    need(receipt['transport_manifest_reference']==transport_ref and receipt['inventory_reference']==inventory_ref
        and transport['source_inventory_reference']==inventory_ref,'Exact accepted transport/producer/inventory binding required')
    need(transport['schema']=='PUBCHEM_PARENT_TRANSPORT_MANIFEST_V1'and transport['status']=='VERIFIED_REPLICAS_CLOSED'
        and transport['destination']==dict(endpoint=ALPHA,uid=1264)and transport['actual_transport_hash_verification']is True,
        'Actual own closed Alpha replicas, not planned paths')
    expected={tuple(row['source_reference'][k]for k in FIELDS):row for row in inventory['files']};observed={}
    for row in transport['replicas']:
        key=tuple(row['source_reference'][k]for k in FIELDS)
        need(key in expected and key not in observed and triple(row['replica_reference'])==triple(expected[key]['replica_reference'])
            and row['origin_endpoint']=='202.38.247.57:22'and row['origin_uid']==1278
            and row['whole_Alpha_replica_SHA_verified']is True,'Every exact Main origin/actual Alpha replica must remain bound')
        frame=row['actual_Alpha_frame'];ref=row['replica_reference']
        need(len(frame)==7 and frame[2]==1264 and frame[3]==1 and frame[4]==ref['bytes'],'Actual native Alpha single-link closed FD evidence required')
        observed[key]=row
    unique={row['replica_reference']['path']:row['replica_reference']for row in observed.values()}
    need(set(observed)==set(expected)and len(expected)==11490 and len(unique)==11488
        and sum(ref['bytes']for ref in unique.values())==12475282830,'Whole exact D27 transport census, never a subset')
    bindings=inventory['source_bindings']
    need(set(BINDINGS)<=set(bindings),'All original source bindings required')
    for name in BINDINGS:need(tuple(bindings[name][k]for k in FIELDS)in observed,'Binding missing from accepted replica map:'+name)
    return dict(review_reference=review_ref,receipt_reference=receipt_ref,transport_reference=transport_ref,
        inventory_reference=inventory_ref,parent=parent,bindings={k:bindings[k]for k in BINDINGS})


def accepted_common(path):
    ref=pin(path);common=load(path)
    need(ref['bytes']==3566 and ref['sha256']==COMMON_SHA
        and common['producer_schema']=='ALPHA_COMMON_GENERIC_REPRESENTATION_REPAIR_COMPLETION_PRODUCER_V1'
        and common['status']=='COMPLETE_ALPHA_FULL_COMMON_GENERIC_REPRESENTATION_REPAIRED_REFERENCE'
        and common['common_molecules']==1196122 and common['exact_common_census']['molecules_by_role']=={'TRAIN':1188592,'VAL':7530}
        and common['Main_parent_C0_claimed']is False,'Exact actually accepted full Common176 reference required')
    review=read(common['final_Root_graph_review_reference'])
    need(review['schema']=='ROOT_ALPHA_FULL_COMMON_GENERIC_REPRESENTATION_REPAIR_ACTUAL_ACCEPTANCE_V1'
        and review['status']=='APPROVED_EXACT_FULL_COMMON_GENERIC_REPRESENTATION_REPAIRED_REFERENCE'
        and review['producer_receipt']==common['actual_full_receipt_reference'],'Actual full Common review remains bound')
    actual_c0(review,'1885176');return ref


def union(*groups):
    result={}
    for group in groups:
        for ref in group:
            ref=triple(ref);need(ref['path']not in result or result[ref['path']]==ref,'Conflicting deployed source references')
            verify(ref);result[ref['path']]=ref
    return list(result.values())


def build(args):
    need(os.getuid()==1264 and sys.flags.isolated==1,'Run standalone metadata builder on actual Alpha with Python-I')
    # A missing transport review fails before making any executable artifact.
    transport=closed_transport(args.transport_review,args.transfer_inventory)
    common_ref=accepted_common(args.common_manifest)
    deployment_ref=pin(args.deployment);dep=load(args.deployment)
    need(deployment_ref['bytes']==43495 and deployment_ref['sha256']==DEPLOYMENT_SHA,'Actual immutable47-source deployment required')
    science=dep['scientific_sources'];need(set(science)==set(SCIENCE),'Actual five imported scientific module refs required')
    for ref in science.values():verify(ref)
    need(pin(args.entry)==triple(dep['entry_reference']),'Actual guarded47-source entry required')
    budget_ref=pin(args.storage_budget)
    need(budget_ref['bytes']==18667 and budget_ref['sha256']==BUDGET_SHA,'Actual reviewed Root V2 budget required')
    resource=load(args.resource_template);resource_ref=pin(args.resource_template)
    keep=('runtime_profile_reference','quota_snapshot','quota_authority','other_future_closed_scope_credit_reference')
    resources={key:resource[key]for key in keep if key in resource}
    need('runtime_profile_reference'in resources and 'quota_snapshot'in resources and 'quota_authority'in resources,'Existing actual Alpha runtime/quota authority template required')
    verify(resources['runtime_profile_reference'])
    resources['quota_authority']=dict(resources['quota_authority']);resources['quota_authority'].pop('publisher',None)
    scope=Path('/gfshome/alpha/pubchem_expansion_20261103/exact')
    need(args.workers>=16 and args.software_rss_budget_bytes>0,'Reviewed actual CPU/resource declaration required')
    need(all(re.fullmatch('[A-Za-z0-9_.-]+',value)for value in(args.tag,args.node,args.partition))
        and '..'not in args.tag,'Simple fixed Slurm node/partition/tag tokens required')
    code=union(resource.get('code_references',[]),dep['code_references'],list(science.values()),
        [pin(args.entry),pin(args.launcher),pin(args.rpc_program),pin(__file__)])
    need(not args.output_directory.exists(),'Fresh metadata builder output required; preserve prior plans')
    args.output_directory.mkdir(parents=True)
    inputs=dict(schema='PUBCHEM_FULL_COMMON_TRAIN_D27_INPUT_BINDINGS_V1',**transport['bindings'],
        parent_transport_manifest=transport['transport_reference'],scientific_sources=science,common_reference_manifest=common_ref)
    inputs_ref=save(args.output_directory/'bindings.json',inputs)
    resources.update(endpoint=ALPHA,uid=1264,workers=args.workers,output_scope_root=str(scope),output_cap_bytes=300000000000,
        other_future_reserved_bytes=1001736873472,minimum_free_bytes=200000000000,
        minimum_node_available_bytes=24<<30,software_rss_budget_bytes=args.software_rss_budget_bytes,
        sqlite_cache_bytes=1<<30,code_references=code,reviewed_storage_budget_reference=budget_ref,
        actual_transport_Root_review_reference=transport['review_reference'],actual_transport_close_receipt_reference=transport['receipt_reference'],
        original_transfer_inventory_reference=transport['inventory_reference'],source_deployment_reference=deployment_ref,
        source_resource_template_reference=resource_ref,
        output_directory=str(scope/(args.tag+'_LAUNCHER_ASSIGN_REAL_JOB_ID')))
    resource_out_ref=save(args.output_directory/'resources.json',resources)
    plan=dict(**resources,**{k:v for k,v in inputs.items()if k!='schema'},
        schema='PUBCHEM_FULL_COMMON_TRAIN_D27_REFERENCE_PLAN_V1',scope_key='fullCommon_train_d27_reference_v1',
        input_bindings_reference=inputs_ref,source_resources_reference=resource_out_ref,
        calibration_scope='fullCommon AND effectiveTRAIN AND NOT originalD5 PM7 base; original record/atom weighting',
        new_UFF_geometry_QM_Pprime_or_R_N_fit=False,mask_over_one_percent_policy='REPORT_ONLY_NO_RECORD_DELETION')
    template=args.output_directory/'fit_plan_template.json';template_ref=save(template,plan)
    argv=[str(args.python),'-I','-B',str(args.launcher),'--template',str(template),'--base-root',str(args.base),
        '--entry',str(args.entry),'--module',MODULE,'--tag',args.tag,'--control-root',str(args.control_root),
        '--gluster-rpc-program',str(args.rpc_program)]
    script='\n'.join(['#!/bin/bash','#SBATCH --partition='+args.partition,'#SBATCH --nodelist='+args.node,
        '#SBATCH --nodes=1','#SBATCH --ntasks=1','#SBATCH --cpus-per-task='+str(args.workers),
        '#SBATCH --time=0','#SBATCH --job-name='+args.tag,'#SBATCH --output='+str(args.control_root/(args.tag+'_%j.out')),
        'set -euo pipefail','unset SBATCH_MEM_PER_NODE SBATCH_MEM_PER_CPU SBATCH_MEM_PER_GPU',
        'export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1',
        'cd '+shlex.quote(str(args.base)),'exec '+shlex.join(argv),''])
    batch=args.output_directory/'fit.sbatch'
    with batch.open('x',encoding='utf-8',newline='\n')as stream:stream.write(script)
    return save(args.output_directory/'build_receipt.json',dict(schema='PUBCHEM_ACTUAL_D27_FIT_TEMPLATE_BUILD_V1',
        status='ACTUAL_INPUTS_BOUND_TEMPLATES_PREPARED_NOT_SUBMITTED',metadata_only=True,new_data_fit_started=False,
        bindings_reference=inputs_ref,resources_reference=resource_out_ref,template_reference=template_ref,sbatch_reference=pin(batch),
        builder_reference=pin(__file__),actual_transport_parent=transport['parent'],actual_transport_Root_review=transport['review_reference'],
        common_reference_manifest=common_ref,deployment_reference=deployment_ref,reviewed_storage_budget_reference=budget_ref,
        deployment_native_source_tests4_policy=dep['native_source_tests4_before_DATA'],
        prior_actual_native_source_tests_reference=pin(args.native_source_tests)if args.native_source_tests else None,launcher_argv=argv))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in('transport-review','transfer-inventory','common-manifest','deployment','storage-budget','resource-template',
            'entry','launcher','rpc-program','base','python','control-root','output-directory'):
        p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--native-source-tests',type=Path,help='Optional actual179 native4 JSON reference; never creates a fixture result')
    p.add_argument('--node',required=True);p.add_argument('--partition',default='cpu');p.add_argument('--tag',default='d27_fullCommon_train_v1')
    p.add_argument('--workers',type=int,default=16);p.add_argument('--software-rss-budget-bytes',type=int,default=64<<30)
    args=p.parse_args();print(json.dumps(build(args),sort_keys=True),flush=True)


if __name__=='__main__':main()
