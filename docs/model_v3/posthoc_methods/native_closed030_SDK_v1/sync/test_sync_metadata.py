"""Four same-job checks; no original full SDK scan or remote call."""
from pathlib import Path
import math
import time
import pytest
from long_common import manifest_metadata,eligible_rows,ref,bind,copy_exact
from one_run_long import expected_remote,integer_step,project_remote_steps,sync_argv


def test_explicit_proofs_preserve_actual_rows_endpoints_and_native_headers():
    _,value=manifest_metadata();_,rows=eligible_rows()
    assert 1<=len(rows)<=3 and list(rows)==[row['run_id'] for row in value['runs']]
    for original in value['runs']:
        row=rows[original['run_id']]
        assert all(row[key]==original[key] for key in ('history_rows','first_explicit_step','last_explicit_step','native_exit_code'))
        assert row['routing']['project']==row['native_RunRecord']['project']
        assert row['routing']['entity']==(row['native_RunRecord']['entity'] or value['default_entity'])
        assert expected_remote(row)['state']==('failed' if row['native_exit_code'] else 'finished')


def test_exact_copy_is_fresh_and_original_hash_is_stable(tmp_path):
    source=tmp_path/'fixture.wandb';source.write_bytes(b'synthetic fixture only')
    raw=ref(source);staged=copy_exact(raw,tmp_path/'stage'/'run-fixture.wandb')
    assert ref(source)==raw and staged['sha256']==raw['sha256']
    with pytest.raises(FileExistsError):copy_exact(raw,staged['path'])
    source.write_bytes(b'changed')
    with pytest.raises(ValueError):bind(raw)


def test_unkeyed_projection_rejects_missing_duplicate_backwards_and_extra_steps():
    deadline=time.monotonic()+30;opaque=object()
    assert project_remote_steps(iter([{'_step':1003,'loss':opaque},{'_step':1004,'loss':opaque}]),deadline,2)==dict(history_rows=2,first_step=1003,last_step=1004)
    for rows in ([{'loss':opaque}],[{'_step':1.5}],[{'_step':True}],
                 [{'_step':1},{'_step':1}],[{'_step':2},{'_step':1}],
                 [{'_step':0},{'_step':1},{'_step':2}]):
        with pytest.raises(ValueError):project_remote_steps(iter(rows),deadline,2)
    for value in (True,None,'1',1.5,math.nan,math.inf):
        with pytest.raises(ValueError):integer_step(value)


def test_official_core_keeps_single_original_id_and_no_legacy_or_append():
    _,rows=eligible_rows();row=next(iter(rows.values()));staged=Path('/owned/stage/offline-run-fixture')/('run-'+row['run_id']+'.wandb')
    argv=sync_argv(row,staged)
    assert argv[-1]==str(staged) and argv[argv.index('--id')+1]==row['run_id']
    assert argv[1:5]==['-B','-m','wandb','sync'] and '--yes' in argv and '--no-sync-tensorboard' in argv
    assert not set(argv)&{'--legacy','--sync-all','--append','--clean','--no-mark-synced','--skip-console'}
