"""Three same-Parent synthetic boundaries; no live HTTP or original DATA."""
import copy,json,sqlite3,tempfile,unittest
from pathlib import Path
from . import closure as R,consumer as V
WORKSPACE=None

class SyntheticBudget:
    def check(self,*args,**kwargs):pass
    def charge(self,n):R.need(type(n)is int and n>=0,'SYNTHETIC_POSITIVE_BYTE_CHARGE')

class Atom:
    def __init__(self,z):self.z=z
    def GetAtomicNum(self):return self.z
    def HasQuery(self):return False

class FakeChem:
    class SmilesParserParams:pass
    @staticmethod
    def MolFromSmiles(text,params):
        R.need(text=='*CO','ONLY_SYNTHETIC_LITERAL')
        class Mol:
            def GetAtoms(self):return [Atom(0),Atom(6),Atom(8)]
            def GetBonds(self):return []
        return Mol()
    @staticmethod
    def MolToInchiKey(*args):raise AssertionError('FULL_KEY_FORBIDDEN')

class FakeTable:
    def GetElementSymbol(self,z):return {1:'H',6:'C',7:'N',8:'O'}.get(z,'E'+str(z))

class Boundaries(unittest.TestCase):
    def test_exact_invalid_marker_scope_and_dummy_without_substitution_or_key(self):
        for node in R.NODES:self.assertEqual(R.parameters(node)['node'],node)
        with self.assertRaises(ValueError):R.parameters('compute-0-19')
        self.assertTrue({11,20,25}.isdisjoint(R.WHITELIST))
        for name in ('record','charge','check'):self.assertIs(getattr(R.Budget,name),getattr(R.M.Budget,name))
        source={'source_id':'toxcast','source_row_ordinal':7,'source_record_sha256':'a'*64,'source_record_bytes':8,'source_offset':0,
          'identity_fields':{'0':{'literal_column_name':'smiles','state':'PRESENT','text':'FAIL'}}}
        case={'subdataset':'ToxCast','original_source':source,'original_identity_row':{'source_id':'toxcast','source_row_ordinal':7,'full_keys':[],'WP5_keys':[],
          'source_record_sha256':'a'*64,'source_record_bytes':8,'source_offset':0}}
        self.assertTrue(R.exact_FAIL(case))
        self.assertEqual(R.marker_binding(case),source)
        bad=copy.deepcopy(case);bad['original_identity_row']['source_record_sha256']='b'*64
        with self.assertRaises(ValueError):R.marker_binding(bad)
        for text in ('CCO','fail',' FAIL','INVALID'):
            bad=copy.deepcopy(case);bad['original_source']['identity_fields']['0']['text']=text;self.assertFalse(R.exact_FAIL(bad))
        bad=copy.deepcopy(case);bad['original_source']['identity_fields']['1']={'literal_column_name':'id','state':'PRESENT','text':'synthetic'};self.assertFalse(R.exact_FAIL(bad))
        bad=copy.deepcopy(case);bad['original_identity_row']['source_row_ordinal']=8;self.assertFalse(R.exact_FAIL(bad))
        audit=R.collections.Counter();bound,facts=R.known_core('*CO',FakeChem,audit);self.assertEqual(bound,[[6,1],[8,1]]);self.assertEqual(facts['all_original_atoms_in_original_order'],[0,6,8])
        self.assertEqual(audit['original_MolFromSmiles_invocations'],1)
        self.assertFalse(facts['dummy_substituted_or_removed']);self.assertFalse(facts['full_key_or_resolved_graph_created'])
        for malformed in ([],[[6,0]],[[6,True]],[[6,1.]],[[6,1],[6,2]],[[8,1],[6,1]]):
            with self.assertRaises(ValueError):V.vector(malformed)

    def test_peptide_altloc_models_are_not_added_and_only_explicit_atom_elements(self):
        entity={'rcsb_polymer_entity_container_identifiers':{'entry_id':'1PTS','entity_id':'2','asym_ids':['C'],'auth_asym_ids':['P']},
          'entity_poly':{'pdbx_seq_one_letter_code_can':'AAAAAAA'}}
        def line(res,atom,element,alt='',record='ATOM'):
            text=list(' '*80);text[:6]=list(record.ljust(6));text[12:16]=list(atom.rjust(4));text[16]=alt or ' ';text[17:20]=list('ALA');text[21]='P';text[22:26]=list(str(res).rjust(4));text[76:78]=list(element.rjust(2));return ''.join(text).encode()
        rows=[b'MODEL        1']+[line(i,'CA','C') for i in range(1,8)]+[line(1,'O','O','A'),line(1,'O','O','B'),line(1,'NA','N',record='HETATM'),b'ENDMDL',b'MODEL        2']
        rows += [line(i,'CA','C') for i in range(1,7)]+[b'ENDMDL',b'END']
        bound,facts=R.peptide_bounds(b'\n'.join(rows)+b'\n',entity,FakeTable())
        self.assertEqual(bound,[[6,6]]);self.assertEqual(len(facts['model_altloc_variants']),3)
        self.assertFalse(facts['coordinates_decoded']);self.assertFalse(facts['exact_composition_claimed']);self.assertFalse(facts['HETATM_or_missing_atoms_inferred'])
        bad=b'\n'.join([line(1,'CA',''),b'END'])
        with self.assertRaises(ValueError):R.peptide_bounds(bad,entity,FakeTable())
        wrong=copy.deepcopy(entity);wrong['rcsb_polymer_entity_container_identifiers']['auth_asym_ids']=['X']
        with self.assertRaises(ValueError):R.peptide_bounds(b'\n'.join(rows),wrong,FakeTable())

    def test_real_SQL_filter_executes_typed_veto_and_retains_original_exact_objects(self):
        self.assertIs(V.identity_keys,V.legacy.identity_keys);self.assertIs(V.contamination_exact,V.legacy.contamination)
        self.assertNotEqual(V.INDEX,'expansion_exclusion_index_v1');self.assertNotEqual(V.MANIFEST,'expansion_decontamination_sources_v1')
        with self.assertRaises(ValueError):V.index_header({'schema':'expansion_exclusion_index_v1','status':'COMPLETE','sources':dict.fromkeys(V.legacy.REQUIRED),'typed_lower_bound_rules':2})
        R.need(WORKSPACE is not None,'ACTUAL_PARENT_SYNTHETIC_WORKSPACE')
        with tempfile.TemporaryDirectory(prefix='molnet_v2_synthetic_',dir=WORKSPACE) as directory:
            root=Path(directory);excluded=sqlite3.connect(root/'excluded.sqlite');V.install_tables(excluded)
            excluded.execute('INSERT INTO excluded VALUES(?,?,?)',('composition','[[6,1]]','qm7'))
            excluded.execute('INSERT INTO constraints VALUES(?,?,?)',('synthetic_core','moleculenet','synthetic_original_case'))
            excluded.execute('INSERT INTO constraint_atoms VALUES(?,?,?)',('synthetic_core',6,2));excluded.commit()
            incoming=sqlite3.connect(root/'incoming.sqlite');incoming.execute('CREATE TABLE candidates(full_key TEXT PRIMARY KEY,cid INTEGER UNIQUE,wp5_key TEXT,features TEXT NOT NULL)')
            for i,pairs in enumerate(([[6,1]],[[6,2]],[[6,1],[7,1]]),1):
                key=chr(64+i)*14+'-'+'B'*10+'-N';feature={'cid':i,'full_key':key,'elements':[p[0] for p in pairs],'non_h_composition':json.dumps(pairs,separators=(',',':'))}
                incoming.execute('INSERT INTO candidates VALUES(?,?,?,?)',(key,i,V.legacy.wp5_key(key),json.dumps(feature)))
            incoming.commit();outgoing=sqlite3.connect(root/'output.sqlite')
            counts=V.filter_rows(incoming,excluded,outgoing,SyntheticBudget())
            self.assertEqual(counts['input_unique_molecules'],3);self.assertEqual(counts['excluded_molecules'],2);self.assertEqual(counts['eligible_molecules'],1)
            self.assertEqual(counts['conservative_lower_bound_exclusions'],1);self.assertEqual(outgoing.execute('SELECT cid FROM candidates').fetchall(),[(3,)])
            self.assertEqual(counts['additional_conservative_veto_beyond_exact_possible_over_exclusion'],1)
            with self.assertRaises(ValueError):V.candidate_domain({'elements':[11],'non_h_composition':'[[11,1]]'})
            with self.assertRaises(ValueError):V.candidate_domain({'elements':[6],'non_h_composition':'[[6,1],[7,1]]'})
            with self.assertRaises(ValueError):V.identity_keys({'source_id':'synthetic','role':'all','non_h_composition_lower_bound':[[6,1]]})
            # Exercise the actual legacy consumer's schema gate: it must stop
            # before quota/data work rather than silently omit V2 constraints.
            sp=root/'screen.json';ip=root/'index.json';rp=root/'regression.json'
            sp.write_text(json.dumps({'schema':'pubchem_screen_v1','complete_source':True}));ip.write_text(json.dumps({'schema':V.INDEX,'status':'COMPLETE'}));rp.write_text('{}')
            with self.assertRaises(ValueError):V.legacy.filter_pool(sp,ip,rp,root/'never_created',None,1)
            incoming.close();excluded.close();outgoing.close()
