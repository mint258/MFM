import unittest
from workflows.benchmark_data.c7_targets import bind_quantity,HARTREE_EV_2014


class PrimaryBindingTests(unittest.TestCase):
    def test_primary_field_selects_its_actual_quantity(self):
        header=['gdb9','1']+['0']*15
        header[11:16]=['0.1','-400.0','-399.99','-399.98','-400.05']
        self.assertEqual(bind_quantity(-400.05*HARTREE_EV_2014,header),'G298')

    def test_ambiguous_or_unmatched_quantity_is_not_guessed(self):
        header=['gdb9','1']+['0']*15
        with self.assertRaises(ValueError):bind_quantity(0,header)
        with self.assertRaises(ValueError):bind_quantity(99,header)

if __name__=='__main__':unittest.main()
