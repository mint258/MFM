"""Explicit corrected filtered-population query projection; unchanged graph recipe."""
import argparse
from pathlib import Path
import traceback
from ..alpha_runtime_v1 import common as Q
from ..alpha_runtime_v1.guard import Guard
from ..alpha_closed500_handoff_v1.projection import RECIPE,query_projection
from ..alpha_closed500_handoff_v1.sql import connection,SQLStopper
from ..pubchem_alpha_technical_unknown_audit_v1.scan import frame
from .runtime import VERSION,admit,read
from .reader import validate_header


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);p.add_argument('--startup-proof',required=True,type=Path)
    a=p.parse_args();plan=Q.load(a.plan);proof=Q.load(a.startup_proof)
    authority=admit(plan,proof,a.plan,a.startup_proof,'PUBCHEM_ALPHA_GENERIC_RECOVERY_QUERY_PLAN_V1','pubchem_alpha_generic_recovery_query_v1')
    from ..alpha_closed500_handoff_v1 import projection as original_projection,sql as original_sql
    for module in (original_projection,original_sql):
        Q.need(Q.reference(module.__file__) in proof['request']['source_references'],'Exact original graph-projection/SQL helper source pin')
    guard=Guard(plan);out=Path(plan['output_directory'])
    try:
        out.mkdir(parents=True,exist_ok=False);ref=plan['filtered_pool_receipt_reference'];f=read(ref)
        Q.need(f['schema']=='expansion_filtered_columnar_pool_v1' and f['status']=='COMPLETE' and f['population_version']==VERSION
            and f['source_endpoint']=='218.192.171.238:22' and f['source_uid']==1264
            and f['all_sources_all_splits_verified'] is True and f['original_graph_unknowns_retained'] is True,
            'Actual complete corrected-population all11 filtered source')
        pool=validate_header(read(f['source_pool_receipt']))
        Q.need(f['counts']['input_unique_molecules']==pool['unique_full_keys']
            and f['counts']['eligible_molecules']+f['counts']['excluded_molecules']==pool['unique_full_keys'],'Whole corrected source filter mass')
        before=frame(Path(f['candidates']['path']).lstat());path=Q.verify(f['candidates'])
        Q.need(before==frame(path.lstat()),'Fresh complete selected-source SHA/current frame')
        db=connection(out,plan['workers'],plan['duckdb_memory_bytes']);monitor=SQLStopper(db,guard.check)
        try:
            db.read_parquet(str(path)).create_view('eligible')
            projection=query_projection(db,'eligible',out/'eligible_query.jsonl',f['counts']['eligible_molecules'],guard.check)
            Q.need(frame(path.lstat())==before,'Full current filtered source frame stable')
            Q.write(out/'manifest.json',dict(schema='EXPANSION_TYPED_DECONTAMINATED_QUERY_PROJECTION_V1',status='COMPLETE',
                population_version=VERSION,source_endpoint='218.192.171.238:22',source_uid=1264,fingerprint_recipe=RECIPE,
                targets_present=False,downstream_features_present=False,projection=projection,filtered_pool_receipt=ref,
                actual_parent=authority,actual_parent_C0_acceptance='PENDING_ROOT_TERMINAL_ACCOUNTING',
                resource_plan=Q.reference(a.plan),startup_proof_reference=Q.reference(a.startup_proof),runtime=guard.receipt()))
        finally:monitor.close();db.close()
    except BaseException as exc:
        if out.is_dir():Q.write(out/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),partials_retained=True,old_sources_changed=False))
        raise
    finally:guard.close()


if __name__=='__main__':main()
