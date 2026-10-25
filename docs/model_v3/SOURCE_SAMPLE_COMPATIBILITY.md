# Frozen source sample field compatibility

Actual selected-TRAIN materialization 4520387 failed before publication with
an AttributeError in the unchanged original `som_payload` line 335. It had
attempted 32 selected members; the failure is preserved and is not a successful
store. No outer target was decoded. The earlier synthetic preparation tests
covered the metadata/native packing boundaries but did not call this real
legacy source-body path, so they missed this interface seam.

The current source reader's `MaterializedSourceSample` has exactly `record`,
`geometry`, `status` and `provenance`. Its unchanged `materialize_geometry`
writes the actual `native_source_graph_binding` into the sealed provenance.
The old materializer instead reads `sample.native_source_graph_binding` as a
direct attribute. This is a field-location incompatibility, not a missing
chemical/source proof or a new label rule.

Only the new model-side adapter changes. `v3_source_sample_compat.py` delegates
the original source module and returns a read-only sample view that exposes
the existing provenance field to the legacy consumer. The same original
record, underlying geometry/tensors, status and provenance are retained. Before exposing
the field, it validates the original sample type, same record identity,
record/member/native structure seals, geometry SHA/tensors, sample provenance
seal and the field's original scope. A ready cached binding must have its own
valid seal and belong to that exact current native graph. A missing field has
no default. A `None` is accepted only when already explicitly sealed for an
original-source 3D or failed-geometry sample. No binding is constructed,
repaired, resealed or inferred, and no target validation is bypassed.

`FrozenSelectedDecoder.prepare` supplies this module view only to the original
`som_payload`. The original `SourceRecordStore`, `materialize_geometry`,
PRIMARY_SOM parsing, author/native atom map and old frozen script remain
unchanged. Labels, masks, coordinates and units still pass through those
same source functions after the native TRAIN allowlist guard.

Actual 4520399 found a separate test-fixture error: the reused minimal source
reader fixture had no `sample_id`, which the older full-source join correctly
requires. All seven new cases stopped there, with 89 unchanged tests passing.
The fixture now declares synthetic sample IDs before reader ingestion so the
original member/record hashes bind that field. No production fallback was
added. Actual 4520402 then passed six cases and exposed a second source-3D
interface problem through the remaining coordinate assertion.

That second problem is substantive: `SourceEncoderGeometry` has FP32 encoder
positions plus a sealed original FP64 coordinate hash, but no direct FP64
tensor attribute. The old materializer fallback reads
`record.structure.pos_angstrom`, which is `None` for the parsed CYP structure.
Accepting `None` would silently mark valid source-3D members unready. The test
was not weakened to accept this.

The authorized additional geometry view reads the same original record's
existing conformer doubles, in unchanged native atom order, only for
`ORIGINAL_SOURCE_3D`. It requires exactly one 3D conformer, original atom
markers and source-block/angstrom provenance, matches
`source_coordinates_float64_sha256` exactly, and checks that one literal cast
to FP32 has the exact typed-byte hash of both the sealed encoder-pos proof and
actual existing pos tensor. It never promotes FP32 back to FP64, generates
geometry, modifies the original molecule or reseals provenance. The older
consumer receives this verified native-coordinate field; cached geometry
already has the field and remains unchanged.

The new regression fixture actually runs synthetic source records through
`SourceRecordStore -> materialize_geometry -> frozen som_payload` for both
source-3D and saved-candidate geometry. It first reproduces the unadapted
AttributeError, then exercises the production selected decoder with the
compatibility view and checks identical source proof, native coordinates,
candidate/supervision masks and expected binary labels. Five additional
negative cases reject absent or changed sample/record/geometry/native-graph
seals. Source-3D explicitly requires non-None exact original FP64 values, the
sealed FP64/once-cast FP32 hashes and packed `geometry_ready=1`. Three further
negative cases reject FP64 drift even when FP32 stays identical, a foreign
same-key source record and a second conformer. Actual 4520407 passed all ten
cases in 2.91 seconds (job C0/7s); no real source targets were read to develop
the fix. The 399 and 402 failures remain separate evidence.

A final CYP-only invariant checks the original
`geometry_artifact_ref.status`: `GEOMETRY_READY` must return coordinates and
`NOT_READY` must return `None`. It does not guess statuses for QM9/Expansion,
change labels or generate geometry. Two new negative tests run the actual
frozen synthetic decoder/source/atom-map path before corrupting only its
returned coordinates, proving that a dropped ready geometry or invented
unready geometry is refused. One positive test retains an original failed
geometry as `None` while preserving its original targets/masks. Actual
4520409 completed C0/58s and passed all three focused cases in 0.53 seconds.
The accepted evidence is 399's 89 unchanged tests, 407's ten repaired
compatibility cases and 409's three new invariant cases. These distinct runs
are retained; no failed parent or earlier revision is upgraded to a pass.

The final frozen compatibility implementation SHA256 is
`e9db79abbfdb727bade39b86a6ceb6b8f21728cf3d2b8dac5f69c42fc4c313cb`;
the selected-source adapter is
`d7b862533042835785c5d148d055db899bb31444ef5a9d55a6feda92bc390c2c`.
The unchanged old materializer remains
`e844e765bef02e3e30bea10f9e6b91137211c4f9fae87e2306ecfeee76a7b634`.
Root must now close a newly source-bound metadata request and real selected
TRAIN materialization. No complete real store or real panel is implied by
these synthetic regressions.

The adapter source SHA changes. Reissue metadata preparation under the actual
new committed source and bind its new request raw SHA; do not weaken the old
request's source inventory. The scientific `selection_sha256`, original
native groups/IDs/roles and original source-contract bytes should match the
379 selection exactly. The correct original request SHA is taken from its
machine-readable `preparation_result.json`:
`ed8b4682ece4f11bf6645ab266000a1f7d26f0a071730c61f3bd1a487b243da1`.
The failed 385 typo run and failed 387 source-interface run remain separate
records and their partial output is not reused.
