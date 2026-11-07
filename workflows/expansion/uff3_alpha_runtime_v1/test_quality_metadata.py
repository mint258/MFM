"""Two targeted metadata boundaries: original1% gate and real catalog EOF."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from .quality_gate import require_within_one_percent
from . import reference_catalog as R


class QualityMetadataTests(unittest.TestCase):
    def test_strict_new_canonical_record_gate_ignores_sourceNA_components_and_z(self):
        row=dict(field_id='26',field_key='SASA_atom',canonical_records=10000,newly_masked_records=100,
                 source_ineligible_records=9000,masked_components=999999,masked_fraction=.99,
                 original_new_mask_record_fraction=.01,robust_z_review_records=9999)
        require_within_one_percent({'all_stream_field_counts':[row]})
        with self.assertRaisesRegex(RuntimeError,'STOP_REPORT_USER.*101'):
            require_within_one_percent({'all_stream_field_counts':[{**row,'newly_masked_records':101}]})
        require_within_one_percent({'all_stream_field_counts':[{**row,'newly_masked_records':0}]})
        with self.assertRaisesRegex(RuntimeError,'COUNTS_REQUIRED'):
            require_within_one_percent({'all_stream_field_counts':[{**row,'newly_masked_records':10001}]})

    def test_real_catalog_complete_rows_SHA_EOF_mutation_duplicates_and_legacy(self):
        class Budget:
            def __init__(self):self.paths=[];self.checks=0
            def check(self):self.checks+=1
            def register(self,path):self.paths.append(path)
        with tempfile.TemporaryDirectory()as folder:
            root=Path(folder);b=Budget()
            rows=[dict(path=str(root/('family'+str(i)+'.parquet')),bytes=i,sha256=str(i)*64,
                       family='complete-original-family',extra_original_metadata={'ordinal':i})for i in range(3)]
            ref=R.write(root/'families.jsonl',rows,root,'family_files',b)
            self.assertEqual(ref['rows'],3);self.assertEqual(b.paths,[root/'families.jsonl'])
            self.assertGreater(b.checks,0);self.assertEqual(list(R.read(ref,root,'family_files')),rows)
            qa_ref={'path':str(root/'result.json')}
            qa={'all_family_file_references_catalog':ref}
            self.assertEqual(list(R.members(qa,'all_family_file_references',qa_ref)),rows)
            self.assertEqual(list(R.members({'all_family_file_references':rows},'all_family_file_references',qa_ref)),rows)
            with self.assertRaisesRegex(ValueError,'Ambiguous'):
                list(R.members({**qa,'all_family_file_references':[]},'all_family_file_references',qa_ref))
            with self.assertRaisesRegex(ValueError,'SHA/rows/bytes/EOF'):
                list(R.read({**ref,'sha256':'f'*64},root,'family_files'))
            with self.assertRaisesRegex(ValueError,'Duplicate'):
                list(R.members({'all_family_file_references':[rows[0],rows[0]]},'all_family_file_references',qa_ref))
            # Valid declared SHA/bytes but missing final newline still fails.
            raw=(root/'families.jsonl').read_bytes()[:-1];(root/'partial.jsonl').write_bytes(raw)
            partial={**ref,'path':str(root/'partial.jsonl'),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
            with self.assertRaisesRegex(ValueError,'newline'):list(R.read(partial,root,'family_files'))
            raw=R.Q.canonical(rows[0])+b'\n';(root/'duplicates.jsonl').write_bytes(raw+raw)
            duplicate={**ref,'path':str(root/'duplicates.jsonl'),'bytes':2*len(raw),'rows':2,'sha256':hashlib.sha256(raw+raw).hexdigest()}
            with self.assertRaisesRegex(ValueError,'Duplicate'):list(R.read(duplicate,root,'family_files'))
            reader=R.read(ref,root,'family_files');self.assertEqual(next(reader),rows[0])
            path=root/'families.jsonl';path.write_bytes(path.read_bytes().replace(b'ordinal',b'Ordinal'))
            with self.assertRaisesRegex(ValueError,'mutated|SHA'):list(reader)
            os.link(root/'duplicates.jsonl',root/'hardlink.jsonl')
            with self.assertRaisesRegex(ValueError,'hardlinks'):
                list(R.read({**duplicate,'path':str(root/'hardlink.jsonl')},root,'family_files'))


if __name__=='__main__':unittest.main()