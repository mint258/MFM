"""Exactly3 synthetic boundaries; actual CPU only, before observer/DATA."""
import hashlib,json,pathlib,struct,tempfile,unittest
from . import contract as C,reader,core,executor,canonical_children


class Boundaries(unittest.TestCase):
    def test_native_Z_old_parquet_local_view_and_full_f64_Arrow_codec_readback(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        z=[6,1];digest=hashlib.sha256(struct.pack('<qq',*z)).hexdigest();row={'source_format':'parquet','atom_order_sha256':digest}
        raw={'atom_order_sha256':digest,'coordinates':[[-0.0,1.0+2**-52,0.0],[0.0,0.0,1.0]]}
        view=reader.verified_atom_view(raw,row,z);self.assertNotIn('atomic_numbers',raw);self.assertEqual(view['atomic_numbers'],z)
        for bad in ([1,6],[6,True]):
            with self.assertRaises(ValueError):reader.verified_atom_view(raw,row,bad)
        with self.assertRaises(ValueError):reader.verified_atom_view(raw,dict(row,source_format='reproduction_json_gz'),z)
        value={'geometry_id':'u:m:42','molecule_id':'m','geometry_source':'uff_sprime','native_record_id':None,
            'sprime_conf_idx':42,'parent_geometry_id':None,'view_id':None,'atomic_numbers':z,'positions_A':raw['coordinates'],
            'order_energy':None,'geometry_sha256':'a'*64,'atom_order_sha256':digest}
        schema=core.schemas()['geometries'];typed={k:value.get(k) for k in schema.names}
        from workflows.data_v1_final.labels.lossless_projection_pilot_v1.projection import signature
        with tempfile.TemporaryDirectory(prefix='d5_compound_source3_') as directory:
            p=pathlib.Path(directory)/'row.parquet';pq.write_table(pa.Table.from_pylist([typed],schema=schema),p)
            actual=pq.read_table(p).to_pylist()[0];self.assertEqual(signature(actual),signature(typed))
            self.assertEqual(signature(core.decode(core.encode(actual))),signature(typed))
            self.assertEqual(actual['positions_A'][0][0].hex(),'-0x0.0p+0');self.assertIsNone(actual['order_energy'])

    def test_canonical_occurrence_is_truthful_and_actual_input_hashes_are_exact(self):
        source={'path':'/actual/large.parquet','bytes':9<<30,'sha256':'a'*64}
        row={'record_id':'native:r','molecule_id':'m','calc_type':'xtb_perturbed_gradient','attempt_id':1,'job_id':3,'task_id':'4','lane':0,'input_bundle_sha256':'b'*64}
        first,identity=canonical_children.canonical_occurrence(source,7,row)
        self.assertTrue(first.startswith('canonical-source-occurrence:'));self.assertNotIn('original_execution_uuid',identity)
        self.assertNotEqual(first,canonical_children.canonical_occurrence(source,8,row)[0]);self.assertEqual(identity['record_id'],'native:r')
        from workflows.data_v1_final.export.d5_inputs_builder_v1 import children as H
        archive=H.sources()[2];rendered={'input.xyz':b'1\nsynthetic\nH 0 0 0\n'}
        files=[{'name':n,'sha256':hashlib.sha256(b).hexdigest()} for n,b in sorted(rendered.items())]
        data=[{'name':n,'data':b,'role':'input','byte_count':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in sorted(rendered.items())]
        digest=hashlib.sha256(archive.bundle(data)[0]).hexdigest();H.O.input_binding(rendered,files,digest,archive.bundle)
        with self.assertRaises(ValueError):H.O.input_binding({'input.xyz':rendered['input.xyz']+b' '},files,digest,archive.bundle)
        with self.assertRaises(ValueError):H.O.input_binding(rendered,files,'0'*64,archive.bundle)

    def test_actual_parent64_and_contiguous_verified_prefix_never_fake_child_C0(self):
        row={'logical_range':[0,512],'molecules':512,'held_molecules':0,'full_typed_source_order_identity_parity':True}
        self.assertEqual(executor.validate_prefix([row,dict(row,logical_range=[512,520],molecules=8)]),520)
        for bad in (dict(row,held_molecules=1),dict(row,logical_range=[1,513]),dict(row,full_typed_source_order_identity_parity=False)):
            with self.assertRaises(ValueError):executor.validate_prefix([bad])
        with self.assertRaises(ValueError):executor.validate_prefix([row,row])
        p={'job_id':'actual','node':'compute-0-18','alloc_cpus':64,'state':'COMPLETED','exit_code':'0:0'}
        self.assertIs(C.Bridge.c0_row(p,'actual','compute-0-18',64),p)
        for bad in (dict(p,state='TIMEOUT'),dict(p,alloc_cpus=16)):
            with self.assertRaises(ValueError):C.Bridge.c0_row(bad,'actual','compute-0-18',64)
        for ref in ({'path':'/a','bytes':True,'sha256':'a'*64},{'path':'/a','bytes':1,'sha256':'a'*65}):
            with self.assertRaises(ValueError):C.reference(ref)


if __name__=='__main__':unittest.main()
