"""Only new metadata substitutions; no actual fit or old test is executed."""
import unittest
from mixed_fullft_runtime_20261126 import native_main_source


SOURCE='''def main(c):
    cpus=int(os.environ["SLURM_CPUS_PER_TASK"])
    objective=sum(x*x for x in c)
    return dict(value=objective,cpus=cpus,job_id=os.environ["SLURM_JOB_ID"])
'''


class NativeFullFTMetadata(unittest.TestCase):
    def test_metadata_needs_no_slurm_environment_and_preserves_the_body(self):
        namespace={}
        exec(compile(native_main_source(SOURCE,16),'<synthetic>','exec'),namespace)
        self.assertEqual(namespace['main']([2,3]),dict(value=13,cpus=16,job_id=None))

    def test_changed_metadata_shape_or_cpu_demand_requires_inspection(self):
        with self.assertRaises(ValueError):native_main_source(SOURCE.replace('SLURM_JOB_ID','OTHER_JOB_ID'),16)
        with self.assertRaises(ValueError):native_main_source(SOURCE.replace('objective=sum','other=os.environ["SLURM_JOB_ID"]; objective=sum'),16)
        with self.assertRaises(ValueError):native_main_source(SOURCE,8)
