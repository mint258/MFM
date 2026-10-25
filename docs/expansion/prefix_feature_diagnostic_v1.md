# Read-only stage localization for original prefix4520427 failures

The old screen.py, completed full4520414 and original prefix4520427 remain
unchanged. This helper does not implement a feature repair or chemical rule.
It reads only the same pinned official raw body (full opaque SHA verification)
and at most the first10000 decoded CID/SMILES records to locate1–32 explicitly
requested CIDs. Default targets are7,52,53 from the actual failed-feature list.
It never opens the old SQLite candidate database or screens a new pool.

Each selected case first calls the actual registered screen.features and
captures the exact Python traceback. An independent stage walk then calls the
old chemical_flags, full-InChIKey/WP5 identity, element counts, Murcko extraction
and genericization, exact old non-ring bond deletion, fragment splitting with
sanitizeFrags=false, each fragment's old sanitize/generic/smiles call, and
independent original-molecule fingerprint/descriptors. Every failing stage
keeps exception class/message and full traceback. Input CID, original ordinal,
raw SMILES, previous rejection, old source hash and raw source hash remain bound.

Intermediate snapshots only read stored atom/bond properties. They do not call
MolToSmiles, ring perception or sanitize before the corresponding old stage,
which could otherwise alter the failure. Independent fingerprint/descriptors
use a fresh original molecule after ring-stage localization. No sanitization
error is converted into an extra chemical exclusion.

Root fills a new READY plan and pins the small original prefix receipt, its
executed plan, its rejection JSONL, original raw producer receipt and actual
diagnostic runtime sources. Runtime code pins include the new helper, frozen
screen.py, common.py, data_authority_v1.py, package init and wrapper. Only the
raw1.49GB ref belongs in request.data_references. Existing old-prefix code pins
must match the currently imported screen.py bytes/SHA exactly.

CLI:

```bash
python -B -m workflows.expansion.prefix_feature_diagnostic_v1 --plan NEW_READY_DIAGNOSTIC_PLAN --root-submit-intent ACTUAL_ROOT_INTENT
```

Wrapper exports `EXPANSION_REPO`, `PREFIX_FEATURE_DIAGNOSTIC_PLAN`,
`PREFIX_FEATURE_DIAGNOSTIC_ROOT_INTENT`. Allocation: node20/16CPU/4GiB/<=1h,
output32MiB, fresh task-owned quota<=300s. The tiny case pool uses at most the
selected case count, reports actual thread IDs and explicitly distinguishes
those threads from allocated16CPUs. No claim of16 active case workers is made
for3 selected CIDs. Root alone runs it in an allocation after static/baseline
entry checks; no actual raw/CID diagnostic has run during code preparation.

Outputs are a new `case_stage_traces.json` and a provenance receipt with status
`READ_ONLY_STAGE_TRACES_RECORDED_NO_REPAIR`. Root reviews the exact failing
stage before any isolated features_v2 or new prefix entry is prepared. A future
feature repair must continue using the unmodified old chemical function; any
chemical-function change would require a new full source-rule replay.
