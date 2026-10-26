"""Four bounded CPU metadata checks within the actual sync job; no network."""
from pathlib import Path
import math
import time
import pytest
from sync_common import HERE, bind, copy_exact, eligible_rows, read, ref
from one_run import expected_remote, integer_step, sync_argv, exact_missing_run,project_remote_steps


def test_fixed_population_and_original_routes():
    manifest,rows=eligible_rows()
    assert len(rows)==50
    assert sum(row['native_exit_code']==0 for row in rows.values())==37
    assert sum(row['native_exit_code']==1 for row in rows.values())==13
    assert manifest['new_native_profiles1331_1332_included'] is False
    for row in rows.values():
        native=row['native_RunRecord']
        assert row['routing']['entity']==(native['entity'] or 'mint_leaf258')
        assert row['routing']['project']==native['project']
        assert row['routing']['run_id']==native['run_id']==row['run_id']
    pilot=rows['4sgxpx8j']
    assert (pilot['native_exit_code'],pilot['history_rows'],pilot['first_explicit_step'],pilot['last_explicit_step'])==(1,500,1,500)


def test_exact_copy_retains_original_and_rejects_tamper(tmp_path):
    source=tmp_path/'original.wandb';source.write_bytes(b'bounded synthetic framing fixture\x00\x01')
    marker=Path(str(source)+'.synced');marker.write_bytes(b'original marker fixture')
    before=ref(source);marker_before=ref(marker)
    staged=copy_exact(before,tmp_path/'stage'/'offline-run-fixture'/'run-fixture.wandb')
    assert staged['sha256']==before['sha256'] and staged['bytes']==before['bytes']
    assert ref(source)==before and ref(marker)==marker_before
    with pytest.raises(FileExistsError):copy_exact(before,staged['path'])
    source.write_bytes(b'changed fixture')
    with pytest.raises(ValueError,match='Raw reference changed'):bind(before)


def test_remote_step_types_and_metadata_only_expectations(monkeypatch):
    monkeypatch.delenv('WANDB_DEBUG',raising=False)
    from wandb.apis.normalize import normalize_exceptions
    from wandb.apis.public.runs import RunNotFoundError
    from wandb.errors import CommError,AuthenticationError
    from requests import HTTPError
    @normalize_exceptions
    def synthetic_missing():raise RunNotFoundError('synthetic fixture only')
    with pytest.raises(CommError) as caught:synthetic_missing()
    assert exact_missing_run(caught.value,RunNotFoundError,CommError)
    assert type(caught.value.exc) is RunNotFoundError
    assert exact_missing_run(RunNotFoundError('fixture'),RunNotFoundError,CommError)
    for error in (CommError('fixture'),CommError('fixture',HTTPError('transport fixture')),
                  AuthenticationError('fixture',RunNotFoundError('unrelated fixture'))):
        assert not exact_missing_run(error,RunNotFoundError,CommError)
    assert [integer_step(value) for value in (0,1.0,500)]==[0,1,500]
    for bad in (True,False,None,'1',1.5,math.nan,math.inf,2**53+1):
        with pytest.raises(ValueError):integer_step(bad)
    _,rows=eligible_rows();expected=expected_remote(rows['4sgxpx8j'])
    assert expected==dict(entity='mint_leaf258',project='mfm_model_v3_development',run_id='4sgxpx8j',
        state='failed',history_rows=500,first_step=1,last_step=500)
    assert all(row['expected_API_state']==('failed' if row['native_exit_code'] else 'finished') for row in rows.values())
    sentinel=object();deadline=time.monotonic()+30
    assert project_remote_steps(iter([{'_step':1,'metric':sentinel},{'_step':2,'metric':sentinel}]),deadline,2)==dict(history_rows=2,first_step=1,last_step=2)
    assert project_remote_steps(iter([]),deadline,0)==dict(history_rows=0,first_step=None,last_step=None)
    for bad_rows in ([{'metric':sentinel}],[{'_step':1.5}],[{'_step':True}],
                     [{'_step':1},{'_step':1}],[{'_step':2},{'_step':1}],
                     [{'_step':1},{'_step':2},{'_step':3}]):
        with pytest.raises(ValueError):project_remote_steps(iter(bad_rows),deadline,2)


def test_installed_core_route_uses_one_explicit_staged_file():
    _,rows=eligible_rows();staged=Path('/owned/stage/offline-run-fixture/run-4sgxpx8j.wandb')
    argv=sync_argv(rows['4sgxpx8j'],staged)
    assert argv[-1]==str(staged) and argv.count(str(staged))==1
    assert argv[1:5]==['-B','-m','wandb','sync']
    assert '--yes' in argv and '--no-sync-tensorboard' in argv and '--include-offline' in argv
    assert not set(argv)&{'--legacy','--sync-all','--append','--clean','--no-mark-synced','--skip-console'}
    installed=read(HERE/'installed_sources.json')
    cli=next(row for row in installed['files'] if row['original'].endswith('/cli/cli.py'))
    source=Path(cli['snapshot']).read_text()
    assert 'beta_sync' in source and 'legacy' in source
    assert argv[argv.index('--id')+1]=='4sgxpx8j'
