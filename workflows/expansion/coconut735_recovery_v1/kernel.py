"""Read the whole original SMILES without repairing its molecular graph.

A dummy atom is an unknown atom, not permission to discard the fixed atoms.
Fixed non-H atom counts therefore give a lower bound on every possible
molecule represented by that original record. The bound is a conservative
exclusion, never a recovered graph, formula, InChIKey or molecular identity.
"""
from collections import Counter
import hashlib
import json
import os

PARSER = dict(sanitize=False, removeHs=False, parseName=False,
              allowCXSMILES=False, strictCXSMILES=True, debugParse=False)
X02_ATOMIC_NUMBERS = (1, 5, 6, 7, 8, 9, 14, 15, 16, 17, 34, 35, 53)
VARIANTS = ('canonical_smiles', 'standardized_canonical_smiles', 'parent_canonical_smiles')


def require(value, message):
    if not value:
        raise ValueError(message)


def chem_module():
    from rdkit import Chem, rdBase
    require(rdBase.rdkitVersion == '2025.09.5', 'Frozen RDKit2025.09.5 required')
    return Chem


def observe_variant(text, chem=None):
    """Observe one original full string; never trim, substitute or derive keys."""
    base = dict(original=text, full_keys=[], original_identity_state='UNKNOWN_UNCHANGED',
                graph_repaired=False, full_key_computations=0, parser_parameters=PARSER)
    if text is None or text == '':
        return dict(base, disposition='ABSENT_OPTIONAL_VARIANT')
    require(isinstance(text, str), 'Original SMILES must be a string or NULL')
    base['original_utf8_sha256'] = hashlib.sha256(text.encode('utf-8')).hexdigest()
    if any(not 33 <= ord(c) <= 126 for c in text):
        return dict(base, disposition='HOLD', reason='WHOLE_STRING_NOT_ASCII33_TO126')
    chem = chem or chem_module()
    params = chem.SmilesParserParams()
    for key, value in PARSER.items():
        setattr(params, key, value)
    require({key: getattr(params, key) for key in PARSER} == PARSER, 'Parser parameter mismatch')
    try:
        molecule = chem.MolFromSmiles(text, params)
    except Exception as exc:
        return dict(base, disposition='HOLD', reason='ORIGINAL_SYNTAX_OR_PARSER_EXCEPTION',
                    exception_type=type(exc).__name__, exception_message=str(exc))
    if molecule is None:
        return dict(base, disposition='HOLD', reason='WHOLE_ORIGINAL_SMILES_SYNTAX_NOT_PARSED')
    atoms = list(molecule.GetAtoms())
    if not atoms or any(atom.HasQuery() for atom in atoms) or any(bond.HasQuery() for bond in molecule.GetBonds()):
        return dict(base, disposition='HOLD', reason='EMPTY_OR_QUERY_GRAPH_NOT_SIMPLE_ATOM_BOUND')
    zs = [int(atom.GetAtomicNum()) for atom in atoms]
    if any(not 0 <= z <= 118 for z in zs):
        return dict(base, disposition='HOLD', reason='INVALID_ORIGINAL_ATOMIC_NUMBER')
    counts = Counter(z for z in zs if z > 1)
    common = dict(base, explicit_atomic_numbers=zs, dummy_atoms=zs.count(0),
                  explicit_non_h_atom_count=sum(counts.values()),
                  bound=[[z, counts[z]] for z in sorted(counts)],
                  all_fragments_retained=True, implicit_hydrogens_inferred=False,
                  original_unsanitized_parse_is_not_graph_validation=True)
    forbidden = sorted(set(zs) - set(X02_ATOMIC_NUMBERS) - {0})
    if forbidden:
        return dict(common, disposition='CANDIDATE_DOMAIN_DISJOINT_X02', forbidden_fixed_elements=forbidden)
    if not counts:
        return dict(common, disposition='HOLD', reason='NO_FIXED_NON_H_ATOM_BOUND_DUMMY_ONLY_OR_HYDROGEN_ONLY')
    return dict(common, disposition='CONSERVATIVE_NON_H_ATOM_LOWER_BOUND',
                reason='FIXED_ORIGINAL_ATOMS_SURVIVE_EVERY_DUMMY_ATOM_COMPLETION',
                conservative_over_exclusion_possible=True,
                requires_candidate_veto_impact_measurement=True)


def physical(row):
    result = (row['source_table'], row['copy_block'], row['source_row_ordinal'])
    require(result[0] == 'entries' and type(result[1]) is int and result[1] > 0
            and type(result[2]) is int and result[2] >= 0, 'Exact original entry physical locator required')
    return result


def observe_row(row):
    """Bind all variants to the immutable original physical observation."""
    require(row.get('original_UNKNOWN_unchanged') is True and row.get('new_authoritative_keys') is False,
            'Original diagnosis does not preserve UNKNOWN')
    src = row['norm_observation']['source']
    locator = row['original_unresolved']['locator']
    require(physical(src) == physical(locator), 'Original locator and normalized source differ')
    fields = json.loads(src['identity_fields_json'])
    require(fields.get('molecule_id') is None and src['source_table'] == 'entries',
            'This recovery only covers original NULL-FK entries')
    require(row['norm_observation'].get('has_any_valid_full_key') is False,
            'Recovery cannot replace a preexisting resolved source identity')
    original_variants = row['norm_observation']['variant_observations']
    require([v['source_field'] for v in original_variants] == list(VARIANTS), 'All original variants required')
    observations = [dict(observe_variant(fields[name]), source_field=name) for name in VARIANTS]
    present = [v for v in observations if v['disposition'] != 'ABSENT_OPTIONAL_VARIANT']
    holds = [v for v in present if v['disposition'] == 'HOLD']
    return dict(schema='COCONUT735_ORIGINAL_ROW_RECOVERY_EVIDENCE_V1',
                locator=dict(source_table=src['source_table'], copy_block=src['copy_block'],
                             source_row_ordinal=src['source_row_ordinal']),
                source_id=fields['id'], source_row_sha256=src['source_row_sha256'],
                original_identity_fields_json=src['identity_fields_json'],
                original_identity_resolution='UNKNOWN_UNCHANGED', original_data_modified=False,
                variant_observations=observations, full_keys=[], full_key_computations=0,
                proposed_exclusion_coverage=bool(present) and not holds,
                hold_count=len(holds) if present else 1,
                source_exclusion_ACCEPTED=False, worker_pid=os.getpid())


def dominates(candidate, bound):
    """A veto is sound only for positive componentwise fixed-atom bounds."""
    require(isinstance(bound, list) and bound and
            all(isinstance(pair, list) and len(pair) == 2 and type(pair[0]) is int and
                2 <= pair[0] <= 118 and type(pair[1]) is int and pair[1] > 0 for pair in bound)
            and [pair[0] for pair in bound] == sorted({pair[0] for pair in bound}),
            'Positive sorted non-H bound required')
    return all(candidate.get(z, 0) >= n for z, n in bound)
