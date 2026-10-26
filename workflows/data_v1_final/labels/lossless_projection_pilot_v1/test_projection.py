"""Three cache-specific synthetic boundaries, no real scientific bodies."""
import json, struct, unittest
from .projection import (encode,decode,signature,source_float_signature,scientific_cells,
                         component_map,cache_row,verify_cache_row)


class ProjectionBoundaries(unittest.TestCase):
    def test_typed_bits_order_and_unsupported_stop(self):
        nan=struct.unpack('<d',bytes.fromhex('420000000000f87f'))[0]
        value={'int64':2**63-1,'bool':True,'null':None,'bytes':b'\x00\xff',
               'scientific_strings':['P-PI','S-SIGMA'],'leaves':[0.0,-0.0,nan,float('inf'),-7.0]}
        template,values=encode(value);restored=decode(template,values)
        self.assertEqual(signature(value),signature(restored))
        self.assertEqual(struct.pack('<d',restored['leaves'][1]),struct.pack('<d',-0.0))
        self.assertEqual(struct.pack('<d',restored['leaves'][2]),bytes.fromhex('420000000000f87f'))
        self.assertIs(type(restored['int64']),int);self.assertIs(type(restored['bool']),bool)
        self.assertEqual(list(restored),list(value))
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED'):encode({'unrecognized':{1,2}})

    def test_original_arrow_width_nan_bits_and_slice_offsets(self):
        import pyarrow as pa
        # Source bit pools are read from Arrow buffers, never inferred from Python float.
        f32=[bytes.fromhex(x) for x in ['0000803f','00000080','4500c07f']]
        f64=[bytes.fromhex(x) for x in ['000000000000f03f','0000000000000080','420000000000f87f']]
        a=pa.Array.from_buffers(pa.float32(),3,[None,pa.py_buffer(b''.join(f32))]).slice(1)
        b=pa.Array.from_buffers(pa.float64(),3,[None,pa.py_buffer(b''.join(f64))]).slice(1)
        batch=pa.record_batch([a,b],names=['original_f32','original_f64'])
        first=source_float_signature(batch,0);second=source_float_signature(batch,1)
        self.assertEqual(first['observed_float_width_counts'],{'32':1,'64':1})
        self.assertEqual(first['original_float32_bit_pool'][0]['bits_le_hex'],f32[1].hex())
        self.assertEqual(second['original_float32_bit_pool'][0]['bits_le_hex'],f32[2].hex())
        self.assertNotEqual(first['source_buffer_bits_sha256'],second['source_buffer_bits_sha256'])

    def test_ordered_basis_pairs_empty_NA_and_reopen_semantics(self):
        from workflows.data_v1_final.labels import common
        field={'field_key':'P.pm7_B.r73.value','registry_id':73,'source_path':'values.sigma_pi_entries',
               'component':'value','level':'sparse_atom_pair','status':'enabled'}
        empty={'field_key':'P.pm7_anion.r199.total','registry_id':199,'source_path':'values.enpart_one_center_eV',
               'component':'total','level':'atom','status':'N/A'}
        pairs=[{'atom_i':0,'basis_i':'S-SIGMA','atom_j':1,'basis_j':'P-PI','value':x} for x in [.1,.3]]
        pairs.insert(1,{'atom_i':1,'basis_i':'P-PI','atom_j':0,'basis_j':'S-SIGMA','value':.2})
        row={'total_atoms':2,'values':[{'registry_id':73,'kind':8,'text':json.dumps(pairs),'shape':[]},
                                      {'registry_id':199,'kind':8,'text':'[]','shape':[]}]}
        cells,decoded,pos,dups=scientific_cells(row,'pm7_neutral',[field,empty],common)
        mapping=component_map(row,'pm7_neutral',[field,empty],common,decoded,pos,dups)
        self.assertEqual(len(mapping[0]['ordered_leaf_paths']),3)
        self.assertEqual(mapping[1]['layout_reason'],'SOURCE_CELL_EMPTY')
        owner={'record_ordinal':9,'record_id':'opaque:9','molecule_id':'m'}
        cached=cache_row('task',owner,2,{'cells':cells,'component_map':mapping,'mask':b'\x00\x01'})
        actual=verify_cache_row(cached)
        self.assertEqual(actual['cells'][0]['decoded_scientific_value'],pairs)
        self.assertEqual([x['value'] for x in actual['cells'][0]['decoded_scientific_value']],[.1,.2,.3])
        self.assertEqual(actual['cells'][0]['decoded_scientific_value'][1]['atom_i'],1)
        broken=dict(cached,values_float64=list(cached['values_float64']))
        broken['values_float64'][0]=-broken['values_float64'][0]
        with self.assertRaisesRegex(ValueError,'CACHE_REOPEN'):verify_cache_row(broken)
        bad={'total_atoms':2,'values':[{'registry_id':73,'kind':8,'text':'{"a":1,"a":2}','shape':[]}]}
        with self.assertRaisesRegex(RuntimeError,'DUPLICATE_JSON_OBJECT_KEYS'):
            scientific_cells(bad,'pm7_neutral',[field],common)

if __name__=='__main__':unittest.main()
