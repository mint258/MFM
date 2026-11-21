def rebind_original_nmr_atoms(native_P_rows, corrected_original_rows):
    """Bind original author identity; unavailable identity never supplies P-prime."""
    corrected={r['record_id']:r for r in corrected_original_rows}
    if len(corrected)!=len(corrected_original_rows):raise ValueError('Duplicate original NMR spectrum ID')
    if len({r['record_id'] for r in native_P_rows})!=len(native_P_rows):
        raise ValueError('Duplicate native NMR spectrum ID')
    output=[]
    for prior in native_P_rows:
        source=corrected.get(prior['record_id'])
        if source is None:raise ValueError('Native P binding has no corrected original spectrum')
        identity=('official_split','retained','domain_eligible')
        if any(prior[k]!=source[k] for k in identity):raise ValueError('Original NMR split or mask changed')
        same_key=prior['full_inchikey']==source['full_inchikey']
        if not same_key and prior['full_inchikey'].split('-')[0]!=source['full_inchikey'].split('-')[0]:
            raise ValueError('Original NMR molecular connectivity changed')
        old={a['original_atom_index']:a for a in prior['atoms']}
        current={a['original_atom_index']:a for a in source['atoms']}
        if len(old)!=len(prior['atoms']) or len(current)!=len(source['atoms']) or set(old)!=set(current):
            raise ValueError('Original NMR atom label set changed')
        atoms=[]
        for atom in source['atoms']:
            previous=old[atom['original_atom_index']]
            if atom['y']!=previous['y']:raise ValueError('Original experimental NMR target changed')
            atoms.append(dict(atom,Pprime_features=previous['Pprime_features'] if same_key else None,
                              Pprime_valid_mask=previous['Pprime_valid_mask'] if same_key else None))
        output.append(dict(source,atoms=atoms,
            native_Pprime_state=prior['native_Pprime_state'] if same_key else 'NATIVE_PPRIME_IDENTITY_UNRESOLVED_NO_IMPUTATION',
            native_UFF_conformer_id=prior['native_UFF_conformer_id'],
            native_Pprime_identity_binding='FULL_INCHIKEY_MATCH' if same_key else 'STEREO_IDENTITY_MISMATCH_PPRIME_UNAVAILABLE',
            legacy_native_full_inchikey=prior['full_inchikey']))
    if len(output)!=len(corrected):raise ValueError('An original NMR spectrum disappeared from native P binding')
    return output
import unittest
class OriginalAtomRebindTests(unittest.TestCase):
    def fixture(self):
        source=dict(record_id='s1',full_inchikey='KEY',official_split='test',retained=True,domain_eligible=True,
                    original_mol_binary=b'CORRECT',atoms=[dict(original_atom_index=3,y=12.7,rdkit_atom37=[6.])])
        prior=dict(source,original_mol_binary=b'OLD_ORDER',atoms=[dict(original_atom_index=3,y=12.7,rdkit_atom37=[1.],
                   Pprime_features=[.25,float('nan')],Pprime_valid_mask=[True,False])],
                   native_Pprime_state='AVAILABLE',native_UFF_conformer_id=7)
        return prior,source
    def test_native_P_values_survive_correct_original_graph_and_RDKit_binding(self):
        prior,source=self.fixture();row=rebind_original_nmr_atoms([prior],[source])[0]
        self.assertEqual(row['original_mol_binary'],b'CORRECT')
        self.assertEqual(row['atoms'][0]['rdkit_atom37'],[6.])
        self.assertEqual(row['atoms'][0]['Pprime_features'][0],.25)
        self.assertEqual(row['atoms'][0]['Pprime_valid_mask'],[True,False])
        self.assertEqual(row['native_UFF_conformer_id'],7)
    def test_experimental_value_or_source_atom_set_cannot_change(self):
        prior,source=self.fixture();source['atoms'][0]['y']=99.
        with self.assertRaises(ValueError):rebind_original_nmr_atoms([prior],[source])
        prior,source=self.fixture();source['atoms'][0]['original_atom_index']=4
        with self.assertRaises(ValueError):rebind_original_nmr_atoms([prior],[source])
    def test_missing_original_spectrum_is_not_silently_discarded(self):
        prior,source=self.fixture()
        with self.assertRaises(ValueError):rebind_original_nmr_atoms([prior],[])



class NativeIdentityAvailabilityTests(unittest.TestCase):
    fixture=OriginalAtomRebindTests.fixture
    def mismatch(self):
        prior,source=self.fixture()
        prior['full_inchikey']='AAAAAAAAAAAAAA-BBBBBBBBBB-N'
        source['full_inchikey']='AAAAAAAAAAAAAA-CCCCCCCCCC-N'
        return prior,source
    def test_stereo_identity_mismatch_never_uses_available_P(self):
        prior,source=self.mismatch();row=rebind_original_nmr_atoms([prior],[source])[0]
        self.assertEqual(row['full_inchikey'],source['full_inchikey'])
        self.assertEqual(row['original_mol_binary'],source['original_mol_binary'])
        self.assertEqual(row['atoms'][0]['y'],source['atoms'][0]['y'])
        self.assertIsNone(row['atoms'][0]['Pprime_features'])
        self.assertIsNone(row['atoms'][0]['Pprime_valid_mask'])
        self.assertEqual(prior['atoms'][0]['Pprime_features'][0],.25)
        self.assertEqual(row['native_UFF_conformer_id'],7)
        self.assertEqual(row['legacy_native_full_inchikey'],prior['full_inchikey'])
    def test_already_missing_P_stays_missing_under_correct_author_identity(self):
        prior,source=self.mismatch();prior['atoms'][0].update(Pprime_features=None,Pprime_valid_mask=None)
        row=rebind_original_nmr_atoms([prior],[source])[0]
        self.assertIsNone(row['atoms'][0]['Pprime_features'])
        self.assertEqual(row['native_Pprime_state'],'NATIVE_PPRIME_IDENTITY_UNRESOLVED_NO_IMPUTATION')
    def test_other_molecular_connectivity_is_not_silently_adopted(self):
        prior,source=self.mismatch();source['full_inchikey']='DDDDDDDDDDDDDD-CCCCCCCCCC-N'
        with self.assertRaises(ValueError):rebind_original_nmr_atoms([prior],[source])
    def test_author_split_and_domain_masks_remain_strict(self):
        for key,value in (('official_split','train'),('retained',False),('domain_eligible',False)):
            prior,source=self.mismatch();source[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):rebind_original_nmr_atoms([prior],[source])
    def test_duplicate_native_spectrum_or_author_atom_cannot_alias(self):
        prior,source=self.fixture()
        with self.assertRaises(ValueError):rebind_original_nmr_atoms([prior,prior],[source])
        prior,source=self.fixture();source['atoms'].append(dict(source['atoms'][0]))
        with self.assertRaises(ValueError):rebind_original_nmr_atoms([prior],[source])

if __name__=='__main__':unittest.main()
