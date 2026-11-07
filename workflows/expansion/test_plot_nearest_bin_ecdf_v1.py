"""The original final finite bin includes1; endpoint must stay visible."""
import unittest
from .plot_nearest_bin_ecdf_v1 import points

def rows(counts):
    bounds=[('-inf','0'),('0','.5'),('.5','1'),('1','inf')];out=[];total=0
    for i,((left,right),n)in enumerate(zip(bounds,counts)):
        total+=n;out.append(dict(bin=str(i),left=left,right=right,count=str(n),cumulative_count=str(total)))
    return out
class Endpoints(unittest.TestCase):
    def test_original_closed_last_bin_keeps_exact_ones(self):
        x,y=points(rows([0,2,2,0]),4,1)
        self.assertEqual((x[-1],y[-1]),(1.,1.))
        self.assertEqual(points(rows([0,0,4,0]),4,4)[1], [0.,0.,1.,1.])
    def test_mass_or_out_of_range_scores_cannot_be_hidden(self):
        for body,n,ones in [(rows([0,2,2,0]),5,1),(rows([0,2,2,0]),4,3),(rows([1,1,2,0]),4,1),(rows([0,1,2,1]),4,1)]:
            with self.assertRaises(ValueError):points(body,n,ones)
if __name__=='__main__':unittest.main()
