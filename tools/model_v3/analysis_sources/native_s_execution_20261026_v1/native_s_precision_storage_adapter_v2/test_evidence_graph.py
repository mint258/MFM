"""Raw metadata graph negative cases; no SDK/data/weights are manufactured."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import evidence_graph as graph


class Metadata:
    def __init__(self,rows): self.rows=rows
    def read_bound(self,ref): return self.rows[ref]


def terminal_fixture(state='COMPLETED',code='0:0',ret=0):
    raw=dict(argv=['sacct','-j','123','-P','-n','--format','JobIDRaw,State,ExitCode'],returncode=ret,
        stdout=f'123|{state}|{code}|\n123.batch|COMPLETED|0:0|\n',stderr='')
    return Metadata(dict(projection=dict(schema='native_S_actual_terminal_projection_v2',job_id='123',
        status='COMPLETED',exit_code=0,raw_sacct='raw'),raw=raw))


def test_raw_sacct_parent_row_is_parsed_not_only_projection_boolean():
    assert graph.terminal(terminal_fixture(),'projection')['job_id']=='123'


@pytest.mark.parametrize('state,code,ret',[('FAILED','1:0',0),('COMPLETED','0:9',0),('COMPLETED','0:0',1),('RUNNING','0:0',0)])
def test_raw_failure_cannot_be_promoted_by_C0_projection(state,code,ret):
    with pytest.raises(ValueError): graph.terminal(terminal_fixture(state,code,ret),'projection')


def test_missing_native_full_sdk_raw_graph_cannot_be_an_old_boolean_certificate():
    storage=Metadata({'old':dict(schema='old_or_unknown',status='VERIFIED',clean_eof=True,exit_code=0)})
    with pytest.raises(ValueError,match='unknown verifier'):
        graph.sdk(storage,'old',configuration={},raw_profile={},profile_ref={})


def test_non_checkpoint_census_requires_raw_post_closed_collector():
    storage=Metadata({'old':dict(schema='old_estimated_SDK_bytes',profile_result='profile',non_checkpoint_output_bytes=1)})
    with pytest.raises(ValueError,match='Post-child'):
        graph.closed_outputs(storage,'old',configuration={},profile_ref='profile')
