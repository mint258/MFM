"""Metadata/IPC-shape fixtures; native integration still requires actual full-ref64."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ..alpha_runtime_v1 import common as Q
from . import entry,workers,namespace,authority


class Wiring(unittest.TestCase):
    def test_only_batch_global_is_changed_and_original_Guard_and_code_retained(self):
        sentinel=object();original=entry.scientific.run;prior=original.__globals__['exact_batches']
        cloned=entry.clone_run(sentinel)
        self.assertIs(cloned.__code__,original.__code__)
        self.assertIs(cloned.__globals__['Guard'],original.__globals__['Guard'])
        self.assertIs(original.__globals__['exact_batches'],prior)
        self.assertEqual([k for k in cloned.__globals__ if cloned.__globals__[k]is not original.__globals__[k]],['exact_batches'])

    def test_full_pool_metadata_refuses_truncation_costpilot_and_pending_projection(self):
        with tempfile.TemporaryDirectory()as d:
            p=Path(d)/'query.json';q=dict(schema='EXPANSION_TYPED_DECONTAMINATED_QUERY_PROJECTION_V1',status='COMPLETE',
                fingerprint_recipe=entry.scientific.RECIPE,targets_present=False,downstream_features_present=False,projection=dict(rows=10000000))
            Q.write(p,q);plan=dict(schema='PUBCHEM_EXACT_CACHED_NN_PLAN_V1',query_manifest=Q.reference(p))
            self.assertEqual(entry.full_query(plan),q)
            for value in (None,1,10000000):
                with self.assertRaises(ValueError):entry.full_query({**plan,'max_queries':value})
            tiny={**q,'projection':dict(rows=52000)};Q.write(p,tiny,replace=True)
            with self.assertRaises(ValueError):entry.full_query({**plan,'query_manifest':Q.reference(p)})
            for key,value in [('schema','expansion_exact_query_cost_pilot_v1'),('status','PENDING')]:
                bad={**q,key:value};Q.write(p,bad,replace=True)
                with self.assertRaises(ValueError):entry.full_query({**plan,'query_manifest':Q.reference(p)})

    def test_fixed_IPC_result_retains_integers_and_F64_without_debug_or_decode_claim(self):
        value=dict(score=.1,score_numerator=11,score_denominator=110,reference_ordinal=0,
            reference_molecules=10,evaluated_references=7,strictly_bound_pruned_references=3,searched_popcount_groups=[11,110])
        class Reference:
            def nearest(self,raw):return copy.deepcopy(value)
        result=workers.fixed_result(Reference(),[(9,b'raw')])
        self.assertEqual(result,[(9,b'raw',{k:v for k,v in value.items()if k!='searched_popcount_groups'})])
        self.assertEqual(value['searched_popcount_groups'],[11,110])

    def test_old_or_changed_namespace_cannot_be_implicitly_resumed(self):
        with tempfile.TemporaryDirectory()as d:
            out=Path(d)/'old201';out.mkdir();(out/'queries.sqlite').write_bytes(b'fixture only')
            plan=dict(output_directory=str(out),resume_output_directory=str(out),cache_namespace=namespace.key({'fixture':'new'}))
            with self.assertRaises((ValueError,FileNotFoundError)):namespace.establish(plan,{'fixture':'new'})
            self.assertFalse((out/'adapter.lock').exists())
            del plan['resume_output_directory']
            with self.assertRaises(ValueError):namespace.establish(plan,{'fixture':'new'})

    def test_206_kernel_approval_never_substitutes_worker_entry_native_acceptance(self):
        with patch.object(authority,'read',return_value=dict(schema='ROOT_ALPHA_COMPILED_EXACT_POPCOUNT_ACTUAL_ACCEPTANCE_V1',
                status='APPROVED_COMPILED_INTEGER_BACKEND_FOR_FUTURE_COMMON_EXACT_NN')):
            with self.assertRaises(ValueError):authority.integration({'fixture':'notactual'}, {'fixture':'206'})


if __name__=='__main__':unittest.main()
