# Alpha MoleculeNet native4: all physical context, bounded SDF keys

Source only. No tests, native input reads, SSH, submissions, graph computations,
Root approval or deployment were performed by the child author. Existing Drugs8,
CSV6, QM7/QM9 and all original792 source/results remain frozen.

The exact scope is QM8 and PDBBind core/general/refined, all four TAR physical
members, native SDF/MOL2 records and identity relationships; then per source at
most1000 SDF records selected uniformly from this job's actual physical N.
Actual792 only observed bounded first native records. It did not close all
payload/current member SHA/CRC, full record N or identity mapping. Its observed
ligand file counts195/12800/4852 are physical inventory facts, not valid molecule
counts or permission to crop core to the author's193. Protein/pocket bodies are
fully hashed but never treated as small-molecule identities. Unknown extra
SDF/MOL2 members also remain physical records with unknown mapping.

Primary frozen DeepChem commit455d07f3e17e880a4d980b5b0365e4a02b417e14:

- [QM8 loader](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/qm8_datasets.py)
  identifies the SDF/companion relationship and warns about source rows lost by
  sanitization. No failed row is dropped here.
- [SDF reader](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/utils/data_utils.py)
  uses sanitize=True/removeHs=False/strictParsing=False for QM8 and physical
  ordinal alignment with its companion. We preserve literal column1 IDs and
  native titles separately, never guess a title-to-ID transformation.
- [PDBBind loader](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/pdbbind_datasets.py)
  specifies the exact index paths, literal core pdb_id or noncomment first4
  characters, and ligand SDF files.
- [General molecule reader](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/utils/rdkit_utils.py)
  can call PDBFixer, add H, calculate charges and take only the first SDF object.
  This new PDB source-only seam is explicitly different: sanitize=True,
  removeHs=False, strictParsing=True, no repair and all records retained.
- [RDKit2025.09.5 MOL2 parser](https://github.com/rdkit/rdkit/blob/Release_2025_09_5/Code/GraphMol/FileParsers/Mol2FileParser.cpp)
  establishes the element before the atom-type dot, but also contains charge
  guessing and graph cleanup. We do not call that parser. Only exact native
  element symbols are counted; pseudo/query/unknown symbols make composition
  UNKNOWN rather than being discarded. Partial charges never imply formal charge.

## Consumer contract and Root preparation

Alpha flat package `ROOT/code/secondary_moleculenet_native4_identity_v1`, ordinary
PYTHONPATH `ROOT/code`. ROOT is /gfshome/alpha/codex_data_v1_20261026, endpoint
218.192.171.238:22, UID1264. Main UID1278 proofs are rejected.

KEY moleculenet_native4_identity_profile_alpha_v1; plan/proof schemas are
SECONDARY_MOLECULENET_NATIVE4_IDENTITY_PROFILE_PLAN_V1 and
SECONDARY_MOLECULENET_NATIVE4_IDENTITY_PROFILE_STARTUP_V1. Module is
secondary_moleculenet_native4_identity_v1.run, stage and literal scope parameters
are exported from contracts.py. Resources: analysis, pilot=true,
performance_profile=true,16CPU/no requested memory/exclusive/GPU,14400s,2GiB.
Root's existing independent Alpha gate/controller requires a new thin whitelist
adapter; this package does not create another queue or submit anything.

Root request needs actual node/python/fresh output and control locations, current
resource/cost refs, scope7 storage authority/reservation, format_authority_reference
to installed authority792.json, actual792 accounting/raw, and actual1884785
kernel_profile_receipt_reference/accounting/raw. Include all792 receipt/plan/proof/
8-fixture refs and four native reports from authority792.json, plus1884785 plan/
proof and all transitive source pins. The frozen_identity_source_references must
match actual1884785's projection/common exactly. All8 new files, existing B4,
CSV6 runtime/journal/guard dependencies, acquisition source/TAR helpers, frozen
format helper and base queue imports must be current source pins. Runtime checks
every actually imported secondary_* source belongs to Alpha/code and is pinned.

DATA is exactly four original payload triples followed by their four complete
inventory triples, in contracts.IDS order, derived from authority792.json. These
are producer locators, never bodies hashed/read on login. Root review schema is
EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1 and needs
source_only_PDB_seam_and_MOL2_unknowns_reviewed=true, full_or_pool_release=false,
and exact scope/argv/parents/sources/resources. Use the existing8-argv form:

```
PY -B -m secondary_moleculenet_native4_identity_v1.run --plan PLAN --startup-proof PROOF
```

## Read/write and unknown semantics

Only the new3 synthetic methods run before DATA. They cover record/title/ID/CSV
grammar, native compositions/MOL2 charge and pseudo-atom boundaries, actual-N
selection, and the two explicit SDF reader seams. Original B3 are not rerun:
their actual1884785 C0/fixtures and same frozen source pins are required.792's
format8 PASS is separately required and never mislabelled as B3.

The consumer currently rehashes all8 inputs, reads every physical TAR member with
declared size/member SHA validation and complete gzip EOF/CRC, and rechecks all
input SHA/frames before keys. Native bytes and identity rows are fsynced before
new relationship SQL. A single retained raw blob avoids many small files.
The derivative SQL uses memory rollback/temp journal to avoid transient SQLite
sidecar deletion races in the unchanged CSV6 Budget monitor; source/result JSONL
is the durable authority before that derivative index.

All native titles, exact ID/SMILES variants, physical member/record ordinals,
all conformers and cross-component memberships remain. Native composition calls
the original frozen native_composition object on complete original atom tables;
coordinates, partial-charge values and assay values are not decoded for it.
No values are invented for unknown or unreadable atoms. Record software limits
are technical STOP/HOLD, never molecular/chemical exclusion.

After complete physical projection, actual per-source SDF N and selected ordinals
are generated and durably stored in this job. Each selected full source row is
durable before key dispatch; results are durable before SQL/unions.16 workers and
32 pending tasks are bounded. Original CSV6 Budget/JSONL helpers are directly
reused, with current RSS/MemAvailable, registered-cap/physical free200GB checks,
natural drain and no signals;48GiB is an algorithm reference, not requested RAM.

MOL2 graph/formal charge/stereo remain UNKNOWN. Selected failed SDF graphs retain
unknown plus actual atom-table composition when readable. Native and all present
SMILES keys are kept in union. PDB IDs union every observed conformer and all
three original component memberships without assuming same ID means same graph.
Unknown path IDs stay separate physical entities. Unselected SDF is
NOT_YET_EXAMINED, never graph-unavailable. Unresolved variant composition is
separate evidence and does not automatically become a broad exclusion for an
entity with known keys. Full identity, global decontamination, pool or full keys
are never released by this profile; follow-up requires actual profile/cost/
unknown review. All actual parent costs, including failures, stay pending Root's
terminal accounting. There are no new QM/UFF/network calls.
