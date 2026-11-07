"""Synthetic metadata refusal tests; no production DB, Slurm or chemistry."""
import copy
import json
from pathlib import Path
import tempfile
import sys
import types
import unittest
from unittest.mock import patch
from .. import alpha_common_followup_plans_v1 as H
from .run import baseline_binding,strict_addition,same_cross_node_frame


class Refusals(unittest.TestCase):
    def test_original_baseline_source_change_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def save(name,value):
                path=root/name;path.write_text(json.dumps(value));return H.pin(path)
            recipe=save('functional_group_recipe.json',{'recipe':'synthetic'})
            baseline=save('baseline_receipt.json',{'synthetic':True})
            population=save('pubchem_baseline_population.json',dict(population='pubchem_1m',expected_molecules=1000000,
              sampling={'uniform':True},baseline_pool_phase='BEFORE_V1_DOWNSTREAM_DECONTAMINATION_AND_NOVELTY',authority_reference=baseline))
            oldplan=save('plan.json',dict(output_directory=str(root),analysis_version='original',baseline_receipt_reference=baseline))
            scope=save('analysis_scope.json',dict(analysis_version='original',functional_group_recipe_reference=recipe))
            parent=dict(State='COMPLETED',ExitCode='0:0',UID='1264',JobIDRaw='synthetic')
            receipt=save('receipt.json',dict(actual_parent={'SlurmJobID':'synthetic'},
              population_manifest_references={'pubchem_1m':population},plan_reference=oldplan,functional_group_recipe_reference=recipe))
            review=save('review.json',dict(schema='ROOT_ALPHA_BASELINE_POPULATION_STATISTICS_ACTUAL_ACCEPTANCE_V1',
              status='ACCEPTED_COMPLETE_FIXED_1M_POPULATION_TABLES',reviewer='root',uid=1264,
              populations={'pubchem_1m':1000000},actual_parent=parent,actual_parents=[parent],producer_receipt_reference=receipt))
            plan=dict(baseline_acceptance_reference=review,baseline_population_reference=population,
              baseline_scope_reference=scope,baseline_recipe_reference=recipe,baseline_database_path=str(root/'counted_statistics.sqlite'))
            baseline_binding(plan)
            changed=copy.deepcopy(plan);changed['baseline_population_reference']['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'cannot change'):baseline_binding(changed)
            (root/'functional_group_recipe.json').write_text('{"recipe":"changed"}')
            with self.assertRaises(ValueError):baseline_binding(plan)
        planned=[42,123456,1264,100,200,300];runtime=[41,*planned[1:]]
        self.assertTrue(same_cross_node_frame(runtime,planned))
        for index in range(1,6):
            changed=list(runtime);changed[index]+=1
            self.assertFalse(same_cross_node_frame(changed,planned))
        with self.assertRaises(ValueError):same_cross_node_frame(runtime[:-1],planned)

    def test_no_non_strict_or_non_c0_common_addition(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'common.json';path.write_text('{}')
            plan=dict(extension_policy='STRICT_ADD_ONLY_FULL_ACCEPTED_COMMON_V1',
              population_names=['pubchem_1m','v1_common'],analysis_version='new',common_reference_manifest=H.pin(path))
            with self.assertRaisesRegex(ValueError,'Accepted actual full Common'):strict_addition(plan,{'analysis_version':'old'})
            for change in ({'population_names':['pubchem_1m','R']},{'extension_policy':'replace_baseline'}, {'analysis_version':'old'}):
                with self.assertRaisesRegex(ValueError,'strict fullCommon addition'):
                    strict_addition({**plan,**change},{'analysis_version':'old'})
            path.write_text(json.dumps({'producer_schema':'ALPHA_COMMON_GENERIC_REPRESENTATION_REPAIR_COMPLETION_PRODUCER_V1','status':'RUNNING'}))
            plan['common_reference_manifest']=H.pin(path)
            package='workflows.expansion.exact_nn_cached_v1';name=package+'.alpha_common_repaired'
            fake_package=types.ModuleType(package);fake_package.__path__=[]
            fake=types.ModuleType(name);calls=[]
            def reject(value):
                calls.append(value)
                raise ValueError('Unapproved repaired Common rejected by strict new authority')
            fake.validate_manifest=reject
            with patch.dict(sys.modules,{package:fake_package,name:fake}),patch.object(H,'actual_common_parent',side_effect=AssertionError('Old authority fallback forbidden for repaired producer')):
                with self.assertRaisesRegex(ValueError,'Unapproved repaired Common'):
                    strict_addition(plan,{'analysis_version':'old'})
            self.assertEqual(len(calls),1)


if __name__=='__main__':unittest.main()
