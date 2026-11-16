import unittest
from physical_pair_identity import select_pairs
class PhysicalPairIdentityChecks(unittest.TestCase):
 def test_export_renumbering_cannot_change_physical_pairs(self):
  a={i:'native-'+str(i) for i in range(10)};b={99-i:'native-'+str(i) for i in range(10)}
  x=[p[2] for p in select_pairs('TRAIN','molecule',a)];y=[p[2] for p in select_pairs('TRAIN','molecule',b)]
  self.assertEqual(x,y);self.assertEqual(len(x),6)
 def test_pair_orientation_is_canonical(self):
  pairs=select_pairs('VAL','m',{2:'source-z',5:'source-a'})
  self.assertEqual(pairs[0][:2],(5,2));self.assertEqual(pairs[0][2],[['m','source-a'],['m','source-z']])
if __name__=='__main__':unittest.main()
