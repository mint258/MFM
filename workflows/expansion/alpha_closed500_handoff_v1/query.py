"""Complete actual Alpha filtered Parquet to original exact graph query fields."""
from pathlib import Path
from ..alpha_runtime_v1.common import frame, load, need, reference, verify, write
from ..alpha_runtime_v1.guard import Guard
from ..alpha_runtime_v1.profile import admit
from .projection import RECIPE, query_projection
from .scientific_contract import verify as verify_science


def run(plan_path):
    plan = load(plan_path); actual = admit(plan); verify_science()
    base = Path(plan['output_directory']); pool_ref = reference(base / 'filtered_all11/receipt.json'); filtered = load(verify(pool_ref))
    need(filtered['schema'] == 'expansion_filtered_columnar_pool_v1' and filtered['status'] == 'COMPLETE' and filtered['source_endpoint'] == plan['endpoint'] and filtered['source_uid'] == plan['uid'] and filtered['all_sources_all_splits_verified'] is True, 'Complete actual Alpha all11 filtering is required')
    source = verify(filtered['candidates']); before = frame(source)
    stage = base / 'eligible_query'; stage.mkdir(exist_ok=True); guard = Guard(plan)
    try:
        final = stage / 'manifest.json'
        if final.exists():
            old = load(final); need(old['filtered_pool_receipt'] == pool_ref, 'Closed eligible query source differs'); verify(old['projection']); return old
        from .sql import SQLStopper, attempt, connection
        out = attempt(stage); db = connection(out, plan['workers'], plan['duckdb_memory_bytes']); monitor = SQLStopper(db, guard.check)
        try:
            db.read_parquet(str(source)).create_view('eligible')
            projection = query_projection(db, 'eligible', out / 'eligible_query.jsonl', filtered['counts']['eligible_molecules'], guard.check)
            need(frame(source) == before, 'SHA-admitted complete eligible source changed during projection')
            guard.sample(); guard.check()
            result = {'schema': 'EXPANSION_TYPED_DECONTAMINATED_QUERY_PROJECTION_V1', 'status': 'COMPLETE', 'source_endpoint': plan['endpoint'], 'source_uid': plan['uid'], 'fingerprint_recipe': RECIPE, 'targets_present': False, 'downstream_features_present': False, 'projection': projection, 'filtered_pool_receipt': pool_ref, 'actual_parent': actual, 'actual_parent_C0_acceptance': 'PENDING_ROOT_TERMINAL_ACCOUNTING', 'resource_plan': reference(plan_path), 'runtime': guard.receipt()}
            write(final, result); return result
        finally:monitor.close(); db.close()
    finally:guard.close()
