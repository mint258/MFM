"""Synthetic metadata fixture: preserve original status and D20 references."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from . import stereo_batch
from .stereo import defaults


class StatusEvolutionTest(unittest.TestCase):
    def test_original_status_and_d20_are_preserved_with_exact_3d_membership(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original = [dict(molecule_id='old', state='SUCCESS', actual_conformers=3,
                pubchem_cid=1, full_key='old-key', stream='R', stream_rank=1,
                source_smiles='old-smiles', isomeric_smiles='old-isomeric', error=None),
                dict(molecule_id='assigned', state=stereo_batch.OLD_STATE, actual_conformers=0,
                pubchem_cid=2, full_key='assigned-key', stream='N', stream_rank=1,
                source_smiles='unspecified', isomeric_smiles='unspecified-isomeric', error=None)]
            schema = pa.Table.from_pylist(original).schema
            (root/'schema').write_bytes(schema.serialize().to_pybytes())
            connection = sqlite3.connect(root/'old.sqlite')
            connection.execute('CREATE TABLE original(mid TEXT PRIMARY KEY,ordinal INTEGER,row_json TEXT)')
            connection.executemany('INSERT INTO original VALUES(?,?,?)',
                                  [(r['molecule_id'],i,json.dumps(r)) for i,r in enumerate(original)])
            connection.commit(); connection.close()
            # This path must be retained verbatim, and must never be opened.
            old_refs = [dict(path='/unreadable-original/D20.parquet',size=123,rows=2),
                        dict(path='/historical/source_status.parquet',size=456,rows=2)]
            stereo_batch.save(root/'old_manifest.json', old_refs)
            prepared = dict(original_manifest=str(root/'old_manifest.json'),
                original_status_schema=str(root/'schema'), original_status_index=str(root/'old.sqlite'),
                original_molecules_with_3D=1, original_conformers=3)
            stereo_batch.save(root/'prepared.json',prepared)
            producer = root/'producer'; producer.mkdir()
            assigned = dict(original[1],**{k:defaults()[k] for k in stereo_batch.FIELDS},job_id=7)
            assigned.update(state='INSUFFICIENT_UNIQUE_CONFORMERS',actual_conformers=1,
                            stereo_assigned=True,assigned_isomeric_smiles='assigned-stereo')
            status = producer/'source_status.parquet'
            pq.write_table(pa.Table.from_pylist([assigned]),status)
            stereo_batch.save(producer/'manifest.json',[dict(path=str(status),size=status.stat().st_size,rows=1)])
            stereo_batch.save(producer/'summary.json',dict(counts=dict(conformers=1)))
            config = dict(prepared=str(root/'prepared.json'),delivery=str(root/'delivery'),
                          producer_outputs=[str(producer)])
            with patch.object(stereo_batch,'EXPECTED',1):
                stereo_batch.finalize(config)
            manifest = stereo_batch.read(root/'delivery/manifest.json')
            self.assertEqual(manifest[0],old_refs[0])
            statuses = pq.read_table(manifest[1]['path']).to_pylist()
            for before,after in zip(original,statuses):
                self.assertEqual({k:after[k] for k in before},before)
            self.assertEqual(statuses[1]['stereo_actual_conformers'],1)
            self.assertEqual(statuses[1]['state'],stereo_batch.OLD_STATE)
            summary = stereo_batch.read(root/'delivery/batch_summary.json')
            self.assertEqual(summary['molecules_with_3D'],2)
            self.assertEqual(summary['final_conformers'],4)
            self.assertEqual(summary['D20_recomputed'],0)


if __name__ == '__main__':
    unittest.main()
