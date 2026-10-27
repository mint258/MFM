"""Strict five-field identity projection, never graph/key/feature computation."""
from workflows.expansion.decontamination import identity_keys,ALLOWED_IDENTITY_FIELDS
from . import contract as C,io as I

def local(row):
    C.need(row['dataset'] in {**C.PRIMARY,**C.PARTIAL} and type(row['source_id'])is str and row['source_id'] and type(row['role'])is str,'CLOSED_ORIGINAL_DATASET_SOURCE_ID_ROLE')
    expected={'SOURCE_TRAIN','SOURCE_FULL','SOURCE_ROUTINE','SOURCE_EMBARGO'} if row['dataset']=='v1_all_roles_and_embargo' else {'train','test'} if row['dataset']=='expansionrx' else {'all'}
    C.need(row['role'] in expected and type(row['memberships'])is list and all(type(v)is str for v in row['memberships']),'ORIGINAL_SOURCE_ROLE_NOT_FINAL_WHOLEMID_ROLE')
    keys=row['inchikeys'];composition=None if row['non_h_composition_json'] is None else I.strict_json(row['non_h_composition_json'])
    C.need(type(keys)is list and all(type(k)is str for k in keys),'ORIGINAL_MULTIKEY_LIST_NOT_REPRESENTATIVE_SELECTION')
    value={'source_id':row['source_id'],'role':row['role'],'subdataset':'','inchikeys':list(keys),'non_h_composition':composition}
    audit={k:row[k] for k in ('dataset','source_id','role','memberships','missing_full_key','missing_identity_or_composition','unresolved_source_variant','conservative_reason')}
    if not keys and composition is None:
        C.need(row['dataset'] in C.PARTIAL,'PRIMARY_IDENTITY_MISSING_HOLD_NOT_EXCLUSION');return None,audit
    identity_keys(value);C.need(set(value)==ALLOWED_IDENTITY_FIELDS,'EXACT_FIVE_OUTPUT_FIELDS');return value,audit

def source_key(row):
    C.need(row['dataset']=='tdc_admet_group_zip' and row['row_width']==3 and row['assay_Y_decoded'] is False
        and row['original_split'] in ('train_val','test') and type(row['physical_record_ordinal'])is int and row['physical_record_ordinal']>=0,'ORIGINAL_TDC_PHYSICAL_SOURCE_FIELDS_ONLY')
    C.need(row['member_name']=='admet_group/'+row['endpoint']+'/'+row['original_split']+'.csv','EXACT_ORIGINAL_ENDPOINT_AND_MEMBER_SPLIT')
    return row['member_name'],row['physical_record_ordinal']

def tdc(source,result,archive_sha,accepted=None):
    member,ordinal=source_key(source);C.need(I.equal_json(result['source'],source),'SOURCE_RESULT_LITERAL_EXACT_NOT_NATIVE_ID_ONLY')
    keys=result['full_InChIKeys'];C.need(type(keys)is list,'ORIGINAL_TDC_KEYS_LIST')
    composition=None
    if result['identity_state']=='FULL_KEYS_DERIVED':C.need(keys and accepted is None,'KNOWN_KEY_ROW_MUST_KEEP_ALL_ORIGINAL_KEYS')
    else:
        C.need(result['identity_state']=='ORIGINAL_SMILES_UNRESOLVED' and not keys and result['WP5_keys']==[] and result['identity_errors']
            and accepted is not None,'ONLY_ROOT_ACCEPTED_EXACT_TWO_FALLBACKS')
        C.need(I.equal_json(accepted['original_source'],source) and I.equal_json(accepted['original_result'],result),'EXACT_SOURCE_AND_RESULT_JOIN_FOR_COMPOSITION')
        composition=accepted['composition']
    # Native Drug_ID is allowed to be repeated/empty; physical source identity is not.
    value={'source_id':I.dump(['TDC_ADMET_ORIGINAL',archive_sha,member,ordinal]).decode().rstrip('\n'),
        'role':source['original_split'],'subdataset':source['endpoint'],'inchikeys':list(keys),'non_h_composition':composition}
    identity_keys(value);return value
