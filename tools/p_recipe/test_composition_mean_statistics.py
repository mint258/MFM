"""Only the new participation and exact registered sign rules."""
import unittest
import numpy as np
from composition_mean_statistics import participation_ratio,b4_decision,hcomp_decision


class MeanStatisticsTests(unittest.TestCase):
    def test_isotropic_and_rank_one(self):
        y=np.array([[1,0],[-1,0],[0,1],[0,-1]],np.float64)
        self.assertAlmostEqual(participation_ratio(y,np.ones(4)),2.)
        self.assertAlmostEqual(participation_ratio(y[:,:1],np.ones(4)),1.)

    def test_molecule_weights_and_translation(self):
        y=np.array([[1,2],[3,1],[-2,3]],np.float64);w=np.array([2,1,1],np.float64)
        repeated=np.repeat(y,w.astype(int),axis=0);cov=np.cov(repeated.T,bias=True)
        expected=np.trace(cov)**2/np.square(cov).sum()
        self.assertAlmostEqual(participation_ratio(y,w),expected,places=12)
        self.assertAlmostEqual(participation_ratio(y+30,w),expected,places=12)

    def test_zero_variance_and_alignment(self):
        self.assertTrue(np.isnan(participation_ratio(np.ones((3,2)),np.ones(3))))
        with self.assertRaises(ValueError):participation_ratio(np.ones((3,2)),np.ones(2))

    def test_B4_registered_boundaries(self):
        s=lambda x:dict(ci95=x)
        self.assertEqual(b4_decision(s([-2,-1]),s([-1,-.1])),"SUPPORT")
        self.assertEqual(b4_decision(s([0,1]),s([0,2])),"NOT_SUPPORT")
        self.assertEqual(b4_decision(s([-1,0]),s([-2,-1])),"UNCERTAIN")
        self.assertEqual(b4_decision(s([-2,-1]),s([0,2])),"UNCERTAIN")

    def test_Hcomp_registered_boundaries_and_missing(self):
        s=lambda x:dict(ci95=x)
        self.assertEqual(hcomp_decision(s([-2,-1]),s([-1,-.1])),"SUPPORT")
        self.assertEqual(hcomp_decision(s([-2,-1]),s([0,1])),"NOT_SUPPORT")
        self.assertEqual(hcomp_decision(s([0,1]),s([-2,-1])),"NOT_SUPPORT")
        self.assertEqual(hcomp_decision(s([-1,0]),s([-2,-1])),"UNCERTAIN")
        self.assertEqual(hcomp_decision(s(None),s([-2,-1])),"UNRESOLVED")
        self.assertEqual(hcomp_decision(s([0,1]),s(None)),"NOT_SUPPORT")
        self.assertEqual(hcomp_decision(s(None),s([0,1])),"NOT_SUPPORT")


if __name__=="__main__":unittest.main()
