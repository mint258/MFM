# Missing11 existing-container identity-input format profile

This new consumer inspects the official containers actually acquired by Alpha
jobs1884783/1884784. It does not acquire another dataset or accept the identities
of any source. The frozen acquisition/controller/identity readers remain
unchanged. Root owns all source checking, actual tests, installation, plan
materialization and CPU submission. No new controller is provided here.

The primary must be
`AlphaRoot/code/secondary_missing11_identity_format_probe_v1/run.py`:

```
ALPHA_PY -B -m secondary_missing11_identity_format_probe_v1.run --plan ABS_PLAN --startup-proof ABS_PROOF
```

Use the existing Alpha `code` PYTHONPATH. The protocol is:

- key `moleculenet_missing11_identity_format_probe_alpha_v1`;
- plan `SECONDARY_MISSING11_IDENTITY_FORMAT_PROFILE_PLAN_V1`;
- proof `SECONDARY_MISSING11_IDENTITY_FORMAT_PROFILE_STARTUP_V1`;
- stage `IDENTITY_INPUT_FORMAT_METADATA_PROBE`;
- mode `format_profile`, kind analysis, pilot=false,16CPU, no memory request,
  no exclusive/GPU request, positive whole-minute wall at most3600seconds;
- output64MiB, a fresh child of
  `AlphaRoot/artifacts/moleculenet_missing11_identity_format_probe_v1`;
- actual Alpha UID1264/node/boot/job/primary/argv/gate identity, new Root review,
  fresh target proof and all pending caps plus200GB storage reserve.

`contracts.PARAMETERS` is the exact scope literal. Runtime reuses the frozen
acquisition `Budget`: current RSS software reference48GiB, observed node
MemAvailable15% floor,1second observations, graceful check/return on STOP,
finite I/O chunks, wall drain reserve and no signals.48GiB is a software
observation reference; it is not Slurm memory allocation or a startup threshold.
The existing Budget retains32MiB output headroom for this non-acquisition mode;
the compact format reports are expected to fit well below that bound. Runtime
failure preserves completed evidence and never automatically retries a source.
Cost overrun remains REPORT_AND_CONTINUE; quality controls are unchanged.

## Exact existing inputs and source evidence

The real full receipt contains11 payloads totaling2,501,171,487bytes. Its SIDER
entry points to the original1884783 profile payload. The four TAR inventories
total25,359,956bytes and89,661physical members. Thus this stage has exactly15
data references totaling2,526,531,443bytes. These figures were obtained only from
the actual small receipt; the data bodies have not been inspected by the author.

Root constructs `data_references` in this exact order:

1. `full_receipt.sources[source_id].payload_reference` in `prior.IDS` order:
   hiv,muv,pcba,sider,tox21,toxcast,qm7b_mat,qm8_sdf,pdbbind_general,
   pdbbind_refined,pdbbind_core.
2. `full_receipt.sources[source_id].container.inventory_reference` in
   `formats.TAR_IDS` order:qm8_sdf,pdbbind_general,pdbbind_refined,pdbbind_core.

Keep all15 as pure existing path/bytes/SHA locator triples. Neither large
inventories nor payloads may enter a pre-fixture small-source hash loop. No
future output receipt receives a fake pin. The guard derives and verifies this
exact set from the real producer receipt and catalog; Root should not type SHA
values by hand or rebind to another download.

Required plan additions beyond the standard exact readonly fields:

- `acquisition_receipt_reference` and `acquisition_accounting_reference` for
  actual1884784;
- `reused_sider_receipt_reference` and `reused_sider_accounting_reference` for
  actual1884783;
- both accounting `raw_sacct_reference` objects in parent_evidence_references;
- `locator_catalog_reference` for the existing actual1094 eleven-source catalog;
- `identity_input_contract_reference`, an unchanged Alpha copy of the Root
  `docs/expansion/missing11_identity_profile_input_contract_v1.md`;
- `resource_authority_reference` and `cost_decision_reference`.

All parent refs must be approved target-verified small pins. Include the new six
files, the existing acquisition four files (`__init__`,contracts,runtime,run),
and imported `secondary_cpu_queue_v1/common.py` plus its `__init__` as source pins.
The receipt's kernel pins must match the installed four acquisition helpers.
The current guard verifies actual C0/raw accounting rather than accepting an
old proof as the new startup. Root's thin controller supplies the usual
source_target_verification, controller_evidence, actual_gate_process,
job_metadata, script_reference and storage_observation bindings. All eight new
synthetic methods run in this same allocation, after fresh admission and small
pins and before any payload or inventory body is read.

## Six CSV sources: actual rows, identity-only projection

This implementation follows Root's newer request to count every physical CSV
data record, extending the earlier contract's header-only proposal. It reads
these six streams to EOF using a byte-level RFC4180 state machine. It supports
quoted delimiters/newlines, escaped quotes and CRLF across chunks. All column
bytes must be traversed for the row grammar; only the bounded header and exact
allowlisted SMILES/opaque ID fields are UTF8-decoded. Assay/feature values are
never text-decoded, numerically decoded or persisted.

Header cap64KiB, whole-record software cap8MiB and selected-field cap1MiB prevent
unbounded buffering. Unsupported/truncated grammar remains UNKNOWN with partial
counts and an explicit incomplete-EOF flag. Blank SMILES,zero IDs,missing fields,
blank records,duplicate header names and surplus fields are counted without row
filtering. The reports keep actual literal headers, selected column indices and
blank/nonblank/invalid-UTF8 observations; no identity value, key or label is saved.

Only lower-case `smiles` is the loader-justified SMILES column. MUV/PCBA admit
`mol_id` with the loader's stated PubChem semantics; values remain uninterpreted.
HIV/SIDER have no assumed ID column. Tox21/ToxCast may observe exact opaque
`mol_id`,id,ID,name,Name columns; they receive no inferred CID semantics. All
other actual headers remain visible but are not silently admitted as IDs. These
counts are the physical all-row input universe, not unique IDs, successful
chemical parses, split membership or accepted decontaminated structures.

## Four archives: conserve metadata, bound native record interpretation

Each complete existing inventory is streamed once and fully SHA-verified with
stable before/after identity. Every ordinal is classified; counts conserve the
producer's full member and regular-byte masses. Duplicate names and nonregular
types remain observations. Filename categories distinguish native ligand SDF,
native ligand MOL2,official index basename,QM8 companion CSV,protein/pocket,
unused ligand PDB and other/unknown. A category is filename evidence, not an
accepted loader-prefix map or index/ligand mapping. Original inventories retain
all names/occurrences/SHAs; reports contain compact counts and selected locators.

The first matching SDF and first matching MOL2 member in physical inventory
order are independently examined. At most one candidate of each format is
opened per archive, and the first complete record must fit1MiB. A malformed,
missing or oversized candidate remains UNKNOWN; it is never silently replaced
by guessed chemistry or accepted as an empty identity source. Sequential gzip
access may traverse substantial compressed/decompressed bytes to reach those
members. Actual counters and elapsed time are reported, with no current whole
gzip CRC/full-member SHA claim for the bounded access.

SDF reports V2000/V3000,declared/observed native atom/bond table counts,property
names and native dimension/charge/isotope/stereo marker presence. Coordinates,
titles and property values are not decoded into output. MOL2 reports TRIPOS
sections,native declared/observed counts and explicit charge attribute markers.
Its formal charge,isotope and stereo interpretations remain UNKNOWN. No RDKit
MOL2 parser,charge guessing,3D chirality assignment or graph perception is used.
No DetermineBonds/DetermineConnectivity,protein/pocket identity,PDB proximity
bonding,largest-fragment choice,neutralization or tautomer repair is performed.

## QM7b and current integrity limits

QM7b uses `scipy.io.whosmat` only. The output contains actual variable name,
shape,class,MAT header version/endian and I/O observations. X/T/names arrays are
not materialized or inverted. An actual rank3 square X can establish only its
matrix-row count. If no direct graph-like variable names are observed, the
source remains `NO_DIRECT_SOURCE_GRAPH_IDENTITY` only for the known X/T/names
feature/property-only variable names. Additional unexplained variables remain
UNKNOWN; candidate graph-like names alone are still unverified. QM7's Z7165
adapter,QM7/QM9 row alignment and property names as
molecule IDs are forbidden. Unsupported SciPy/MAT paths remain explicit UNKNOWN.

For all11 payloads this stage explicitly reuses the producer's full disk SHA
and exact current portable device/inode/size/mtime/UID frame, with an additional
stable current ctime before/after reading. `current_full_payload_SHA_reverified`
is false. Current full SHA is performed for the four inventory bodies only.
CSV gzip EOF/CRC may be freshly proven when its full physical-row traversal
finishes; bounded archive/native reads may not be relabeled full CRC/hash.

No result from this format profile releases all-split identities,normalization,
the expansion pool,novelty,UFF/QM,training or exports. Later native-graph readers
still need their own source-level atom/bond/charge/isotope/stereo audit and
original-row/index/component/split reconciliation.
