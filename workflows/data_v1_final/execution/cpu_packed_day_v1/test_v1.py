"""Three synthetic resource boundaries, intended inside the same day parent."""
import unittest
from . import contract as C

def request(cpus=64):
    plan={'path':str(C.ROOT/'control/synthetic_packed_plan.json'),'bytes':1,'sha256':'a'*64}
    proof=str(C.BASE/'dv1_pack_synthetic'/'proof.json')
    return {'schema':C.REQUEST,'scope_key':C.KEY,'kind':'conformer','pilot':False,'node':'compute-0-13','partition':'cpu','cpus':cpus,
        'requested_cpus':cpus,'wall_seconds':86400,'memory_policy':C.MEMORY,'exclusive_requested':False,'workdir':str(C.PROJECT),
        'startup_wait_seconds':120,'scope_parameters':{'synthetic':True},'estimated_peak_output_bytes':1,'producer_plan_reference':plan,
        'execution_argv':[C.PY,'-B','-m',C.MODULE,'--plan',plan['path'],'--startup-proof',proof],'startup_proof_path':proof,
        'job_name':'dv1_pack_synthetic','source_references':[],'data_references':[]}

class Boundaries(unittest.TestCase):
    def test_only_packed_real_cpu_count_and_no_old16_proof(self):
        C.shape(request());C.shape(request(16))
        for n in (True,15,64.0):
            with self.assertRaises(ValueError):C.shape(request(n))
        r=request();r['schema']=C.O.REQUEST_SCHEMA
        with self.assertRaises(ValueError):C.shape(r)
        r=request();r['exclusive_requested']=True
        with self.assertRaises(ValueError):C.shape(r)

    def test_actual_free_CPU_and_one_parent_identity(self):
        r=request();node='NodeName=compute-0-13 Partitions=cpu CPUTot=96 CPUAlloc=32'
        self.assertEqual(C.free_cpu(r,node)['free_cpus'],64)
        with self.assertRaises(ValueError):C.free_cpu(r,node.replace('CPUAlloc=32','CPUAlloc=33'))
        r['script_reference']={'path':str(C.BASE/'synthetic.sbatch'),'bytes':1,'sha256':'a'*64}
        job={'JobId':'123','UserId':'zixiao(1278)','JobName':r['job_name'],'Partition':'cpu','NumCPUs':'64','NumTasks':'1','Requeue':'0',
            'Command':r['script_reference']['path'],'WorkDir':str(C.PROJECT),'TimeLimit':'1-00:00:00','JobState':'RUNNING','NodeList':'compute-0-13','NumNodes':'1'}
        C.job_identity(r,job,'123')
        with self.assertRaises(ValueError):C.job_identity(r,dict(job,NumCPUs='16'),'123')
        with self.assertRaises(ValueError):C.job_identity(r,dict(job,JobId='124'),'123')

    def test_quota_bridge_full_byte_inverse_and_original_parser(self):
        C.inverse()
        row={'argv':C.Provider.QUOTA_ARGV,'returncode':0,'stderr':'','raw_output_complete':True,
            'stdout':'Disk quotas for user zixiao (uid 1278):\n/dev/sda1 100 200 300\n'}
        parsed=C.Provider.parse_quota(row,'/dev/sda1');self.assertEqual(parsed['free_bytes'],100*1024)
        with self.assertRaises(ValueError):C.Provider.parse_quota(dict(row,stderr='bad'),'/dev/sda1')
        with self.assertRaises(ValueError):C.Provider.parse_quota(dict(row,stdout=row['stdout'].replace('1278','1264')),'/dev/sda1')
if __name__=='__main__':unittest.main()
