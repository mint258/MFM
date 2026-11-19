import unittest
from workflows.benchmark_data.c7_reference import parse_xyz,number


class QM9ParserTests(unittest.TestCase):
    def test_xyz_order_and_both_source_smiles_survive(self):
        text='3\ngdb9 17 '+ ' '.join(['0']*15)+'\nO -1.16 0 0 -0.1\nC 0 0 0 0.2\nO 1.16 0 0 -0.1\n100 200\nO=C=O O=C=O\nInChI=a InChI=b\n'
        row=parse_xyz(text)
        self.assertEqual(row['gdb9_index'],17)
        self.assertEqual(row['atomic_numbers'],[8,6,8])
        self.assertEqual(row['coordinates_A'][0],[-1.16,0,0])
        self.assertEqual(row['relaxed_smiles'],'O=C=O')
        self.assertEqual(len(row['header_lexemes']),17)

    def test_author_exponent_lexeme_is_parsed_without_unit_conversion(self):
        self.assertEqual(number('-1.25*^2'),-125.0)
        self.assertEqual(number('1.25e-2'),.0125)

if __name__=='__main__':unittest.main()
