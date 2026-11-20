"""Only new confirmation dispatch logic; no fitted outputs or real data are read."""
import unittest
from workflows.benchmark_evaluation.confirmation import prepare_confirmation_source
from workflows.benchmark_evaluation.selection import IncompleteComparison

class ConfirmationTests(unittest.TestCase):
    def source(self):
        return """SEED=20261025
calls=[]
class Model:
    def __init__(self,random_state):self.seed=random_state
    def fit(self,*args):calls.append((task,population,self.seed,SEED))
group='DATA'
for task in ('keep','skip'):
    for population in ('retained','full'):
        model=Model(random_state=SEED)
        model.fit()
report=dict(seed=SEED)
"""
    def prepare(self,source=None,learner="TabPFN",reason="FINAL_SIGNIFICANT_IMPROVEMENT"):
        return prepare_confirmation_source(source or self.source(),learner,
                    [dict(dataset="DATA",producer_task="keep")],default_dataset="DATA",reason=reason)
    def test_only_selected_native_task_and_primary_fit_are_executed(self):
        namespace={};exec(self.prepare(),namespace)
        self.assertEqual(namespace["calls"],[("keep","retained",20261026,20261025)])
        self.assertEqual(namespace["report"]["seed"],20261026)
        self.assertFalse(namespace["report"]["conditional_confirmation"]["task_roster_reselection"])
    def test_CV_conditional_population_loop_is_also_primary_only(self):
        source=self.source().replace("('retained','full')","(('retained',) if False else ('retained','full'))")
        namespace={};exec(self.prepare(source),namespace)
        self.assertEqual(namespace["calls"],[("keep","retained",20261026,20261025)])
    def test_Chemprop_seed_changes_without_changing_budget_or_statistics(self):
        source="""from __future__ import annotations
SEED=20261025
class PL:
    def seed_everything(self,value,**kw):self.model_seed=value
pl=PL()
def train_predict():
    pl.seed_everything(SEED,workers=True)
    return 50,64,SEED
group='DATA'
seen=[]
for task in ('keep','skip'):
    for population in ('retained','full'):
        seen.append(train_predict())
report={'seed':SEED}
"""
        namespace={};exec(self.prepare(source,"Chemprop-v2"),namespace)
        self.assertEqual(namespace["pl"].model_seed,20261026)
        self.assertEqual(namespace["seen"],[(50,64,20261025)])
    def test_frozen_scaffold_generation_cannot_be_replaced(self):
        with self.assertRaises(IncompleteComparison):
            self.prepare(self.source()+"\nscaffold_folds(groups,seed=SEED)\n")
    def test_traditional_ML_or_unregistered_reason_is_rejected(self):
        with self.assertRaises(ValueError):self.prepare(learner="LightGBM")
        with self.assertRaises(ValueError):self.prepare(reason="TIE")
    def test_source_without_exactly_one_model_task_loop_is_rejected(self):
        with self.assertRaises(IncompleteComparison):self.prepare("SEED=20261025\n")
    def test_dataset_identity_prevents_same_named_task_from_another_source(self):
        namespace={};exec(self.prepare(self.source().replace("group='DATA'","group='OTHER'")),namespace)
        self.assertEqual(namespace["calls"],[])

if __name__=="__main__":unittest.main()
