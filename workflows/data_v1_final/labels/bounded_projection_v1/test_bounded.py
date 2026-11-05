"""Four new boundaries; synthetic values only, no real data or submission."""
import concurrent.futures,struct,tempfile,unittest
from pathlib import Path
from .parts import Ledger,TicketStop,TypedPart,CappedBuffer,publish_bytes,pin,slices
from . import records
from workflows.data_v1_final.labels.lossless_projection_pilot_v1.projection import cache_row,verify_cache_row,signature


class BoundedBoundaries(unittest.TestCase):
    def test_durable_cursor_unknown_and_cross_connection_ticket_race(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);ranges=[{'range_id':'r','physical_row_lo':0,'physical_row_hi':10}]
            ledger=Ledger(root/'state.sqlite',True,data_cap=100,inode_cap=10,ranges=ranges)
            ticket=ledger.reserve('r',0,40,2);self.assertEqual(ledger.cursor('r'),(0,10))
            with self.assertRaisesRegex(ValueError,'SECOND_DISPATCH'):ledger.reserve('r',0,40,2)
            receipt=publish_bytes(root/'receipt.json',b'{}\n');ledger.commit(ticket,4,receipt,3,1);ledger.close()
            ledger=Ledger(root/'state.sqlite');self.assertEqual(ledger.cursor('r'),(4,10))
            unknown=ledger.reserve('r',4,40,2);ledger.abandon(unknown);ledger.close()
            ledger=Ledger(root/'state.sqlite');self.assertEqual(ledger.snapshot()['charged_bytes_including_unknown'],43)
            with self.assertRaisesRegex(ValueError,'UNKNOWN_RETRY'):ledger.reserve('r',4,1,1)
            ledger.close()
            ranges+=[{'range_id':'s','physical_row_lo':0,'physical_row_hi':10}]
            ledger=Ledger(root/'race.sqlite',True,data_cap=20,inode_cap=10,ranges=ranges);ledger.close()
            def claim(key):
                db=Ledger(root/'race.sqlite')
                try:
                    try:db.reserve(key,0,12,1);return True
                    except TicketStop:return False
                finally:db.close()
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(claim,['r','s']))
            self.assertEqual(sum(results),1)

    def test_atomic_real_typed_part_reopens_bits_order_and_rejects_task_or_cap(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        pa.set_cpu_count(1);pa.set_io_thread_count(1)
        nan=struct.unpack('<d',bytes.fromhex('420000000000f87f'))[0]
        payload={'ordered_pairs':[{'atom_i':2,'basis_i':'P-PI','atom_j':1,'basis_j':'S-SIGMA','value':-0.0}],
          'scalars':[None,True,2**63-1,b'\x00\xff',nan,0.0],'float32_original_bits':'0100c07f'}
        owner={'record_ordinal':7,'record_id':'r','molecule_id':'m'};row=cache_row('task',owner,0,payload)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'part.parquet';part=TypedPart('task',0,1<<20,64<<20);part.add(row);report=part.finish(path)
            self.assertEqual(report['rows'],1);source=pq.ParquetFile(path)
            try:actual=source.read().to_pylist()[0]
            finally:source.close()
            restored=verify_cache_row(actual);self.assertEqual(signature(restored),signature(payload))
            self.assertEqual(struct.pack('<d',restored['scalars'][4]),bytes.fromhex('420000000000f87f'))
            self.assertEqual(list(restored['ordered_pairs'][0]),['atom_i','basis_i','atom_j','basis_j','value'])
            with self.assertRaisesRegex(ValueError,'OVERWRITE'):publish_bytes(path,b'x')
            other=TypedPart('task',1,1<<20,64<<20)
            with self.assertRaisesRegex(ValueError,'ONE_FAMILY_TASK'):other.add(row)
            other.writer.close();other.stream.release()
        cap=CappedBuffer(3)
        with self.assertRaisesRegex(ValueError,'NO_TRUNCATION'):cap.write(b'1234')
        cap.release()

    def test_actual_directory_resume_skips_closed_groups_and_rejects_gap(self):
        groups=[{'row_group':i,'physical_row_lo':4*i,'physical_row_hi':4*i+4} for i in range(3)]
        selected=list(slices(groups,6,11))
        self.assertEqual([(r['row_group'],r['selected_lo'],r['selected_hi']) for r in selected],[(1,6,8),(2,8,11)])
        self.assertEqual(selected[0]['selected_lo']-selected[0]['physical_row_lo'],2)
        with self.assertRaisesRegex(ValueError,'GAP_OR_OVERLAP'):
            list(slices([groups[0],dict(groups[1],physical_row_lo=5),groups[2]],2,10))

    def test_failed_base_retained_and_parity_excludes_only_declared_metadata(self):
        import pyarrow as pa
        from workflows.data_v1_final.labels.payload_audit_v1.payload import evaluate
        from workflows.data_v1_final.labels.lossless_projection_pilot_v1.projection import component_map,scientific_cells
        self.assertIs(records.evaluate,evaluate);self.assertIs(records.component_map,component_map);self.assertIs(records.scientific_cells,scientific_cells)
        row={'record_id':'r','molecule_id':'m','atomic_numbers':None,'positions_A':None,'geometry_status':'PROPERTY_FAILED'}
        batch=pa.RecordBatch.from_pylist([row]);owner={'record_ordinal':0,'record_id':'r','molecule_id':'m','total_atoms':1}
        cache,stats,observed=records.project(dict(row),batch,0,owner,{'family':'base_geometry'},{'source':'fixture'}, {})
        decoded=verify_cache_row(cache);self.assertEqual(decoded['original_geometry'],row)
        self.assertIn('BASE_ATOMIC_NUMBERS_UNUSABLE_RETAINED_NOT_LABEL_MASK',decoded['source_base_observations'])
        self.assertEqual((stats,observed),({},{}))
        task={k:[] for k in ('cells','component_map','field_observations','structural_reviews')}
        task.update(task='fixture',source_status_and_precision={'status':'SUCCESS'},source_float_bits={},raw_counts={},
          original_compact_candidate={'valid_fields':b'\x01','review_groups':[{'code':records.compact.CODE['ROBUST_Z_GT20_REVIEW_ONLY']}]})
        other=dict(task,provenance={'different':'physical-part'},original_compact_candidate={'valid_fields':b'\x01','review_groups':[]})
        self.assertEqual(records.parity_signature(task,'task'),records.parity_signature(other,'task'))
        other['original_compact_candidate']['valid_fields']=b'\x00'
        self.assertNotEqual(records.parity_signature(task,'task'),records.parity_signature(other,'task'))
        other['original_compact_candidate']={'valid_fields':b'\x01','review_groups':[{'code':records.compact.CODE['SUCCESS_WITH_CONVERGENCE_EVIDENCE_UNKNOWN']}]}
        self.assertNotEqual(records.parity_signature(task,'task'),records.parity_signature(other,'task'))

if __name__=='__main__':unittest.main()
