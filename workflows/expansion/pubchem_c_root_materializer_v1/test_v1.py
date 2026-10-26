"""Three pure resource/partition boundaries; no real metadata or scientific IO."""
import copy,unittest
from . import math_v1 as M


def source():
    return M.measured({'group':'uniform10000','completed_rows':10000,'dispatched_rows':10000,
        'counts':{'accepted':8773,'chemReject':1223,'technicalUnresolved':4},'worker_records':{str(i):625 for i in range(16)},
        'full_dispatch_and_result_journal':{'bytes':20000},'features':{'bytes':10000},
        'worker_task_phase_sums':{'audit_CPU_seconds':100,'dispatcher_CPU_seconds_includes_legacy_X_parse':200},
        'phase_wall_seconds':8,'total_bundle_bytes':999999999999,'independent_longest16_bytes':999999999})


def root():return {'output_expansion_factor':'2','wall_expansion_factor':'2','admin_reserved_bytes':4096,
    'wall_seconds':1440,'output_cap_bytes':M.DRAIN+4096+1500000,'root_IO_and_startup_allowance_seconds':300,
    'wall_projection_basis':'UNIFORM_WORKER_CPU_AT16_PLUS_ROOT_IO_ALLOWANCE'}


class MetadataBoundaries(unittest.TestCase):
    def test_uniform_only_bytes_fixed_drain_admin_and_one_byte_cap_short(self):
        observed=source();self.assertEqual(observed['row_payload_bytes'],30000)
        approved=root();value=M.reviewed_limits(observed,approved,250000)
        self.assertEqual(value['projected_payload_bytes_after_margin'],1500000);self.assertEqual(value['fixed_pending_drain_bytes'],(1<<30)+(128<<20))
        self.assertEqual(value['minimum_profile_derived_output_cap_bytes'],approved['output_cap_bytes'])
        self.assertFalse(value['longest16_or_total_bundle_bytes_in_mean']);self.assertFalse(value['worst_case_feature_size_proven'])
        approved['output_cap_bytes']-=1
        with self.assertRaisesRegex(ValueError,'CAP_BELOW'):M.reviewed_limits(observed,approved,250000)
    def test_500_parts_cover_every_ordinal_once_and_reject_hole_overlap_or_bool(self):
        shards=[];first=1
        for index in range(500):
            last=min(M.N,first+250000-1);shards.append({'shard_index':index,'first_part':index,'last_part':index,'first_ordinal':first,'last_ordinal':last});first=last+1
        value={'schema':'ALPHA_PUBCHEM_EXCLUSIVE_ORDINAL_MANIFEST_V1','population_N':M.N,'part_count':500,'pool_release_authorized':False,'shards':shards}
        self.assertIs(M.partition(value),value);self.assertEqual(shards[-1]['last_ordinal']-shards[-1]['first_ordinal']+1,107440)
        for delta in (-1,1):
            invalid=copy.deepcopy(value);invalid['shards'][1]['first_ordinal']+=delta
            with self.assertRaises(ValueError):M.partition(invalid)
        invalid=copy.deepcopy(value);invalid['shards'][0]['first_ordinal']=True
        with self.assertRaises(ValueError):M.partition(invalid)
    def test_wall_basis_is_explicit_measured_reference_not_allocated_cost(self):
        observed=source();approved=root();cpu=M.reviewed_limits(observed,approved,250000)
        self.assertEqual(cpu['minimum_chosen_wall_reference_seconds'],1358);self.assertTrue(cpu['worker_CPU_sums_not_parent_allocation_cost'])
        approved['wall_projection_basis']='UNIFORM_PHASE_WALL_ROW_SCALED_REFERENCE';approved['wall_seconds']=840
        phase=M.reviewed_limits(observed,approved,250000);self.assertEqual(phase['minimum_chosen_wall_reference_seconds'],820)
        approved['wall_seconds']=780
        with self.assertRaisesRegex(ValueError,'WALL_BELOW'):M.reviewed_limits(observed,approved,250000)
        approved['wall_projection_basis']='UNREVIEWED_ARBITRARY_MEAN'
        with self.assertRaisesRegex(ValueError,'BASIS'):M.reviewed_limits(observed,approved,250000)
