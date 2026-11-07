"""One canonical-order metadata regression; no source data or calculations."""
import copy,unittest
from .source_bridge import order_ranks


class OrderRanksCheck(unittest.TestCase):
    def test_canonical_orders_ignore_complete_metadata_and_preserve_ranks(self):
        pm7={'energy':['native-1','native-2','COMPLETE'],'status':'COMPLETE',
             'fixed_random':['native-2','COMPLETE','native-1'],'diversity':None,
             'description':'COMPLETE','other_metadata':['COMPLETE']}
        uff={'fixed_random':[4,7,2],'status':'COMPLETE','energy':None,
             'diversity':[7,2,4],'count':3,'description':'ordinary UFF metadata'}
        originals=copy.deepcopy((pm7,uff))
        self.assertEqual(order_ranks(pm7,'native-2'),{'fixed_random':0,'energy':1})
        self.assertEqual(order_ranks(pm7,'COMPLETE'),{'fixed_random':1,'energy':2})
        self.assertEqual(list(order_ranks(pm7,'COMPLETE')),['fixed_random','energy'])
        self.assertEqual(order_ranks(uff,7),{'fixed_random':1,'diversity':0})
        self.assertEqual(order_ranks(uff,4),{'fixed_random':0,'diversity':2})
        self.assertEqual(order_ranks(pm7,'absent'),{})
        self.assertEqual(order_ranks(uff,99),{})
        self.assertEqual(order_ranks({'fixed_random':None,'status':'COMPLETE'},7),{})
        self.assertEqual(order_ranks({'energy':[7],'status':'COMPLETE'},7),{'energy':0})
        self.assertEqual(order_ranks({'status':'COMPLETE','description':'no lists'},'COMPLETE'),{})
        self.assertEqual((pm7,uff),originals)


if __name__=='__main__':unittest.main()
