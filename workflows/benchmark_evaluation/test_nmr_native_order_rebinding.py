def rebind_original_nmr_atoms(native_P_rows, corrected_original_rows):
    """Preserve native P values, using each original graph's own atom-indexed RDKit fields."""
    corrected={r['record_id']:r for r in corrected_original_rows}
    if len(corrected)!=len(corrected_original_rows):raise ValueError('Duplicate original NMR spectrum ID')
    output=[]
    for prior in native_P_rows:
        source=corrected.get(prior['record_id'])
        if source is None:raise ValueError('Native P binding has no corrected original spectrum')
        identity=('full_inchikey','official_split','retained','domain_eligible')
        if any(prior[k]!=source[k] for k in identity):raise ValueError('Original NMR identity, split or mask changed')
        old={a['original_atom_index']:a for a in prior['atoms']}
        if len(old)!=len(prior['atoms']) or set(old)!={a['original_atom_index'] for a in source['atoms']}:
            raise ValueError('Original NMR atom label set changed')
        atoms=[]
        for atom in source['atoms']:
            previous=old[atom['original_atom_index']]
            if atom['y']!=previous['y']:raise ValueError('Original experimental NMR target changed')
            atoms.append(dict(atom,Pprime_features=previous['Pprime_features'],
                              Pprime_valid_mask=previous['Pprime_valid_mask']))
        output.append(dict(source,atoms=atoms,native_Pprime_state=prior['native_Pprime_state'],
                           native_UFF_conformer_id=prior['native_UFF_conformer_id']))
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

if __name__=='__main__':unittest.main()
