"""Standard-library-only fixtures; synthetic metadata is not actual acceptance."""
import copy
from pathlib import Path
import tempfile
import unittest
from . import authority,budget
from ..alpha_runtime_v1 import common as Q
from ..pubchem_generic_recovery_overlay_v1.runtime import VERSION


def budget_fixture():
    global_budget=dict(schema='ROOT_ALPHA_ALL_FUTURE_STORAGE_BUDGET_V2',reviewer='root',endpoint='218.192.171.238:22',uid=1264,
      quota_root='/gfshome/alpha',scope_total_caps_bytes={'exact':1000,'bulk':400,'UFF':500},
      closed_credit_bytes_by_scope={'exact':100,'bulk':100},minimum_free_after_all_future_bytes=200)
    root='/gfshome/alpha/pubchem_expansion_20261103/exact/'
    review=dict(schema='ROOT_ALPHA_PRIVATE_EXACT_BUDGET_PARTITION_ACTUAL_REVIEW_V1',status='APPROVED_PRIVATE_EXACT_PARTITIONS',
      reviewer='root',endpoint=global_budget['endpoint'],uid=1264,quota_root='/gfshome/alpha',aggregate_scope_root=root[:-1],
      closed_legacy_allocated_bytes=100,closed_legacy_scopes=[dict(path=root+'closed',allocated_bytes=100,owned_uid=1264,all_writers_gone=True)],
      closed_legacy_writers_gone=True,closed_legacy_own_disjoint=True,closed_legacy_scope_census_reference={'synthetic':True},
      closed_legacy_actual_accounting_references=[{'synthetic':True}],partition_cap_total_bytes=900,
      nonexact_remaining_reserved_bytes=800,all_other_goals_and_exact_partitions_reserved=True,
      partitions=[dict(partition_key='rank',output_scope_root=root+'rank',output_cap_bytes=500,allocated_bytes_credit=0,
        remaining_reserved_bytes=500,other_future_reserved_bytes=1200,minimum_free_bytes=200),
        dict(partition_key='other',output_scope_root=root+'other',output_cap_bytes=400,allocated_bytes_credit=0,
        remaining_reserved_bytes=400,other_future_reserved_bytes=1300,minimum_free_bytes=200)])
    return review,global_budget


class Source(unittest.TestCase):
    def test_real_colocated_copies_are_required_instead_of_a_borrowed_import_only_path(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);origin=root/'origin';origin.mkdir()
            expansion=root/'capsule/workflows/expansion';package=expansion/'exact_nn_cached_v1';package.mkdir(parents=True)
            bindings={};refs=[]
            for name,destination in [('typed_rank.py',package/'typed_rank.py'),('external_sort.py',expansion/'external_sort.py')]:
                (origin/name).write_text('synthetic-original-body:'+name);destination.write_bytes((origin/name).read_bytes())
                bindings[name]=dict(origin_reference=Q.reference(origin/name),execution_reference=Q.reference(destination));refs.append(Q.reference(destination))
            ns_source=package/'__init__.py';ns_source.write_text('synthetic namespace metadata fixture');refs.append(Q.reference(ns_source))
            ns=root/'namespace.json';Q.write(ns,dict(capsule_exact_nn_cached_v1_path=str(package),
              exact_nn_cached_v1_search_paths=[str(package),'/gfshome/alpha/code/exact_Common_fixture/workflows/expansion/exact_nn_cached_v1'],
              namespace_source_reference=Q.reference(ns_source)))
            deployment=dict(original_rank_source_bindings=bindings,rank_namespace_manifest_reference=Q.reference(ns),code_references=refs)
            self.assertEqual(set(authority.deployed(deployment)),{'typed_rank.py','external_sort.py'})
            bad=copy.deepcopy(deployment);borrowed=bindings['external_sort.py']['origin_reference']
            bad['original_rank_source_bindings']['external_sort.py']['execution_reference']=borrowed;bad['code_references'].append(borrowed)
            with self.assertRaises(ValueError):authority.deployed(bad)

    def test_legacy_blocks_and_peer_remaining_futures_cannot_be_omitted(self):
        review,g=budget_fixture();self.assertEqual(budget.choose(review,g,'rank')['output_cap_bytes'],500)
        bad=copy.deepcopy(review);bad['closed_legacy_allocated_bytes']=101
        with self.assertRaises(ValueError):budget.choose(bad,g,'rank')
        bad=copy.deepcopy(review);bad['partitions'][0]['other_future_reserved_bytes']=1199
        with self.assertRaises(ValueError):budget.choose(bad,g,'rank')
        bad=copy.deepcopy(review);bad['partitions'][0]['output_cap_bytes']=501;bad['partitions'][0]['remaining_reserved_bytes']=501;bad['partition_cap_total_bytes']=901
        with self.assertRaises(ValueError):budget.choose(bad,g,'rank')

    def test_private_scopes_cannot_overlap_legacy_or_peer_and_remaining_must_be_exact(self):
        review,g=budget_fixture();bad=copy.deepcopy(review)
        bad['partitions'][0]['output_scope_root']=review['closed_legacy_scopes'][0]['path']+'/nested'
        with self.assertRaises(ValueError):budget.choose(bad,g,'rank')
        bad=copy.deepcopy(review);bad['partitions'][1]['remaining_reserved_bytes']=399
        with self.assertRaises(ValueError):budget.choose(bad,g,'rank')

    def test_wrapper_flags_and_full_census_cannot_be_replaced_by_small_validation_or_baseline(self):
        w=dict(schema='ALPHA_COMPILED_FULL_POOL_EXECUTION_METADATA_V1',status='FULL_POOL_EXECUTION_COMPLETE_PENDING_ROOT_ACTUAL_C0_REVIEW',
          original_run_code_object_preserved=True,only_injected_global='exact_batches',RDKit_nearest_engine_used=False,no_automatic_scientific_retry=True)
        n=dict(schema='expansion_exact_novelty_v1',status='COMPLETE',nearest_similarity_exact=True,downstream_features_used=False,
          fingerprint_recipe='ECFP4_2048_radius2_chiralityFalse_rdkit2025.09.5',queries=10000000,projection={'rows':10000000},reference_molecules=1196122)
        q=dict(schema='EXPANSION_TYPED_DECONTAMINATED_QUERY_PROJECTION_V1',status='COMPLETE',producer_schema='PUBCHEM_FULL_FP_ORDERED_TYPED_QUERY_V1',
          projection_order='ecfp4_2048_hex_ASC_full_key_ASC_cid_ASC',population_version=VERSION,fingerprint_recipe=n['fingerprint_recipe'],
          targets_present=False,downstream_features_present=False,projection={'rows':10000000})
        r=dict(schema='ROOT_ALPHA_COMPILED_FULL_POOL_ACTUAL_ACCEPTANCE_V1',status='APPROVED_COMPLETE_COMPILED_COMMON_EXACT_FULL_POOL',reviewer='root',queries=10000000)
        authority.execution_shapes(w,n,q,r)
        for changes in ({'queries':64},{'queries':1000000},{'status':'BOUNDED_COST_PILOT'}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):authority.execution_shapes(w,{**n,**changes},q,r)
        with self.assertRaises(ValueError):authority.execution_shapes({**w,'RDKit_nearest_engine_used':True},n,q,r)


if __name__=='__main__':unittest.main()
