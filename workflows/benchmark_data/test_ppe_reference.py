import io
import unittest
from workflows.benchmark_data.ppe_reference import xyz_frames,target_rows,numeric


class PPEParserTests(unittest.TestCase):
    def test_frames_keep_comment_identity_and_xyz_atom_order(self):
        frames=list(xyz_frames(io.StringIO('3\nCarbon dioxide\nO -1.16 0 0\nC 0 0 0\nO 1.16 0 0\n')))
        self.assertEqual(frames[0][:3],(0,'Carbon dioxide',[8,6,8]))
        self.assertEqual(frames[0][3][0],[-1.16,0,0])

    def test_multitoken_names_and_failed_published_method_values_survive(self):
        names,rows=target_rows(iter(['Sl System Expt PM6 PM7\n','1 Carbon dioxide -94.05 failed -84.52\n']))
        self.assertEqual(names,['Expt','PM6','PM7'])
        self.assertEqual(rows[1]['name'],'Carbon dioxide')
        self.assertEqual(rows[1]['lexemes']['PM6'],'failed')
        self.assertIsNone(numeric(rows[1]['lexemes']['PM6']))

if __name__=='__main__':unittest.main()
