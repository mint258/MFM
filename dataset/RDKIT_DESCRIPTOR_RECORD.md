# RDKit Descriptor Record

This file records the RDKit-derived labels planned for the next LMDB rebuild.
It is intended as a stable backup of what to store, why each item is included,
and how each item is expected to be used during pretraining.

## Scope

- These labels are stored as auxiliary supervision targets, not as model inputs.
- Graph-level descriptors are fixed-size molecule labels.
- Node-level labels are atom-aligned chemical-state labels derived from the
  final RDKit `Mol` whose atom order matches the 3D coordinate order.
- Samples that fail RDKit reconstruction/validation should keep the original
  3D tasks and set RDKit-derived label masks to `0`.

## Status

- Selected for LMDB rebuild: `Yes`
- Mordred in first rebuild: `No`
- Training policy: store all labels once, enable only a subset during early
  experiments if runtime or task conflict becomes a problem.

## Graph-Level Descriptors

| Name | RDKit family | Type | Purpose |
| --- | --- | --- | --- |
| `MolLogP` | Crippen | regression | Global lipophilicity summary; adds coarse physicochemical semantics not directly covered by energy or geometry. |
| `MolMR` | Crippen | regression | Global molar refractivity proxy; captures polarizability and size-related chemistry. |
| `TPSA` | MolSurf | regression | Polar surface area; useful for polarity and heteroatom environment beyond raw element identity. |
| `LabuteASA` | MolSurf | regression | Approximate accessible surface area; complements 3D geometry with chemically aware surface information. |
| `ExactMolWt` | Descriptors | regression | Exact molecular mass; compact composition summary. |
| `NumValenceElectrons` | Descriptors | regression | Total valence-electron count; global electronic budget. |
| `HeavyAtomCount` | Lipinski | regression | Molecule size without hydrogens; simple complexity/scale prior. |
| `NumHeteroatoms` | Lipinski | regression | Counts non-C/H atoms; captures polarity and functional diversity. |
| `NumHAcceptors` | Lipinski | regression | Global hydrogen-bond acceptor count; strong chemical-function summary. |
| `NumHDonors` | Lipinski | regression | Global hydrogen-bond donor count; complements acceptor semantics. |
| `NumRotatableBonds` | Lipinski | regression | Flexibility summary; not redundant with static 3D coordinates. |
| `FractionCSP3` | Lipinski | regression | Measures saturation and local 3D character from bond topology. |
| `RingCount` | Lipinski | regression | Overall ring richness; useful topology prior. |
| `NumAromaticRings` | Lipinski | regression | Aromatic system count; important chemistry not directly supervised now. |
| `NumAliphaticRings` | Lipinski | regression | Non-aromatic ring count; complements aromatic ring signal. |
| `NumSaturatedRings` | Lipinski | regression | Saturated ring count; helps distinguish ring chemistry families. |
| `NumHeterocycles` | Lipinski | regression | Heterocycle count; strong medicinal-chemistry prior. |
| `NumBridgeheadAtoms` | Lipinski | regression | Captures rigid bridged topology motifs. |
| `NumSpiroAtoms` | Lipinski | regression | Captures spiro topology motifs. |
| `NumAmideBonds` | Lipinski | regression | Simple functional-group summary with strong chemical meaning. |
| `BertzCT` | GraphDescriptors | regression | Topological complexity score; useful global structural summary. |
| `HallKierAlpha` | GraphDescriptors | regression | Encodes atom-type/topology corrections for shape/connectivity complexity. |
| `Kappa1` | GraphDescriptors | regression | Molecular shape/topology index; low-cost global topology summary. |
| `Kappa2` | GraphDescriptors | regression | Same family as `Kappa1`, adds complementary shape sensitivity. |
| `Kappa3` | GraphDescriptors | regression | Same family as `Kappa1`, adds complementary shape sensitivity. |
| `RadiusOfGyration` | Descriptors3D | regression | Global compactness from 3D coordinates; low-dimensional shape supervision. |
| `NPR1` | Descriptors3D | regression | Normalized principal moment ratio; coarse 3D shape class indicator. |
| `NPR2` | Descriptors3D | regression | Complements `NPR1` for rod/disc/sphere-like shape discrimination. |
| `Asphericity` | Descriptors3D | regression | Measures deviation from spherical shape. |
| `Eccentricity` | Descriptors3D | regression | Measures elongation/anisotropy of the 3D shape. |
| `PBF` | Descriptors3D | regression | Plane-of-best-fit score; good low-cost descriptor for planarity. |

## Node-Level Labels

Unless explicitly needed otherwise, these labels should be generated for heavy
atoms and masked on atoms where RDKit semantics are unavailable or unreliable.

| Name | Type | Suggested encoding | Purpose |
| --- | --- | --- | --- |
| `formal_charge` | node-level | integer class or small-range regression | Local formal charge state; useful chemistry signal but should be low-weight because it partially overlaps with partial charge prediction. |
| `hybridization` | node-level | multiclass | Supervises local bonding/orbital state (`sp`, `sp2`, `sp3`, etc.). |
| `is_aromatic` | node-level | binary | Supervises aromatic participation, which is absent from the current four tasks. |
| `is_in_ring` | node-level | binary | Supervises whether an atom belongs to any ring system. |
| `min_ring_size` | node-level | multiclass | Encodes smallest ring membership (`none`, `3`, `4`, `5`, `6`, `7+`). |
| `total_degree` | node-level | multiclass | Captures local connectivity count in the 2D graph. |
| `total_num_Hs` | node-level | multiclass | Captures local hydrogen substitution pattern. |
| `total_valence` | node-level | multiclass | Captures local valence environment beyond element identity. |
| `donor` | node-level | binary | Marks hydrogen-bond donor functionality at atom level. |
| `acceptor` | node-level | binary | Marks hydrogen-bond acceptor functionality at atom level. |
| `EState_atom_type` | node-level | multiclass | Encodes RDKit EState atom-type semantics; compact local environment label. |
| `EState_index` | node-level | regression | Continuous electrotopological summary of local topological/electronic context. |
| `chiral_tag` | node-level | multiclass | Encodes tetrahedral/chiral state when available. |
| `CIP_code` | node-level | multiclass | Encodes `R` / `S` / `None` for stereocenters with assigned CIP labels. |

## Required RDKit Metadata to Store Alongside Labels

These are not descriptors, but they are required to make the descriptor pack
usable, auditable, and extensible.

| Name | Purpose |
| --- | --- |
| `canonical_smiles` | Canonical 2D structure reference for verification and downstream processing. |
| `isomeric_smiles` | Preserves stereochemistry when available; preferred template string. |
| `total_charge` | Needed to stabilize bond perception for ionic systems. |
| `rdkit_status` | Marks success/failure/ambiguous outcome of RDKit reconstruction. |
| `rdkit_fail_reason` | Human-readable failure reason for audits and filtering. |
| `graph_desc_mask` | Per-descriptor mask in case a subset fails. |
| `node_rdkit_mask` | Atom-level mask for RDKit-derived node labels. |
| `canonical_smiles_from_rdkit` | Optional post-rebuild verification output. |
| `registration_hash` | Optional stronger identity check than direct SMILES string comparison. |
| `match_is_unique` | Records whether graph alignment was unique or ambiguous. |

## Explicitly Deferred or Excluded Families

These are intentionally not part of the first rebuild.

- `Mordred` full descriptor set
- `PEOE_VSA*`
- `BCUT2D`
- `AUTOCORR3D`
- `GETAWAY`
- `MORSE`
- `RDF`
- `WHIM`
- `USR`
- `USRCAT`
- `QED`
- full `Fragments` family

Reasons:

- too much overlap with existing charge/geometry supervision,
- high dimensionality,
- higher preprocessing burden,
- lower interpretability,
- or low expected marginal value for the current multitask pretraining setup.

## Operational Notes

- Build the final RDKit `Mol` so that RDKit atom index equals 3D atom index.
- Use 3D coordinates to recover connectivity, then use stored `SMILES` as the
  bond-order/aromaticity template.
- Validate aggressively; prefer masking uncertain samples over accepting
  ambiguous matches.
- Store all selected labels in LMDB once, but do not assume all of them must be
  turned on in the first training run.
