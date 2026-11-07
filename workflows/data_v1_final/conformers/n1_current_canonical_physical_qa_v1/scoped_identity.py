"""Current-release identity authority; never claims complete noncanonical history."""
from portable_n1_source_physical_qa_v1 import identity as ORIGINAL
from portable_n1_source_remaining_v1 import contract as C

SCOPE={
 'dataset_namespace':'data_v1_20261025',
 'release_version':'v1-final-candidate',
 'identity_contract_version':'current-canonical-extra-identity-v1',
 'scope_id':'v1-current-canonical-N1-extra',
 'registry_version':'current-canonical-registry-v1'}
OUTPUT=C.MAIN/'artifacts/conformers/n1_current_canonical_physical_qa_v1'
CURRENT_REGISTRY=C.MAIN/'control/n1_current_canonical_registry_v1/current.json'

def authority(reference):
    value=C.load(reference)
    C.need(value['schema']=='ROOT_N1_CURRENT_CANONICAL_PHYSICAL_ID_AUTHORITY_V1'
      and value['status']=='APPROVED_CURRENT_CANONICAL_SCOPE' and value['reviewer']=='root'
      and value['endpoint']=='202.38.247.57:22' and value['uid']==1278
      and value['identity_scope']==SCOPE,'EXPLICIT_CURRENT_RELEASE_IDENTITY_AUTHORITY')
    C.need(value['historical_noncanonical_coverage']=='UNKNOWN'
      and value['all_registered_extra_identity_tables_included'] is False
      and value['all_current_canonical_registered_extra_identity_tables_included'] is True,
      'SCOPED_COMPLETENESS_NEVER_MASQUERADES_AS_GLOBAL_HISTORY')
    C.need(value['source_import_reference']==ORIGINAL.IMPORT
      and value['all_ordinary_physical_maps_included'] is True
      and value['all_historical_attempted_physical_ids_included'] is True
      and value['ordinary_N_counts_and_D5_unchanged'] is True,'ORIGINAL_ORDINARY_AND_ATTEMPTED_ID_DOMAIN')
    original=C.load(value['original_sprime_manifest_reference'])
    expected=[C.triple(row) for row in original['references'] if row['kind']=='conformers']
    actual=[C.triple(row) for row in value['historical_attempted_physical_id_tables']]
    C.need(len(expected)==len(actual)==5 and {r['path']:r for r in expected}=={r['path']:r for r in actual},
      'ALL_FIVE_ORIGINAL_ATTEMPTED_TABLES_INCLUDING_FAILURES')
    for name in ('ordinary_physical_map_tables','historical_attempted_physical_id_tables','registered_extra_identity_tables'):
        C.need(type(value[name]) is list,'EXPLICIT_SCOPED_TABLE_LIST:'+name)
        for row in value[name]:C.triple(row)
    C.need(value['ordinary_physical_map_tables'] and value['coverage_evidence_references'],
      'POSITIVE_ORDINARY_ID_AND_COVERAGE_REFERENCES')
    for parent in value['closed_source_parents']:
        ORIGINAL.terminal(parent['accounting_reference'],parent['job_id'],1278,parent['requires_C0'])
    census=C.load(value['current_canonical_census_reference'],32<<20)
    C.need(census['schema']=='CURRENT_CANONICAL_N1_REGISTERED_PUBLICATION_CENSUS_CANDIDATE_V1'
      and census['canonical_scope_closed'] is True and not census['unresolved'],
      'CURRENT_CANONICAL_SUBDOMAIN_CLOSED_NOT_A_GLOBAL_EMPTY_ASSERTION')
    C.need(census['all_registered_extra_identity_tables_included'] is False
      and census['portable_noncanonical_boundary']['writer']=='portable_n1_source_physical_qa_v1',
      'HISTORICAL_NONCANONICAL_BOUNDARY_REMAINS_EXPLICIT')
    parent=value['census_actual_parent'];ORIGINAL.terminal(parent['accounting_reference'],parent['job_id'],1278,True)
    base={row['reference']['path']:C.triple(row['reference']) for row in census['closed_accepted_extra_indexes']}
    registry_ref=value['current_registry_reference']
    C.need(registry_ref['path']==str(CURRENT_REGISTRY),'CANONICAL_CURRENT_REGISTRY_POINTER_REQUIRED')
    registry=C.load(registry_ref)
    C.need(registry['schema']=='N1_CURRENT_CANONICAL_EXTRA_REGISTRY_V1'
      and registry['status']=='CLOSED_CURRENT_CANONICAL_SCOPE' and registry['identity_scope']==SCOPE
      and registry['historical_noncanonical_coverage']=='UNKNOWN'
      and registry['base_canonical_census_reference']==value['current_canonical_census_reference'],
      'VERSIONED_CURRENT_REGISTRY_WITHOUT_GLOBAL_HISTORY_CLAIM')
    indexes={}
    for member in registry['members']:
        ref=C.triple(member['accepted_extra_index_reference'])
        C.need(ref['path'] not in indexes,'ONE_CURRENT_REGISTERED_PUBLICATION_PER_PATH')
        indexes[ref['path']]=ref
        if ref['path'] not in base:
            ORIGINAL.terminal(member['actual_parent_accounting_reference'],member['actual_parent_job_id'],1278,True)
            accepted=C.load(ref,32<<20);receipt=C.load(member['publisher_receipt_reference'])
            C.need(accepted['identity_scope']==receipt['identity_scope']==SCOPE
              and str(receipt['job_id'])==str(member['actual_parent_job_id'])
              and receipt['accepted_extra_index']==ref,'PRESERVE_ACTUAL_CLOSED_CURRENT_SCOPE_REGISTERED_IDS')
    C.need(all(indexes.get(path)==ref for path,ref in base.items()),'NO_BASE_CANONICAL_REGISTERED_INDEX_DROPPED')
    bindings=value['current_registered_extra_table_bindings']
    C.need({row['accepted_extra_index_reference']['path']:C.triple(row['accepted_extra_index_reference']) for row in bindings}==indexes,
      'EVERY_DECLARED_CURRENT_REGISTERED_INDEX_RETAINS_ITS_ID_TABLE')
    tables=[C.triple(row['registered_identity_table_reference']) for row in bindings]
    C.need(tables==[C.triple(row) for row in value['registered_extra_identity_tables']],
      'SCOPED_REGISTERED_TABLES_EXACTLY_BOUND_TO_CLOSED_INDEXES')
    return value

# Existing registered IDs come verbatim from closed accepted-index metadata.
# The lookup is a format adaptation, not a new geometry/graph/numerical QA pass.
def census(value,mids,budget):
    bindings=value['current_registered_extra_table_bindings'];tables=[]
    if bindings:
        import pyarrow as pa,pyarrow.parquet as pq
        directory=budget.out/'current_registered_identity_lookup';directory.mkdir()
        for number,binding in enumerate(bindings):
            source=binding['accepted_extra_index_reference'];index=C.load(source,32<<20)
            rows=index['records']
            if not rows:continue
            table=pa.Table.from_pylist(rows)
            for key in ('sprime_conf_idx','canonical_sprime_conf_idx','maximum_all_previous_physical_or_attempted_ids'):
                table=table.set_column(table.schema.get_field_index(key),key,pa.array([row[key] for row in rows],type=pa.int64()))
            sink=pa.BufferOutputStream();pq.write_table(table,sink,compression='zstd')
            ref=budget.write(directory/('registered_'+str(number)+'.parquet'),sink.getvalue().to_pybytes());tables.append(ref)
            budget.write(directory/('registered_'+str(number)+'.source.json'),C.canonical({
              'schema':'CURRENT_CANONICAL_REGISTERED_ID_METADATA_LOOKUP_V1','identity_scope':SCOPE,
              'accepted_extra_index_reference':source,'lookup_reference':ref,
              'physical_IDs_reassigned':False,'historical_noncanonical_coverage':'UNKNOWN'})+b'\n')
    view=dict(value,registered_extra_identity_tables=tables)
    return ORIGINAL.census(view,mids,budget)

# Original integration includes int64 max+1, registered-ID reuse, canonical
# geometry_id and complete producer/native alias and source witnesses.
integrate=ORIGINAL.integrate

def check_plan(plan):
    C.need(plan['identity_scope']==SCOPE and plan['historical_noncanonical_coverage']=='UNKNOWN'
      and plan['global_history_completeness_claimed'] is False,'PLAN_DECLARED_CURRENT_CANONICAL_IDENTITY_SCOPE')
    output=C.literal(plan['output_directory'])
    C.need(OUTPUT in output.parents,'NEW_CURRENT_SCOPE_OUTPUT_NAMESPACE')
    return plan
