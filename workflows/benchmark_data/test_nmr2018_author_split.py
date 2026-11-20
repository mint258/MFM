import unittest
import pandas as pd
from workflows.benchmark_data.nmr2018_author_split import split_records

class TestAuthorSplitMembership(unittest.TestCase):
    def test_repeated_spectra_preserve_original_rows_and_indices(self):
        frame=pd.DataFrame({'molecule_id':[7,7,9]},index=[42,43,90])
        rows=list(split_records('13C','test',frame,'author.13C.pickle'))
        self.assertEqual([r['molecule_id'] for r in rows],[7,7,9])
        self.assertEqual([r['source_frame_row'] for r in rows],[0,1,2])
        self.assertEqual([r['source_frame_index'] for r in rows],['42','43','90'])
        self.assertEqual({r['official_split'] for r in rows},{'test'})
    def test_train_and_test_are_not_reassigned(self):
        frame=pd.DataFrame({'molecule_id':[11]})
        for split in ('train','test'):
            self.assertEqual(list(split_records('1H',split,frame,'author.1H.pickle'))[0]['official_split'],split)
    def test_unknown_split_or_missing_identity_fails(self):
        with self.assertRaises(ValueError):list(split_records('13C','validation',pd.DataFrame({'molecule_id':[1]}),'x'))
        with self.assertRaises(ValueError):list(split_records('13C','test',pd.DataFrame({'value':[1]}),'x'))

if __name__=='__main__':unittest.main()
