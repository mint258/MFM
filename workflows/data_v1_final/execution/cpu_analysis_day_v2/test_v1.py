"""Three resource-only pure boundaries, run inside the actual day parent."""
import unittest
from . import contract as C

def request(cpus=64,scope='common_train_normalization_day_v1',node='compute-0-14'):
    plan={'path':str(C.ROOT/'control/synthetic_analysis_plan.json'),'bytes':1,'sha256':'a'*64}
    proof=str(C.BASE/'dv1_aday_synthetic'/'proof.json')
    return {'schema':C.REQUEST,'scope_key':scope,'kind':'analysis','pilot':False,'node':node,'partition':'cpu','cpus':cpus,
      'requested_cpus':cpus,'wall_seconds':86400,'memory_policy':C.MEMORY,'exclusive_requested':False,'workdir':str(C.PROJECT),
      'startup_wait_seconds':120,'scope_parameters':{'synthetic':True},'estimated_peak_output_bytes':100,'producer_plan_reference':plan,
      'execution_argv':[C.PY,'-B','-m',C.SCOPES.get(scope,'bad'),'--plan',plan['path'],'--startup-proof',proof],
      'startup_proof_path':proof,'job_name':'dv1_aday_synthetic','source_references':[],'data_references':[]}

class Boundaries(unittest.TestCase):
    def test_two_exact_modules_truthful_cpu_node_and_no_old_proof(self):
        C.shape(request());C.shape(request(16,'d5_inputs_compound_day_v1','compute-0-18'))
        for n in (True,15,64.0):
            with self.assertRaises(ValueError):C.shape(request(n))
        for key,value in (('schema',C.O.REQUEST_SCHEMA),('node','compute-0-13'),('kind','conformer'),('exclusive_requested',True)):
            r=request();r[key]=value
            with self.assertRaises(ValueError):C.shape(r)
        r=request();r['execution_argv'][3]='workflows.data_v1_final.conformers.sprime_packed_day_v1.run'
        with self.assertRaises(ValueError):C.shape(r)

    def test_actual_free_cpu_real_parent_and_current_future_once(self):
        r=request();self.assertEqual(C.free_cpu(r,'NodeName=compute-0-14 Partitions=cpu CPUTot=96 CPUAlloc=32')['free_cpus'],64)
        with self.assertRaises(ValueError):C.free_cpu(r,'NodeName=compute-0-14 Partitions=cpu CPUTot=96 CPUAlloc=33')
        c={'schema':'ROOT_ANALYSIS_DAY_CURRENT_FUTURE_CARVEOUT_V1','status':'APPROVED','reviewer':'root','scope_key':r['scope_key'],
          'node':r['node'],'resource_authority_reference':{'synthetic':True},'parent_output_cap_bytes':100,'other_future_reserved_bytes':200,
          'quota_provider_future_reserve_bytes':64<<20,'admin_future_reserve_bytes':64<<20,'total_future_reserved_bytes':(128<<20)+300,
          'previous_total_future_reserved_bytes':(128<<20)+200,'approved_additional_future_reserve_bytes':100,'future_within_previous_plus_explicit_Root_increment':True,
          'parent_included_exactly_once':True,'all_other_active_and_future_writers_included':True,'closed_writer_space_is_in_actual_quota_used':True,
          'old_jobs_and_costs_and_UNKNOWN_preserved':True,'accounting_basis_references':[{'synthetic':True}]}
        r['resource_authority_reference']=c['resource_authority_reference'];C.carveout(c,r)
        with self.assertRaises(ValueError):C.carveout(dict(c,total_future_reserved_bytes=c['total_future_reserved_bytes']+100),r)
        with self.assertRaises(ValueError):C.carveout(dict(c,old_jobs_and_costs_and_UNKNOWN_preserved=False),r)
        with self.assertRaises(ValueError):C.carveout(dict(c,approved_additional_future_reserve_bytes=99),r)

    def test_complete_quota_inverse_original_parser_and_strict_uid(self):
        C.inverse()
        row={'argv':C.Provider.QUOTA_ARGV,'returncode':0,'stderr':'','raw_output_complete':True,
          'stdout':'Disk quotas for user zixiao (uid 1278):\n/dev/sda1 100 200 300\n'}
        self.assertEqual(C.Provider.parse_quota(row,'/dev/sda1')['free_bytes'],100*1024)
        with self.assertRaises(ValueError):C.Provider.parse_quota(dict(row,stderr='bad'),'/dev/sda1')
        with self.assertRaises(ValueError):C.Provider.parse_quota(dict(row,stdout=row['stdout'].replace('1278','1264')),'/dev/sda1')
if __name__=='__main__':unittest.main()
