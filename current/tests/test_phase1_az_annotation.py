"""Synthetic literal-field grammar only; no actual AZ/source labels or molecules."""
from dataclasses import FrozenInstanceError
import ast
import builtins
import hashlib
import json
import random

import pytest

from phychem_mfm.phase1.identity import canonical_hash
from phychem_mfm.phase1 import az_annotation as module
from phychem_mfm.phase1.az_annotation import AZAnnotationError, AZExactGroups, parse_az_exact_groups


def parse(groups, flags, n=3):
    return parse_az_exact_groups(groups, flags, n_author_atoms=n)


def test_literal_string_flags_match_pinned_author_documentation_example():
    # Fixed dataset.py:48,64 examples, not a downloaded benchmark row.
    result = parse("['8,9', '12']", "['1', '0']", n=13)
    assert result.groups == ((8, 9), (12,))
    assert result.flags == (1, 0) and result.exact_author_ids == (8, 9)
    assert result.provenance['raw_flag_types'] == ['string', 'string']


def test_zero_is_kept_without_decrement_and_repetitions_are_binary_idempotent():
    result = parse("['0, 00, 1', '2,0', '3']", '[1,1,0]', n=4)
    assert result.groups == ((0, 0, 1), (2, 0), (3,))
    assert result.exact_author_ids == (0, 1, 2)
    proof = result.provenance
    assert proof['source_index_base'] == proof['output_index_base'] == proof['index_decrement_count'] == 0
    assert proof['all_index_occurrences'] == 6 and proof['all_unique_index_count'] == 4
    assert proof['all_duplicate_occurrence_count'] == proof['exact_duplicate_occurrence_count'] == 2
    assert proof['exact_index_occurrences'] == 5 and proof['unique_exact_author_atom_count'] == 3
    assert proof['duplicate_occurrences'] == proof['exact_duplicate_occurrences'] == [[0, 1, 0], [1, 1, 0]]


def test_flags_keep_input_representation_hashes_and_empty_group_alignment():
    flags = "[' 1\t', 0, '0', 1]"
    result = parse("['', '2', '  ', '0,2']", flags)
    assert result.groups == ((), (2,), (), (0, 2)) and result.flags == (1, 0, 0, 1)
    assert result.raw_group_strings == ('', '2', '  ', '0,2') and result.exact_author_ids == (0, 2)
    proof = result.provenance
    assert proof['raw_flag_types'] == ['string', 'integer', 'string', 'integer']
    assert proof['raw_flag_string_utf8_sha256'] == [hashlib.sha256(b' 1\t').hexdigest(), None, hashlib.sha256(b'0').hexdigest(), None]
    assert proof['empty_group_count'] == 2 and proof['exact_group_count'] == proof['extended_group_count'] == 2
    assert proof['all_duplicate_occurrence_count'] == 1 and proof['exact_duplicate_occurrence_count'] == 0


def test_exact_set_order_is_first_appearance_and_extended_groups_are_not_merged():
    result = parse("['2,0', '1,2', '3']", '[1,1,0]', n=4)
    assert result.exact_author_ids == (2, 0, 1)
    assert 3 not in result.exact_author_ids and result.groups[-1] == (3,)


@pytest.mark.parametrize('groups,flags,state', [
    ('[]', '[]', 'NO_GROUPS'),
    ("['']", '[0]', 'EMPTY_GROUPS'),
    ("['1']", '[0]', 'EXTENDED_ONLY'),
    ("['', '1']", '[1,0]', 'EXACT_GROUPS_EMPTY'),
    ("['0']", '[1]', 'EXACT_INDICES_PRESENT'),
])
def test_empty_extended_and_exact_states_do_not_create_negative_labels(groups, flags, state):
    result = parse(groups, flags)
    assert result.annotation_state == result.provenance['annotation_state'] == state
    for name in ('formal_eligible', 'annotation_truth_verified', 'annotation_completeness_verified',
                 'chemical_negative_truth_verified', 'source_or_property_association_verified',
                 'labels_or_supervision_masks_generated', 'native_mapping_or_geometry_used'):
        assert result.provenance[name] is False
    assert not hasattr(result, 'labels') and not hasattr(result, 'supervision_mask')


@pytest.mark.parametrize('groups', ["[0]", "[['0']]", "('0',)", "['0 1']", "['1,']",
                                    "['-1']", "['+0']", "['3']", "['٠']", "[b'0']"])
def test_wrong_group_shapes_tokens_unicode_and_range_are_rejected(groups):
    with pytest.raises(AZAnnotationError):
        parse(groups, '[1]')


@pytest.mark.parametrize('flags', ['[True]', '[False]', '[2]', '[-1]', '[0.0]', '[None]',
                                   "['01']", "['+1']", "['-0']", "['١']", "['\u00a01']", "[b'1']"])
def test_flag_types_are_not_coerced_to_arbitrary_truthiness(flags):
    with pytest.raises(AZAnnotationError):
        parse("['0']", flags)


@pytest.mark.parametrize('groups,flags', [("['0', '1']", '[1]'), ("['0']", '[1,0]')])
def test_cardinality_is_checked_before_zip_without_truncation(groups, flags):
    with pytest.raises(AZAnnotationError, match='cardinality'):
        parse(groups, flags)


@pytest.mark.parametrize('groups', ['[x for x in []]', "__import__('os')", "['0'] + ['1']"])
def test_expressions_are_rejected_before_literal_evaluation(groups, monkeypatch):
    monkeypatch.setattr(ast, 'literal_eval', lambda *a: (_ for _ in ()).throw(AssertionError('unsafe AST must not reach literal evaluator')))
    with pytest.raises(AZAnnotationError):
        parse(groups, '[1]')


@pytest.mark.parametrize('bound', ['utf8', 'nodes', 'depth', 'groups', 'tokens'])
def test_each_declared_parser_budget_has_an_actual_rejection_path(bound, monkeypatch):
    groups, flags = "['0']", '[1]'
    if bound == 'utf8':
        monkeypatch.setattr(module, 'MAX_FIELD_BYTES', 5)
        groups = "['é']"  # Five characters, six UTF8 bytes; bound precedes ASCII grammar.
    elif bound == 'nodes': monkeypatch.setattr(module, 'MAX_AST_NODES', 3)
    elif bound == 'depth': monkeypatch.setattr(module, 'MAX_AST_DEPTH', 1)
    elif bound == 'groups':
        monkeypatch.setattr(module, 'MAX_GROUPS', 1)
        groups, flags = "['0','1']", '[1,1]'
    else:
        monkeypatch.setattr(module, 'MAX_INDEX_TOKENS', 1)
        groups = "['0,0']"
    with pytest.raises(AZAnnotationError, match='cap'):
        parse(groups, flags)


@pytest.mark.parametrize('n', [False, 0, -1, 1.0, module.MAX_AUTHOR_ATOMS + 1])
def test_atom_count_is_explicit_positive_integer_metadata(n):
    with pytest.raises(AZAnnotationError):
        parse("['0']", '[1]', n=n)


def test_returned_values_are_frozen_and_receipt_access_returns_owned_snapshots():
    result = parse("['0,1']", '[1]')
    before = result.to_dict()
    with pytest.raises(FrozenInstanceError): result.flags = (0,)
    with pytest.raises(TypeError): result.groups[0][0] = 2
    with pytest.raises(AZAnnotationError): AZExactGroups(groups=((2,),), provenance={'formal_eligible': True})
    mutated = result.provenance
    mutated['groups'][0][0] = 2
    mutated['limits']['author_atoms'] = 999999
    mutated['annotation_truth_verified'] = True
    public = result.to_dict()
    public['exact_author_ids'].append(2)
    assert result.to_dict() == before
    with pytest.raises(TypeError):
        parse_az_exact_groups("['0']", '[1]', n_author_atoms=3, provenance=mutated)


def test_raw_field_hashes_and_canonical_receipt_are_finite_json_bound_not_source_truth():
    groups, flags = " ['00'] ", " ['1'] "
    result = parse(groups, flags)
    proof = result.provenance
    assert proof['groups_field']['decoded_field_utf8_sha256'] == hashlib.sha256(groups.encode()).hexdigest()
    assert proof['flags_field']['decoded_field_utf8_sha256'] == hashlib.sha256(flags.encode()).hexdigest()
    digest = proof.pop('annotation_provenance_sha256')
    assert canonical_hash(proof) == digest
    assert json.loads(json.dumps(result.to_dict(), allow_nan=False)) == result.to_dict()
    altered = result.provenance
    altered['normalized_flags'][0] = 0
    assert canonical_hash({k: v for k, v in altered.items() if k != 'annotation_provenance_sha256'}) != altered['annotation_provenance_sha256']
    assert 'supplied decoded text' in proof['groups_field']['hash_scope']
    assert proof['author_atom_count_independently_verified'] is proof['source_or_property_association_verified'] is False


def test_pure_parser_uses_no_eval_files_or_global_randomness(monkeypatch):
    before = random.getstate()
    denied = lambda *a, **k: (_ for _ in ()).throw(AssertionError('no eval/file access'))
    monkeypatch.setattr(builtins, 'eval', denied)
    monkeypatch.setattr(builtins, 'open', denied)
    assert parse("['0']", "['1']").exact_author_ids == (0,)
    assert random.getstate() == before


def test_long_leading_zero_token_remains_bounded_without_python_integer_digit_limit():
    result = parse("['" + '0' * 5000 + "2']", '[1]')
    assert result.groups == ((2,),) and result.exact_author_ids == (2,)


def test_missing_invalid_utf8_or_unclosed_field_never_leaks_a_parser_exception():
    for groups, flags in ((None, '[1]'), ("['0']", None), ("['\ud800']", '[1]'), ("['0'", '[1]')):
        with pytest.raises(AZAnnotationError):
            parse(groups, flags)
