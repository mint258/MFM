"""Keep the validated v1 behavior and expose the existing loader's sampler seed."""
from s_training_components_v1 import EpochCoverage,SMeter,TASKS
from s_training_components_v1 import ExposureBoundedSampler as OriginalExposureBoundedSampler

class ExposureBoundedSampler(OriginalExposureBoundedSampler):
    @property
    def seed(self):return self.base.seed
