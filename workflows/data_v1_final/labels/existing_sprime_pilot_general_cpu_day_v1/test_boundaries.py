"""Exactly three general-context boundaries; executed only in the actual CPU Parent."""
import copy,unittest
from . import contract as C,geometry as G,source_inverse as S
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import geometry as OLD,bindings as B,io as I,statistics as T

class Boundaries(unittest.TestCase):
    def test_real_general_context_and_fake_old_node_rejected(self):
        for node in ('compute-0-2','compute-0-19'):
            proof={'job_id':'synthetic-not-actual','boot_id':'synthetic-boot','request':{'node':node,'cpus':16}}
            facts={'uid':1278,'node':node,'cpus':16,'job_id':'synthetic-not-actual','boot_id':'synthetic-boot',
                'partition':'cpu','cuda_visible_devices':''}
            G.validate_worker_identity(proof,facts)
            for field,value in (('node','compute-0-14'),('uid',1264),('cpus',64),('job_id','wrong-parent'),
                ('boot_id','wrong-boot'),('partition','gpu'),('cuda_visible_devices','0')):
                bad=copy.deepcopy(facts);bad[field]=value
                with self.subTest(node=node,field=field),self.assertRaises(ValueError):G.validate_worker_identity(proof,bad)
        proof={'job_id':'x','boot_id':'b','request':{'node':'compute-0-20','cpus':16}}
        facts={'uid':1278,'node':'compute-0-20','cpus':16,'job_id':'x','boot_id':'b','partition':'cpu','cuda_visible_devices':''}
        with self.assertRaises(ValueError):G.validate_worker_identity(proof,facts)

    def test_direct_original_science_and_independent_context_no_global_patch(self):
        before=(OLD.OriginalWorker.SCIENCE,OLD.OriginalWorker.CONTEXT)
        self.assertIs(G.WORKER.d7,OLD.OriginalWorker.d7)
        self.assertIs(G.WORKER.pm7_compute,OLD.OriginalWorker.pm7_compute)
        self.assertIs(G.metadata_children,OLD.metadata_children)
        self.assertIs(G.gid,OLD.gid);self.assertIs(G.CacheContext,OLD.CacheContext)
        self.assertIsNot(G.WORKER,OLD.OriginalWorker)
        self.assertIsNot(G.WORKER.I,OLD.OriginalWorker.I)
        from . import run
        self.assertIs(run.I,I);self.assertIs(run.T,T);self.assertIs(run.B,B)
        self.assertIs(B.views,B.series.views);self.assertIs(B.inventory,B.series.inventory)
        self.assertEqual(B.verify()['TSQR_chunk'],256)
        worker=G.WORKER.proof();self.assertTrue(worker['no_native_or_science_called_by_proof'])
        self.assertIs(OLD.OriginalWorker.SCIENCE,before[0]);self.assertIs(OLD.OriginalWorker.CONTEXT,before[1])

    def test_complete_inverse_new_primary_and_same_mathematical_scope(self):
        result=S.proof()
        self.assertEqual(result['status'],'EXACT_GENERAL_CPU_RESOURCE_MODULE_INVERSES_AND_DIRECT_ORIGINAL_SCIENTIFIC_OBJECTS')
        self.assertFalse(result['scientific_math_recipe_seed_threshold_changed'])
        self.assertFalse(result['old_globals_patched']);self.assertFalse(result['scientific_DATA_read_or_native_called'])
        self.assertEqual(C.KEY,'existing_sprime_pilot_general_cpu_day_v1')
        self.assertEqual(C.MODULE,'workflows.data_v1_final.labels.existing_sprime_pilot_general_cpu_day_v1.run')
        from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import contract as OC
        p={'node':'compute-0-19','output_directory':'synthetic-review-not-a-real-plan','whole_output_cap_bytes':32<<30,
            'pilot_input_review_reference':{},'projection_origin_review_reference':{},'pm7_prefix_review_reference':{},'field_scope':{}}
        self.assertEqual(C.scope(p),OC.scope(p))
        self.assertNotEqual(C.HERE,OC.HERE);self.assertNotEqual(C.MODULE,OC.MODULE)
        self.assertEqual(len(C.FILES),8)

if __name__=='__main__':unittest.main()
