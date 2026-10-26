"""Eight new resource-policy boundaries; synthetic metadata only, no scheduler."""
from copy import deepcopy
import hashlib,json,unittest
from . import contract as q
from .runtime import primary_binding


def raw(value):return (json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode()
def ref(path,value):return {'path':path,'bytes':len(value),'sha256':hashlib.sha256(value).hexdigest()}


def fixture(kind='analysis',node='compute-0-12'):
    root=q.RUN;name='dv1_q_auto_synthetic';files={}
    authority={'schema':'USER_AUTHORIZED_CPU_AUTO_MEMORY_DECISION_V1','status':'USER_AUTHORIZED',
        'user_statements':['request no memory or exclusive flag','CPU11 through19 available for conformer and QM'],
        'memory_policy':q.MEMORY_POLICY,'partition':'cpu','cpus_per_task':16,'allowed_nodes':q.NODES,
        'max_wall_seconds':172800,'quota_reserve_bytes':200000000000,'memory_directives_allowed':False,
        'exclusive_requested':False,'declared_memory_fraction_admission':False,'record_actual_memory':True,
        'no_forced_signals':True,'old_scientific_gates_unchanged':True}
    apath=root+'/repository/configs/data_v1/synthetic_auto_authority.json';files[apath]=raw(authority);ar=ref(apath,files[apath])
    argv=[q.PY,'-B','-m','workflows.synthetic_not_run','--startup-proof','__ROOT_STARTUP_PROOF__']
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1','kind':kind,'pilot':True,
        'scope_key':'synthetic_auto_boundary','scope_parameters':{'records':0},'scope':{},
        'wall_seconds':600,'estimated_peak_output_bytes':4096,'stage_output_cap_bytes':4096,
        'execution_argv':argv,'source_references':[ar],'data_references':[
            {'path':root+'/synthetic_never_opened.parquet','bytes':10**12,'sha256':'a'*64}]}
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'APPROVED_FOR_EXACT_STAGE',
        'reviewer':'root','resource_authority_reference':ar,'scope_mode':'FIXTURE_ONLY',
        'parent_evidence_references':[],'source_status_stage':None}
    for key in ('kind','scope_key','scope_parameters','pilot','wall_seconds','estimated_peak_output_bytes',
                'execution_argv','stage_output_cap_bytes'):review[key]=deepcopy(spec[key])
    rpath=root+'/control/synthetic_auto_review.json';files[rpath]=raw(review);rr=ref(rpath,files[rpath])
    spec['scope']={'mode':'FIXTURE_ONLY','review':rr,'parent_profile':None}
    spath=root+'/control/synthetic_auto_spec.json';files[spath]=raw(spec);sr=ref(spath,files[spath])
    script_path=root+'/control/scripts/'+name+'.sbatch'
    script=('#!/bin/bash\n#SBATCH --job-name='+name+'\n#SBATCH --partition=cpu\n#SBATCH --nodelist='+node+
        '\n#SBATCH --nodes=1\n#SBATCH --ntasks=1\n#SBATCH --cpus-per-task=16\n#SBATCH --time=00:10:00\nset -euo pipefail\n')
    files[script_path]=script.encode()
    request={'schema':q.REQUEST_SCHEMA,'kind':kind,'partition':'cpu','node':node,'job_name':name,'cpus':16,
        'memory_policy':q.MEMORY_POLICY,'exclusive_requested':False,'wall_seconds':600,'pilot':True,
        'estimated_peak_output_bytes':4096,'workdir':q.PROJECT,'startup_wait_seconds':120,
        'startup_proof_path':root+'/control/queue_startup/'+name+'.json','queue_authority_reference':ar,
        'script_reference':ref(script_path,files[script_path]),'source_references':[ar,rr,sr],
        'data_references':spec['data_references'],'execution_argv':[s.replace('__ROOT_STARTUP_PROOF__',
            root+'/control/queue_startup/'+name+'.json') for s in argv],'dependencies':[],
        'root_review':{'status':'APPROVED','reviewer':'root','stage_spec_reference':sr},
        'scope_key':spec['scope_key'],'scope_parameters':spec['scope_parameters'],'scope':spec['scope'],
        'stage_output_cap_bytes':4096}
    return request,files


def job(req,held=False):
    fields={'JobId':'900','JobName':req['job_name'],'UserId':'synthetic(1278)',
        'JobState':'PENDING' if held else 'RUNNING','Reason':'JobHeldUser' if held else 'None','Priority':'0',
        'Partition':'cpu','ReqNodeList':req['node'],'NodeList':req['node'],'NumNodes':'1-1' if held else '1',
        'NumCPUs':'16','NumTasks':'1','MinMemoryNode':'0','TRES':'cpu=16,mem=0,node=1',
        'Requeue':'0','OverSubscribe':'NO','Command':req['script_reference']['path'],
        'WorkDir':q.PROJECT,'TimeLimit':'00:10:00','RunTime':'00:00:01'}
    return ' '.join(k+'='+v for k,v in fields.items())


def proof(req):
    return {'schema':q.PROOF_SCHEMA,'request':deepcopy(req),'job_id':'900','uid':1278,'boot_id':'boot',
        'memory_policy':q.MEMORY_POLICY,'memory_admission_evaluated':False,'memory_limits_requested':False,'job_metadata':job(req),
        'memory_observation':{'uid':1278,'boot_id':'boot','node':req['node'],'observed_unix_seconds':1000.0,
            'total_bytes':1,'available_bytes':0,'used_bytes':1},
        'source_references':deepcopy(req['source_references']),'script_reference':deepcopy(req['script_reference']),
        'queue_authority_reference':deepcopy(req['queue_authority_reference']),
        'existing_jobs_all_users':[{'metadata':'MinMemoryNode=0','declarations_observation_only':True}],
        'account_free_bytes':200000000000+req['estimated_peak_output_bytes'],'execution_admission_granted':True}


class AutoMemoryBoundaries(unittest.TestCase):
    def test_01_new_authority_and_exact_source_scope_without_data_reads(self):
        request,files=fixture();reads=[]
        def reader(path):reads.append(path);return files[path]
        q.validate_request(request,read_small=reader);q.validate_bound_request(request,read_small=reader)
        self.assertNotIn(request['data_references'][0]['path'],reads)
        self.assertNotIn('memory_gib',request)
        bad=deepcopy(request);bad['memory_gib']=64
        with self.assertRaisesRegex(ValueError,'OLD_MEMORY'):q.validate_request(bad,read_small=reader)

    def test_02_new_science_nodes11to13_and_exact_cpu(self):
        for kind in ('analysis','conformer','qm'):
            for node in ('compute-0-11','compute-0-12','compute-0-13'):
                request,files=fixture(kind,node);q.validate_request(request,read_small=files.__getitem__)
        for kind,node in (('qm','compute-0-8'),('conformer','compute-0-2'),('analysis','compute-0-20')):
            request,files=fixture(kind,node)
            with self.subTest(kind=kind,node=node),self.assertRaises(ValueError):q.validate_request(request,read_small=files.__getitem__)
        request,files=fixture();request['cpus']=32
        with self.assertRaisesRegex(ValueError,'EXACT16'):q.validate_request(request,read_small=files.__getitem__)

    def test_03_no_memory_even_zero_or_exclusive_or_gpu_directive(self):
        request,files=fixture();text=files[request['script_reference']['path']].decode()
        for line in ('--mem=0','--mem=64G','--mem-per-cpu=1G','--exclusive=user','--gres=gpu:1'):
            changed=text.replace('set -euo pipefail','#SBATCH '+line+'\nset -euo pipefail')
            with self.subTest(line=line),self.assertRaises(ValueError):q.validate_script(request,changed)

    def test_04_zero_declarations_and_memory_pressure_are_record_only(self):
        request,files=fixture();value=proof(request)
        result=q.validate_fresh_startup_proof(value,request,now_unix=1001,uid=1278,boot_id='boot')
        self.assertFalse(result['memory_admission_evaluated'])
        q.job_identity(request,job(request,held=True),job_id='900',held=True)
        self.assertEqual(value['memory_observation']['available_bytes'],0)

    def test_05_old_proofs_stale_future_and_boot_mismatch_reject(self):
        request,files=fixture()
        for patch,now in (({'schema':'FRESH_QUEUED_CPU_EXECUTION_ADMISSION_V1'},1001),
                          ({'memory_admission_evaluated':True},1001),({},1121),({},999),({'boot_id':'other'},1001)):
            value=proof(request);value.update(patch)
            with self.subTest(patch=patch,now=now),self.assertRaises(ValueError):
                q.validate_fresh_startup_proof(value,request,now_unix=now,uid=1278,boot_id='boot')

    def test_06_actual16_idle_cpus_not_memory_percentage(self):
        request,files=fixture()
        node='NodeName=compute-0-12 Partitions=cpu CPUTot=64 CPUAlloc=48 RealMemory=1 AllocMem=999999'
        self.assertEqual(q.free_cpu_observation(request,node)['free_cpus'],16)
        with self.assertRaisesRegex(ValueError,'FREE_CPU'):q.free_cpu_observation(request,node.replace('CPUAlloc=48','CPUAlloc=49'))

    def test_07_primary_is_not_an_argv_substring_and_all_options_match(self):
        main=q.RUN+'/repository/workflows/synthetic_not_run.py'
        request={'execution_argv':[q.PY,'-B','-m','workflows.synthetic_not_run','--output','value']}
        primary_binding(request,main,['--output','value'])
        for argv,tail in (([q.PY,'-B','wrapper.py','--producer',main],['--producer',main]),
                          (request['execution_argv'],['--output','other'])):
            with self.subTest(argv=argv,tail=tail),self.assertRaises(ValueError):
                primary_binding({'execution_argv':argv},main,tail)

    def test_08_new_registry_is_disjoint_from_unchanged_old_jobs(self):
        request,files=fixture();old=deepcopy(request);old['job_name']='dv1_q_old_synthetic'
        old['startup_proof_path']=q.RUN+'/control/queue_startup/'+old['job_name']+'.json'
        def reg(jid,req,schema):
            path=q.RUN+'/control/requests/'+req['job_name']+'.json'
            return {'schema':schema,'jobs':[{'job_id':jid,'request_reference':{'path':path,'bytes':1,'sha256':'a'*64}}]}
        before=reg('800',old,'REGISTERED_QUEUED_CPU_JOBS_V3');after=reg('900',request,'REGISTERED_CPU_AUTO_MEMORY_JOBS_V1')
        data={before['jobs'][0]['request_reference']['path']:old,after['jobs'][0]['request_reference']['path']:request}
        rows=[(q.RUN+'/control/queue_v3_registries/old.json',before),(q.REGISTRY_DIR+'/new.json',after)]
        q.validate_disjoint(rows,load_request=lambda ref:data[ref['path']])
        after['jobs'][0]['job_id']='800'
        with self.assertRaisesRegex(ValueError,'REGISTRY_OVERLAP:job_id'):
            q.validate_disjoint(rows,load_request=lambda ref:data[ref['path']])


if __name__=='__main__':unittest.main()
