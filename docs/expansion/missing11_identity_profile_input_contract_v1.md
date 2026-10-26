# Missing11: next identity input contract

Status: `SOURCE_PROPOSAL_NO_READY_PLAN_OR_IDENTITY_ACCEPTANCE`. Prepared only
from small catalog/source metadata and official text. No Alpha payload,
container-inventory JSONL body, Parquet, SQLite or molecular record was read on
login/Windows; no Python, AST, tests, SSH, Slurm or Git was executed. This file
adds no controller/guard and changes no registered source.

Root reports actual Alpha1884783 profile C0/10s/160coresec and1884784 full
C0/338s/5408coresec, all11 containers complete,2501171487 compressed bytes,
with sider reused. Their actual receipt/accounting/file triples must be supplied
by Root, not inferred from this report. These prove container integrity; they
do not prove original identity-row counts, usable keys, all-split coverage or
successful chemical normalization.

## Exact original identity sources

The metadata version is DeepChem
`455d07f3e17e880a4d980b5b0365e4a02b417e14`. Source references below identify
loader text, not the newly downloaded payload version or its current SHA.

| Physical source(s) | Identity fields justified by official loader | Source ID / coverage boundary |
| --- | --- | --- |
| hiv | `smiles` | No native unique ID is established by this loader; retain original row ordinal plus source pin. Do not decode activity/HIV_active. |
| muv | `smiles`, `mol_id` | Preserve opaque original mol_id and row ordinal; the loader documents mol_id as PubChem CID. Do not filter any assay class/missing target. |
| pcba | `smiles`, `mol_id` | Same physical-record rule; the default loader selects pcba.csv.gz, not another PCBA variant. |
| sider | `smiles` | Reuse1884783 payload. Any additional identifier must first be established by actual header metadata; do not assume a CID column. |
| tox21 | `smiles` | Preserve all physical rows. If actual header has an identifier, retain its literal name as an opaque source ID; do not invent PubChem semantics. |
| toxcast | `smiles` | Same rule; no assay/feature-column decoding, target completeness filter or featurizer-success filter. |
| qm8_sdf | Loader expects `qm8.sdf`; companion `qm8.sdf.csv` has a source-ID column | Actual member names/occurrences must be proven. Keep every SDF boundary, including unparseable structures, and all original structure/SMILES/key variants. Project only the companion's original ID column to prove mapping; do not read energy/property values. |
| qm7b_mat | Current loader only declares the qm7b.mat URL | Inspect actual variable name/shape/class first. Do not reuse QM7's Z7165 adapter or assume QM7b contains Z/R/graph/SMILES. |
| pdbbind_general, pdbbind_refined, pdbbind_core | Loader uses each complex's native `PDBID_ligand.sdf` and a source index | Keep component/version + original PDB code + native member path/occurrence. Read SDF native atom/bond graph; include any actual ligand MOL2 as a separately attributed variant. Proteins/pockets are excluded from small-molecule identity normalization, not from member accounting. |

Official loader references:
[HIV](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/hiv_datasets.py),
[MUV](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/muv_datasets.py),
[PCBA](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/pcba_datasets.py),
[SIDER](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/sider_datasets.py),
[Tox21](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/tox21_datasets.py),
[ToxCast](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/toxcast_datasets.py),
[QM8](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/qm8_datasets.py),
[QM7/QM7b locator](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/qm7_datasets.py),
[PDBbind](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/pdbbind_datasets.py).

Do not run these training loaders: they featurize, split, transform and can
drop invalid structures. Raw originals are the conservative all-split superset.
Prove source IDs/ordinals and the split-input universe from pinned loader text;
when real split membership files exist, project only their IDs/roles and prove
subset/union. Do not generate stratified splits using labels or make up
train/valid/test assignments. Preserve missing identity, duplicate source IDs,
blank SMILES, parse failures and original class/role provenance as observations.

## QM7b: distinguish source facts from recoverable identity

The [original Quantum-Machine release description](https://www.quantum-machine.org/datasets/)
describes QM7b as X(7211x23x23) Coulomb matrices, T(7211x14) properties, and
14 property names. It does not describe a native graph/SMILES/Z/R array.
The Z/R paragraph in the current DeepChem file describes QM7, not QM7b.
The [historical official DeepChem MAT loader](https://github.com/deepchem/deepchem/blob/2.1.0/deepchem/molnet/load_function/qm7_datasets.py)
uses QM7b X/T with generated IDs; that is not a molecular graph mapping.

Run only a CPU metadata inventory such as scipy.io.whosmat: name, shape,
MATLAB class, endian/version, complete file pin and current frame. Do not
materialize X/T/names values. If the physical container has only these fields,
record its actual matrix-row universe and `NO_DIRECT_SOURCE_GRAPH_IDENTITY` for
each ordinal. Do not infer Z/composition/bonds from Coulomb features, assume
row alignment with QM7/QM9, or relabel the property names as molecule IDs.
An official explicit row-to-structure association would be separately needed;
none has been proven here. This is a real unresolved source limitation,
not permission to drop QM7b or call its identities decontaminated. No author
contact, alternate derived dataset or additional download is authorized here.

## PDBbind / QM8: original bonds and variants

PDBbind's pinned loader locates these three independent physical components:

| Component | Loader index locator | Loader ligand locator pattern |
| --- | --- | --- |
| other_PL2019 | v2019-other-PL/index/INDEX_general_PL_data.2019 | v2019-other-PL/PDBID/PDBID_ligand.sdf |
| refined2019 | refined-set/index/INDEX_refined_data.2019 | refined-set/PDBID/PDBID_ligand.sdf |
| core2013 | v2013-core/pdbbind_v2013_core.csv | v2013-core/PDBID/PDBID_ligand.sdf |

Those are loader locators, not yet observed archive names. First reconcile the
real members with an explicit Root-reviewed prefix map; do not silently guess
another directory. Count all index IDs using only the original four-character
PDB code or core CSV pdb_id column. Skip affinity/resolution/reference values.
Conserve index IDs, ligand members, duplicates, missing ligands, extra ligands
and component overlap. Retain extra native ligand files conservatively instead
of dropping them because an index/label is absent. Each retained physical variant
keeps component, member ordinal/name/full SHA, source record ordinal and errors.
Do not collapse components merely because their PDB code repeats.

For QM8, count complete SDF records independently of RDKit successes. Reconcile
the actual title/source-ID field with the companion CSV first ID column; field
spelling, extra IDs and missing records remain pending actual CPU observation.
Do not substitute a sanitized loader's returned subset. Preserve each original
native SMILES/InChI/key property only after its exact property name is observed
and allowlisted; do not decode arbitrary property values.

Native SDF/MOL2 atom/bond tables are the source of graph connectivity. No
distance-based DetermineBonds/DetermineConnectivity, PDB proximity bonding,
XYZ graph perception, largest-fragment choice, neutralization or tautomer
repair is allowed. Frozen full_keys/source_smiles_keys/wp5_key and RDKit2025.09.5
remain the later key policy for actual SMILES variants. A new native-graph
reader needs an explicit small profile and source-level atom/bond/charge/
isotope/stereo audit; it cannot claim to be the old SMILES function unchanged.

There is a concrete MOL2 caution in the
[RDKit2025.09.5 wrapper](https://github.com/rdkit/rdkit/blob/Release_2025_09_5/Code/GraphMol/Wrap/rdmolfiles.cpp)
and [MOL2 parser](https://github.com/rdkit/rdkit/blob/Release_2025_09_5/Code/GraphMol/FileParsers/Mol2FileParser.cpp):
cleanup/removeHs default true, missing explicit UNITY charge attributes cause
formal-charge guessing even with cleanupSubstructures=false, and chirality is
assigned from3D. Therefore do not label a default MOL2 call pure native
charge/stereo passthrough. Prefer the loader's SDF native bond record, retain
MOL2 independently, and report its charge/stereo interpretation or uncertainty.
No guessed MOL2 key may silently replace a failed SDF variant. Coordinate
parsing is not permission for new connectivity perception or chemistry edits.

## Minimal next CPU format-probe metadata

No executable is added by this proposal. Suggested next exact key:
`moleculenet_missing11_identity_format_probe_alpha_v1`, stage
`IDENTITY_INPUT_FORMAT_METADATA_PROBE`, analysis/pilotfalse/CPU16/no_mem,
wall<=3600s whole minutes, whole output64MiB, fresh independent Alpha proof.
Reuse Root's existing thin readonly adapter and real startup guard; do not
create another controller. A future eight-argument primary may be:

```text
ALPHA_PY -B -m secondary_missing11_identity_format_probe_v1.run --plan ABS_PLAN --startup-proof ABS_PROOF
```

Required actual small parents:1884784 receipt/accounting/raw sacct, reused
1884783 receipt/accounting, current11-source catalog/loader references, and
actual four-kernel source pins. Root maps source_id to the actual payload
triple from the receipts, and maps the four TAR_GZIP source_ids to their actual
container-inventory JSONL triples. Flat data_references contains the11 payloads
plus those four inventories, never fake future hashes. Large inventories stay
CPU-only data; they must not enter a login small-source hash loop. Root provides
new output/proof paths, exact sources, review, current UID/node/boot/job/argv,
default-memory authority, REPORT_AND_CONTINUE cost authority and all-cap200GB
storage proof. The probe makes no payload acquisition or normalization request.

The bounded probe would produce only:

1. Six CSV headers: complete RFC4180 header within64KiB decoded bytes per source,
   literal column names/count, exact identity/ID column admission or missing
   schema fact. Persist no data row or assay value. Gzip may be read only this
   bounded prefix; claim no new complete CRC for this bounded probe.
2. Full streaming inventory-metadata classification for four TAR sources:
   names/occurrence ordinal/type/bytes/member SHA; counts by native ligand SDF,
   ligand MOL2, expected index, protein/pocket, other/unknown. Emit a compact
   selected-member locator list, not all large JSONL into a small receipt.
   Missing/duplicate/unknown patterns remain explicit.
3. At most the first complete native SDF record and first complete MOL2 record
   per relevant archive, each<=1MiB, selected by inventory physical order.
   Persist only format/V2000-V3000 or TRIPOS section markers, declared and
   observed atom/bond counts, native property names, dimension/stereo/charge/
   isotope marker presence and source-member pins. No coordinates, molecular
   row values, properties, labels or graph keys in this format-only output.
   Sequential compressed access can still read substantial archive bytes to
   reach selected members; measure actual compressed/decompressed I/O/time.
4. QM7b whosmat variable metadata only, with explicit direct-identity present/
   absent/unknown decision. No loadmat(X/T), feature inversion or graph call.

CPU verifies the current inventory SHA and stable file identity. For payloads,
Root may choose complete current SHA revalidation, or explicitly reuse producer
full SHA plus portable inode/size/mtime/UID and current before/after frame for
this bounded format probe. The latter must report `current_full_payload_SHA_reverified=false`;
bounded prefix/member checks cannot be relabeled a full rehash. No symlink,
whole-output/invalid-metric/hard-wall bypass or signals. Completed metadata
observations are durable; an unsupported/partial format is UNKNOWN, not a
successful empty identity source.

## Existing primitives and later implementation boundary

`identity_v2/readers_v2.py:csv_identity_rows` is a useful projection pattern,
but its frozen CSV_COLUMNS omits lower-case smiles/mol_id; using it directly
would reject these sources. Add a new explicit-reader allowlist in a new
namespace after actual headers; do not edit/widen the frozen reader in place.
`qm7_native_z` is deliberately pinned to QM7 source7165 and must not be called
on QM7b. Existing qm9 token parsing is not an SDF/PDBbind parser.

Reuse original `projection_v2.full_keys`, `source_smiles_keys`,
`rdkit_identity_modules` and `common.wp5_key` only for their real functions.
Preserve all source variants and errors, stable row IDs and raw graph refs,
write fresh external Parquet/SQLite identity-only outputs, and independently
reconcile original rows, missing identities and all split/component unions.
The format probe does not establish these counts or authorize a full export.
The next separately reviewed profile must test the new CSV/native-graph
adapters and unknown paths before a whole-source identity stage. Downloaded
containers, B's COCONUT profile and local1192 remain separate evidence chains;
none releases the pool, novelty/UFF/QM/training or global decontamination.
