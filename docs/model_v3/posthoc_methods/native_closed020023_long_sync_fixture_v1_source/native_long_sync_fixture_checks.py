"""Same metadata4 session selfchecks; no extra QA parent or sync/API operation."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import sys

from native_long_sync_fixture_census import owned_output_bytes
from supervise_fixture import inputs,verify_sources,need,raw_ref,ORIGINAL


def rejected(function):
    try:function()
    except ValueError:return True
    raise AssertionError('Unsafe production fixture unexpectedly admitted')


def original_monitor(path):
    spec=importlib.util.spec_from_file_location('strict_original_monitor_for_fixture_checks',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module


def checks(base,strict):
    base.mkdir(mode=0o700);results=[]
    ordinary=base/'ordinary';ordinary.mkdir();(ordinary/'value').write_bytes(b'ordinary metadata only')
    a=owned_output_bytes(ordinary);b=strict.owned_output_bytes(ordinary)
    assert a==b;results.append({'name':'ordinary_production_count_unchanged','bytes':a})

    target=base/'outside_fixture_scope';target.write_bytes(b'x'*(64 << 10))
    fixture=base/'fixture';(fixture/'metadata_tmp').mkdir(parents=True)
    link=fixture/'metadata_tmp'/'external';link.symlink_to(target)
    missing=fixture/'metadata_tmp'/'dangling';missing.symlink_to(base/'missing_target')
    expected=sum(p.lstat().st_size for p in (fixture,fixture/'metadata_tmp',link,missing))
    assert owned_output_bytes(fixture)==expected
    rejected(lambda:strict.owned_output_bytes(fixture))
    metadata_root_link=base/'metadata_root_link';metadata_root_link.mkdir()
    (metadata_root_link/'metadata_tmp').symlink_to(ordinary,target_is_directory=True)
    rejected(lambda:owned_output_bytes(metadata_root_link))
    rejected(lambda:strict.owned_output_bytes(metadata_root_link))
    results.append({'name':'fixture_internal_links_only_root_symlink_rejected','bytes':expected,
        'external_target_bytes_excluded':64 << 10,'dangling_internal_link_counted':True,
        'metadata_tmp_itself_symlink_rejected':True})

    bad=base/'bad_production';(bad/'wandb').mkdir(parents=True);(bad/'wandb'/'arbitrary').symlink_to(target)
    rejected(lambda:owned_output_bytes(bad));rejected(lambda:strict.owned_output_bytes(bad))
    results.append({'name':'arbitrary_production_WandB_link_still_rejected'})

    sdk=base/'canonical';run='offline-run-20261027_000000-abcdefgh'
    logs=sdk/'wandb'/run/'logs';logs.mkdir(parents=True)
    cache=sdk/'cache'/'wandb'/'logs';cache.mkdir(parents=True)
    for name in ('debug.log','debug-internal.log'):
        (logs/name).write_bytes(b'metadata-only SDK layout fixture')
        (sdk/'wandb'/name).symlink_to(run+'/logs/'+name)
    (cache/'core-debug-20261027_000000.log').write_bytes(b'core layout fixture')
    (logs/'debug-core.log').symlink_to('../../../cache/wandb/logs/core-debug-20261027_000000.log')
    (sdk/'wandb'/'latest-run').symlink_to(run,target_is_directory=True)
    assert owned_output_bytes(sdk)==strict.owned_output_bytes(sdk)
    results.append({'name':'all_four_original_canonical_SDK_link_forms_preserved'})

    linked_root=base/'linked_root';linked_root.symlink_to(ordinary,target_is_directory=True)
    rejected(lambda:owned_output_bytes(linked_root));rejected(lambda:strict.owned_output_bytes(linked_root))
    results.append({'name':'symlink_inventory_root_still_rejected'})

    rejected(lambda:owned_output_bytes(ordinary,max_entries=1))
    rejected(lambda:strict.owned_output_bytes(ordinary,max_entries=1))
    results.append({'name':'entry_cap_preserved_with_small_exhaustion_case','production_limit':50000,'tested_limit':1})
    assert len(results)==6
    return results


def pytest_sessionstart(session):
    config=session.config;request,bound=inputs();deps,sources=verify_sources()
    output=Path(bound['output']);base=output/'metadata_tmp'
    need([str(Path(p).absolute()) for p in config.args]==[str(ORIGINAL/'test_sync_metadata.py')]
        and Path(config.option.basetemp).absolute()==base
        and Path(config.option.xmlpath).absolute()==output/'metadata4.xml',
        'Fixture selfchecks only accompany the exact original metadata4 request')
    actual_base=config._tmp_path_factory.getbasetemp()
    need(actual_base==base and base.is_dir() and not base.is_symlink(),'Actual pytest basetemp differs')
    report=output/'fixture_accounting_selfchecks.json';result=None;failure=None
    try:
        strict=original_monitor(deps['runtime_monitor']['path'])
        result=checks(base/'fixture_accounting_checks',strict)
        _,after=verify_sources();need(sources==after,'Fixture/selfcheck source changed')
    except BaseException as exc:
        failure={'type':type(exc).__name__,'message':str(exc)[:600]}
        raise
    finally:
        value={'schema':'native_closed_long_sync_fixture_selfchecks_v1',
            'status':'SIX_SAME_JOB_SELFCHECKS_PASSED' if failure is None else 'FAILED_BEFORE_SYNC',
            **bound,'checks':result,'failure':failure,'source_refs':sources,
            'original_pytest_collection_unchanged':True,'expected_original_metadata_tests':4,
            'extra_pytest_cases_added':0,'original_SDK_or_target_payload_read_by_selfchecks':False,
            'network_sync_or_API_called_by_selfchecks':False,'scientific_acceptance':False}
        raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
        need(len(raw)<=128 << 10,'Bounded selfcheck receipt required')
        with report.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
