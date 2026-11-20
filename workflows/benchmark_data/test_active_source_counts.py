"""Metadata-only count routing; no label readback or scientific calculations."""
import json
from pathlib import Path
import tempfile
import unittest

from .handoff import active_source_counts, flatten


class ActiveSourceCountTests(unittest.TestCase):
    def test_current_nmr_replaces_reference_and_preserves_other_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'nmr.json'
            manifest=dict(dataset='NMRShiftDB2',original_author_split_preserved=True,
                counts=[dict(nucleus='13C',before=7,domain_eligible=5,retained=5,
                    reason_counts_nonexclusive={'CHARGE':2},primary_reason_counts={'CHARGE':2}),
                    dict(nucleus='1H',before=4,domain_eligible=3,retained=3,
                    reason_counts_nonexclusive={'SIZE':1},primary_reason_counts={'SIZE':1})])
            path.write_text(json.dumps(manifest))
            other=flatten('ASAP',dict(counts=[dict(before=4,domain_eligible=3,
                retained=4,blind_fallback_required=1)]),'blind.json')
            historical=flatten('NMRShiftDB2',dict(counts=[dict(nucleus='13C',before=99,
                domain_eligible=99,retained=99)]),'reference.json')
            groups={'NMRShiftDB2':{'count_rows':historical},'ASAP':{'count_rows':other}}
            rows=active_source_counts(groups,{'NMR2018_targets':str(path)})
            self.assertEqual([r['before'] for r in rows],[7,4,4])
            self.assertEqual([r['known_rejected'] for r in rows],[2,1,1])
            self.assertEqual(rows[0]['primary_reason_counts'],{'CHARGE':2})
            self.assertEqual(rows[0]['source_manifest'],str(path))
            self.assertEqual(rows[2],other[0])
            self.assertEqual(historical[0]['before'],99)

    def test_legacy_entry_without_override_preserves_historical_counts(self):
        rows=[{'dataset':'fixture','before':3}]
        self.assertEqual(active_source_counts({'fixture':{'count_rows':rows}},{}),rows)

    def test_invalid_override_fails_instead_of_silently_using_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'invalid.json'
            path.write_text(json.dumps(dict(dataset='NMRShiftDB2',
                original_author_split_preserved=True,counts=[{'nucleus':'13C'}])))
            with self.assertRaisesRegex(ValueError,'two original author nuclei'):
                active_source_counts({'NMRShiftDB2':{'count_rows':[]}},
                    {'NMR2018_targets':str(path)})
            with self.assertRaises(FileNotFoundError):
                active_source_counts({'NMRShiftDB2':{'count_rows':[]}},
                    {'NMR2018_targets':str(Path(tmp)/'missing.json')})


if __name__=='__main__':
    unittest.main()
