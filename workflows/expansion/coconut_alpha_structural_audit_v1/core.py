"""Classify supplied evidence, never the existence of a real-world molecule."""
import collections
import hashlib
import re


def variable_metadata(text,kind):
    if text is None:return dict(whole_text_scanned=False,markers=[],query_or_repeat_metadata_marker=False,interpretation='NOT_REEXTRACTED')
    markers=[];explicit=False
    if kind=='MOL':
        for number,line in enumerate(text.splitlines(),1):
            if (re.match(r'^M\s+(STY|SAL|SBL|SMT|SCN|SDS|SPL|SNC|SBT|SST|RGP|LOG|ALS|APO)\b',line)
                    or re.search(r'\b(BEGIN SGROUP|BEGIN RGROUP|ENDPTS=|ATTACH=|RGROUPS=)\b',line)):
                markers.append(dict(line_ordinal_1based=number,sha256=hashlib.sha256(line.encode()).hexdigest(),
                    prefix=line[:240],prefix_truncated=len(line)>240))
                explicit=explicit or bool(re.match(r'^M\s+(RGP|LOG|ALS)\b',line)
                    or re.search(r'\b(SRU|COP|RGROUP|RGROUPS=)\b',line))
    return dict(whole_text_scanned=True,markers=markers,query_or_repeat_metadata_marker=explicit,
        interpretation='LEXICAL_MOL_METADATA_REQUIRES_REVIEW_NOT_PROOF_OF_VARIABLE_ATOM_COUNT' if markers else 'NO_LISTED_VARIABLE_OR_GROUP_METADATA_MARKER')


def variant(value,text=None):
    observed=value.get('unsanitized_atom_observation') or {};atoms=observed.get('atoms_in_parser_order')
    complete=(isinstance(atoms,list) and bool(atoms) and type(observed.get('atom_count')) is int
        and len(atoms)==observed['atom_count'] and all(isinstance(a,dict) and type(a.get('index')) is int and a['index']==i
        and type(a.get('atomic_number')) is int and 0<=a['atomic_number']<=118
        and type(a.get('has_query')) is bool for i,a in enumerate(atoms)))
    query=[a['index'] for a in atoms if a['has_query']] if complete else None
    dummy=[a['index'] for a in atoms if a['atomic_number']==0] if complete else None
    bonds=observed.get('query_bond_indices');bond_list=(isinstance(bonds,list) and all(type(i) is int and i>=0 for i in bonds))
    consistent=complete and bond_list and observed.get('query_atom_indices')==query and observed.get('dummy_atom_indices')==dummy
    all_real=bool(consistent and all(1<=a['atomic_number']<=118 for a in atoms))
    fixed=bool(all_real and not query)
    counts=collections.Counter(a['atomic_number'] for a in atoms if a['atomic_number']>1) if fixed else None
    vector=None if counts is None else [[z,counts[z]] for z in sorted(counts)]
    lexical=variable_metadata(text,value['representation'])
    candidate=fixed and not lexical['markers']
    reasons=[]
    if not complete:reasons.append('NO_COMPLETE_INDEXED_ATOM_TABLE_OBSERVATION')
    elif not consistent:reasons.append('OBSERVATION_INDEX_OR_QUERY_FLAGS_INCONSISTENT')
    if query:reasons.append('EXPLICIT_QUERY_ATOMS_OBSERVED_NOT_ASSUMED_FIXED_ELEMENT')
    if dummy:reasons.append('EXPLICIT_DUMMY_ATOMS_OBSERVED')
    if bonds:reasons.append('QUERY_BONDS_OBSERVED_ELEMENT_COUNTS_INDEPENDENT_IF_ATOMS_FIXED')
    if lexical['markers']:reasons.append('LEXICAL_GROUP_OR_VARIABLE_METADATA_REQUIRES_INTERPRETATION')
    if candidate:reasons.append('FIXED_EXPLICIT_ATOM_COMPOSITION_CANDIDATE_NOT_GRAPH_IDENTITY')
    if candidate and bonds:reasons.append('QUERY_BONDS_ONLY_DO_NOT_CHANGE_RECORDED_ATOMIC_NUMBERS')
    if not lexical['whole_text_scanned']:reasons.append('SOURCE_TEXT_VARIABLE_METADATA_NOT_REEXTRACTED')
    return dict(variant_id=value['variant_id'],representation=value['representation'],text_reference=value['text_reference'],
        source_pointer=value.get('source_pointer'),decoded_container=value.get('decoded_container'),
        upstream_source_reference=value.get('upstream_source_reference'),
        observation_state=observed.get('state','NOT_CALLED'),complete_atom_record_table=complete,
        atom_record_indices_and_query_flags_consistent=bool(consistent),atom_count=observed.get('atom_count'),
        all_recorded_atomic_numbers_real_Z=all_real,query_atom_indices=observed.get('query_atom_indices'),
        dummy_atom_indices=observed.get('dummy_atom_indices'),query_bond_indices=bonds,
        query_atom_descriptions=[dict(index=a['index'],atomic_number=a['atomic_number'],query_description=a.get('query_description'))
            for a in atoms if a['has_query']] if complete else [],
        producer_closed_explicit_atom_table=observed.get('closed_explicit_atom_table'),
        producer_full_non_H_composition_observation=observed.get('full_non_H_composition_observation'),
        producer_known_atom_lower_bound_observation=observed.get('positive_known_non_H_atom_lower_bound_observation'),
        fixed_atom_non_H_composition_observation=vector,fixed_atom_record_composition_observed=fixed,
        candidate_blocked_by_uninterpreted_group_metadata=bool(fixed and lexical['markers']),
        fixed_explicit_atom_composition_candidate=candidate,
        fixed_atoms_query_bonds_only=bool(fixed and bonds),variable_metadata=lexical,
        key_observation_state=(value.get('key_observation') or {}).get('state'),
        observed_full_keys=(value.get('key_observation') or {}).get('keys',[]),reasons=reasons,
        exact_composition_or_graph_accepted=False,world_nonexistence_inferred=False)


def partition(variants,finite=False,ontology=False):
    if finite:return 'FINITE_EXACT_SOURCE_RECOVERED_PROPOSAL'
    if ontology:return 'OFFICIAL_ONTOLOGY_CLASSIFICATION_WITNESS'
    if any(v['fixed_explicit_atom_composition_candidate'] for v in variants):return 'INSUFFICIENT_EVIDENCE'
    if any(v['query_atom_indices'] or v['dummy_atom_indices'] or v['query_bond_indices']
           or v['variable_metadata']['query_or_repeat_metadata_marker'] for v in variants):
        return 'SUPPLIED_REPRESENTATIONS_UNDERSPECIFIED_QUERY_DUMMY_OR_VARIABLE'
    return 'INSUFFICIENT_EVIDENCE'
