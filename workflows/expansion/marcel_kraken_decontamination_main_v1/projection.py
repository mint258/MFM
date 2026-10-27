"""Identity-only joins; unchanged producer relationship/comparison/consumer objects."""
import collections,hashlib,json
from workflows.expansion.marcel_kraken_keys_main_v1.source import relationship,token
from workflows.expansion.marcel_kraken_keys_main_v1.run import comparison
from workflows.expansion.decontamination import identity_keys
from workflows.expansion.common import wp5_key,KEY_RE
from . import contract as C
Q=C.Q


def canonical(value):return json.dumps(value,ensure_ascii=True,separators=(',',':'),sort_keys=True,allow_nan=False).encode('utf-8')
def sha(value):return hashlib.sha256(canonical(value)).hexdigest()


def strict_json(raw):
    def pairs(rows):
        out={}
        for k,v in rows:Q.need(k not in out,'DUPLICATE_JSON_OBJECT_MEMBER');out[k]=v
        return out
    def invalid(value):raise ValueError('NONFINITE_JSON_CONSTANT')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid)


def integer(value,upper,label):
    Q.need(type(value) is int and 0<=value<upper,label);return value


def native(value):
    Q.need(type(value) is dict and set(value)=={'text','UTF8_surrogatepass_bytes','sha256','strict_UTF8_valid'}
        and type(value['text']) is str and value==token(value['text']),'UNCHANGED_NATIVE_TOKEN_BYTES_SHA_AND_UTF8_STATE')
    return value


def locator(row):
    root=integer(row['root_assignment_ordinal'],1552,'EXACT_NATIVE_ROOT_ORDINAL');kind=row['kind'];native(row['native_root_ID'])
    Q.need(kind in ('root_SMILES','conformer_MolBlock'),'ONLY_ORIGINAL_SOURCE_KINDS')
    if kind=='root_SMILES':
        Q.need(type(row['all_original_conformer_relationships']) is int and 0<=row['all_original_conformer_relationships']<=21287,
            'DECLARED_NATIVE_CONFORMER_CARDINALITY');position=None
    else:
        integer(row['secondary_assignment_ordinal'],21287,'EXACT_NATIVE_LOCAL_ORDINAL');native(row['native_conformer_ID'])
        position=integer(row['global_conformer_assignment_ordinal'],21287,'EXACT_NATIVE_GLOBAL_ORDINAL')
    return json.dumps([kind,root,position],separators=(',',':'))


def compact(result):
    Q.need(type(result['has_any_unknown']) is bool and type(result['identity_state']) is str
        and type(result['full_key_and_WP5_pairs']) is list,'EXPLICIT_ORIGINAL_IDENTITY_STATE')
    pairs=result['full_key_and_WP5_pairs']
    for p in pairs:Q.need(type(p) is list and len(p)==2 and type(p[0]) is str and KEY_RE.fullmatch(p[0]) is not None
        and p[1]==wp5_key(p[0]),'UNCHANGED_VALID_FULL_KEY_AND_ORIGINAL_WP5')
    Q.need(len({p[0] for p in pairs})==len(pairs),'NO_DUPLICATE_NORMALIZED_PAIR')
    Q.need(result['has_any_unknown'] or bool(pairs),'EMPTY_KNOWN_RESULT_IS_NOT_AN_IDENTITY')
    return {k:result[k] for k in ('identity_state','has_any_unknown','full_key_and_WP5_pairs')}


def expected_union(root_context,root_result,conformers):
    """Rebuild producer aggregation from its compact results without new chemistry."""
    ordinal=root_context['root_assignment_ordinal'];pairs=set(map(tuple,root_result['full_key_and_WP5_pairs']));comparisons=[]
    for ctx,result in conformers:
        Q.need(ctx['root_assignment_ordinal']==ordinal and ctx['native_root_ID']==root_context['native_root_ID'],'EXACT_NATIVE_PARENT_RELATION')
        pairs.update(map(tuple,result['full_key_and_WP5_pairs']))
        comparisons.append({k:ctx[k] for k in ('global_conformer_assignment_ordinal','secondary_assignment_ordinal','native_conformer_ID')}
            |result|{'root_SMILES_vs_conformer_comparison':comparison(root_result,result)})
    Q.need([x['secondary_assignment_ordinal'] for x in comparisons]==list(range(len(comparisons)))
        and len(comparisons)==root_context['all_original_conformer_relationships'],'ALL_NATIVE_LOCAL_ASSIGNMENTS_NO_SKIPPING')
    local=dict(collections.Counter(x['root_SMILES_vs_conformer_comparison'] for x in comparisons))
    return {'root_assignment_ordinal':ordinal,'native_root_ID':root_context['native_root_ID'],'source_root_SMILES_result':root_result,
        'all_original_conformer_relationships':len(comparisons),'selected_conformer_results':len(comparisons),
        'all_selected_native_conformer_key_observations':comparisons,'comparison_counts':local,
        'conservative_full_InChIKey_union':sorted({k for k,w in pairs}),'conservative_WP5_key_union':sorted({w for k,w in pairs}),
        'all_conformers_covered':True,'coverage_state':'ALL_ORIGINAL_CONFORMERS','multiple_observed_full_keys':len({k for k,w in pairs})>1,
        'representative_source_or_conformer_selected':False,'unknowns_or_mismatches_discarded':False,'source_graph_stereo_or_pool_accepted':False}


def identity(root,archive_sha):
    Q.need(root['all_conformers_covered'] is True and root['coverage_state']=='ALL_ORIGINAL_CONFORMERS'
        and root['representative_source_or_conformer_selected'] is False and root['unknowns_or_mismatches_discarded'] is False,'ONLY_COMPLETE_CONSERVATIVE_NATIVE_UNIONS')
    unknown=root['source_root_SMILES_result']['has_any_unknown'] or any(x['has_any_unknown'] for x in root['all_selected_native_conformer_key_observations'])
    source_id=json.dumps(['MARCEL/Kraken',archive_sha,root['root_assignment_ordinal'],native(root['native_root_ID'])['text']],ensure_ascii=True,separators=(',',':'))
    row={'source_id':source_id,'role':'all','subdataset':'','inchikeys':list(root['conservative_full_InChIKey_union']),'non_h_composition':None}
    # Unknown evidence is retained independently; it may never become READY by
    # merely having at least one known key. The consumer sees only its 5 fields.
    Q.need(row['inchikeys']==sorted(set(row['inchikeys'])),'EXACT_UNIQUE_UNION_NOT_A_REPRESENTATIVE')
    keys=identity_keys(row) if row['inchikeys'] else []
    expected_wp5=[wp5_key(k) for k in row['inchikeys']]
    Q.need(root['conservative_WP5_key_union']==sorted(set(expected_wp5)) and [v for kind,v in keys if kind=='full']==row['inchikeys']
        and [v for kind,v in keys if kind=='wp5']==expected_wp5,'DIRECT_CONSUMER_EXACT_FULL_AND_WP5_KEYS')
    return row,unknown or not bool(row['inchikeys'])
