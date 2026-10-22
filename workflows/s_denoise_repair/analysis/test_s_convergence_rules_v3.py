import pytest

from s_convergence_rules_v3 import task_comparison, probe_comparison, joint_judgment, S_RULES


def test_worse_B3_is_not_unconverged():
    assert task_comparison("local_rmse_A", [0.04, 0.04], [0.06, 0.07])["converged_under_rule"]
    assert task_comparison("bond_order_accuracy", [0.99, 0.99], [0.90, 0.91])["converged_under_rule"]
    assert not probe_comparison("QM7", [70, 71], [80, 81], higher_is_better=False)["unconverged"]


def test_strict_two_percent_threshold_and_zero_baseline():
    assert not task_comparison("masked_element_nll", [100, 100], [98, 98])["converged_under_rule"]
    assert task_comparison("masked_element_nll", [100, 100], [98.01, 98.01])["converged_under_rule"]
    assert task_comparison("noise_mse_normalized", [0, 0], [0, 0])["converged_under_rule"]


def test_bond_uses_percentage_points():
    row = task_comparison("bond_order_accuracy", [0.9, 0.9], [0.9011, 0.9011])
    assert not row["converged_under_rule"]
    assert row["comparison"] == "absolute"
    assert task_comparison("bond_order_accuracy", [0.9, 0.9], [0.9009, 0.9009])["converged_under_rule"]


@pytest.mark.parametrize("direction,a,b,expected", [
    (False, [10, 12], [6, 8], True),
    (False, [10, 12], [6, 10], False),
    (False, [10, 12], [8, 12], False),
    (False, [10, 12], [7, 13], False),
    (True, [0.2, 0.3], [0.5, 0.6], True),
    (True, [0.5, 0.6], [0.2, 0.3], False),
])
def test_probe_must_exceed_both_seed_spreads(direction, a, b, expected):
    assert probe_comparison("probe", a, b, higher_is_better=direction)["unconverged"] is expected


def comparisons():
    return [task_comparison(name, [1, 1], [1, 1]) if name != "bond_order_accuracy"
            else task_comparison(name, [0.99, 0.99], [0.99, 0.99]) for name in S_RULES]


def probes():
    return [probe_comparison(str(i), [1, 1], [1, 1], higher_is_better=False) for i in range(32)]


def test_known_failure_is_not_hidden_by_missing_probe():
    s, p = comparisons(), probes()
    s[0] = task_comparison("noise_mse_normalized", [1, 1], [0.5, 0.5])
    p[0] = probe_comparison("0", None, None, higher_is_better=False)
    assert joint_judgment(s, p)["status"].startswith("ONE_EPOCH_INSUFFICIENT")


def test_missing_alone_does_not_establish_sufficiency():
    s, p = comparisons(), probes()
    p[0] = probe_comparison("0", None, None, higher_is_better=False)
    assert joint_judgment(s, p)["status"] == "NOT_YET_EVALUABLE"


def test_all_converged_and_auxiliary_excluded():
    s, p = comparisons(), probes()
    p.append(probe_comparison("QM9_A", [100, 100], [1, 1], higher_is_better=False, primary=False))
    assert joint_judgment(s, p)["status"].startswith("ONE_EPOCH_SUFFICIENT")


def test_bad_values_and_duplicate_tasks_rejected():
    with pytest.raises(ValueError):
        task_comparison("local_rmse_A", [float("nan"), 1], [1, 1])
    with pytest.raises(ValueError):
        task_comparison("bond_order_accuracy", [1.1, 1], [1, 1])
    p = probes()
    p[-1]["id"] = "0"
    with pytest.raises(ValueError):
        joint_judgment(comparisons(), p)
