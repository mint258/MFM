import unittest
from stage5_graph_retention import fixed_layers
class FixedPhysicalSubsetChecks(unittest.TestCase):
 def test_first_is_frozen_native_record_not_smallest_export_address(self):
  a={8:dict(source=11.,pilot=11.,current=11.,normalized=1.),0:dict(source=99.,pilot=99.,current=99.,normalized=9.)}
  self.assertEqual(fixed_layers(a,[8,0],'first')['current'],11.)
  a[8]['current']=None
  self.assertIsNone(fixed_layers(a,[8,0],'first'))
 def test_exposure_change_cannot_fabricate_a_processing_difference(self):
  a={8:dict(source=11.,pilot=11.,current=11.,normalized=1.),0:dict(source=99.,pilot=99.,current=None,normalized=None)}
  q=fixed_layers(a,[8,0],'median')
  self.assertEqual(q['source'],11.);self.assertEqual(q['pilot'],q['current']);self.assertEqual(q['common_records'],1)
if __name__=='__main__':unittest.main()