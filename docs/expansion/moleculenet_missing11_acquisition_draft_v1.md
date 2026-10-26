# Eleven missing official MoleculeNet source containers

Draft for Root review; no Python, AST, tests, network, data-body read, SSH,
Slurm or Git execution. No READY plan or future payload SHA is manufactured.
The existing local closure1192 remains valid for its explicit source union;
this stage does not normalize or release any identity/pool.

The machine-readable table is
`configs/data_v1/expansion/moleculenet_missing11_actual_head_locators_v1.json`.
Its 11 HEAD observations were individually read back and matched to the
registered1094 small-file pins. All were HTTP200. Total Content-Length is
2,501,171,487B, not an expanded/output budget or a payload SHA proof.

| Source ID | Frozen official URL | Actual1094 compressed bytes |
| --- | --- | ---: |
| hiv | https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/HIV.csv | 2193844 |
| muv | https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/muv.csv.gz | 1755511 |
| pcba | https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/pcba.csv.gz | 15449358 |
| sider | https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/sider.csv.gz | 34759 |
| tox21 | https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/tox21.csv.gz | 122925 |
| toxcast | https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/toxcast_data.csv.gz | 404948 |
| qm7b_mat | https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/qm7b.mat | 16067096 |
| qm8_sdf | https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/gdb8.tar.gz | 8764619 |
| pdbbind_general | https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/pdbbindv2019/pdbbind_v2019_other_PL.tar.gz | 1759178739 |
| pdbbind_refined | https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/pdbbindv2019/pdbbind_v2019_refined.tar.gz | 651882567 |
| pdbbind_core | https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/pdbbind_v2013_core_set.tar.gz | 45317121 |

Official loader metadata is pinned at DeepChem
`455d07f3e17e880a4d980b5b0365e4a02b417e14`; links and exact HEAD ETag/Last-Modified
and per-HEAD SHA pins are in the JSON. No nine-dataset union is reduced: PDBbind
has three distinct physical components. QM8's SDF container suffices as the next
raw source; its CSV companion is not an additional mandatory download here.
MAT headers do not establish that graph identity is extractable. Do not derive
a graph from numerical arrays or coordinates.

Reuse six existing local CSVs (BACE/BBBP/ClinTox/ESOL/FreeSolv/Lipophilicity),
QM7 original Z7165, and all133885 original QM9 records. Their version/ID mapping
and unresolved rows remain explicit. Do not download their companions merely
because the catalog lists them. COCONUT CSV/SQL already exist and are excluded.

Other missing families are separate requests: TDC file4426004, containing44
logical train_val/test members for22 endpoints, returned403 for the original
redirected HEAD. Both MARCEL official Drive landing URLs returned curl28
timeout. These observations prove neither a successful GET nor a permanent
denial of a payload GET. Root can review a new ordinary Alpha observation of
the same official URLs; there is no alternate mirror, authentication bypass,
author contact, repeated retry or TDC/Drive download in this11-source stage.

## Exact new two-phase protocol

Source package: `workflows/expansion/secondary_external_sources_acquisition_v1/`
(`__init__.py`, `contracts.py`, `runtime.py`, `run.py`). Alpha deploys the exact
four bytes as `Alpha/code/secondary_external_sources_acquisition_v1/`. Reuse the
existing Alpha base common/gate/probe/storage helpers and Root's new exact
adapter; do not alter a registered queue or create another queue.

Producer/scope key: `moleculenet_missing11_acquisition_alpha_v1`.
Plan/proof: `SECONDARY_EXTERNAL_SOURCE_ACQUISITION_PLAN_V1` /
`SECONDARY_EXTERNAL_SOURCE_ACQUISITION_STARTUP_V1`.

```text
ALPHA_PY -B -m secondary_external_sources_acquisition_v1.run --plan ABS_PLAN --startup-proof ABS_PROOF
```

Only Root materializes the plan/review. All common exact Alpha fields follow
the existing A contract: endpoint218.192.171.238:22/UID1264, run_root, node,
CPU16, default unspecified memory, no explicit memory/exclusive/GPU,
real primary/full argv/boot/job/exec-gate identity, <=120s fresh proof and
storage with all outstanding caps plus200GB. Stage-specific fields:

- `mode=profile`: stage
  `OFFICIAL_MOLECULENET11_DOWNLOAD_AND_CONTAINER_INVENTORY_PROFILE`, pilottrue,
  wall<=3600s whole minute, output64MiB, data_references=[]; only sider GET.
- `mode=full`: corresponding `_FULL`, pilotfalse, wall<=48h whole minute,
  output16GiB. Require an actual same-four-kernel profile C0 and raw parent
  accounting, plus Root review `actual_profile_cost_and_container_path_reviewed`.
  GET only the other10 sources. `data_references` is the one exact sider
  profile payload triple; CPU rehashes and portable-fstat checks it, then
  references its prior container evidence without a second GET.

`scope_parameters` must equal `contracts.parameters(mode)` exactly. Small
sources include the actual locator catalog copy, all11 original HEAD JSON
copies and original1094 receipt (same bytes/SHA; keep original paths inside
those metadata bytes), current four-code kernel, base helper imports,
resource/cost authorities and actual new adapter sources. Fields:
`locator_catalog_reference`, `head_receipt_reference`,
`head_observation_references=[{source_id,reference}]`,
`resource_authority_reference`, `cost_decision_reference`. Full additionally
binds `accepted_profile_receipt_reference` and
`accepted_profile_accounting_reference` in parent_evidence_references.

Each source uses one ordinary official HTTPS GET, no retries or redirects,
with original HEAD If-Match/If-Unmodified-Since. Normal proxy environment,
including existing authenticated proxies, is inherited; credentials, cookies,
raw exception messages and proxy settings are not persisted. Status/length/
ETag/Last-Modified must match the actual HEAD. A changed version/403/429/timeout
is preserved; stop dispatch, keep partials, do not find an alternate route.
At most16 threads are available (only1/10 new source units in these phases),
and actual nonempty thread IDs are reported without claiming16 active workers.

Download writes fresh owned payloads without assembly copies or deletion.
CPU independently hashes actual disk bytes after complete HTTP EOF. Gzip reads
to true EOF/CRC, tar members are streamed and independently hashed/inventoried
without extraction, and full stream bytes/SHA are counted. CSV records/values
are not decoded. MAT reads only128 header bytes; complete raw payload SHA is
still required. Tar inventory JSONL is <=4KiB per member. Expanded stream has
a256GiB per-source ceiling; whole output cap includes all payloads, partials,
inventory, fixtures and failure receipts. Unknown size/type/layout or exceeded
cap remains UNKNOWN with preserved evidence, never a silently omitted source.
Ceilings are not forecasts. A34,759B gzip profile cannot forecast large TAR/MAT
or chemical normalization throughput.

Three guarded boundary fixtures check gzip EOF corruption, the exact one/ten
mode split, and credential-free metadata whitelist. The CRC/boundary method
also opens in-memory invalid-header and valid512B-header-plus-truncated-tail
streams and requires ReadError; the fixture count remains three. No fixture
has been run.

The TAR call supplies `tarinfo=StrictTarInfo` and `ignore_zeros=True`. The new
subclass converts only `InvalidHeaderError` and `TruncatedHeaderError` to
`ReadError`; it does not catch true-empty `EmptyHeaderError` or true-zero
`EOFHeaderError`. This prevents invalid/truncated-header skipping while
retaining traversal of zero padding/concatenated archives. The
[official CPython3.11.9 source](https://github.com/python/cpython/blob/v3.11.9/Lib/tarfile.py)
defines these four header exceptions as separate HeaderError subclasses,
accepts the TarInfo class argument, and rethrows ReadError in TarFile.next rather
than entering its invalid-header skipping branch. This is a source review,
not a claim of execution on Alpha's installed interpreter.

Per-source receipts are durable as sources finish. Aggregate schema is
`SECONDARY_EXTERNAL_SOURCE_ACQUISITION_RECEIPT_V1`; success statuses are
`OFFICIAL_SINGLE_SOURCE_CONTAINER_PROFILE_COMPLETE` or
`OFFICIAL_ELEVEN_SOURCE_CONTAINER_ACQUISITION_COMPLETE`. Full requires eleven
distinct complete sources, including reused sider. Actual terminal parent
accounting is a later required closure; failed costs remain. REPORT_AND_CONTINUE
changes only the cost gate. Current RSS/MemAvailable, output, storage and hard
wall safeguards remain; no forced signal or deletion is implemented.

This stage grants no all-split identity coverage, source normalization,
benchmark-label access, novelty ranking, UFF/QM, pool repair or training release.
