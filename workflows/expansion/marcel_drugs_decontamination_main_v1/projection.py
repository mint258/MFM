"""No chemistry: accepted complete conservative union -> original strict consumer."""
import json
from workflows.expansion.marcel_kraken_decontamination_main_v1.projection import strict_json,canonical,sha
from workflows.expansion.identity_v2.projection_v2 import full_keys
from workflows.expansion.decontamination import identity_keys
from workflows.expansion.common import wp5_key
from workflows.expansion.marcel_drugs_keys_main_v1.rows import token
from . import contract as C
Q=C.Q
FIELDS={'source_id','original_CSV_physical_ordinal','original_name_fields','source_conformers','source_profile_keys_observed_conformers',
    'native_graph_observed_conformers','native_graph_NOT_YET_EXAMINED_conformers','unknown_observed_native_conformers',
    'native_source_key_mismatch_conformers','native_source_key_comparison_known_conformers','native_source_key_comparison_UNKNOWN_conformers',
    'distinct_original_SMILES_byte_variants','original_multiple_SMILES_status','source_SMILES_full_key_union','native_graph_full_key_union',
    'conservative_all_observed_full_InChIKey_union','conservative_all_observed_WP5_key_union','coverage','representative_chosen',
    'native_graph_full_or_pool_release','source_full_keys_observed_conformers','original_source_profile_count_field_retained_as_legacy_alias',
    'unknown_or_mismatch_is_chemical_exclusion'}

def count(n,label,minimum=0):Q.need(type(n)is int and n>=minimum,label);return n

def project(value,ordinal,archive_sha):
    Q.need(type(value)is dict and set(value)==FIELDS and value['source_id']=='marcel_drugs_zip'
        and count(value['original_CSV_physical_ordinal'],'EXACT_CSV_ORDINAL')==ordinal and 0<=ordinal<C.N,
        'EXACT_UNCHANGED_PRODUCER_ROW_FIELDS_AND_CONTIGUOUS_CSV_ORDINAL')
    Q.need(archive_sha==C.ARCHIVE_SHA,'EXACT_OFFICIAL_ARCHIVE_IDENTITY_NAMESPACE')
    total=count(value['source_conformers'],'POSITIVE_NATIVE_CONFORMER_POPULATION',1)
    for key in ('source_profile_keys_observed_conformers','source_full_keys_observed_conformers','native_graph_observed_conformers','native_source_key_comparison_known_conformers'):
        Q.need(count(value[key],'INTEGER_FULL_COVERAGE:'+key)==total,'EVERY_ORIGINAL_SOURCE_AND_NATIVE_CONFORMER_COVERED')
    for key in ('native_graph_NOT_YET_EXAMINED_conformers','native_source_key_comparison_UNKNOWN_conformers'):
        Q.need(count(value[key],'INTEGER_MISSING:'+key)==0,'NO_PARTIAL_SOURCE_OR_UNKNOWN_COMPARISON_ACCEPTANCE')
    unknown=count(value['unknown_observed_native_conformers'],'INTEGER_NATIVE_UNKNOWNS')
    mismatch=count(value['native_source_key_mismatch_conformers'],'INTEGER_SOURCE_NATIVE_DIFFERENCES');Q.need(unknown<=total and mismatch<=total,'COUNTS_WITHIN_ORIGINAL_CONFORMER_POPULATION')
    variants=count(value['distinct_original_SMILES_byte_variants'],'ORIGINAL_SOURCE_VARIANTS',1)
    Q.need(type(value['original_multiple_SMILES_status'])is bool and value['original_multiple_SMILES_status']==(variants>1)
        and value['representative_chosen'] is False and value['native_graph_full_or_pool_release'] is False
        and value['unknown_or_mismatch_is_chemical_exclusion'] is False and value['original_source_profile_count_field_retained_as_legacy_alias'] is True
        and value['coverage']=='FULL558002_NATIVE_1000_ACTUAL_C0_ADOPTED557002_NEW_ALL_VARIANTS_AND_NAMES_RETAINED',
        'ALL_VARIANTS_NO_REPRESENTATIVE_NO_EXCLUSION_OR_FALSE_NATIVE_RELEASE')
    Q.need(type(value['original_name_fields'])is list and len(value['original_name_fields'])==1
        and bool(token(value['original_name_fields'][0])),'LITERAL_ORIGINAL_CSV_NAME_TOKEN_NO_NORMALIZATION')
    source,invalid=full_keys(value['source_SMILES_full_key_union'],strict=False);Q.need(not invalid and source==value['source_SMILES_full_key_union'],'ORIGINAL_SOURCE_FULL_KEYS_VALID_EXACT_ORDER')
    native,invalid=full_keys(value['native_graph_full_key_union'],strict=False);Q.need(not invalid and native==value['native_graph_full_key_union'],'ORIGINAL_NATIVE_FULL_KEYS_VALID_EXACT_ORDER')
    union=sorted(set(source)|set(native));Q.need(value['conservative_all_observed_full_InChIKey_union']==union
        and value['conservative_all_observed_WP5_key_union']==sorted({wp5_key(k) for k in union}),'EXACT_SOURCE_PLUS_NATIVE_CONSERVATIVE_UNION_NO_ALIAS_REPAIR')
    row={'source_id':json.dumps(['MARCEL/Drugs',archive_sha,ordinal],separators=(',',':')),'role':'all','subdataset':'',
        'inchikeys':list(union),'non_h_composition':None}
    keys=identity_keys(row) if union else []
    Q.need([k for kind,k in keys if kind=='full']==union and [k for kind,k in keys if kind=='wp5']==[wp5_key(k) for k in union],
        'ACTUAL_ORIGINAL_STRICT_CONSUMER_EXACT_FULL_WP5')
    return row,{'conformers':total,'native_unknown':unknown,'mismatch_conformers':mismatch,'mismatch_names':int(mismatch>0),
        'multi_SMILES_names':int(variants>1),'unresolved':int(unknown>0 or not union)}

def mass(n,totals):
    Q.need(n==C.N and dict(totals)=={'conformers':558002,'native_unknown':0,'mismatch_conformers':126,'mismatch_names':31,
        'multi_SMILES_names':290,'unresolved':0},'ALL75099_558002_UNKNOWNS_126_DIFFERENCES31_NAMES290_VARIANTS_CONSERVED')
