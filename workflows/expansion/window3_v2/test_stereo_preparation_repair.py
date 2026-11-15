"""Synthetic metadata only: never replay a native failure or existing geometry."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from . import stereo_batch as batch
from .stereo import defaults


class RepairTests(unittest.TestCase):
    def test_only_known_zero_native_preparation_paths_are_selected(self):
        for state,error,expected in [
            (batch.OLD_STATE,None,True),
            ('SOURCE_INTEGRITY_HOLD','IntegrityError: POTENTIAL_DOUBLE_WITHOUT_STEREO_REFERENCES',True),
            ('SOURCE_INTEGRITY_HOLD','IntegrityError: GENERATED_GRAPH_OR_ATOM_ORDER_CHANGED',False),
            ('EMBED_FAILED',None,False),('INSUFFICIENT_UNIQUE_CONFORMERS',None,False),
            ('UFF_UNSUPPORTED',None,False),('SUCCESS',None,False),('TECHNICAL_UNKNOWN',None,False)]:
            self.assertEqual(batch.preparation_failure(dict(state=state,error=error)),expected)

    def test_repair_preserves_original_status_and_native_failure_and_replaces_only_preparation_outcome(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);base=root/'base';base.mkdir()
            original=[]
            for i in (1,2):
                key='KEY'+str(i)
                original.append(dict(molecule_id='expansion-pubchem:test:'+str(i)+':'+key,
                    state=batch.OLD_STATE,error=None,actual_conformers=0,pubchem_version='test',
                    pubchem_cid=i,full_key=key,wp5_key=key+':N',stream='R',stream_rank=i,
                    source_smiles='CC(=N)N',isomeric_smiles='CC(=N)N',
                    orders_json='{}',generation_order_json='[]',cache_complete=True))
            schema=pa.Table.from_pylist(original).schema
            (root/'schema').write_bytes(schema.serialize().to_pybytes())
            connection=sqlite3.connect(root/'old.sqlite')
            connection.execute('CREATE TABLE original(mid TEXT PRIMARY KEY,ordinal INTEGER,row_json TEXT)')
            connection.executemany('INSERT INTO original VALUES(?,?,?)',
                [(r['molecule_id'],i,json.dumps(r)) for i,r in enumerate(original)])
            connection.commit();connection.close()
            batch.save(root/'old_manifest.json',[dict(path='/unreadable/D20.parquet',size=1,rows=2)])
            batch.save(root/'prepared.json',dict(original_manifest=str(root/'old_manifest.json'),
                original_status_schema=str(root/'schema'),original_status_index=str(root/'old.sqlite'),
                original_molecules_with_3D=0,original_conformers=0))
            rows=[dict(r,**{k:defaults()[k] for k in batch.FIELDS},job_id=1) for r in original]
            rows[0].update(stereo_draw_index=3)  # Superseded preparation redraw.
            rows[1].update(state='EMBED_FAILED',stereo_draw_index=3)
            status=base/'source_status.parquet';pq.write_table(pa.Table.from_pylist(rows),status)
            timing=base/'timings.parquet'
            pq.write_table(pa.Table.from_pylist([dict(molecule_id=r['molecule_id'],
                assigned_CIP_counts_json=json.dumps({label:1}),assigned_EZ_counts_json='{}')
                for r,label in zip(rows,['R','S'])]),timing)
            batch.save(base/'manifest.json',[dict(path=str(p),size=p.stat().st_size,rows=2) for p in [status,timing]])
            batch.save(base/'summary.json',dict(counts=dict(molecules=2,conformers=0),
                stereo=dict(CIP=dict(R=1,S=1),EZ={},redrawn_molecules=2)))
            selection=batch.prepare_repair(dict(base_output=str(base),output=str(root/'selection')))
            self.assertEqual(selection['stereo_molecules'],1)
            selected=[json.loads(line) for r in selection['stereo_source_parts'] for line in Path(r['path']).read_text().splitlines()]
            self.assertEqual([r['cid'] for r in selected],[1])
            repair=root/'repair';repair.mkdir()
            corrected=dict(rows[0],state='SUCCESS',actual_conformers=3,job_id=2,stereo_assigned=True,stereo_draw_index=0,
                orders_json='{"energy":[0,1,2]}',generation_order_json='[0,1,2]',cache_complete=True)
            corrected_path=repair/'source_status.parquet';pq.write_table(pa.Table.from_pylist([corrected]),corrected_path)
            batch.save(repair/'manifest.json',[dict(path=str(corrected_path),size=corrected_path.stat().st_size,rows=1),
                dict(path='/unreadable/new/geometry.parquet',size=1,rows=3)])
            batch.save(repair/'summary.json',dict(counts=dict(molecules=1,conformers=3),
                stereo=dict(CIP=dict(S=1),EZ={},redrawn_molecules=0)))
            config=dict(prepared=str(root/'prepared.json'),delivery=str(root/'delivery'),producer_outputs=[str(base)],
                preparation_repairs=[dict(prepared=str(root/'selection/prepared.json'),output=str(repair))])
            with patch.object(batch,'EXPECTED',2):batch.finalize(config)
            summary=batch.read(root/'delivery/batch_summary.json')
            self.assertEqual(summary['effective_states'],dict(SUCCESS=1,EMBED_FAILED=1))
            self.assertEqual(summary['preparation_repairs'],1)
            self.assertEqual(summary['processing_events'],3)
            self.assertEqual(summary['assigned_CIP_counts'],dict(R=0,S=2))
            self.assertEqual(summary['redrawn_molecules'],1)
            self.assertEqual(summary['redrawn_processing_events'],2)
            self.assertEqual(summary['redrawn_final_zero_conformers'],1)
            self.assertEqual(summary['redrawn_unknown_conformer_count'],0)
            self.assertEqual(summary['effective_conformer_counts'],{'0':1,'3':1})
            self.assertEqual(summary['zero_geometry_states'],{'EMBED_FAILED':1})
            refs=batch.read(root/'delivery/manifest.json')
            final=pq.read_table(next(r['path'] for r in refs if Path(r['path']).name=='source_status.parquet')).to_pylist()
            for old,new in zip(original,final):self.assertEqual({k:new[k] for k in old},old)
            self.assertEqual([r['stereo_preparation_repaired'] for r in final],[True,False])
            self.assertEqual(final[0]['effective_generation_order_json'],'[0,1,2]')
            # A separate correction aimed at the known native failure is refused.
            corrected=dict(rows[1],state='SUCCESS',actual_conformers=3,job_id=2)
            pq.write_table(pa.Table.from_pylist([corrected]),corrected_path)
            config['delivery']=str(root/'refused')
            with patch.object(batch,'EXPECTED',2),self.assertRaisesRegex(ValueError,'WOULD_REPEAT_NATIVE_WORK'):
                batch.finalize(config)


if __name__ == '__main__':unittest.main()
