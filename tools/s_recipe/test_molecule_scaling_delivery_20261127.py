"""New subset reporting boundaries; synthetic retained arrays only."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import molecule_scaling_delivery_20261127 as m


def score(value,groups=('MID0',)):
    return dict(complete=True,bootstrap_defined=1000,bootstrap_samples=1000,
        mean_normalized_improvement=value,tasks=dict(task=0),paired_bootstrap=dict(
            groups=groups,seed=20261025,samples=1000,confidence=.95,values=[value]*1000))


class MoleculeScalingDelivery(unittest.TestCase):
    def test_only_matched_boundaries_and_no_recipe_verdict(self):
        a={n:{k:score(.3) for k in ('R1','R3')} for n in m.SAMPLES}
        b={n:{k:score(.2) for k in ('R1','R3')} for n in m.SAMPLES}
        result=m.contrasts(a,b)
        self.assertAlmostEqual(result[3000000]['R3']['delta'],.1)
        self.assertNotIn('verdict',result[3000000]['R3'])
        with self.assertRaises(ValueError):m.contrasts({3000000:a[3000000]},b)
        b[6000000]['R3']=score(.2,('different_MID',))
        with self.assertRaises(ValueError):m.contrasts(a,b)

    def test_missing_second_subset_cannot_consume_any_original_primary(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(m,'C',Path(tmp)),patch.object(m,'read') as read,\
                    patch.object(m,'closed_subset',side_effect=[{},FileNotFoundError('second subset pending')]):
                with self.assertRaises(FileNotFoundError):m.collect()
                read.assert_not_called()


if __name__=='__main__':unittest.main()
