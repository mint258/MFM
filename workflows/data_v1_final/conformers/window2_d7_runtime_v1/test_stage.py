import unittest
from .stage import same_source_inputs
class PreparedSource(unittest.TestCase):
    def test_only_transport_and_worker_fields_may_change(self):
        data={'workers':16,'workspace':'first','output':'first-output','common':'fixed','seed':20261025,'science_path':'original','formal_index':'index'}
        self.assertTrue(same_source_inputs(data,dict(data,workers=64,workspace='second',output='second-output')))
        for key in ('common','seed','science_path','formal_index'):
            self.assertFalse(same_source_inputs(data,dict(data,**{key:'different'})))
