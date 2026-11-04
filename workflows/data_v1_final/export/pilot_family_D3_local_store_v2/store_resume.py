"""Same-root continuation of actual closed stores and node-local route files."""
import json, os, pathlib
from . import contract as C, io as I


def enabled(plan):
    return bool(plan.get('store_write_resume'))


def checked(plan):
    r = plan['store_write_resume']
    old = C.meta(r['prior_plan_reference'])
    terminal = r['actual_prior_terminal']
    C.need(str(terminal['job_id']) == str(r['actual_job_id']) == '4525785'
      and terminal['state'] in ('FAILED','CANCELLED','COMPLETED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL')
      and terminal['uid'] == 1278 and terminal['allocated_cpus'] == 16
      and terminal['node'] == plan['node'] == 'compute-0-8', 'ACTUAL_CLOSED_PRIOR_WRITER_ON_SAME_NODE')
    C.need(old['output_directory'] == plan['output_directory'] == r['output_directory']
      and old['pilot_acceptance_reference'] == plan['pilot_acceptance_reference']
      and old['direct_source_resume']['closed_groups_reference'] == plan['direct_source_resume']['closed_groups_reference']
      and old['direct_source_resume']['geometry_index_reference'] == plan['direct_source_resume']['geometry_index_reference']
      and old['direct_source_resume']['local_directory'] == r['local_directory'] == plan['direct_source_resume']['local_directory'],
      'SAME_REAL_SHARED_OUTPUT_FROZEN55K_AND_NODE_LOCAL_ROUTES')
    C.need(r['observation']['uid'] == 1278 and r['observation']['node'] == plan['node']
      and str(r['observation']['actual_job_id']) == str(plan['job_id']), 'ACTUAL_NEW_ALLOCATED_NODE_OBSERVATION')
    return r


def prepare_output(plan, root):
    r = checked(plan); root = pathlib.Path(root)
    C.need(root.is_dir() and root.stat().st_uid == 1278
      and not any(p.is_symlink() for p in (root,*root.parents))
      and (root/'delivery_meta.sqlite').is_file() and not (root/'receipt.json').exists()
      and not (root/'export_manifest.json').exists(), 'CLOSED_PARTIAL_OUTPUT_NOT_ALREADY_QA_OR_DELIVERED')
    # Preserve the original failure record. It is not a new failure report and
    # is excluded from normal delivery_files.list0 by the unchanged distributor.
    failure = root/'failure.DATA.json'
    if failure.exists():
        target = root/('failure.DATA.previous_'+str(r['actual_job_id'])+'.json')
        C.need(not target.exists(), 'PRIOR_FAILURE_HISTORY_NOT_OVERWRITTEN')
        failure.rename(target)
    return r


def local_frames(plan):
    r = checked(plan); local = pathlib.Path(r['local_directory'])
    C.need(local.is_absolute() and pathlib.Path('/tmp') in local.parents
      and local.is_dir() and local.stat().st_uid == 1278
      and not any(p.is_symlink() for p in (local,*local.parents)), 'SAME_OWN_CLOSED_NODE_LOCAL_DIRECTORY')
    for name, frame in r['observation']['local_database_frames'].items():
        C.need(name in ('source_routes.sqlite','geometry_index.sqlite')
          and I.identity(local/name) == frame, 'UNCHANGED_CLOSED_NODE_LOCAL_DATABASE_FRAME')
    C.need(set(r['observation']['local_database_frames']) == {'source_routes.sqlite','geometry_index.sqlite'},
           'BOTH_ORIGINAL_NODE_LOCAL_INPUTS_BOUND')
    return local
