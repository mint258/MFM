"""Exactly6 synthetic methods, once per real parent before scientific DATA."""
import ast,gzip,hashlib,inspect,json,pathlib,tempfile,unittest
from . import contract as C,runtime as I,census as Z,worker as W
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import runtime_io as OLD


class Boundaries(unittest.TestCase):
    def test_shared_original_key_and_seed_no_resource_namespace_retry(self):
        mid='mol_synthetic_0001';key=C.F.task_key(mid,'fill_10N')
        expected=hashlib.sha256(('sprime-fill-once-v1:'+C.F.KERNEL_SHA+':'+mid+':fill_10N').encode()).hexdigest()
        self.assertEqual(key,expected);self.assertNotEqual(key,C.F.task_key(mid,'retry_once'))
        self.assertEqual(C.F.seed_for(mid,False),max(int.from_bytes(hashlib.sha256(('sprime-ETKDGv3-v1:'+mid).encode()).digest()[:4],'big')&0x7fffffff,1))
    def test_original_retained_geometry_and_real_fallback_not_claimed_unique(self):
        selection=C.F.module('selection',C.F.sources()['selection'])
        old={'candidate_key':'existing:0','coordinates':[[0.,0.,0.]],'energy':0.,'seed':3,'origin':'accepted_sprime','original_sprime_conf_idx':0}
        candidate={'candidate_key':'generated:0','coordinates':[[0.,0.,0.]],'energy':1.,'seed':7,'origin':'data_v1_fill_10N','candidate_id':0}
        rows=selection.select_fill([old],[candidate],2,lambda a,b:0.,0.5)
        self.assertEqual(rows[0]['coordinates'],old['coordinates']);self.assertEqual(rows[0]['seed'],3)
        self.assertTrue(rows[1]['below_dedup_threshold']);self.assertEqual(rows[1]['min_rmsd_to_previously_selected_A'],0.)
    def test_canonical_clock_real_shape_including_startup_and900_drain(self):
        from datetime import datetime
        start=datetime.fromisoformat('2026-10-28T08:00:00+08:00').timestamp()
        proof={'observed_at':'2026-10-28T00:00:10+00:00','root_observed_at':'2026-10-28T08:00:10+08:00','job_id':'1',
            'job_metadata':'JobId=1 JobState=RUNNING RunTime=00:00:10 TimeLimit=1-00:00:00 StartTime=2026-10-28T08:00:00 EndTime=2026-10-29T08:00:00'}
        clock=I.wall_clock(proof,86400,now_wall=start+30,now_monotonic=100.)
        self.assertEqual(clock['conservative_elapsed_at_anchor_seconds'],30);self.assertEqual(I.remaining_wall(clock,100.),86370.)
        self.assertEqual(I.remaining_wall(clock,85570.),900.)
        with self.assertRaises(ValueError):I.remaining_wall(clock,99.)
    def test_exclusive_claim_and_orphan_evidence_never_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            path=pathlib.Path(d)/'original-key.json';row={'task_key':'a'*64,'job_id':'123','science_result_observed':False}
            ref=I.save(path,row)
            with self.assertRaises(FileExistsError):I.save(path,dict(row,job_id='fake-new'))
            self.assertEqual(I.read_json(ref),row)
            I.save(pathlib.Path(d)/'orphan_start.json',{'task_key':row['task_key'],'owner':'old'})
            self.assertTrue((pathlib.Path(d)/'orphan_start.json').exists());self.assertFalse(row['science_result_observed'])
    def test_float64_identity_bits_and_bounded_full_packet_readback(self):
        import numpy as np
        numbers=[6,1];coords=[[float(np.nextafter(1.,2.)),0.,0.],[0.,0.,1.]];atom=hashlib.sha256(np.asarray(numbers,dtype='<i8').tobytes()).hexdigest()
        geo=OLD.common().geometry_sha(numbers,coords)
        row={'molecule_id':'synthetic','sprime_conf_idx':0,'atomic_numbers':numbers,'coordinates':coords,'atom_order_sha256':atom,
            'geometry_sha256':geo,'source_record_id':'native_1','status':'SUCCESS','converged':True,'uff_energy_kcal_mol':1.,
            'origin':'accepted_sprime','original_sprime_conf_idx':0,'seed':3,'candidate_id':None,'below_dedup_threshold':False}
        packet={'summary':{'molecule_id':'synthetic','source_record_id':'native_1','atom_order_sha256':atom},'conformers':[row]}
        value={'packet_compressed_limit_bytes':1<<20,'packet_uncompressed_limit_bytes':4<<20}
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'toy.json.gz';ref=I.exclusive(p,gzip.compress(C.F.canonical(packet),mtime=0));self.assertEqual(OLD.read_packet(ref,value),packet)
            with self.assertRaises(ValueError):OLD.read_packet(dict(ref,sha256='0'*64),value)
        other=dict(row,coordinates=np.asarray(coords,dtype='<f4').astype('<f8').tolist())
        with self.assertRaises(ValueError):Z.coordinate_identity(other)
        other.pop('geometry_sha256')
        self.assertNotEqual(Z.coordinate_identity(row),Z.coordinate_identity(other))
    def test_exact_one_original_scientific_call_and_single_real_parent(self):
        tree=ast.parse(inspect.getsource(W.one));calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call)
            and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='SCIENCE' and n.func.attr=='process_task']
        self.assertEqual(len(calls),1)
        text=inspect.getsource(W);self.assertNotIn('subprocess.',text);self.assertNotIn('os.system',text)
        plan={'original_plan_reference':{'path':'/synthetic/plan','bytes':1,'sha256':'a'*64},'inputs_review_reference':{'path':'/synthetic/review','bytes':1,'sha256':'b'*64},
            'cpus':64,'output_cap_bytes':528<<30}
        params=C.parameters(plan);self.assertTrue(params['one_true_parent_no_child_sbatch_srun_or_child_C0']);self.assertEqual(params['cpus'],64)
        self.assertEqual(params['stop_dispatch_before_wall_seconds'],900)
