"""Source lineage routing only; mocked acceptance never authorizes real DATA."""
import unittest
from unittest.mock import patch
from ..regression_common_scope_v1.run import common_lineage

REPAIRED='ALPHA_COMMON_GENERIC_REPRESENTATION_REPAIR_COMPLETION_PRODUCER_V1'


class OriginalCommonLineage(unittest.TestCase):
    def test_completion_plan_never_replaces_original_formal_membership_transport(self):
        manifest={'producer_schema':REPAIRED,'actual_full_receipt_reference':'FIXTURE_COMPLETION',
            'original_full_source_receipt_reference':'FIXTURE_ORIGINAL','common_population_manifest':'FIXTURE_MEMBERSHIP'}
        source={'schema':'ALPHA_COMMON_GRAPH_CONTINUATION_PRODUCER_V1','mode':'full','plan':'FIXTURE_ORIGINAL_PLAN'}
        original_plan={'origin_input_manifest_reference':'FIXTURE_ORIGINAL_INPUTS','transport_bindings':['ORIGINAL_BINDINGS']}
        bodies={'FIXTURE_ORIGINAL':source,'FIXTURE_MEMBERSHIP':{'membership_tables':['ORIGINAL_TABLE']},
            'FIXTURE_ORIGINAL_PLAN':original_plan,'FIXTURE_ORIGINAL_INPUTS':{'origin_formal_reference':'ORIGINAL_FORMAL'}}
        opened=[]
        def small(ref):opened.append(ref);return bodies[ref]
        # This isolates routing after acceptance. The real repaired validator is
        # tested separately and remains required by every production entry.
        with patch('workflows.expansion.exact_nn_cached_v1.alpha_common_repaired.validate_manifest',return_value=manifest)as validate:
            producer,common,plan,origin,source_ref=common_lineage(manifest,small)
        validate.assert_called_once_with(manifest)
        self.assertEqual(opened,['FIXTURE_ORIGINAL','FIXTURE_MEMBERSHIP','FIXTURE_ORIGINAL_PLAN','FIXTURE_ORIGINAL_INPUTS'])
        self.assertIs(producer,source);self.assertIs(plan,original_plan)
        self.assertEqual(common['membership_tables'],['ORIGINAL_TABLE'])
        self.assertEqual(origin['origin_formal_reference'],'ORIGINAL_FORMAL')
        self.assertEqual(source_ref,'FIXTURE_ORIGINAL')

    def test_missing_original_source_binding_never_falls_back_to_completion(self):
        manifest={'producer_schema':REPAIRED,'actual_full_receipt_reference':'FIXTURE_COMPLETION'}
        with self.assertRaises(KeyError):common_lineage(manifest,lambda ref:self.fail('No completion may be opened'))


if __name__=='__main__':unittest.main()
