import importlib.util,sys
from pathlib import Path
p=Path(__file__).resolve().parents[2]/'tools/p_followup'
sys.path.insert(0,str(p))
s=importlib.util.spec_from_file_location('followup_compare_dedup',p/'compare_dedup.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def score(value):return dict(included_tasks=['a'],mean_normalized_improvement=value,paired_bootstrap=dict(values=[value]*1000))

def test_followup_uses_ci_sign_without_mainline_effect_gate():
    assert m.paired_ci(score(.2001),score(.2))['verdict']=='win'
    assert m.paired_ci(score(.1999),score(.2))['verdict']=='loss'
    assert m.paired_ci(score(.2),score(.2))['verdict']=='tie'