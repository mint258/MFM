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
AUTO_CPU_SCHEMAS={'model_v3_single_CPU_submission_auto_memory_v1',
    'model_v3_CPU_automatic_memory_source_checker_submission_v1'}
CPU_SCHEMAS |= AUTO_CPU_SCHEMAS
CPU_INTENT_SCHEMA='model_v3_single_CPU_submission_auto_memory_intent_v1'
CPU_INTENT_PEERS={N/(slug+'_full_auto_pre_v1_Root_submission_intent_v1.json'):
    O/(slug+'_full_auto_pre_v1_part0_submission_v4.json')
    for slug in ('A_acceptance_v2','C_bias_free','residual_fp32','tensor_math')}
INTENT_CLASSIFICATION='INTENT_ONLY_BOUND_TO_ACTUAL_NO_ADDITIONAL_JOB'


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


def auto_script(argv,value,*,nested,node,cpus):
    """Observed automatic-memory layouts with exact optional duplicate bindings."""
    require(type(argv) is list and all(type(item) is str for item in argv)
        and len(argv)>=3 and argv[0]=='sbatch','Typed actual auto CPU sbatch argv required')
    script=Path(argv[-1]);require(script.is_absolute() and script.parent in (O,N)
        and script.suffix=='.sbatch','Immediate owned O/N sbatch script required')
    reference=raw_ref(script)
    if nested:
        require(type(value['script']) is dict and set(value['script'])=={'path','bytes','sha256'}
            and value['script']==reference,'Nested actual submission script raw reference differs')
        require(argv==['sbatch','--parsable',str(script)],'Exact nested no-override sbatch invocation required')
    else:
        require(type(value['script_sha256']) is str and re.fullmatch('[0-9a-f]{64}',value['script_sha256'])
            and value['script_sha256']==reference['sha256'],'Flat actual submission script SHA differs')
        require(argv==['sbatch','--parsable','--partition=cpu','--nodelist='+node,
            '--cpus-per-task='+str(cpus),str(script)],'Exact flat CPU/no-memory invocation required')
        if 'script' in value:
            require(type(value['script']) is dict and set(value['script'])=={'path','bytes','sha256'}
                and value['script']==reference,'Flat optional actual script raw reference differs')
    directives={};active=True
    allowed={'partition','nodelist','cpus-per-task','job-name','time','output','error'}
    for line in script.read_text().splitlines():
        stripped=line.strip()
        if stripped.startswith('#SBATCH'):
            require(active and line.startswith('#SBATCH '),'Active canonical SBATCH header required')
            match=re.fullmatch(r'#SBATCH --([a-z][a-z0-9-]*)=([^\s]+)',line)
            require(match is not None,'Only explicit long SBATCH key=value headers supported')
            key,item=match.groups()
            require(key in allowed and key not in directives,'Unknown/duplicate/GPU/memory SBATCH directive refused')
            directives[key]=item
        elif stripped and not stripped.startswith('#'):active=False
    require(directives.get('partition')=='cpu' and directives.get('cpus-per-task')==str(cpus),
        'Bound script must itself declare CPU partition and16 CPUs')
    if nested:require(directives.get('nodelist')==node,'Nested script must declare exact actual CPU node')
    elif 'nodelist' in directives:require(directives['nodelist']==node,'Flat script/argv node differs')
    require(raw_ref(script)==reference,'Bound submission script changed during directive parsing')
    return reference


def auto_cpu_receipt(path,value,job):
    schema=value['schema'];has_actual='actual_sbatch' in value
    flat_keys={'sbatch_returncode','stdout','stderr','script_sha256'}
    present=flat_keys.intersection(value)
    require(not present or present==flat_keys,'Partial flat/mixed submission result fields refused')
    flat=bool(present);nested=not flat
    require(value['requested_memory_MiB'] is None and type(value['submission_memory_environment']) is dict
        and value['submission_memory_environment']=={},'Auto receipt must declare null memory/no environment override')
    fields=['schema','job_id','requested_memory_MiB','submission_memory_environment']
    if schema=='model_v3_CPU_automatic_memory_source_checker_submission_v1':
        require(nested and has_actual and value['authority']=='ROOT_ACTUAL' and value['actual_sbatch_job_id']==job
            and value['Slurm_memory_request_mode']=='site_default_automatic_no_explicit_request'
            and value['removed_SBATCH_environment_keys']==[] and 'argv' not in value,
            'Exact automatic-memory source-checker receipt declaration required')
        node=value['expected_node'];cpus=value['requested_CPUs']
        fields+=['authority','actual_sbatch_job_id','Slurm_memory_request_mode',
            'removed_SBATCH_environment_keys','expected_node','requested_CPUs']
    else:
        require(schema=='model_v3_single_CPU_submission_auto_memory_v1'
            and value['Slurm_memory_mode']=='automatic_default','Known single automatic-memory declaration required')
        node=value['node'];cpus=value['cpus'];fields+=['Slurm_memory_mode','node','cpus']
    require(type(node) is str and re.fullmatch('compute-0-(?:2|[8-9]|1[0-9])',node)
        and type(cpus) is int and cpus==16,'Actual automatic CPU node and exact16 CPUs required')
    if flat:
        require(schema=='model_v3_single_CPU_submission_auto_memory_v1',
            'Only the observed single-CPU schema may carry flat result fields')
        argv=value['argv'];code=value['sbatch_returncode'];stdout=value['stdout'];stderr=value['stderr']
        fields+=['argv','sbatch_returncode','stdout','stderr','script_sha256']
        if has_actual:
            actual=value['actual_sbatch']
            require(type(actual) is dict and set(actual)=={'argv','returncode','stdout','stderr'}
                and type(actual['returncode']) is int
                and actual==dict(argv=argv,returncode=code,stdout=stdout,stderr=stderr),
                'Mixed nested observation must exactly duplicate every flat submission result')
            fields+=['actual_sbatch.argv','actual_sbatch.returncode','actual_sbatch.stdout','actual_sbatch.stderr']
        if 'script' in value:fields+=['script']
    else:
        require(has_actual,'Complete nested or complete flat actual submission result required')
        actual=value['actual_sbatch']
        require(type(actual) is dict and set(actual)=={'argv','returncode','stdout','stderr'},
            'Exact nested actual sbatch observation required')
        argv=actual['argv'];code=actual['returncode'];stdout=actual['stdout'];stderr=actual['stderr']
        if schema=='model_v3_single_CPU_submission_auto_memory_v1':
            require(value['argv']==argv,'Nested duplicated actual argv differs');fields+=['argv']
        fields+=['actual_sbatch.argv','actual_sbatch.returncode','actual_sbatch.stdout','actual_sbatch.stderr','script']
    require(type(code) is int and code==0 and type(stdout) is str and type(stderr) is str and stderr==''
        and stdout.split(';',1)[0].strip()==job,'Actual automatic CPU sbatch result/job differs')
    script=auto_script(argv,value,nested=nested,node=node,cpus=cpus)
    fields+=['script.#SBATCH.partition','script.#SBATCH.cpus-per-task']
    fields+=['script.#SBATCH.nodelist'] if nested else ['argv.--nodelist']
    return dict(job_id=job,submission_receipt=str(path),submission_receipt_sha256=raw_ref(path)['sha256'],
        receipt_job_id_field='job_id',receipt_schema=schema,verified_receipt_fields=fields,
        expected_node=node,requested_cpus=cpus,classification='CPU_ONLY_EXPLICIT_RECEIPT',
        submission_script=script,receipt_shape=('AUTO_NESTED_BOUND_SBATCH' if nested else
            'AUTO_CONSISTENT_MIXED' if has_actual or 'script' in value else 'AUTO_FLAT_EXPLICIT_ARGV'))

def cpu_receipt(path):
    path=Path(path);require(path.parent in (O,N),'CPU registry only accepts immediate O/N receipts')
    value=read(path);schema=value.get('schema');require(schema in CPU_SCHEMAS,'Known actual CPU receipt schema required')
    job=value['job_id'];require(type(job) is str and re.fullmatch('[1-9][0-9]*',job),'Exact actual CPU parent jobID required')
    if schema in AUTO_CPU_SCHEMAS:return auto_cpu_receipt(path,value,job)
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


def cpu_intent(path):
    """Only four known pre-submit records, bound to actual parents; never jobs."""
    path=Path(path);require(path in CPU_INTENT_PEERS,'Unreviewed CPU intent path refused')
    reference=raw_ref(path);value=read(path)
    require(value['schema']==CPU_INTENT_SCHEMA and not set(value).intersection({
        'job_id','actual_job_id','actual_sbatch_job_id','job_ids','actual_sbatch',
        'sbatch_returncode','actual_sbatch_returncode','returncode','stdout','stderr',
        'raw_submission','submission_result'}),'Intent must not contain a jobID or submission result')
    peer_path=CPU_INTENT_PEERS[path];peer_ref=raw_ref(peer_path)
    checked=cpu_receipt(peer_path);peer=read(peer_path)
    require(checked['receipt_schema']=='model_v3_single_CPU_submission_auto_memory_v1'
        and checked['submission_receipt_sha256']==peer_ref['sha256']
        and type(peer['intent']) is dict and set(peer['intent'])=={'path','bytes','sha256'}
        and peer['intent']==reference,'Actual CPU receipt must bind this exact original intent')
    keys=('argv','node','cpus','script_sha256','bindings','requested_memory_MiB',
        'Slurm_memory_mode','submission_memory_environment')
    require(all(value[key]==peer[key] for key in keys)
        and type(value['cpus']) is int and value['cpus']==16
        and type(value['bindings']) is dict and value['bindings']
        and value['requested_memory_MiB'] is None and value['Slurm_memory_mode']=='automatic_default'
        and type(value['submission_memory_environment']) is dict
        and value['submission_memory_environment']=={},'Intent and actual CPU request/bindings/auto-memory differ')
    require(raw_ref(path)==reference and raw_ref(peer_path)==peer_ref,'Intent/actual peer changed while binding')
    return dict(classification=INTENT_CLASSIFICATION,actual_peer_receipt=peer_ref,
        peer_job_id=checked['job_id'],verified_intent_fields=['schema','absence_of_job_and_result_fields',
            'actual_peer.intent',*keys],additional_actual_jobs=0)

def load_cpu_registry(path):
    registry=read(path);require(registry['schema']=='model_v3_explicit_CPU_receipt_registry_v1','Explicit CPU registry schema required')
    entries=registry['jobs'];require(type(entries) is list and 0<len(entries)<=1024,'Finite nonempty CPU registry required')
    ids=set();refs=[]
    for entry in entries:
        checked=cpu_receipt(entry['submission_receipt'])
        require(checked==entry,'CPU registry source fields/hash/schema differ')
        require(entry['job_id'] not in ids,'Duplicate actual CPU job in registry')
        ids.add(entry['job_id']);refs.append(raw_ref(entry['submission_receipt']))
        if entry['receipt_schema'] in AUTO_CPU_SCHEMAS:refs.append(entry['submission_script'])
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
            elif schema==CPU_INTENT_SCHEMA:
                row.update(cpu_intent(path))
                require(raw_ref(path)==reference,'Top inventory intent raw bytes changed')
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
    require(all(row['peer_job_id'] in ids for row in files if row['classification']==INTENT_CLASSIFICATION),
        'Every intent must point to an independently inventoried actual CPU parent')
    return sorted(result,key=lambda row:int(row['job_id'])),files
