"""Metadata authority boundaries; no scientific data are read or fabricated."""
import copy
import sys
from types import SimpleNamespace
from pathlib import Path
import unittest
from unittest.mock import patch
from . import quality_authority as A
from .collector import select_replicas


def pin(name):return {'path':'/metadata-fixture/'+name,'bytes':1,'sha256':name}


def documents():
    parent={'State':'COMPLETED','ExitCode':'0:0','endpoint':A.Q.ENDPOINT,'UID':'1264','JobIDRaw':'fixture'}
    review=dict(schema='ROOT_NO_PM7_UFF_D_MATCHED_TRAIN_REFERENCE_V1',status='APPROVED_REFERENCE_APPLICATION_ONLY',
        reviewer='root',R_N_fit_as_TRAIN=False,same_D_function_units_and_family_field_map_reviewed=True,
        UFF_D3_vs_original_TRAIN_domain_difference_reviewed=True,actual_parent=parent,
        actual_accounting_reference=pin('account'),producer_receipt_reference=pin('producer'),
        TRAIN_calibration_reference=pin('cal'),TRAIN_reference_domain_reference=pin('domain'),
        fit_records=10953084,Common_TRAIN_native_records_before_D5_exclusion=10973084,
        D5_PM7_held_native_records_excluded=20000)
    cal=dict(schema='PUBCHEM_FULL_COMMON_TRAIN_D27_CALIBRATION_V1',fit_role='TRAIN_ONLY',coverage_fingerprint='fixture',
        provisional_scope_not_final_Common=False,R_N_used_for_fit=False,
        fields={str(i):{'TRAIN_n':580397586 if i==24 else 10953084}for i in range(27)})
    domain=dict(schema='PUBCHEM_FULL_COMMON_TRAIN_D27_REFERENCE_DOMAIN_V1',fit_role='TRAIN_ONLY',
        calibration_reference=pin('cal'),coverage_fingerprint='fixture',actual_source_and_role_census_closed=True,
        full_Common_census_closed=True,new_R_N_TRAIN_fit=False,robust_z_review_only_no_automatic_mask=True,fit_records=10953084)
    account=dict(endpoint=A.Q.ENDPOINT,uid=1264,actual_parents=[parent],raw_sacct_reference=pin('raw'))
    return {'review':review,'cal':cal,'domain':domain,'account':account,'producer':{}}


class QualityMetadataTests(unittest.TestCase):
    def validate(self,docs):
        with patch.object(A,'read',side_effect=lambda ref:docs[ref['sha256']]),patch.object(A.Q,'verify',return_value=Path('/not-read')):
            return A.accepted(pin('review'))

    def test_real_scope_contract_rejects_provisional_and_nonTRAIN_fits(self):
        docs=documents();self.assertEqual(self.validate(docs)[1]['fields']['24']['TRAIN_n'],580397586)
        for section,field,value in [('cal','provisional_scope_not_final_Common',True),
                ('domain','full_Common_census_closed',False),('cal','R_N_used_for_fit',True),('domain','fit_records',50000)]:
            bad=copy.deepcopy(docs);bad[section][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):self.validate(bad)

    def test_atom_weighting_and_actual_parent_are_not_substitutable(self):
        docs=documents();docs['cal']['fields']['24']['TRAIN_n']=10953084
        with self.assertRaises(ValueError):self.validate(docs)
        docs=documents();docs['account']['actual_parents']=[{**docs['review']['actual_parent'],'JobIDRaw':'other'}]
        with self.assertRaisesRegex(ValueError,'same independent Root accounting'):self.validate(docs)

    def test_transport_projection_does_not_import_large_data_or_replace_named_code(self):
        code=pin('code');needed=pin('mask-json');large=pin('large-DATA')
        item=lambda ref,path:dict(source_reference=ref,replica_reference={**ref,'path':path},origin_endpoint='Main',origin_uid=1278)
        original={'replicas':[item(code,'/actual/common.py')]}
        extra={'replicas':[item(code,'/actual/anonymous.blob'),item(needed,'/actual/mask.blob'),item(large,'/actual/large.blob')]}
        rows=select_replicas(original,extra,[code,needed])
        self.assertEqual(len(rows),2);self.assertEqual(rows[0]['replica_reference']['path'],'/actual/common.py')
        self.assertFalse(any(i['source_reference']==large for i in rows))
        with self.assertRaisesRegex(ValueError,'Missing required'):select_replicas(original,extra,[pin('absent')])

    def test_current_key_only_shards_no_composition_prefix_or_old_policy(self):
        from .ordered_contract import complete
        f={'schema':'PUBCHEM_EXACT_KEY_FILTERED_SHARDS_V1','status':'COMPLETE',
           'policy':{'identity_kinds':['full','wp5'],'composition_veto':False},
           'eligible_molecules':16000000,'candidates':[{**pin(str(i)),'rows':1000000,'fp_bucket':format(i,'x')}for i in range(16)]}
        rank={'schema':'expansion_nested_queues_v1','status':'CANDIDATE_ORDER_COMPLETE_NO_CONFORMERS_COMPUTED',
              'pool_molecules':16000000,'seed':20261025,'queue_molecules_each':5000000,
              'first_batch_molecules_each':1250000,'downstream_features_used':False,'filtered_pool':pin('filtered')}
        nn={'schema':'PUBCHEM_SHARDED_FULL_POOL_NOVELTY_V1','status':'COMPLETE','queries':16000000,
            'filtered_pool_reference':pin('filtered'),'projection_parts':[pin('whole-part')]}
        self.assertEqual(len(complete(rank,f,nn)),16)
        split=copy.deepcopy(f);part=split['candidates'].pop(0);split['candidates'][:0]=[{**part,'rows':400000},{**part,'path':'other-part','rows':600000}]
        self.assertEqual(len(complete(rank,split,nn)),17)
        for mutate in ('composition','old','prefix','invalid-bucket'):
            bad=copy.deepcopy(f)
            if mutate=='composition':bad['policy']['composition_veto']=True
            elif mutate=='old':bad['schema']='expansion_filtered_columnar_pool_v1'
            elif mutate=='prefix':bad['candidates'][0]['rows']-=1
            else:bad['candidates'][0]['fp_bucket']='10'
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):complete(rank,bad,nn)
        with self.assertRaises(ValueError):complete(rank,f,{**nn,'queries':15999999})

if __name__=='__main__':unittest.main()