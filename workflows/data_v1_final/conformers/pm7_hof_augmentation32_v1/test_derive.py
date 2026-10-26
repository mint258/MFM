"""Three synthetic derived-cache boundaries, never native readers or QM."""
import copy,unittest
from . import contract as C
from .derive import augment,geometry_orders,golden_compare
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1.contract import missing_hof


def sample():
    ids=['r0','r1','r2'];matrix=[[.01,.3,.8],[.31,.02,.6],[.81,.61,.03]]
    index={rid:i for i,rid in enumerate(ids)};rows=[{'conformer_id':r,'energy':None} for r in ids]
    orders=geometry_orders(rows,lambda a,b:matrix[index[a['conformer_id']]][index[b['conformer_id']]],'m','pm7')
    task={'molecule_id':'m','ids':ids,'matrix':matrix,'matrix_sha256':C.digest([ids,matrix]),'original_orders':orders,
      'original_unique_representatives':['r0','r2'],'geometry_hashes':{r:r for r in ids},
      'original_cache_key':'old','geometry_packet_reference':{'path':'/old','bytes':1,'sha256':'0'*64},'golden_reference':None}
    hof={rid:dict(missing_hof('not-used'),value_kcal_mol=value,valid=True,reason=None,converged=True,
                 source_status='SUCCESS') for rid,value in zip(ids,[0.0,-1.0,2.0])}
    return task,hof


class DerivedBoundaries(unittest.TestCase):
    def test_cached_directional_matrix_and_random_unchanged(self):
        task,hof=sample();before=copy.deepcopy(task);result=augment(task,hof,{})
        self.assertEqual(task,before);self.assertEqual(result['orders']['fixed_random'],task['original_orders']['fixed_random'])
        self.assertEqual(result['orders']['energy'],['r1','r0','r2'])
        self.assertEqual(result['inherited_directional_matrix_sha256'],C.digest([task['ids'],task['matrix']]))
        self.assertEqual(result['new_geometry_or_RMSD_calls'],0)

    def test_null_review_missing_is_pending_and_zero_is_real(self):
        task,hof=sample();hof['r0'].update(converged=None,convergence_null_review=True)
        result=augment(task,hof,{})
        self.assertEqual(result['hof_float64_bit_signatures']['r0'],C.bits(0.0))
        self.assertEqual(result['hof_valid_count'],3);self.assertEqual(result['convergence_null_review_records'],1)
        hof['r1']=missing_hof('CANONICAL_HOF_RECORD_MISSING');result=augment(task,hof,{})
        self.assertIsNone(result['orders']['energy']);self.assertFalse(result['hof_range_complete'])
        old={'status':'D7_MOLECULE_PROFILE_COMPLETE','molecule_id':'m','hof_by_record':hof,'hof_range_complete':True}
        self.assertEqual(golden_compare(result,old)['status'],'PENDING_CURRENT_CANONICAL_HOF')

    def test_exact_golden_bits_and_mismatch_no_tolerance(self):
        task,hof=sample();result=augment(task,hof,{})
        old={'status':'D7_MOLECULE_PROFILE_COMPLETE','molecule_id':'m','hof_by_record':copy.deepcopy(hof),
          'hof_range_complete':True,'orders':{'pm7':copy.deepcopy(result['orders'])},
          'geometry_hashes':{'pm7':result['geometry_hashes']},
          'unique_representatives':{'pm7':result['inherited_unique_representatives']}}
        self.assertEqual(golden_compare(result,old)['status'],'GOLDEN_CANONICAL_HOF_BITS_STATE_AND_ORDERS_EQUAL')
        old['hof_by_record']['r0']['value_kcal_mol']=-0.0
        self.assertEqual(golden_compare(result,old)['status'],'GOLDEN_MISMATCH_HOLD')

if __name__=='__main__':unittest.main()
