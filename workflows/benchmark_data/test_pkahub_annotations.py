import unittest
from workflows.benchmark_data.pkahub_annotations import summarize_macro,transition


class AnnotationTests(unittest.TestCase):
    def test_author_exclusions_and_nonfinite_are_not_counted_as_labels(self):
        rows=[dict(dataset='synthetic',molid='m',exclude_flag=flag,
              Exp_Macro_pKa_processed=value,assigned_charge_state_transition=step)
              for flag,value,step in [('', '7.0','1>>0'),(' EXCLUDE ','8','0>>-1'),
                    ('','NaN','0>>-1'),('','-1.1','0>>-1'),('','bad','n/a')]]
        report=summarize_macro(rows)
        self.assertEqual(report['counts']['author_excluded_rows'],1)
        self.assertEqual(report['counts']['author_curated_rows'],4)
        self.assertEqual(report['counts']['curated_finite_numeric_labels'],2)
        self.assertEqual(report['counts']['curated_numeric_assigned_rows'],2)
        self.assertEqual(report['curated_molecules_with_multiple_distinct_numeric_macro_transitions'],1)
        self.assertTrue(report['macro_transition_count_is_not_atom_site_count'])

    def test_transition_is_an_explicit_ordered_integer_pair(self):
        self.assertEqual(transition(' +1 >> 0 '),(1,0))
        self.assertEqual(transition('0>>-1'),(0,-1))
        self.assertIsNone(transition('0>>-1>>-2'))
        self.assertIsNone(transition('unknown'))

if __name__=='__main__':unittest.main()
