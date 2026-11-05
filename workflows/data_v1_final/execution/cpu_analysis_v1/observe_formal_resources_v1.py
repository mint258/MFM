"""Read scheduler metadata for the unchanged formal 16CPU64GiB admission rule."""
import argparse,datetime,importlib.util,json,pathlib,subprocess
from workflows.data_v1_final.execution.cpu_analysis_v1 import policy

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=pathlib.Path,required=True)
    a=p.parse_args();policy.require(not a.output.exists(),'NEW_METADATA_OBSERVATION_REQUIRED')
    source=policy.REPO/'workflows/data_v1_final/execution/submit_reviewed.py'
    spec=importlib.util.spec_from_file_location('original_formal_metadata_helpers',source)
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    argv_nodes=['scontrol','show','node','--oneliner']
    argv_jobs=['scontrol','show','job','--oneliner']
    nodes=subprocess.run(argv_nodes,capture_output=True,text=True,check=True)
    jobs=subprocess.run(argv_jobs,capture_output=True,text=True,check=True)
    jobrows=[old.fields(line) for line in jobs.stdout.splitlines() if line.strip()]
    rows=[]
    for line in nodes.stdout.splitlines():
        if not line.strip():continue
        node=old.fields(line);name=node['NodeName']
        if name not in {'compute-0-'+str(n) for n in range(14,20)}:continue
        declarations=[];unknown=[];positive=0
        for job in jobrows:
            if job.get('JobState') not in {'RUNNING','COMPLETING'}:continue
            assigned=job.get('NodeList','')
            if '[' in assigned:
                assigned=subprocess.check_output(['scontrol','show','hostnames',assigned],text=True).strip().replace('\n',',')
            if name not in assigned.split(','):continue
            if 'MinMemoryNode' in job:memory=old.memory_mib(job['MinMemoryNode'])
            elif 'MinMemoryCPU' in job:memory=old.memory_mib(job['MinMemoryCPU'])*int(job['NumCPUs'])
            else:memory=None
            declarations.append({'job_id':job['JobId'],'declared_memory_mib':memory,
                'zero_or_missing_is_unbounded':memory is None or memory==0})
            if memory is None or memory==0:unknown.append(job['JobId'])
            else:positive+=memory
        cpu_free=int(node['CPUTot'])-int(node['CPUAlloc'])
        limit=int(node['RealMemory'])*.85
        reservation=max(float(node.get('AllocMem',0)),positive)+64*1024
        rows.append({'node':name,'free_cpus':cpu_free,'memory_declarations_all_users':declarations,
            'unbounded_job_ids':unknown,'known_declarations_plus_64GiB_mib':reservation,
            'declaration_limit85pct_mib':limit,
            'scheduler_declaration_admission_passed':cpu_free>=16 and not unknown and reservation<=limit,
            'actual_memory_probe_performed':False,
            'reason':'UNBOUNDED_OTHER_DECLARATION' if unknown else 'CPU_OR_DECLARATION_LIMIT' if cpu_free<16 or reservation>limit else 'REQUIRES_FRESH_ACTUAL_MEMORY_AND_QUOTA_NEXT'})
    policy.require(len(rows)==6,'ALL_SIX_FORMAL_CPU_NODES_REQUIRED')
    result={'schema':'DATA_V1_FORMAL_RESOURCE_METADATA_OBSERVATION_V1',
        'observed_at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        'formal_requirements':{'nodes':'14-19','cpus':16,'memory_gib':64,'all_user_declared_memory_fraction':.85},
        'queries':[{'argv':argv_nodes,'returncode':nodes.returncode,'stdout':nodes.stdout},
                   {'argv':argv_jobs,'returncode':jobs.returncode,'stdout':jobs.stdout}],
        'nodes':rows,'scheduler_eligible_nodes':[r['node'] for r in rows if r['scheduler_declaration_admission_passed']],
        'submission_commands_run':[],'other_jobs_modified':False,'formal_authority_relaxed':False,
        'source_reference':policy.ref(pathlib.Path(__file__).absolute())}
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({'status':'FORMAL_ADMISSION_METADATA_OBSERVED_NO_SUBMISSION',
        'reference':policy.ref(a.output),'eligible_nodes':result['scheduler_eligible_nodes']}))
if __name__=='__main__':main()