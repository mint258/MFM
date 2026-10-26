"""Pure budget/pause/failure/summary tests; no CUDA is mocked."""
import json
from pathlib import Path
import pytest
import profile_lifecycle as life


def test_inherited_budget_is_exact_outer_minus96MiB_and_environment_unchanged():
    environment={'MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES':str((2<<30)-(96<<20))}
    before=dict(environment)
    assert life.inherited_budget(2<<30,environment)==(2<<30)-(96<<20)
    assert environment==before


@pytest.mark.parametrize('raw',[None,'2147483648','1','-1','NaN'])
def test_missing_or_expanded_child_budget_rejected(raw):
    environment={} if raw is None else {'MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES':raw}
    with pytest.raises(ValueError): life.inherited_budget(2<<30,environment)


def test_real300second_boundary_requests_pause_before_more_updates():
    assert not life.should_pause(10.,6900,6609.999)
    assert life.should_pause(10.,6900,6610.)
    assert life.should_pause(10.,6900,6880.)


@pytest.mark.parametrize('sdk,payload,actual',[(0,1,20),(2,1,20),(1,0,20),(1,2,20),(1,1,19)])
def test_every_failed_artifact_or_short_target_produces_exit_error(sdk,payload,actual):
    errors=life.completion_errors(failure=None,cleanup_errors=[],target_updates=20,actual_updates=actual,
        sdk_count=sdk,payload_count=payload)
    with pytest.raises(RuntimeError): life.enforce_failed_exit(errors,original_failure=None)


def test_complete_short_goal_needs_no_science_gate_change():
    assert not life.completion_errors(failure=None,cleanup_errors=[],target_updates=20,actual_updates=20,sdk_count=1,payload_count=1)


def test_full_summary_expectation_comes_from_actual_committed_mirror(tmp_path):
    path=tmp_path/'mirror.jsonl'
    rows=[dict(step=0,commit=True,row=dict(fields={'s_noise':{'RMSE':1.,'unit':'angstrom'}},optimizer_updates=0)),
        dict(step=1,commit=True,row=dict(loss=2.,optimizer_updates=1))]
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    assert life.summary_from_mirror(path)==dict(fields={'s_noise':{'RMSE':1.,'unit':'angstrom'}},optimizer_updates=1,loss=2.)
    rows[1]['commit']=False; path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    with pytest.raises(ValueError): life.summary_from_mirror(path)
