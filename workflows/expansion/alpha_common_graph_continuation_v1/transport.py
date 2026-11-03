"""One-to-one physical transport; original Main manifest remains byte-identical."""
from pathlib import Path
from . import io as I


def bindings(origin,rows,root):
    expected=[origin[k] for k in ('origin_common_manifest_reference','origin_roles_manifest_reference','origin_formal_authority_reference')]+origin['origin_graph_input_references']
    I.need(len(expected)==36 and len(rows)==36,'EXACT33_BODY_PLUS3_METADATA_TRANSPORTS')
    sources={r['path']:I.triple(r) for r in expected};I.need(len(sources)==36,'ORIGIN_UNIQUE_PHYSICAL_VIEWS')
    result={};destinations=set();root=Path(root)
    for row in rows:
        source=I.triple(row['origin_reference']);target=I.triple(row['destination_reference']);path=Path(target['path'])
        I.need(source['path'] in sources and source==sources[source['path']],'EXACT_DECLARED_MAIN_ORIGIN')
        I.need(target['bytes']==source['bytes'] and target['sha256']==source['sha256'],'TRANSPORT_BYTES_SHA_EQUAL_WITH_DISTINCT_REAL_PATH')
        I.need(path.is_absolute() and '..' not in path.parts and root in path.parents and target['path']!=source['path'],'HONEST_ALPHA_DESTINATION_SCOPE')
        I.need(source['path'] not in result and target['path'] not in destinations,'BIJECTIVE_TRANSPORT_NO_PATH_COLLAPSE')
        result[source['path']]=target;destinations.add(target['path'])
    I.need(set(result)==set(sources),'COMPLETE_REQUIRED_SOURCE_TRANSPORT')
    return result


def inputs(plan):
    origin=I.read(plan['origin_input_manifest_reference']);mapping=bindings(origin,plan['transport_bindings'],plan['input_transport_root'])
    approval=I.read(plan['origin_transport_review_reference'])
    I.need(approval['schema']=='ROOT_ALPHA_COMMON_TRANSPORT_APPROVAL_V1' and approval['reviewer']=='root'
      and approval['origin_input_manifest_reference']==plan['origin_input_manifest_reference']
      and approval['Main_origin_job_id']=='4525659' and approval['Main_origin_uid']==1278
      and approval['Main_origin_endpoint']=='202.38.247.57:22' and approval['Main_origin_parent_state']=='STOPPED'
      and approval['Main_parent_C0_claimed'] is False and approval['closed_Common_stage_not_terminal_parent_accepted'] is True
      and approval['independent_Alpha_C0_required'] is True and approval['D7_or_orders_release'] is False,'HONEST_ROOT_ORIGIN_STAGE_REVIEW_NO_MAIN_C0_FABRICATION')
    def mapped(ref):return mapping[ref['path']]
    common=I.read(mapped(origin['origin_common_manifest_reference']))
    roles=I.read(mapped(origin['origin_roles_manifest_reference']))
    formal=I.read(mapped(origin['origin_formal_authority_reference']))
    I.need(common['schema']=='COMMON_POPULATION_PRODUCER_V1' and common['status']=='PENDING_ACTUAL_PARENT_C0_AND_INDEPENDENT_ROOT_REVIEW'
      and common['pilot_only'] is False and common['execution_unresolved_molecules']==3436
      and common['denominator_molecules']==1214218 and common['excluded_molecules']==18096
      and common['orders_frozen'] is False,'EXACT_FULL_CLOSED_COMMON_STAGE_NOT_PROXY_OR_D7')
    I.need([I.triple(r) for r in common['membership_tables']]==origin['origin_membership_references']
      and I.triple(common['roles_manifest'])==origin['origin_roles_manifest_reference']
      and I.triple(common['formal_population_authority_receipt'])==origin['origin_formal_authority_reference'],'ORIGINAL_CLOSED_COMMON_BINDS_SAME_VIEWS')
    observed_roles=[I.triple(r) for r in roles['outputs'] if '/molecule_roles/' in r['path']]
    original_formal=[I.triple(r['reference']) for r in formal['outputs'] if r['name']=='formal_population']
    I.need(roles['status']=='ROUTINE_MOLECULE_VAL_ROLES_FROZEN' and formal['status']=='ALL_BOUND_INPUTS_SHA_VERIFIED'
      and observed_roles==origin['origin_role_references'] and original_formal==[origin['origin_formal_reference']],'FROZEN_ALL16_ROLE_AND_FORMAL_AUTHORITY')
    members=[mapped(r) for r in origin['origin_membership_references']];parts=[mapped(r) for r in origin['origin_role_references']];source=mapped(origin['origin_formal_reference'])
    I.need(len(members)==len(parts)==16 and len(common['physical_geometry_tables'])==32
      and common['physical_geometry_tables']==origin['origin_physical_geometry_references']
      and common['uff_identity_tables']==origin['origin_uff_identity_references'],'CLOSED_ORIGINAL_PHYSICAL_SOURCE_PROVENANCE_RETAINED_NOT_RECOMPUTED')
    return origin,common,members,parts,source,mapping
