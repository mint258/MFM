"""Saved metadata/F64/unknown/storage boundaries; no RDKit, UFF or D calls."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ..uff3_candidate_v1 import core as C
from . import validation as V,storage,closed


def fixture(n=3,missing=False):
    source={'pubchem_version':'fixture','cid':1,'full_key':'fixture-key','source_smiles':'C','isomeric_smiles':'C','stream':'R','stream_rank':1}
    mid=C.molecule_id(source);numbers=[6];rows=[]
    for i in range(n):
        xyz=[[-0.0,float(i),0.0]];rows.append({'candidate_id':i,'coordinates':xyz,'energy':float(i),
            'geometry_sha256':C.geometry_sha(numbers,xyz)})
    d20=None if missing else{'names':['n'+str(i)for i in range(20)],'values':[-0.0]+[1.]*19,'valid_mask':[True]*20,'issues':[]}
    cache={'schema':'PUBCHEM_UFF3_CLOSED_CANDIDATE_CACHE_V1','source':source,'source_identity_sha256':C.source_identity(source),
        'recipe_sha256':C.recipe_sha(),'recipe':C.RECIPE,'molecule_id':mid,'seed':C.seed_for(mid),'D20':d20,
        'atomic_numbers':numbers,'canonical_candidates':copy.deepcopy(rows),'valid_candidates':copy.deepcopy(rows),
        'embedding_calls':int(n>0),'optimizer_calls':n,'complete':True,'error':None}
    cache['cache_content_sha256']=C.sha(C.canonical(cache))
    confs=[{**r,'conformer_id':i,'D3':{name:([1.]if name=='SASA_atom_A2'else 1.)for name in V.D3_NAMES},'D3_issues':[]}for i,r in enumerate(rows)]
    p={'schema':'PUBCHEM_UFF3_SELECTED_PACKET_V1','source':source,'molecule_id':mid,'recipe_sha256':C.recipe_sha(),
       'candidate_cache_sha256':cache['cache_content_sha256'],'seed':cache['seed'],'atomic_numbers':numbers,'atom_order_sha256':'fixture-order',
       'D20':d20,'dataset_version':'v2_candidate','training_eligible':False,'requested_conformers':3,'actual_conformers':n,
       'no_fill':True,'no_retry':True,'new_QM_calls':0,'conformers':confs,'generation_order':list(range(n)),
       'orders':{name:list(range(n))for name in ('fixed_random','energy','diversity')},'state':'SUCCESS'if n==3 else'SPARSE',
       'insufficient_conformers':n<3,'cache_complete':True}
    p['packet_content_sha256']=C.sha(C.canonical(p))
    m={'export_limit':3,'actual_conformers':n,'closed_cache_reused_without_UFF':False}
    e=[{'phase':'molecule_intent'},{'phase':'graph_return'}]
    if n:e.append({'phase':'embedding_intent'})
    e.extend({'phase':'optimizer_intent','candidate_id':i}for i in range(n))
    e.extend({'phase':'descriptor_intent','conformer_id':i}for i in range(n))
    e.append({'phase':'packet_closed','packet':copy.deepcopy(p)})
    return source,cache,p,m,e


class ClosureMetadataTests(unittest.TestCase):
    def test_saved_zero_sparse_and_full_records_are_all_retained(self):
        for n in (0,1,3):
            result=V.packet(*fixture(n,missing=n==0))
            self.assertEqual(result['delivered_conformers'],n)
            self.assertEqual(result['actual_conformers'],n)
            self.assertFalse(result['D20_native_call_count_replayed_or_inferred'])
            self.assertEqual(result['cache_available'],True)
        self.assertEqual(V.packet(*fixture(0,True))['D20_state'],'UNAVAILABLE_FAILED_OR_UNKNOWN_NO_REPLAY')

    def test_saved_coordinate_bits_and_duplicate_optimizer_intent_rejected(self):
        args=list(fixture());p=args[2];p['conformers'][0]['coordinates'][0][0]=0.0
        p.pop('packet_content_sha256');p['packet_content_sha256']=C.sha(C.canonical(p))
        with self.assertRaisesRegex(ValueError,'Saved coordinate'):V.packet(*args)
        args=list(fixture());args[4].insert(2,{'phase':'optimizer_intent','candidate_id':0})
        with self.assertRaisesRegex(ValueError,'once intents'):V.packet(*args)
        self.assertNotEqual(V.numeric_hash(-0.0),V.numeric_hash(0.0))
        self.assertNotEqual(V.numeric_hash(None),V.numeric_hash([]))

    def test_interrupted_delivered_zero_does_not_become_known_generated_zero_or_cache(self):
        source=fixture()[0];m={'schema':'PUBCHEM_UFF3_INTERRUPTED_MOLECULE_V1','source':source,
            'source_identity_sha256':C.source_identity(source),'state':'INTERRUPTED_NO_AUTOMATIC_SCIENCE_RETRY'}
        r=V.interrupted(source,m)
        self.assertIsNone(r['actual_conformers']);self.assertEqual(r['delivered_conformers'],0)
        self.assertIsNone(r['saved_cache_supports_at_least_four_total']);self.assertFalse(r['cache_available'])
        self.assertEqual(r['D20_state'],'UNKNOWN_INTERRUPTED_NO_REPLAY')

    def test_projection_scales_only_variable_UFF_D_not_shared_NN_QA_cost(self):
        rows=[{'category':c,'logical_file_bytes':n,'actual_allocated_blocks_bytes':n*2}for c,n in
              [('UFF_D_FAMILY_DATA',100),('SAVED_MOLECULE_EVIDENCE',200),('QA_ANALYSIS_AND_SQL_SCRATCH',9000),('SHARED_READ_ONLY_INPUT',8000)]]
        p=storage.projection(rows,0)
        self.assertEqual(p['projected_logical_dataset_bytes'],1200)
        self.assertEqual(p['projected_allocated_dataset_bytes'],2400)
        self.assertIsNone(storage.projection(rows,1))

    def test_native_closed_file_SHA_and_symlink_not_just_declared_size(self):
        from ..alpha_runtime_v1 import common as Q
        with tempfile.TemporaryDirectory()as folder:
            root=Path(folder);path=root/'closed.json';path.write_bytes(b'{"saved":true}\n');ref=Q.reference(path)
            # Only replace the Alpha path-prefix admission in this pure Main
            # filesystem fixture; production entry still requires actual Alpha.
            with patch.object(Path,'is_relative_to',return_value=True):
                self.assertEqual(closed.document(ref,1024),{'saved':True})
                path.write_bytes(b'{"saved":null}\n')
                with self.assertRaises(ValueError):closed.document(ref,1024)
                link=root/'link';link.symlink_to(path)
                with self.assertRaises(ValueError):closed.content({**Q.reference(path),'path':str(link)},1024)


if __name__=='__main__':unittest.main()