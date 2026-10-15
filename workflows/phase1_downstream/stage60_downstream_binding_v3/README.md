# Stage60 downstream binding V3 — exact geometry-kind projection

FINAL static draft. Root is the sole CPU/Slurm executor. Author operations were local text/JSON/.NET bytes only: no Python, AST, tests, SSH, X, geometry/target/archive decoding or model execution. New test execution and a corrected full materialization are PENDING. Original V1/V2 bytes, failures and receipts remain unchanged.

Only materialize_downstream_bindings.py changes. closed_geometry_kind(status,basis) accepts exactly:

| Actual sample status | Actual geometry_basis | Historical geometry_artifact_ref.kind |
| --- | --- | --- |
| GEOMETRY_READY | ORIGINAL_SOURCE_3D | original_source_3d |
| GEOMETRY_READY | SAVED_GENERATED_CANDIDATE | cached_generated |
| NOT_READY | SAVED_GENERATED_CANDIDATE | not_ready |

Inputs must be literal strings. Every other status/basis tuple is rejected. No case conversion, alias fallback or availability inference is permitted. som_payload still requires sample.status == expected.status; its one kind comparison now calls this projection. The immediately following geometry_provenance_sha256 and all encoder_tensor_hashes exact checks are byte-identical to V2. No geometry coordinates, native atom order, tensors, source bytes, annotation grammar, candidates, masks, labels, folds or scientific protocol are changed.

Root's actual store70 failure is preserved as FAILED_CLOSED; the locally copied failure metadata records DownstreamBindingError with error SHA 0fefa247fb2d8da27cc7d03191d44ea1d9648c97eaf3c79f075f492bced8d8d3. The actual frozen materialize_geometry source returns ORIGINAL_SOURCE_3D or SAVED_GENERATED_CANDIDATE, whereas the closed membership vocabulary is lower case. Root's closed2112 metadata distribution is 1927 original_source_3d/GEOMETRY_READY, 178 cached_generated/GEOMETRY_READY and 7 not_ready/NOT_READY. Those aggregate counts are attributed to Root's actual audit; this author did not open the original consumed ledger or rerun materialize_geometry.

The V2 four-ledger physical-size bridge remains exact, including strict old path/SHA/rows, universal verify_binding, input postchecks and published sidecar. downstream_binding_data.py and prepare_expansion_geometry.py are byte-identical copies of V2. DELTA.json proves the entire V2 materializer text is recovered by removing the new function and reversing the single comparison replacement. This is a static byte proof, not runtime scientific verification.

Root can first AST-parse the NEW Python files and run the single test_closed_geometry_kind.py stdlib method in its owned CPU allocation. It checks the three literal outputs and rejects unexpected statuses, aliases and non-string input. Root's separate actual all2112 geometry audit can verify ready provenance/tensor hashes without label decoding or generating new geometry. Neither operation was run by the author.

For any subsequent corrected store execution, Root derives a NEW request/binder from the actual store70 request, replacing only implementation/executing-helper refs with the physical V3 pins and using a new allocation/output. Keep the scientific source/protocol, membership, graph joins, cached geometry, readout and budgets unchanged. Failed70 is not rewritten or relabelled. This external vocabulary seam is unrelated to MFM source/protocol/checkpoint conversion.
