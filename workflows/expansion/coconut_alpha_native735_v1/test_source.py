"""Real original COPY decoder/formula boundaries, no external DATA fixtures."""
import hashlib,json,unittest
from . import kernel as K


class Source(unittest.TestCase):
    def fixture(self):
        names=list(K.OLD+K.NATIVE);fields={k:None for k in names}
        fields.update(id='17',canonical_smiles='*C',standardized_canonical_smiles='*C',collection_id='8',status='REJECTED',is_invalid='f',
          molecular_formula='C6H12O6',reference_id='literal\\N',link='https://example.invalid/a\tb')
        def encode(value):
            if value is None:return b'\\N'
            return value.replace('\\','\\\\').replace('\t','\\t').replace('\n','\\n').encode()
        raw=b'\t'.join(encode(fields[k]) for k in names)+b'\n'
        row=dict(source_table='entries',copy_block=1,source_row_ordinal=1,source_bytes=len(raw),source_row_sha256=hashlib.sha256(raw).hexdigest(),
          identity_fields_json=json.dumps({k:fields[k] for k in K.OLD}))
        return names,fields,raw,row

    def test_original_copy_preserves_NULL_literal_and_escapes(self):
        names,fields,raw,row=self.fixture();value=K.decode(raw,row,names,K.STATE['copy_text'],1024)
        self.assertEqual(value['reference_id'],'literal\\N');self.assertEqual(value['link'],fields['link'])
        self.assertIsNone(value['coconut_id']);self.assertEqual(value['molecular_formula'],'C6H12O6')

    def test_row_digest_identity_fields_and_NULL_FK_are_bound(self):
        names,fields,raw,row=self.fixture()
        with self.assertRaises(ValueError):K.decode(raw+b'\n',row,names,K.STATE['copy_text'],1024)
        other=dict(row,identity_fields_json=json.dumps({**{k:fields[k] for k in K.OLD},'id':'18'}))
        with self.assertRaises(ValueError):K.decode(raw,other,names,K.STATE['copy_text'],1024)
        fields['molecule_id']='123';cells=raw[:-1].split(b'\t');cells[names.index('molecule_id')]=b'123';raw2=b'\t'.join(cells)+b'\n'
        # Even a self-consistent FK can never be silently reparented by native fields.
        bad=dict(row,source_bytes=len(raw2),source_row_sha256=hashlib.sha256(raw2).hexdigest(),identity_fields_json=json.dumps({k:fields[k] for k in K.OLD}))
        with self.assertRaisesRegex(ValueError,'NULL_FK'):K.decode(raw2,bad,names,K.STATE['copy_text'],1024)

    def test_actual_original_formula_whole_string_and_all_components(self):
        formula=K.STATE['kernel'].formula
        self.assertEqual(formula('C6H12O6')['composition'],[[6,6],[8,6]])
        self.assertEqual(formula('2CH4.O')['composition'],[[6,2],[8,1]])
        for text in [' C6H12O6','C6H12O6?','C6H12O6 R','C6H12O6.','C6H12O6\\N']:
            self.assertIsNone(formula(text)['composition'])

    def test_native_formula_never_accepts_graph_or_source_ID_association(self):
        names,fields,raw,row=self.fixture()
        diagnosis=dict(norm_observation=dict(source=row,has_any_valid_full_key=False),original_UNKNOWN_unchanged=True,
          new_authoritative_keys=False,strict5_written=False,replay=dict(covered=False))
        opaque=dict(source=row,opaque_original_row_reference=dict(path='/not/read/by/worker',bytes=len(raw),sha256=row['source_row_sha256']))
        value=K.work((diagnosis,opaque,raw,names,1024))
        self.assertEqual(value['native_formula_observation']['composition'],[[6,6],[8,6]])
        self.assertIs(value['original_diagnosis'],diagnosis)
        for key in ('graph_identity_repaired','new_authoritative_keys','native_formula_exclusion_accepted','official_reference_association_accepted','all11_ready'):self.assertIs(value[key],False)


if __name__=='__main__':unittest.main()
