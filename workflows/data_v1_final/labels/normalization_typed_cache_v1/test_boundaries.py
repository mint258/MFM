"""Three synthetic source-interface boundaries. No DATA, native call or mocks."""
from __future__ import annotations

import copy
import hashlib
import json
import unittest
from . import contract as C
from .index import validate_locator
from .ordering import logical_manifest, ordered_keys, row_key


def ref(name):
    return {'path':'/share/home/zixiao/descriptor_analysis/SYNTHETIC_D4_FIXTURE/'+name,'bytes':1,'sha256':'0'*64}


def authorities():
    origin = {'origin_id':'synthetic-adopted','origin_type':'TIMEOUT_ADOPTED_CLOSED_WINDOWS',
              'old_producer_state':'TIMEOUT', **{k:ref(k) for k in
              ('old_producer','inventory','seed','root_adoption','root_parent_chain_review')}}
    release = {'schema':C.RELEASE_SCHEMA,'reviewer':'root','status':'ROOT_APPROVED_EXACT_FINAL_D4_INPUTS',
               'reason':'SYNTHETIC FIXTURE ONLY; no existing/future artifact asserted',
               'parents':{k:ref(k) for k in C.FINAL_PARENTS},'coverage_counts':dict(C.COUNTS),
               'accepted_origin_reviews':[origin], 'fit_role':'TRAIN','validation_source':'ROUTINE',
               'final_mask_validity_regeneration_unchanged':True,'dataset_geometry_source':'pm7',
               'no_P_value_substitution_for_Pprime':True}
    coverage = {'schema':C.COVERAGE_SCHEMA,'status':'FULL_NUMERIC_SOURCE_COVERAGE_OBSERVED_NOT_FINAL_MASKS',
                'all14task_and_base_exact_once':True,'unresolved_consumed_count':0,'held_source_count':0,
                'unverified_part_count':0,'quality_hold_fields':[],
                'actual_parts_inventory_reference':release['parents']['parts_inventory'],
                'accepted_origins':[{'origin_id':origin['origin_id'],'origin_type':origin['origin_type']}],
                'origin_counts':{'TIMEOUT_ADOPTED_CLOSED_WINDOWS':1},'final_mask_release':False,'D4_release':False}
    return release, coverage


class Boundaries(unittest.TestCase):
    def test_complete_mixed_origin_authority_never_promotes_timeout_or_partial(self):
        release, coverage = authorities()
        self.assertIs(C.validate_release(release,coverage),release)
        for key in ('unresolved_consumed_count','held_source_count','unverified_part_count'):
            for value in (1,False):
                bad=copy.deepcopy(coverage);bad[key]=value
                with self.assertRaises(ValueError):C.validate_release(release,bad)
        bad=copy.deepcopy(release);bad['accepted_origin_reviews'][0]['old_producer_state']='COMPLETED'
        with self.assertRaises(ValueError):C.validate_release(bad,coverage)
        bad=copy.deepcopy(coverage);bad['quality_hold_fields']=[73]
        with self.assertRaises(ValueError):C.validate_release(release,bad)
        candidate=C.candidate({'schema':'ROOT_D4_TYPED_CACHE_CANDIDATE_REQUEST_V1'})
        self.assertFalse(candidate['stage_spec_generated']);self.assertTrue(candidate['missing_parents'])

    def test_exact_locator_fit_side_and_independent_pprime_boundary(self):
        owner={'record_id':'r','molecule_id':'m','record_ordinal':0,'attempt_id':1,'job_id':2,'task_id':'t',
               'lane':0,'total_atoms':2,'heavy_atoms':1,'record_payload_sha256':'a'*64,'new_role':'TRAIN',
               'effective_role':'TRAIN','common_population':True,'geometry_source':'pm7','geometry_id':'opaque',
               'fit_reason':'FIT_TRAIN_COMMON_NOT_DIAGNOSTIC','fit_eligible':True}
        row={'partition_id':0,'record_ordinal':0,'task_code':0,'row_kind':'task','original_file_position':0,
             'source_physical_row':7,'part':ref('part'),'row_group':0,'local_row':0,'origin_id':'synthetic','owner':owner}
        self.assertIs(validate_locator(row),row)
        for updates in ({'effective_role':'VAL'},{'fit_reason':'HELDOUT_GEOMETRY_OR_ITS_PERTURBED_VIEW'},
                        {'geometry_source':'uff_sprime'},{'common_population':False}):
            bad=copy.deepcopy(row);bad['owner'].update(updates)
            with self.assertRaises(ValueError):validate_locator(bad)
        bad=copy.deepcopy(row);bad['local_row']=True
        with self.assertRaises(ValueError):validate_locator(bad)
        from . import bindings as B
        from .reader import final_compact_parity
        candidate={key:[] for key in B.cache_original.PARITY_KEYS}
        candidate.update(record_ordinal=0,task_code=0)
        for key in ('in_scope_fields','source_valid_fields','valid_fields','all_leaves_valid_fields'):
            candidate[key]=B.compact.bits([0])
        candidate['newly_masked_fields']=B.compact.bits([])
        final=copy.deepcopy(candidate)
        final['review_groups']=[{'code':1,'fields':B.compact.bits([0])}]
        self.assertTrue(final_compact_parity(candidate,final))
        final['valid_fields']=B.compact.bits([])
        with self.assertRaises(ValueError):final_compact_parity(candidate,final)

    def test_original_logical_groups_and_chunk256_survive_physical_repacking(self):
        from . import bindings as B
        self.assertTrue(all(B.verify_function_objects()['checks'].values()))
        groups=[{'group_index':5+p,'source_job_id':20+p,'owner_index':ref('owners'+str(p)),
                 'label_files':[ref('file0_'+str(p)),ref('file1_'+str(p))]} for p in range(3)]
        manifest=logical_manifest('PM7_PD',ref('original_plan'),groups,[3,5])
        self.assertEqual(manifest['TSQR_chunk'],256)
        rows=[{'partition_id':p,'original_file_position':i//137,'source_physical_row':i%137,
               'value':float((i+1)*(p+1))/7,'numbers':[1,6] if i%2 else [1,1,8]}
              for p in range(3) for i in range(274)]
        # Two cache packet layouts and arrival orders contain the same originals.
        layouts=[rows, list(reversed(rows[::2]))+list(reversed(rows[1::2]))]
        states=[]; hashes=[]; models=[]
        for layout in layouts:
            ordered=sorted(layout,key=row_key);self.assertEqual(len(list(ordered_keys(ordered))),822)
            qrs={p:B.TSQR([1,6,8]) for p in range(3)}
            self.assertTrue(all(qr.chunk==256 for qr in qrs.values()));digest=hashlib.sha256()
            for row in ordered:
                qrs[row['partition_id']].add(row['numbers'],row['value'])
                digest.update(json.dumps([row_key(row),row['value']]).encode())
            ordered_states=[qrs[p].state() for p in range(3)]
            states.append(ordered_states);hashes.append(digest.hexdigest())
            models.append(B.merge_qr(ordered_states))
        self.assertEqual(states[0],states[1]);self.assertEqual(hashes[0],hashes[1])
        self.assertEqual(models[0],models[1])
        with self.assertRaises(ValueError):list(ordered_keys([rows[0],rows[0]]))


if __name__=='__main__':
    unittest.main()
