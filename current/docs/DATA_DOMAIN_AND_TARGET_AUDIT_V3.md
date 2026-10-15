# Data Domain and Target Interface Audit v3.1

## Authoritative source

The authoritative generator inspected on the server is `/share/home/zixiao/unimol_data`. The pretraining LMDB
interface is `/share/home/zixiao/dataset/lmdb_new`. No new QM calculation is part of protocol v3.

## Domains

`molecule` records have keys `molecule_<parent-id>_<structure-id>` and originate from the UniMol-side molecular
collection. `principal` records have keys `principal_<parent-id>_<structure-id>` and originate from the
`principal_smiles.csv`/Open Babel conformer-generation path. Both paths produce up to ten structures per parent,
then use PM7 processing and the same stable XYZ/LMDB target interface.

The enriched LMDB records contain `sample_key`, original/canonical/isomeric SMILES and a registration hash.
Protocol v3 uses canonical molecular identity first and the parsed parent ID for audit evidence; a structure ID
alone is never sufficient for train/validation separation.

## V2 defect

The V2 discovery train pools are prefixes of `principal_00000001_00300000.lmdb`, while
`DISCOVERY_VALIDATION_8K_V1` is drawn from `unimol_05000001_06000000.lmdb`. Thus train is principal-only and
validation is molecule-only. Removing direct molecule overlap does not repair this domain-composition mismatch.
Existing V2 checkpoints remain historical artifacts but are not valid V3 domain-matched comparisons.

## V3 policy

`domain-matched-v3.1` uses deterministic 50:50 structure-level stratification between principal and molecule
domains for discovery pools and validation. Pools are interleaved deterministic prefixes, preserving strict
50k ⊂ 100k ⊂ 200k ⊂ 400k nesting. Validation uses the same ratio and excludes every parent molecule found in
the largest train pool. The 50:50 ratio is a project-defined discovery policy chosen to prevent either source
from dominating architecture selection; it is not claimed to reproduce a natural population prevalence.

The canonical validation manifest is `DISCOVERY_VALIDATION_DOMAIN_MATCHED_V3` and records domain, parent
molecule ID, structure ID, counts, ratios and hashes. The old validation manifest is not canonical under v3.

## Target interface

- `energy`: PM7 final heat of formation, `kcal/mol`.
- `y`: stored MOPAC net atomic charge, `e`; not labeled Mulliken because the generator does not request `MULLIK`.
- `pos`: final/selected Cartesian coordinates, Å.
- `rdkit_graph_desc`: 31 descriptor-specific values with per-value mask.
- RDKit node descriptors: regression, binary and multiclass fields with a shared node-validity mask.
- bonds: positive bond indices/order plus deterministically stored negative-pair candidates.

The current compatibility loader can synthesize missing defaults. Domain and target audits therefore inspect
raw, non-normalized LMDB items when determining whether a field was originally present.
