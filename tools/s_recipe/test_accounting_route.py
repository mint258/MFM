import subprocess
import pytest
import collect


def test_empty_accounting_never_queries_scheduler(monkeypatch):
    monkeypatch.setattr(collect.subprocess, 'check_output', lambda *a, **k: pytest.fail('unexpected query'))
    assert collect.accounting([]) == {}


def test_compute_database_failure_uses_established_login_metadata_route(monkeypatch):
    calls = []

    def output(command, **kwargs):
        calls.append(command)
        if len(calls) == 1:
            raise subprocess.CalledProcessError(1, command)
        return 'Welcome to sonmiHPC!\n4537671|RUNNING|0:0|compute-0-7|1800\n'

    monkeypatch.setattr(collect.subprocess, 'check_output', output)
    observed = collect.accounting([4537671])
    assert calls[0][0] == 'sacct'
    assert calls[1][:7] == ['ssh', '-n', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', 'sonmi']
    assert observed[4537671]['state'] == 'RUNNING'
    assert observed[4537671]['elapsed_seconds'] == 1800


def test_two_unavailable_observation_routes_are_not_a_training_failure(monkeypatch):
    def fail(command, **kwargs):
        raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(collect.subprocess, 'check_output', fail)
    with pytest.raises(subprocess.CalledProcessError):
        collect.accounting([4537671])
