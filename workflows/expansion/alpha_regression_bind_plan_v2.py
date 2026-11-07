"""Prepare fresh Alpha SQL-only Common regression templates; never submit."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys

A=Path('/gfshome/alpha/codex_data_v1_20261026')
B=A/'control/pubchem_expansion_runtime_20261103'
D=A/'control/pubchem_completion_environment_20261103'
BASE=A/'code/pubchem_completion_20261103_497c584'
MODULE='workflows.expansion.regression_common_scope_v1.run'
FIELDS=('path','bytes','sha256')


def need(value,message):
    if not value:raise ValueError(message)


def pin(path):
    path=Path(path).absolute();s=path.stat()
    need(path.is_file() and not path.is_symlink() and s.st_size<=2<<20,
         'Only small regular metadata/source files are read by this builder')
    raw=path.read_bytes();t=path.stat()
    frame=lambda x:(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns)
    need(frame(s)==frame(t),'Metadata/source changed during read')
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def triple(ref):return {k:ref[k] for k in FIELDS}


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def verify(ref):
    need(pin(ref['path'])==triple(ref),'Actual small metadata/source differs from pin')
    return Path(ref['path'])


def unique(*groups):
    values={}
    for group in groups:
        for ref in group:
            ref=triple(ref)
            need(ref['path'] not in values or values[ref['path']]==ref,'Conflicting source pins')
            values[ref['path']]=ref
    return list(values.values())


def save(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,sort_keys=True,separators=(',',':'));stream.write('\n')
    return pin(path)


def build(a):
    need(os.getuid()==1264 and sys.flags.isolated,'Run isolated on actual Alpha UID1264')
    common=read(verify(pin(a.common_manifest)))
    need(common.get('producer_schema')=='ALPHA_COMMON_GENERIC_REPRESENTATION_REPAIR_COMPLETION_PRODUCER_V1'
      and common.get('status')=='COMPLETE_ALPHA_FULL_COMMON_GENERIC_REPRESENTATION_REPAIRED_REFERENCE'
      and common['common_molecules']==1196122 and common['current_HOLD_molecules']==0
      and common['original_HOLD_molecules']==119 and common['Main_parent_C0_claimed'] is False,
      'Require actual complete repaired Common authority, preserving historical HOLD')
    review=read(verify(common['final_Root_graph_review_reference']))
    need(review['schema']=='ROOT_ALPHA_FULL_COMMON_GENERIC_REPRESENTATION_REPAIR_ACTUAL_ACCEPTANCE_V1'
      and review['status']=='APPROVED_EXACT_FULL_COMMON_GENERIC_REPRESENTATION_REPAIRED_REFERENCE'
      and review['reviewer']=='root' and review['producer_receipt']==common['actual_full_receipt_reference'],
      'Existing Root actual Common acceptance required')
    parent=review['actual_parent'];account=read(verify(review['actual_accounting_reference']))
    need(parent['State']=='COMPLETED' and parent['ExitCode']=='0:0' and parent['endpoint']=='218.192.171.238:22'
      and str(parent.get('UID',parent.get('uid')))=='1264' and parent in account['actual_parents'],
      'Actual Alpha Common C0 must remain separate from original Main state')
    transport=read(verify(pin(a.regression_transport)))
    need(transport['schema']=='PUBCHEM_PARENT_TRANSPORT_MANIFEST_V1'
      and transport['status']=='VERIFIED_REPLICAS_CLOSED' and len(transport['replicas'])==9
      and transport['actual_transport_hash_verification'] is True
      and transport['destination']==dict(endpoint='218.192.171.238:22',uid=1264),
      'Existing nine original Main regression replicas must be closed')
    by_name={}
    for row in transport['replicas']:
        origin=row['source_reference'];replica=row['replica_reference']
        need(row['origin_endpoint']=='202.38.247.57:22' and row['origin_uid']==1278
          and origin['bytes']==replica['bytes'] and origin['sha256']==replica['sha256'],
          'Preserve exact original Main source provenance')
        name=Path(replica['path']).name;need(name not in by_name,'Unambiguous original replica basenames')
        by_name[name]=row
    oldrow=by_name['original_full_v3_receipt.json'];old=read(verify(oldrow['replica_reference']))
    accountrow=by_name['4520414_actual_accounting.json'];oldaccount=read(verify(accountrow['replica_reference']))
    need(old['status']=='FULL_X_RULE_PASS_COMMON_SCOPE_PENDING' and old['job_id']=='4520414'
      and old['uid']==1278 and old['evaluated_records']==15879477
      and old['full_v1_selection_regression_passed'] is False and old['common_population_scope_bound'] is False,
      'Bind the immutable full original regression, never relabel it as PASS')
    parents=oldaccount.get('actual_parents') or [oldaccount.get('actual_parent',{})]
    need(any(str(p.get('JobIDRaw',p.get('job_id')))=='4520414' and p.get('State',p.get('state'))=='COMPLETED'
      and p.get('ExitCode',p.get('exit_code'))=='0:0' for p in parents),'Actual original Main regression C0 required')
    deployment=read(verify(pin(a.source_deployment)))
    need(deployment['base_code_root']==str(a.base),'Deployment clean base must match launcher cwd')
    refs=deployment['code_references'];entry=verify(deployment['entry_reference'])
    suffixes=('regression_common_scope_v1/run.py','regression_common_scope_v1/sql.py',
      'regression_common_scope_v1/source.py','regression_common_scope_v1/test_sql.py',
      'regression_common_scope_v1/finalize.py','exact_nn_cached_v1/alpha_common_repaired.py',
      'exact_nn_cached_v1/alpha_common.py','alpha_common_graph_continuation_v1/io.py',
      'common_molecular_fp_candidate_v1/census.py','portable_sources_v1/transport.py','alpha_runtime_v1/guard.py')
    for suffix in suffixes:need(any(r['path'].endswith('/'+suffix) for r in refs),'Missing deployed dependency: '+suffix)
    resource=read(verify(pin(a.resource_template)));budget=read(verify(pin(a.budget_review)))
    need(budget['schema']=='ROOT_ALPHA_ALL_FUTURE_STORAGE_BUDGET_V2' and budget['reviewer']=='root'
      and budget['endpoint']=='218.192.171.238:22' and budget['uid']==1264,'Actual shared Alpha V2 budget required')
    keep=('runtime_profile_reference','quota_authority','quota_snapshot','minimum_node_available_bytes',
      'output_scope_root','other_future_closed_scope_credit_reference')
    plan={k:resource[k] for k in keep if k in resource}
    need(plan['output_scope_root']=='/gfshome/alpha/pubchem_expansion_20261103/exact',
      'Use the aggregate exact scope, not an independent extra allowance')
    plan.update(output_cap_bytes=budget['scope_total_caps_bytes']['exact'],
      other_future_reserved_bytes=budget['other_future_reserved_bytes_for_each_scope']['exact'],
      minimum_free_bytes=budget['minimum_free_after_all_future_bytes'])
    need(plan['output_cap_bytes']==300000000000 and plan['minimum_free_bytes']==200000000000,
      'Preserve reviewed exact cap and floor')
    verify(plan['runtime_profile_reference'])
    plan['quota_authority']=dict(plan['quota_authority']);plan['quota_authority'].pop('publisher',None)
    sources=unique(refs,[deployment['entry_reference'],pin(a.launcher),pin(a.rpc_program),pin(__file__)])
    for ref in sources:verify(ref)
    plan.update(schema='ALPHA_COMMON_SELECTION_REGRESSION_BIND_PLAN_V1',scope_key='regression_common_scope_v1',
      endpoint='218.192.171.238:22',uid=1264,workers=16,software_rss_budget_bytes=48<<30,
      duckdb_memory_bytes=32<<30,common_reference_manifest=pin(a.common_manifest),
      accepted_Alpha_Common_parent=parent,Main_origin_parent_C0_claimed=False,
      original_full_regression_reference=triple(oldrow['source_reference']),
      original_regression_accounting_reference=triple(accountrow['source_reference']),
      parent_transport_manifest=pin(a.regression_transport),code_references=sources,
      future_budget_review_reference=pin(a.budget_review),source_template_reference=pin(a.resource_template),
      regression_source_deployment_reference=pin(a.source_deployment),
      output_directory=str(Path(plan['output_scope_root'])/(a.tag+'_LAUNCHER_ASSIGN_REAL_JOB_ID')))
    need(not a.output_directory.exists(),'Fresh output namespace required')
    a.output_directory.mkdir(parents=True)
    template=a.output_directory/'regression_common_plan_template.json';pref=save(template,plan)
    sm=save(a.output_directory/'source_metadata_manifest.json',dict(schema='ALPHA_REGRESSION_BIND_SOURCE_METADATA_MANIFEST_V2',
      status='SOURCE_AND_METADATA_PINNED_NOT_EXECUTED',code_references=sources,
      large_input_SHA_deferred_to_admitted_native_SQL_binder=True,source_deployment=pin(a.source_deployment)))
    argv=[str(A/'software/pubchem_completion_20261103_venv/bin/python'),'-I','-B',str(a.launcher),
      '--template',str(template),'--base-root',str(a.base),'--entry',str(entry),'--module',MODULE,
      '--tag',a.tag,'--control-root',str(a.control_root),'--gluster-rpc-program',str(a.rpc_program)]
    batch=a.output_directory/'regression_common.sbatch'
    lines=['#!/bin/bash','#SBATCH --job-name='+a.tag,'#SBATCH --partition=cpu','#SBATCH --nodelist=compute-0-1',
      '#SBATCH --cpus-per-task=16','#SBATCH --time=0','#SBATCH --output='+str(a.control_root/(a.tag+'_%j.out')),
      'set -euo pipefail','cd '+shlex.quote(str(a.base)),
      'export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1',shlex.join(argv)]
    with batch.open('x',encoding='utf-8',newline='\n') as stream:stream.write('\n'.join(lines)+'\n')
    return save(a.output_directory/'build_receipt.json',dict(schema='ALPHA_REGRESSION_BIND_PLAN_BUILD_V2',
      status='PREPARED_NOT_SUBMITTED',metadata_only=True,large_bodies_read=False,approval_created=False,
      template_reference=pref,source_metadata_manifest=sm,sbatch_reference=pin(batch),launcher_argv=argv,
      expected_finalizer_module='workflows.expansion.regression_common_scope_v1.finalize'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-deployment',required=True,type=Path)
    p.add_argument('--output-directory',required=True,type=Path)
    p.add_argument('--tag',default='corrected_pool_Common_regression_v2')
    p.add_argument('--common-manifest',type=Path,default=Path('/gfshome/alpha/pubchem_expansion_20261103/exact/fullCommon_representation_repaired_completion_v1_job_1885176/fullCommon_repaired_manifest.json'))
    p.add_argument('--regression-transport',type=Path,default=A/'inputs/regression_full_v3_original_replicas_20261103/source_transport.json')
    p.add_argument('--resource-template',type=Path,default=B/'all11_actual_exclusion_index_v3_plans/index_plan_template.json')
    p.add_argument('--budget-review',type=Path,default=B/'all_future_storage_budget_v2_20261104.json')
    p.add_argument('--base',type=Path,default=BASE)
    p.add_argument('--launcher',type=Path,default=D/'node_launcher_rpc_v3_resume.py')
    p.add_argument('--rpc-program',type=Path,default=D/'gluster_readonly_rpc.py')
    p.add_argument('--control-root',type=Path,default=B/'node_epochs')
    print(json.dumps(build(p.parse_args()),sort_keys=True))


if __name__=='__main__':main()
