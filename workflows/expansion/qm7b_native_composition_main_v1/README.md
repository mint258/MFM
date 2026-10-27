# QM7b author XYZ conservative native composition

This consumer directly reuses frozen `identity_v2.projection_v2.native_composition`
and `identity` function objects. It makes no graph, bond, charge, isotope, stereo,
SMILES, InChIKey or WP5 inference, does not align MAT rows, and computes no new
QM/UFF. No old config, source, format report, data file or once ledger is changed.

The existing policy `configs/data_v1/decontamination_sources.json:9` explicitly
uses conservative native non-H element composition when original graph identity
is unavailable. This stage applies that already frozen fallback to all7211 author
XYZ frames, retaining every row even when compositions repeat. Each output has
empty `inchikeys`, empty WP5 keys, unresolved graph identity, a native composition
and the explicit conservative reason. Completion is a conservative source-set
coverage observation requiring Root review, not exact graph/key coverage or a
global pool/training release.

Actual prerequisite: Main4521897 C0/34s/16CPU/compute-0-17 (544coresec),
`qm7b_materialscloud_v3_format_v2/receipt.json`, account/raw, config and historical
proof. It observed all7211 frames and actual H/C/N/O/S/Cl symbols with no native
identity tokens in their headers. The original failed format4521888/cost remains
explicit evidence. The >2MiB `frame_identity_format.jsonl` is scientific DATA;
the login helper neither hashes nor parses it and this adapter does not need it.

Single DATA input, already actually obtained by Root:

```
artifacts/expansion/qm7b_materialscloud_v3_original_v1/qm7b_coords.xyz
7837328 bytes
SHA256 03e1362a1103e5c82c843550f927593905143e5bb02f3e4ba38bcfeb7bc7563a
published MD5 a0d313a486513690bb172da819a3f622
```

The actual transport receipt and small README/files_description are required and
pinned. They bind [Materials Cloud v3](https://archive.materialscloud.org/records/rmp9p-1k216),
DOI10.24435/materialscloud:2019.0002/v3. Its actual
[README](https://archive.materialscloud.org/records/rmp9p-1k216/preview/README.txt?include_deleted=0)
describes all7211 QM7b molecules in a farthest-point reordered XYZ collection.
The [author paper](https://www.nature.com/articles/s41597-019-0157-8) describes
translation to nuclear-charge centers, FPS reordering and new molecule names.
Those are author provenance/set statements, not a native XYZ-to-MAT ID mapping.
No new scientific archive was fetched by this author.

The actual XYZ header carries Properties/polarizability metadata and no native
ID. Therefore `source_id` is explicitly a **file-frame locator** in namespace
`materialscloud:2019.0002/v3:qm7b_coords.xyz`, with a zero-based physical ordinal;
`native_author_ID=None`. It does not invent molecule0001, MAT sample IDs, missing
SMILES, benchmark splits or a representative source variant. Root explicitly
approves only author-asserted same-population set coverage plus conservative
composition; exact native IDs/graph/row correspondence remain UNKNOWN.

Actual CPU runtime requires fresh central `cpu_auto_memory_queue_v2` admission,
analysis/pilotfalse/16CPU/no memory or exclusive request, any currently authorized
analysis node,128MiB output cap and whole-minute600..1800s wall. It does not bind
historical13-only storage facts to17/19. Fresh central account-free minus whole
128MiB must leave200GB. It directly uses frozen Drugs9 Budget/Writer with
`dispatch=False` and the original2MiB drain reserve, checking the original latched
`budget.stop_new` before every new input read. This preserves the actual job/UID/
node/boot/start checks, RSS16GiB soft cap, MemAvailable≥4GiB and15%, wall−180s and
physical statvfs capacity. Runtime statvfs is not a new account-quota observation.
Root retains responsibility for concurrent output reservations. No signals,
kill/retry, old guard rewrite or monkeypatch is introduced.

Three meaningful pure methods run in that allocation before XYZ body access:
native H removal and empty keys via the original functions; H-only/unknown/zero/
fake-native-ID rejection; complete/truncated byte frames, opaque comment/coordinate
tokens and distinct locators for duplicate compositions. No test was run by this
author. The reader mirrors the actual format producer's1024-byte count line,
1MiB comment,4096-byte atom line,512-atom bound and lexical numeric-token grammar.
Coordinates are never converted to floats or used; comment values are hashed
opaquely, not text/numeric decoded. Only explicit native species are counted.

CPU first proves complete current source SHA and published MD5 on a stable FD,
then parses every frame from that same FD. Each source-symbol-count event is
fsynced before calling the unchanged native composition/identity functions.
Original frame byte range/SHA, opaque comment SHA and native symbol counts remain
auditable. Source and result row counts must both equal7211; native symbol totals
and atom histogram must exactly equal the actual4521897 format receipt. All rows,
including repeated non-H compositions, are kept. A malformed/unsupported frame,
resource STOP or source mismatch preserves prefix files and a failure report,
without claiming complete source coverage or silently dropping a frame.

Root metadata request schema `ROOT_REQUESTED_QM7B_AUTHOR_NATIVE_COMPOSITION_V1`,
`status=REQUESTED_FOR_REVIEW`, `requested_by=root`, actual references:
`accepted_format_receipt_reference`, `accepted_format_accounting_reference`,
`author_transport_reference`, `decontamination_policy_reference`,
`resource_authority_reference`, `cost_decision_reference`; plus `wall_seconds`
and new absolute `output_directory`. The helper derives only the real source
locator from the actual receipt; all small author/policy/old-account/source refs
are pinned, while XYZ remains DATA. No future pin/approval/job is generated.

From Root repo with the established PYTHONPATH:

```
PY -B -m workflows.expansion.qm7b_native_composition_main_v1.materialize draft --request ACTUAL_ROOT_REQUEST --output NEW_CONTROL
```

Root independently reviews the template, including the explicit author set-only
composition approval, and makes a new approved copy (status/reviewer changes).

```
PY -B -m workflows.expansion.qm7b_native_composition_main_v1.materialize finalize --draft NEW_CONTROL/draft_receipt.json --root-review ACTUAL_APPROVED_COPY
```

Root submits the resulting spec with the unchanged serialized central helper.
This source adds no queue/controller. Exact scope
`qm7b_author_v3_native_composition_main_v1`, stage
`QM7B_ALL7211_AUTHOR_NATIVE_COMPOSITION_ONLY`, plan
`QM7B_AUTHOR_NATIVE_COMPOSITION_PLAN_V1`, proof
`FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1`:

```
PY -B -m workflows.expansion.qm7b_native_composition_main_v1.run --plan ACTUAL --startup-proof ACTUAL_FRESH
```

Outputs are source-first and identity DATA journals plus a small receipt with
actual counts and explicit graph/key UNKNOWN versus conservative composition
coverage axes. New actual Slurm cost remains pending independent Root accounting.
The source family's final decontamination integration is a separate Root decision;
the requested exact key rules, quality thresholds and global release remain intact.
