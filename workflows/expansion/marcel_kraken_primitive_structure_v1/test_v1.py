"""Three exact synthetic primitive/structure boundaries before original bytes."""
import io,unittest
from . import primitive as P,structure as S


def u(s):
    raw=s.encode('utf-8',errors='surrogatepass')
    return b'\x8c'+bytes([len(raw)])+raw if len(raw)<256 else b'X'+len(raw).to_bytes(4,'little')+raw


def decode(body,frame=False):
    raw=b'\x80\x04'+(b'\x95'+len(body).to_bytes(8,'little') if frame else b'')+body
    return P.Reader(io.BytesIO(raw),lambda:None,len(raw)).decode()


class Boundaries(unittest.TestCase):
    def test_literal_ID_string_and_binary64_negative_zero_exact(self):
        body=b'}('+u('000')+u(' C[C@H](F)Cl ')+b'G'+bytes.fromhex('8000000000000000')+b'}\x87u.'
        root,proof=decode(body);native,value=root.entries[0]
        self.assertEqual(native,'000');self.assertEqual(value[0],' C[C@H](F)Cl ')
        self.assertEqual(value[1].raw.hex(),'8000000000000000');self.assertIs(type(value[2]),P.AssignmentMap)
        self.assertTrue(proof['BINFLOAT_original_eight_bytes_retained']);self.assertFalse(proof['payload_globals_imported_or_executed'])
        large,other=decode(b'}('+u('long')+u('x'*300)+b'u.',frame=True)
        self.assertEqual(large.entries[0][1],'x'*300);self.assertEqual(other['opcode_counts']['BINUNICODE'],1)
    def test_frame_memo_duplicate_assignments_cycle_and_unsafe_rejection(self):
        body=b'}\x94'+u('name')+u('first')+b's('+u('name')+b'h\x00u.'
        root,proof=decode(body,True);self.assertEqual(len(root.entries),2);self.assertIs(root.entries[1][1],root)
        self.assertEqual(proof['opcode_counts']['SETITEM'],1);self.assertEqual(proof['opcode_counts']['SETITEMS'],1)
        self.assertEqual(S.graph(root)['cycle_edges'],1);self.assertEqual(S.inspect(root)['status'],'SOURCE_STRUCTURE_UNKNOWN_HOLD')
        for raw in (b'\x80\x04cbuiltins\neval\n.',b'\x80\x04h\x00.',b'\x80\x04\x95\xff\xff\xff\x7f\x00\x00\x00\x00}.',
                    b'\x80\x04\x95\x01\x00\x00\x00\x00\x00\x00\x00X\x01\x00\x00\x00x.'):
            with self.assertRaises(P.UnknownPrimitive):P.Reader(io.BytesIO(raw),lambda:None,len(raw)).decode()
    def test_shape_positions_first_no_semantic_key_or_assay_acceptance(self):
        mean=P.AssignmentMap();mean.entries.append(('property',P.F64Bits(bytes.fromhex('3ff0000000000000'))))
        props=P.AssignmentMap();props.entries.append(('sterimol_B5',P.F64Bits(bytes.fromhex('7ff8000000000042'))))
        conf=P.AssignmentMap();conf.entries.append(('conf_000',('opaque molblock\nM  END\n',P.F64Bits(bytes.fromhex('3ff0000000000000')),props)))
        root=P.AssignmentMap();root.entries.append(('0007',(' CCO ',mean,conf)))
        report=S.inspect(root);self.assertTrue(report['matches_author_loader_expected_tuple_positions'])
        self.assertEqual((report['top_source_assignments'],report['secondary_source_assignments']),(1,1))
        self.assertEqual(report['literal_top_entry_examples'][0]['native_root_key']['literal_if_at_most_512_bytes'],'0007')
        self.assertEqual(report['literal_top_entry_examples'][0]['tuple_position_0_literal_evidence']['literal_if_at_most_512_bytes'],' CCO ')
        self.assertFalse(report['ligand_conformer_ID_or_field_semantics_accepted']);self.assertEqual(report['normalized_key_calls'],0)
        self.assertFalse(report['assay_float_values_persisted'])
