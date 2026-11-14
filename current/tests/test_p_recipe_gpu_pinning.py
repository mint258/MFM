"""A per-card calibration must not silently run on a different available card."""
import importlib.util
import sys
from pathlib import Path


def launcher():
    path=Path(__file__).resolve().parents[2]/'tools/p_recipe'
    sys.path.insert(0,str(path))
    spec=importlib.util.spec_from_file_location('calibration_launcher',path/'launch_plan.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_pin_uses_matching_card_and_leaves_higher_ranked_card_available():
    cards=[dict(gpu_uuid='5090'),dict(gpu_uuid='4090')]
    selected=launcher().take_card(cards,[],required_gpu_uuid='4090')
    assert selected['gpu_uuid']=='4090'
    assert cards==[dict(gpu_uuid='5090')]


def test_missing_pin_waits_without_consuming_another_card():
    cards=[dict(gpu_uuid='5090')];fallback=[dict(gpu_uuid='3090')]
    assert launcher().take_card(cards,fallback,required_gpu_uuid='absent') is None
    assert len(cards)==len(fallback)==1


def test_pin_can_select_the_previously_used_fallback_gpu():
    cards=[dict(gpu_uuid='5090')];fallback=[dict(gpu_uuid='3090')]
    assert launcher().take_card(cards,fallback,required_gpu_uuid='3090')['gpu_uuid']=='3090'
    assert len(cards)==1 and not fallback
