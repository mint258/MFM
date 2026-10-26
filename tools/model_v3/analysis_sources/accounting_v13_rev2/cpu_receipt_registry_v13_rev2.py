"""Strict top-level CPU receipt bindings; no scheduler calls or GPU inference."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import stat

P=Path('/share/home/zixiao/descriptor_analysis')
O=P/'runs/model_v3_20261025';N=P/'runs/model_v3_20261026'
CPU_SCHEMAS={'model_v3_single_CPU_submission_v1','model_v3_queued_CPU_submission_v1'}


def require(ok,message):
    if not ok:raise ValueError(message)


def raw_ref(path,cap=16<<20):
    path=Path(path).absolute();before=path.stat()
    require(path==path.resolve(strict=True) and stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid()
        and before.st_nlink==1 and before.st_size<=cap,'Owned physical bounded metadata required')
    raw=path.read_bytes();after=path.stat()
    require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
        (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'Metadata changed while binding')
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def read(path):
    before=raw_ref(path)
    def pairs(items):
        result={}
        for key,value in items:require(key not in result,'Duplicate JSON key');result[key]=value
        return result
    value=json.loads(Path(path).read_bytes(),object_pairs_hook=pairs,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON literal')))
    require(raw_ref(path)==before,'Metadata changed while parsing');return value


def bound(value):
    require(set(value)=={'path','bytes','sha256'} and raw_ref(value['path'])==value,'Exact raw reference differs')
    return read(value['path'])


def option(argv,name):
    values=[value.split('=',1)[1] for value in argv if value.startswith(name+'=')]
    require(len(values)==1,'One explicit '+name+' required');return values[0]


def cpu_receipt(path):
    path=Path(path);require(path.parent in (O,N),'CPU registry only accepts immediate O/N receipts')
    value=read(path);schema=value.get('schema');require(schema in CPU_SCHEMAS,'Known actual CPU receipt schema required')
    job=value['job_id'];require(type(job) is str and re.fullmatch('[1-9][0-9]*',job),'Exact actual CPU parent jobID required')
    if schema=='model_v3_single_CPU_submission_v1':
        argv=value['argv'];require(type(value['sbatch_returncode']) is int and value['sbatch_returncode']==0
            and value['stdout'].split(';',1)[0].strip()==job,'Actual CPU sbatch result differs')
        require(type(value['cpus']) is int and value['cpus']>=16,'Original CPU request must have>=16CPUs')
        cpus=value['cpus'];fields=['schema','job_id','argv','sbatch_returncode','stdout','node','cpus']
    else:
        argv=value['actual_sbatch_argv'];require(value['mode']=='QUEUED_ONLY'
            and type(value['actual_sbatch_returncode']) is int and value['actual_sbatch_returncode']==0,
            'Actual queued CPU sbatch result differs')
        stdout=value['raw_submission']['stdout'];stderr=value['raw_submission']['stderr']
        require(raw_ref(stdout['path'])==stdout and raw_ref(stderr['path'])==stderr,
            'Actual raw queued submission stream differs')
        require(Path(stdout['path']).read_text().split(';',1)[0].strip()==job,'Raw queued sbatch job token differs')
        require(type(value['cpus_requested']) is int and value['cpus_requested']>=16,'Queued CPU request must have>=16CPUs')
        cpus=value['cpus_requested'];fields=['schema','job_id','actual_sbatch_argv','actual_sbatch_returncode',
            'raw_submission.stdout','raw_submission.stderr','node','cpus_requested','mode']
    require(type(argv) is list and all(type(item) is str for item in argv) and Path(argv[0]).name=='sbatch'
        and option(argv,'--partition')=='cpu' and int(option(argv,'--cpus-per-task'))==cpus
        and option(argv,'--nodelist')==value['node']
        and re.fullmatch('compute-0-(?:2|[8-9]|1[0-9])',value['node']),'Explicit actual CPU partition/node/request required')
    require(not any(item.startswith(('--gres','--gpus','--gpu-bind','--gpu-freq')) for item in argv),
        'CPU receipt must not request/route GPU resources')
    return dict(job_id=job,submission_receipt=str(path),submission_receipt_sha256=raw_ref(path)['sha256'],
        receipt_job_id_field='job_id',receipt_schema=schema,verified_receipt_fields=fields,
        expected_node=value['node'],requested_cpus=cpus,classification='CPU_ONLY_EXPLICIT_RECEIPT')


def load_cpu_registry(path):
    registry=read(path);require(registry['schema']=='model_v3_explicit_CPU_receipt_registry_v1','Explicit CPU registry schema required')
    entries=registry['jobs'];require(type(entries) is list and 0<len(entries)<=1024,'Finite nonempty CPU registry required')
    ids=set();refs=[]
    for entry in entries:
        checked=cpu_receipt(entry['submission_receipt'])
        require(checked==entry,'CPU registry source fields/hash/schema differ')
        require(entry['job_id'] not in ids,'Duplicate actual CPU job in registry')
        ids.add(entry['job_id']);refs.append(raw_ref(entry['submission_receipt']))
        if entry['receipt_schema']=='model_v3_queued_CPU_submission_v1':
            original=read(entry['submission_receipt'])
            refs += [original['raw_submission']['stdout'],original['raw_submission']['stderr']]
    return registry,ids,refs


def top_cpu_inventory():
    """Top-level metadata only. Legacy grouped inputs remain bound by prior accounting."""
    result=[];files=[];ids=set();total=0
    for root in (O,N):
        paths=sorted(path for path in root.iterdir() if path.is_file() and re.search(r'submi.*\.json$',path.name,re.I))
        require(len(files)+len(paths)<=1024,'Top receipt file-count bound exceeded')
        for path in paths:
            value=read(path);reference=raw_ref(path);total+=reference['bytes']
            require(total<=16<<20,'Top receipt metadata byte bound exceeded')
            if type(value) is list:
                require(path==O/'A_first_candidates_export_submission_v1.json' and len(value)==2
                    and [item['job_id'] for item in value]==['4520456','4520457'],
                    'Unknown top-level array receipt requires explicit review')
                files.append(dict(receipt=reference,schema=None,classification='LEGACY_ARRAY_RETAINED_BY_PREVIOUS_EXACT_GPU_SCOPE',
                    legacy_array_job_fields=[dict(job_id=item['job_id'],field=str(index)+'.job_id')
                        for index,item in enumerate(value)]))
                continue
            require(type(value) is dict,'Explicit top-level receipt metadata object required')
            schema=value.get('schema')
            row=dict(receipt=reference,schema=schema,top_level_fields=sorted(value),classification='OTHER_TOP_LEVEL_SUBMISSION_METADATA')
            if schema in CPU_SCHEMAS:
                entry=cpu_receipt(path);require(entry['job_id'] not in ids,'Duplicate actual top-level CPU receipt')
                ids.add(entry['job_id']);result.append(entry);row.update(classification='CPU_ONLY_EXPLICIT_RECEIPT',job_id=entry['job_id'],verified_receipt_fields=entry['verified_receipt_fields'])
            elif schema=='model_v3_CPU_node_submission_v1':
                row['classification']='LEGACY_GROUPED_CPU_RECEIPT_RETAINED_BY_PREVIOUS_LEDGER'
                row['legacy_grouped_job_fields']=[dict(job_id=item['job_id'],field='submitted.'+str(index)+'.job_id')
                    for index,item in enumerate(value['submitted'])]
            else:
                require(not(re.fullmatch('compute-0-(?:2|[8-9]|1[0-9])',str(value.get('node','')))
                    and any(value.get(key) for key in ('job_id','actual_job_id','actual_sbatch_job_id'))),
                    'Unrecognized actual CPU-node receipt cannot be silently excluded')
                for key in ('argv','actual_sbatch_argv'):
                    argv=value.get(key,[])
                    require(type(argv) is not list or '--partition=cpu' not in argv,'Unrecognized actual CPU receipt cannot be silently excluded')
            files.append(row)
    return sorted(result,key=lambda row:int(row['job_id'])),files
