"""Four synthetic time-classification boundaries, no quota query or body read."""
import unittest
from .admission import future_delay,ERROR


class InitialResourceBoundaries(unittest.TestCase):
    def evidence(self,sampled=101,expiry=200):return dict(provider_status='RUNNING',observed_unix_seconds=sampled,
        publisher_expires_unix_seconds=expiry,identity_reference={'synthetic':True},snapshot_reference={'synthetic':True})
    def test_only_short_positive_future_can_wait(self):
        self.assertEqual(future_delay(ValueError(ERROR),self.evidence(),100),1)
        self.assertIsNone(future_delay(ValueError(ERROR),self.evidence(103),100))
    def test_stale_or_expired_never_wait(self):
        for sampled,expiry in ((-21,200),(100,100),(201,200)):
            self.assertIsNone(future_delay(ValueError(ERROR),self.evidence(sampled,expiry),100))
    def test_other_failures_and_stopped_provider_never_wait(self):
        self.assertIsNone(future_delay(ValueError('RAW_QUOTA_PARSE_FAILED'),self.evidence(),100))
        self.assertIsNone(future_delay(ValueError(ERROR),dict(self.evidence(),provider_status='ERROR'),100))
    def test_unbound_or_nonfinite_time_never_wait(self):
        self.assertIsNone(future_delay(ValueError(ERROR),dict(self.evidence(),identity_reference=None),100))
        self.assertIsNone(future_delay(ValueError(ERROR),self.evidence(float('nan')),100))
