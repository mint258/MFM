"""New traversal checks; no original source, label or geometry is opened."""
import unittest
from .build_index import iter_identity
from .read_index import aligned_row


class FakeBatch:
    def __init__(self,n):self.num_rows=n
    def to_pylist(self):return [{} for _ in range(self.num_rows)]


class FakeParquet:
    num_row_groups=2
    def iter_batches(self,row_groups,**kwargs):
        return iter([FakeBatch(n) for n in ((2,1) if row_groups==[0] else (1,2))])
    class metadata:
        @staticmethod
        def row_group(index):
            class Group:num_rows=3
            return Group()


class IndexTraversal(unittest.TestCase):
    def test_absolute_physical_rows_across_batches_and_groups(self):
        actual=[(rg,base+local,len(rows)) for rg,base,local,rows in iter_identity(FakeParquet(),['record_id'])]
        self.assertEqual(actual,[(0,0,2),(0,2,1),(1,3,1),(1,4,2)])

    def test_record_and_molecule_alignment_at_numeric_read(self):
        locator={'record_id':'rid','molecule_id':'mid'}
        row={'record_id':'rid','molecule_id':'mid','value':3.0}
        self.assertIs(aligned_row(locator,row),row)
        self.assertEqual(aligned_row(locator,{'record_id':'rid'})['record_id'],'rid')
        with self.assertRaisesRegex(ValueError,'RECORD_ID'):
            aligned_row(locator,{'record_id':'other','molecule_id':'mid'})
        with self.assertRaisesRegex(ValueError,'MOLECULE_ID'):
            aligned_row(locator,{'record_id':'rid','molecule_id':'other'})


if __name__=='__main__':unittest.main()
