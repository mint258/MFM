"""Original Alpha SMILES objects plus explicitly separate new MOL diagnostics."""
import collections
import importlib
import os
import sys
from pathlib import Path
from . import support as S
from .extract import PLACEHOLDER, extract

STATE = {}
SMILES_PARAMS = dict(sanitize=False, removeHs=False, parseName=False,
                     allowCXSMILES=False, strictCXSMILES=True, debugParse=False)
MOL_PARAMS = dict(removeHs=False, strictParsing=True)


def initialize(plan):
    root = Path(plan['original_source_root'])
    S.need(root == Path('/gfshome/alpha/codex_data_v1_20261026/code'), 'ACTUAL_ORIGINAL_ALPHA_SOURCE_ROOT')
    refs = plan['original_source_references']
    for ref in refs:
        S.read(ref, 2 << 20)
    declared = {r['path']: r for r in refs}
    sys.path.append(str(root))
    import workflows.expansion as expansion
    old = str(root / 'workflows/expansion'); saved = list(expansion.__path__)
    expansion.__path__[:] = [old, *[p for p in saved if p != old]]
    try:
        projection = importlib.import_module('workflows.expansion.identity_v2.projection_v2')
        common = importlib.import_module('workflows.expansion.common')
        norm = importlib.import_module('secondary_coconut_identity_norm_profile_v1.run')
        original = importlib.import_module('secondary_coconut_strict5_day_v1.kernel')
    finally:
        expansion.__path__[:] = saved
    from rdkit import Chem, rdBase
    import numpy
    S.need(sys.version_info[:3] == (3, 11, 14) and rdBase.rdkitVersion == '2025.09.5'
           and numpy.__version__ == '2.2.6', 'EXACT_ORIGINAL_NATIVE_ENVIRONMENT')
    S.need(original.C.PARAMS == SMILES_PARAMS, 'EXACT_ORIGINAL_UNSANITIZED_SMILES_RECIPE')
    for key, module in [('projection', projection), ('common', common)]:
        relative, size, digest = norm.c.FROZEN[key]
        S.need(Path(module.__file__).absolute() == root / relative
               and S.pin(module.__file__) == dict(path=str(root / relative), bytes=size, sha256=digest),
               'EXACT_FROZEN_IDENTITY_SOURCE_OBJECT_' + key)
    imported = []
    for name, module in list(sys.modules.items()):
        if (name.startswith(('secondary_coconut_', 'secondary_cpu_queue_v1'))
                or name in ('workflows.expansion.common', 'workflows.expansion.identity_v2',
                            'workflows.expansion.identity_v2.projection_v2',
                            'workflows.expansion.identity_v2.readers_v2')):
            file = getattr(module, '__file__', None)
            if file and file.endswith('.py'):
                ref = S.pin(file)
                S.need(declared.get(ref['path']) == ref, 'EVERY_ORIGINAL_TRANSITIVE_SOURCE_PIN:' + name)
                imported.append(ref)
    functions = dict(full_keys=projection.full_keys, source_smiles_keys=projection.source_smiles_keys,
                     wp5_key=common.wp5_key)
    objects = dict(functions, normalize=norm.normalize, native_composition=projection.native_composition,
                   original_composition=original.composition, original_atoms_only=original.atoms_only)
    proof = dict(basis='ACTUAL_ORIGINAL_FUNCTION_OBJECTS_FULL_FILE_SHA',
                 original_transitive_sources=imported,
                 objects={k:dict(qualified_name=v.__module__ + '.' + v.__qualname__,
                                 filename=v.__code__.co_filename, first_line=v.__code__.co_firstlineno)
                          for k, v in objects.items()},
                 environment=dict(python=sys.version.split()[0], RDKit=rdBase.rdkitVersion,
                                  numpy=numpy.__version__),
                 MOL_adapter_is_new_diagnostic_seam=True,
                 MOL_adapter_is_original_normalize_recipe=False)
    STATE.update(Chem=Chem, projection=projection, original=original, norm=norm,
                 functions=functions, proof=proof)
    return proof


def exception(exc):
    return dict(type=type(exc).__name__, message=str(exc))


def atom_evidence(mol):
    """Count only unqueried explicit known Z; never infer wildcard contents/H."""
    atoms = []; counts = collections.Counter(); queries = []; dummy = []
    for atom in mol.GetAtoms():
        z = int(atom.GetAtomicNum()); query = bool(atom.HasQuery()); index = int(atom.GetIdx())
        item = dict(index=index, atomic_number=z, has_query=query,
                    isotope=int(atom.GetIsotope()), formal_charge=int(atom.GetFormalCharge()))
        if query:
            item['query_description'] = atom.DescribeQuery(); queries.append(index)
        if z == 0:
            dummy.append(index)
        if not query and 1 <= z <= 118 and z != 1:
            counts[z] += 1
        atoms.append(item)
    bond_queries = [int(b.GetIdx()) for b in mol.GetBonds() if b.HasQuery()]
    vector = [[z, counts[z]] for z in sorted(counts)]
    closed = bool(atoms) and all(not a['has_query'] and 1 <= a['atomic_number'] <= 118 for a in atoms)
    closed = closed and not bond_queries
    return dict(atoms_in_parser_order=atoms, atom_count=len(atoms), query_atom_indices=queries,
                dummy_atom_indices=dummy, query_bond_indices=bond_queries,
                closed_explicit_atom_table=closed,
                positive_known_non_H_atom_lower_bound_observation=vector or None,
                lower_bound_basis='WHOLE_REPRESENTATION_PARSED_UNQUERIED_EXPLICIT_POSITIVE_ATOMIC_NUMBERS_ONLY',
                lower_bound_accepted_for_exclusion=False, implicit_H_or_formula_inferred=False,
                query_or_dummy_completion_inferred=False,
                full_non_H_composition_observation=vector if closed and vector else None,
                composition_is_explicit_atom_observation_not_formula=True)


def parse_atoms(text, kind):
    Chem = STATE['Chem']
    if kind == 'SMILES':
        if any(not 33 <= ord(c) <= 126 for c in text):
            return dict(state='NOT_PARSED', reason='WHOLE_ORIGINAL_ASCII_GUARD_NO_TRIM_OR_PREFIX_PARSE')
        params = Chem.SmilesParserParams()
        for name, value in SMILES_PARAMS.items():
            setattr(params, name, value)
        S.need({k:getattr(params, k) for k in SMILES_PARAMS} == SMILES_PARAMS, 'NATIVE_PARSER_RECIPE')
        mol = Chem.MolFromSmiles(text, params)
        recipe = dict(api='MolFromSmiles', parameters=SMILES_PARAMS, original_recipe=True)
    else:
        mol = Chem.MolFromMolBlock(text, sanitize=False, **MOL_PARAMS)
        recipe = dict(api='MolFromMolBlock', parameters=dict(MOL_PARAMS, sanitize=False),
                      original_recipe=False, explicit_new_diagnostic_seam=True)
    if mol is None:
        return dict(state='PARSE_RETURNED_NONE', recipe=recipe)
    evidence = atom_evidence(mol)
    if evidence['full_non_H_composition_observation'] is not None:
        # Use the actual frozen composition object to validate the complete vector.
        evidence['full_non_H_composition_observation'] = STATE['projection'].native_composition(
            evidence['full_non_H_composition_observation'])
    return dict(state='UNSANITIZED_WHOLE_REPRESENTATION_ATOMS_OBSERVED', recipe=recipe, **evidence)


def keys(text, kind):
    if kind == 'SMILES':
        value, errors = STATE['functions']['source_smiles_keys']({'whole_source_variant': text})
        return dict(state='DIAGNOSTIC_KEYS_OBSERVED' if value else 'UNRESOLVED_ORIGINAL_RECIPE',
                    keys=value, WP5_keys=[STATE['functions']['wp5_key'](v) for v in value],
                    errors=errors, recipe='ACTUAL_FROZEN_source_smiles_keys_FUNCTION_OBJECT',
                    whole_string_passed_unchanged=True,
                    parser_consumption_beyond_original_recipe_independently_proven=False)
    mol = STATE['Chem'].MolFromMolBlock(text, sanitize=True, **MOL_PARAMS)
    if mol is None:
        return dict(state='SANITIZED_MOL_PARSE_RETURNED_NONE', keys=[], errors=[],
                    recipe=dict(api='MolFromMolBlock', parameters=dict(MOL_PARAMS, sanitize=True),
                                explicit_new_diagnostic_seam=True))
    raw = STATE['Chem'].MolToInchiKey(mol)
    valid, invalid = STATE['functions']['full_keys']([raw], strict=False)
    return dict(state='DIAGNOSTIC_KEYS_OBSERVED' if valid else 'NO_VALID_FULL_KEY', keys=valid,
                WP5_keys=[STATE['functions']['wp5_key'](v) for v in valid],
                invalid_key_tokens=invalid, errors=[],
                recipe='NEW_NATIVE_MOL_SANITIZE_TRUE_THEN_MolToInchiKey_AND_FROZEN_full_keys',
                original_normalize_recipe=False)


def observe_variant(variant):
    value = {k:v for k, v in variant.items() if k != 'text'}
    text = variant['text']
    value.update(identity_accepted=False, composition_accepted=False, strict5_written=False)
    if text in (None, '', PLACEHOLDER):
        value['state'] = variant['text_reference']['state']; return value
    for label, function in [('unsanitized_atom_observation', parse_atoms), ('key_observation', keys)]:
        try:
            value[label] = function(text, variant['representation'])
        except Exception as exc:
            value[label] = dict(state='DIAGNOSTIC_EXCEPTION_UNKNOWN_RETAINED', exception=exception(exc))
    if variant['representation'] == 'SMILES':
        try:
            value['original_composition_function_observation'] = STATE['original'].composition(
                text, STATE['Chem'], {'native_composition': STATE['projection'].native_composition})
        except Exception as exc:
            value['original_composition_function_observation'] = dict(
                state='DIAGNOSTIC_EXCEPTION_UNKNOWN_RETAINED', exception=exception(exc))
    value['state'] = 'COMPLETE_SOURCE_BOUND_DIAGNOSTIC_OBSERVATION_NOT_ACCEPTANCE'
    return value


def work(record):
    row = extract(record)
    variants = [observe_variant(v) for v in row.pop('variants')]
    original_norm = STATE['norm'].normalize(row['source'], STATE['functions'])
    # Exact source row, not a synthetic injected cached field masquerading as SQL.
    S.need(original_norm['source'] == row['source'], 'ORIGINAL_NORMALIZE_PHYSICAL_ROW_UNCHANGED')
    seen_keys = any(v.get('key_observation', {}).get('keys') for v in variants)
    complete_comp = any(v.get('unsanitized_atom_observation', {}).get('full_non_H_composition_observation')
                        for v in variants)
    bound = any(v.get('unsanitized_atom_observation', {}).get(
        'positive_known_non_H_atom_lower_bound_observation') for v in variants)
    return dict(row, variants=variants, original_normalize_function_observation=original_norm,
                diagnostic_availability=dict(any_variant_has_observed_full_key=seen_keys,
                    any_variant_has_closed_explicit_composition=complete_comp,
                    any_variant_has_positive_known_atom_lower_bound=bound,
                    availability_does_not_prove_source_graph_association=True),
                worker_pid=os.getpid(), original_UNKNOWN_unchanged=True,
                new_authoritative_keys=False, graph_identity_repaired=False,
                full_key_observations_accepted=False, formula_or_lower_bound_exclusion_accepted=False,
                strict5_written=False, all11_ready=False, global_pool_release=False)
