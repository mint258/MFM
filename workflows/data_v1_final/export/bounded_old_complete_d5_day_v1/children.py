"""Direct original WP5 input-body binding, exact whole20k heldout scope."""
import pathlib
from . import contract as C
from . import produce as P
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as I,geometry as G

def run(ctx,base,selected_catalog):
    p=dict(ctx.plan,resolved_coverage_catalog_reference=selected_catalog)
    book=I.load_data(ctx.plan['source_inventory_reference'],2<<20)
    from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import TASK_FAMILIES
    C.need(all((s['source_kind']=='base' and s['family']=='base_geometry') or (s['source_kind']=='label' and s['family']in set(TASK_FAMILIES.values())) for s in book['files']),'ONLY_ORIGINAL_BASE_AND_DECLARED14_TASK_TRAINING_SOURCE_INVENTORY')
    result=G.metadata_children(p,ctx.proof,ctx.out/'held_actual_WP5_children',ctx.budget,base,
        {r[0] for r in ctx.db.execute('SELECT molecule_id FROM diagnostic_mids').fetchall()})
    C.need(result['actual_in_pilot_diagnostic_MIDs']==20000 and result['global_preselected_diagnostic_MIDs']==20000
      and result['unknown_input_bindings']==0 and result['all_in_scope_actual_direct_children_bound']is True,
      'ALL20K_HELDOUT_PM7_TWELVE_CALLS_DUAL_HASH_NO_UNKNOWN_NOT55K_INTERSECTION')
    census=C.meta(ctx.plan['actual_UFF_child_census_review_reference'])
    C.need(census['accepted_Pprime_training_source_references']==[] and census['current_UFF_Pprime_input_child_training_rows_admitted']==0,
      'CURRENT_BOUNDED_ACCEPTED_UFF_S_D_ONLY_NOT_GLOBAL_NATIVE_ZERO')
    # The original function validates all twelve actual PM7 input hashes and
    # explicitly includes all real children AND unperturbed program input views.
    count=0;seen=set()
    for row in P._rows(result['diagnostic_base_reference']):
        C.need(row['geometry_id']not in seen,'NO_DUPLICATE_HELDOUT_BASE_EXCLUSION');seen.add(row['geometry_id']);count+=1
    C.need(count==40000,'EXACT40K_ACTUAL_BASE_GEOMETRIES_REOPENED')
    targets=set()
    for row in P._rows(result['diagnostic_target_reference']):
        C.need(row['geometry_id']not in targets,'NO_DUPLICATE_BASE_CHILD_INPUT_VIEW_TARGET');targets.add(row['geometry_id'])
    C.need(seen<=targets,'ALL_REAL40K_BASES_PRESENT_IN_TARGET_EXCLUSION')
    return result,targets
