# Exact source and report-figure publication

The completion coordinator exports a clean, checked committed tree with
`publish_payload.py`. UTF-8 source, Markdown, JSON and SVG use the existing inline
tree transport. Small final-report PNG/PDF files are allowed only under
`docs/expansion/`, with `--allow-report-figures`; the repository's existing 2 MiB
per-file limit and required checker remain unchanged. Scientific DATA, catalogs,
coordinates, weights and large outputs remain external.

For a manifest with `binary_blobs`, publish each payload before creating trees:

1. Read the declared blob JSON and verify its transport bytes/SHA256. Decode
   base64 and verify original bytes/SHA256 and the exact Git blob SHA.
2. Call the connected GitHub `create_blob` with its `content` and `encoding`.
   Require the returned SHA to equal `git_blob_sha`; no branch changes yet.
3. Create the ordinary tree chunks in order. Binary tree entries already contain
   the exact original Git object SHA; UTF-8 entries retain inline source content.
4. Require the final tree SHA to equal `expected_final_tree_sha`. Create the
   commit with the declared public parent, update only the existing completion
   branch with a matching-head lease and no force, then read back the exact tree,
   parent, branch and draft PR. Never merge.

Do not treat the export manifest as scientific completion evidence. Complete
producer outputs, native cost inventory and the taskbook audit establish that
separately. The exporter deliberately makes no positive scientific-completion
claim, including for figure-only updates.

`test_publication_figures.py` checks exact UTF-8 and binary round trips, original
Git identity, scoped file signatures, size/mode restrictions and refusal of
binary scientific formats. A transport test is not visual QA: inspect the actual
rendered scientific figures before final delivery, and keep their native input
references and reproducible plotting sources.
