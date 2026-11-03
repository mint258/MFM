"""Root invokes after graph review: actual Alpha accounting + existing finalizer.

Metadata only. Never submit jobs, accept a partial producer or claim Main C0.
"""
import argparse
import csv
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys


def need(value,message):
    if not value:raise ValueError(message)


def pin(path):
    path=Path(path).absolute();raw=path.read_bytes()
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def save(path,value):
    with Path(path).open('x',encoding='utf-8') as stream:
        json.dump(value,stream,sort_keys=True,ensure_ascii=False,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    return pin(path)


def close_after_root_review(producer_path,directory,layer,base):
    need(os.getuid()==1264,'Run actual Alpha metadata closure as alpha, never Main identity')
    # This is the existing verified two-level namespace layout, not a copied
    # Main data tree or a modification of either immutable code directory.
    sys.path[:0]=[str(layer),str(base)]
    workflows=importlib.import_module('workflows')
    workflows.__path__=[str(layer/'workflows'),str(base/'workflows')]
    expansion=importlib.import_module('workflows.expansion')
    expansion.__path__=[str(layer/'workflows/expansion'),str(base/'workflows/expansion')]
    from workflows.expansion.exact_nn_cached_v1 import alpha_common as A
    producer=json.loads(producer_path.read_text());component=A.component_ready(producer)
    job=str(producer['job_id']);need(job.isdecimal(),'Actual numeric Alpha parent job required')
    fields=['JobIDRaw','User','UID','State','ExitCode','ElapsedRaw','AllocCPUS','NodeList','Partition']
    argv=['sacct','-X','-n','-P','-j',job,'--format=JobIDRaw,User,UID,State%24,ExitCode,ElapsedRaw,AllocCPUS,NodeList,Partition']
    queried=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    need(queried.returncode==0,'Actual sacct query failed')
    values=[row for row in csv.reader(io.StringIO(queried.stdout.decode()),delimiter='|') if row and row[0].strip()==job]
    need(len(values)==1 and len(values[0])>=len(fields),'Exactly one actual parent accounting row required')
    parent={key:value.strip() for key,value in zip(fields,values[0])}
    need(parent['State']=='COMPLETED' and parent['ExitCode']=='0:0' and parent['UID']=='1264' and parent['User']=='alpha',
      'Actual Alpha C0 required; running/stopped/failed parents cannot close')
    parent.update(endpoint='218.192.171.238:22',uid=int(parent['UID']))
    need(not directory.exists(),'Fresh Root closure directory required; preserve previous records')
    directory.mkdir(parents=True)
    raw=directory/'actual_sacct.txt';raw.write_bytes(queried.stdout)
    accounting=dict(schema='ALPHA_COMMON_ACTUAL_PARENT_ACCOUNTING_V1',endpoint='218.192.171.238:22',uid=os.getuid(),
      command_argv=argv,query_returncode=queried.returncode,query_stderr=queried.stderr.decode(),
      raw_sacct_reference=pin(raw),actual_parents=[parent],
      allocated_core_seconds=int(parent['AllocCPUS'])*int(parent['ElapsedRaw']),
      source_helper_reference=pin(__file__),Main_parent_C0_claimed=False)
    account_ref=save(directory/'actual_accounting.json',accounting)
    # Invocation is Root's existing review step. No child executes this helper
    # automatically, and a source-only/partial receipt fails above before writes.
    review=dict(schema='ROOT_ALPHA_FULL_COMMON_GRAPH_ACTUAL_ACCEPTANCE_V1',status='APPROVED_EXACT_FULL_COMMON_REFERENCE',reviewer='root',
      producer_receipt=pin(producer_path),Main_parent_C0_claimed=False,original_graph_variants_and_HOLD_reviewed=True,
      actual_parent=parent,actual_accounting_reference=account_ref,
      exact_common_census=component['expected_all_common_census'],
      io_policy_reference=producer.get('io_policy_reference'),grouped_io_source_tests=producer.get('grouped_io_source_tests'),
      D7_or_orders_release=False)
    review_ref=save(directory/'root_actual_graph_review.json',review)
    output=directory/'common_reference_manifest.json'
    result=A.finalize(producer_path,Path(review_ref['path']),output)
    return dict(consumer_manifest=pin(output),root_review=review_ref,actual_accounting=account_ref,
      existing_finalizer_source=pin(A.__file__),status=result['status'],common_molecules=result['common_molecules'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--producer',type=Path,required=True)
    parser.add_argument('--output-directory',type=Path,required=True)
    parser.add_argument('--layer',type=Path,default=Path('/gfshome/alpha/codex_data_v1_20261026/code/exact_uff_runtime_cb98b34_namespace_v2'))
    parser.add_argument('--base',type=Path,default=Path('/gfshome/alpha/codex_data_v1_20261026/code/pubchem_completion_20261103_497c584'))
    args=parser.parse_args();print(json.dumps(close_after_root_review(args.producer,args.output_directory,args.layer,args.base),sort_keys=True))


if __name__=='__main__':main()
