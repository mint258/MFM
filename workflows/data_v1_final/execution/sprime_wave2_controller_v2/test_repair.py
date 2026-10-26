"""Four synthetic narrow repair-map boundaries; no scheduler/files/body access."""
import unittest
from . import repair as R


class RepairBoundaries(unittest.TestCase):
    def value(self):return dict(batch_id=R.BID,stage='close',failed_job_id=R.FAILED,science_job_id=R.SCIENCE,no_science_retry=True,
        replacement_output_root=str(R.V.G.WAVE2/R.BID/'closed_root_repair_v1'),replacement_primary_reference={'path':str(R.CLOSER/'run.py')})
    def test_only_actual33_close_metadata_scope_allowed(self):
        R.literals(self.value())
        for key,value in (('batch_id','batch-00034'),('stage','run'),('science_job_id','other'),('failed_job_id','other')):
            with self.assertRaises(ValueError):R.literals(dict(self.value(),**{key:value}))
    def test_no_scientific_retry_switch(self):
        with self.assertRaises(ValueError):R.literals(dict(self.value(),no_science_retry=False))
    def test_legacy_or_arbitrary_output_is_not_a_repair(self):
        for path in (str(R.V.G.WAVE2/R.BID/'closed_v1'),'/arbitrary/closed_root_repair_v1'):
            with self.assertRaises(ValueError):R.literals(dict(self.value(),replacement_output_root=path))
    def test_other_primary_or_producer_option_does_not_bind(self):
        with self.assertRaises(ValueError):R.literals(dict(self.value(),replacement_primary_reference={'path':str(R.V.G.CLOSER/'run.py')}))
