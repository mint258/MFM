"""New E1 source routing rejects a 9M midpoint or changed frozen geometry."""
import unittest
from e1_decision_entry import validate_frozen_source

class E1SourceRoutingTest(unittest.TestCase):
    def test_original_own3M_and_layer_ancestry(self):
        n=dict(samples=3000000,seed=0,run="original_F2")
        e=dict(samples=3000000,run="original_F2")
        s=dict(status="COMPLETE",samples=3000000)
        validate_frozen_source(10,n,e,s)
        with self.assertRaisesRegex(ValueError,"own3M"):
            validate_frozen_source(10,dict(n,samples=9000000),e,s)
        with self.assertRaisesRegex(ValueError,"source/budget"):
            validate_frozen_source(10,n,dict(e,source_training_budget=9000000),s)
        with self.assertRaisesRegex(ValueError,"L6"):
            validate_frozen_source(10,n,dict(e,layer=5),s)

if __name__=="__main__":unittest.main()
