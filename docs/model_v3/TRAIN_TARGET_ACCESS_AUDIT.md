# Selected-TRAIN semantic target access audit

2026-10-25. Read-only source audit after actual metadata preparation 4520379.
No real target values or old downstream scores were read for this review;
the tested Python source remains frozen at the committed implementation.

The audited call chain has no whole-table numeric/annotation cache. Opaque
whole-file SHA checks and byte framing may physically touch excluded target
tokens, but do not interpret those tokens as numbers, annotations, masks or
model scores. The only semantic target conversions occur after the selected
native `(dataset,index,role)` guard.

| Boundary | Actual source and behavior |
| --- | --- |
| Metadata preparation | `tools/model_v3/prepare_selected_training_store.py:38–47` calls `load_context`, `make_selection_request` and `close_context`; it neither instantiates `FrozenSelectedDecoder` nor calls its target methods. These paths inspect original membership/role/geometry metadata and opaque source hashes. |
| Numeric cache | `current/phychem_mfm/phase1/v3_selected_training_store.py:272–291` reads byte content, invokes the existing byte CSV framer and retains `graph_frames` only for wanted native indices. It decodes header names, not target field values. |
| Original CSV framer | `current/phychem_mfm/phase1/downstream_source_records.py:171–221` handles byte delimiters, quotes, escapes and spans. It has no UTF8/numeric/annotation interpretation of data values. Excluded numeric tokens are discarded as opaque byte fields. |
| Native allowlist | `v3_selected_training_store.py:323–332` requires the sealed native key and selected TRAIN role, prevents duplicate decode and verifies original member-row SHA before either target branch. |
| Source structural join | `docs/phase1/evidence/stage44_missing_masks/graph_field_masks.py:80–124` checks original dataset/sample ID/fold/XYZ path or raw SMILES/name/frame association. It never invokes the helper's separate `_finite` numeric parser. |
| Scalar conversion | `v3_selected_training_store.py:358` is the numeric conversion call, after native allowlisting, structural join and geometry proof. The original `observed_scalar` in `stage60_downstream_binding_v3/materialize_downstream_bindings.py:188–206` receives one field's bytes; its UTF8/regex/Decimal/FP32 operations have no file or table cache interface. |
| Original XYZ | `current/phychem_mfm/phase1/downstream_structures.py:130–190` reads N and the element/three-coordinate columns of N atom rows. The comment, fifth/extra columns and trailing annotations remain opaque. It is called only within the selected QM9 branch. |
| SDF raw cache | `downstream_source_records.py:257–320` stores `_files` bytes and `_frames` offsets. `_sdf_frames:153–168` identifies structural `M END` and record `$$$$` boundaries without interpreting property values. No whole-SDF numeric/PRIMARY_SOM cache is built. |
| Selected structural record | `SourceRecordStore.get:328–362` parses only the requested record's structural block, validates native graph/member/key association, and returns its opaque property frame with `annotation_values_decoded=false`. Structural parsing revalidates the existing key as part of the unchanged source reader; it does not select a new grouping identity. |
| Saved geometry | `ClosedCandidateLedger:644–675` and `materialize_geometry:704–760` validate the existing target-free native geometry/receipts. They do not call a benchmark annotation decoder or generate new coordinates. |
| CYP target call | New `decode:334` invokes original `som_payload:276–306` only for an allowlisted member. That function obtains the selected source record, checks source/native/geometry/author mapping, then calls `primary_or_absence:209–217`. |
| PRIMARY text extraction | `downstream_source_records.py:591–629` inspects the single selected record; it UTF8-decodes only that record's `PRIMARY_SOM` property. Other property values are skipped. The author supplier receives the structural block plus delimiter, not the full SDF or annotation table. |
| PRIMARY numeric meaning | `current/phychem_mfm/phase1/som_annotation.py:239–318` is a pure single-string parser. It maps the passed decimal atom IDs once through the original author/native mapping. It has no I/O or global dataset cache. |

The new materializer never calls the historical all-role `run`,
`iter_graph_field_masks`, whole-table `_finite` pass, old probe CLI or
full-evaluation entry point. The panel's CYP-only source store indexes nine
raw CYP files; the numeric Expansion reader uses only its original official
TRAIN file. Other original native task columns within an allowed TRAIN record
retain the unchanged source transport; this does not authorize any excluded
member or held-out file to reach a semantic decoder.

Actual 4520372 passed the selected-store regression bundle, 15/15, with
unchanged source hashes. Actual 4520379 completed metadata preparation in
25 seconds and reported zero target records decoded: CYP 1,803,
ExpansionRx 5,326 and QM9 10,473 selected native records. The immutable
selection request is 27,382,324 bytes, raw SHA256
`ed8b4682ece4f11bf6645ab266000a1f7d26f0a071730c61f3bd1a487b243da1`.
The reported zero is supported by the source call-chain boundary above;
it is not a claim that every physical source byte was avoided.

No non-TRAIN semantic target access requiring a source fix was found.
The real selected-TRAIN materialization and real nine-task GPU evaluation
remain separate actions; neither is inferred from this audit or metadata run.
