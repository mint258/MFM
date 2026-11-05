"""Metadata seams only: sealed-source delegation and mixed baseline rejection."""
import unittest
from unittest.mock import patch
from .contracts import complete_source,corrected_baseline
from ..pubchem_generic_recovery_overlay_v1.runtime import VERSION


class OverlayContracts(unittest.TestCase):
    def test_pending_overlay_never_bypasses_the_actual_sealed_reader(self):
        pool={'schema':'PUBCHEM_EXACT_MINCID_OVERLAY_POOL_V1','population_version':VERSION}
        with patch('workflows.expansion.pubchem_generic_recovery_overlay_v1.reader.validate_header',
                side_effect=ValueError('SEALED_ROOT_REVIEW_REQUIRED'))as validator:
            with self.assertRaisesRegex(ValueError,'SEALED_ROOT'):complete_source(pool)
        validator.assert_called_once_with(pool)

    def test_mixed_version_or_missing_history_fails_before_any_projection_body_read(self):
        source={'population_version':VERSION,'unique_full_keys':109875599}
        q={'population_version':'HISTORICAL_OLD_POPULATION','source_pool_receipt':{'fixture':True}}
        with self.assertRaisesRegex(ValueError,'population version'):corrected_baseline(q,source,None,None)
        q.update(population_version=VERSION,sample_hash_domain='PubChem-baseline-uniform',source_pool_molecules=109875599,
            internal_deduplicated_pool_reference=q['source_pool_receipt'],
            scope={'population_version':VERSION,'source_pool_receipt':q['source_pool_receipt']})
        with self.assertRaisesRegex(ValueError,'history'):corrected_baseline(q,source,None,None)
        q.update(previous_baseline_receipt_reference={'fixture':True},previous_baseline_actual_reference={'fixture':True},
            exact_incremental_method='INSERT_ONLY_TOPK_FROM_PROVEN_FROZEN_OLD_TOPK_PLUS_ALL_NEW_FULLKEYS')
        with self.assertRaisesRegex(ValueError,'Root baseline review'):corrected_baseline(q,source,None,None)


if __name__=='__main__':unittest.main()
