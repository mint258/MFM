"""Fixed additive fragment descriptors shared by Common/PubChem/R/N."""
from __future__ import annotations
from functools import lru_cache
import math
from pathlib import Path
import struct
from .io import need, reference

FUNCTIONS = (
    'fr_Al_OH', 'fr_Ar_OH', 'fr_COO', 'fr_aldehyde', 'fr_ketone', 'fr_ester',
    'fr_ether', 'fr_amide', 'fr_NH0', 'fr_NH1', 'fr_NH2', 'fr_nitro',
    'fr_nitrile', 'fr_halogen', 'fr_alkyl_halide', 'fr_Ar_N', 'fr_Nhpyrrole',
    'fr_SH', 'fr_sulfide', 'fr_sulfonamd', 'fr_sulfone', 'fr_phos_acid',
    'fr_phos_ester', 'fr_urea', 'fr_lactam', 'fr_lactone', 'fr_epoxide', 'fr_Imine',
)
NUMERIC_FIELDS = ('heavy_atoms', 'molecular_weight_Da', 'rings', 'aromatic_rings', 'isotopic_atoms', 'stereocenters', 'logp', 'tpsa_A2', 'hbd', 'hba', 'rotatable_bonds')
STRUCTURE_FIELDS = ('full_key', 'elements', 'non_h_composition', 'element_combination', 'generic_murcko', 'generic_ring_systems')


@lru_cache(maxsize=1)
def modules():
    from rdkit import Chem, RDConfig, rdBase
    from rdkit.Chem import Fragments
    need(rdBase.rdkitVersion == '2025.09.5', 'Distribution chemistry must match v1 RDKit2025.09.5')
    definitions = []
    for name in FUNCTIONS:
        fn = getattr(Fragments, name)
        patterns = [value for value in (fn.__defaults__ or ()) if hasattr(value, 'GetNumAtoms')]
        need(len(patterns) == 1, 'Cannot recover installed fragment SMARTS: ' + name)
        definitions.append({'name': name, 'SMARTS': Chem.MolToSmarts(patterns[0]), 'count_unique': True, 'description': fn.__doc__})
    data = Path(RDConfig.RDDataDir) / 'FragmentDescriptors.csv'
    recipe = {'schema': 'EXPANSION_FUNCTIONAL_GROUP_RECIPE_V1', 'rdkit': rdBase.rdkitVersion, 'definitions': definitions, 'fragments_python': reference(Fragments.__file__), 'fragment_definitions': reference(data), 'overlap_policy': 'Definitions overlap; prevalence is not mutually exclusive', 'selection_or_screening_decisions_changed': False}
    return Chem, Fragments, recipe


def recipe():
    return modules()[2]


def same_field(a, b):
    if type(a) is float and type(b) is float:
        return struct.pack('>d', a) == struct.pack('>d', b)
    return a == b


def enrich_batch(task):
    records, identity_column, allow_descriptor_completion = task
    Chem, Fragments, unused = modules()
    output = []
    for row in records:
        need(row.get(identity_column) is not None and row.get('full_key'), 'Original member identity and full InChIKey required')
        # Use the same source spelling bound to the original feature result.
        # Native historical identity is not a new graph admission criterion.
        smiles = row.get('source_smiles') or row.get('isomeric_smiles')
        need(isinstance(smiles, str) and smiles, 'Exact source structure required for functional groups')
        molecule = Chem.MolFromSmiles(smiles)
        need(molecule is not None, 'Original bound descriptor structure must parse')
        missing = [name for name in (*NUMERIC_FIELDS, *STRUCTURE_FIELDS) if name not in row]
        result = dict(row)
        if missing:
            need(allow_descriptor_completion, 'Complete original descriptors missing: ' + ','.join(missing))
            from ..features_legacy_compatible_v2 import features_candidate
            # Identifiers are pass-through only. Common has no PubChem CID;
            # None is retained internally and no fake CID is emitted.
            fresh = features_candidate(row.get('cid'), smiles, row.get('ordinal'))
            need(fresh.get('reasons') == [] and fresh['full_key'] == row['full_key'], 'Additive Common descriptor extraction failed; no silent molecule removal')
            for name in (*NUMERIC_FIELDS, *STRUCTURE_FIELDS, 'ecfp4_2048_hex'):
                if name in row:
                    need(same_field(row[name], fresh[name]), 'Existing original descriptor cannot change: ' + name)
                elif name in fresh:
                    result[name] = fresh[name]
        for name in NUMERIC_FIELDS:
            need(type(result[name]) in (int, float) and math.isfinite(result[name]), 'Finite original descriptor required: ' + name)
        result['functional_groups'] = {name: int(getattr(Fragments, name)(molecule, countUnique=True)) for name in FUNCTIONS}
        need('functional_groups' not in row or row['functional_groups'] == result['functional_groups'], 'Existing enrichment differs from fixed recipe')
        output.append(result)
    return output
