# PubChem expansion completion

This run implements all taskbook sections 2.1–2.9. The confirmed user amendment in `configs/data_v1/expansion/user_completion_20261103.json` supersedes the old ten-conformer/fill/retry requirements: at most three actual UFF conformers, fixed seed and generation order, no fill and no retry, durable append-only extension support, D20 once per molecule and D3 for every actual conformer. No P′, QM or training.

## Requirements and completion evidence

| Section | Required deliverable | Evidence needed; initial status |
|---|---|---|
| 2.1 | Common v1 and same-rule PubChem 1M distributions, exact nearest neighbors, gaps and figures | Frozen full Common reference, distribution tables including functional groups, complete 1M exact query results; incomplete |
| 2.2 | Official complete CID–SMILES, version/date/SHA | Existing complete download 4520348 and EOF inventory 4521093, 124857440 unique CID rows; preserve/reuse |
| 2.3 | Same X01–X05/RDKit, >=99.9% regression, explained discrepancies, full funnel | Existing full15,879,477 regression 4520414; original500 source units fully accounted, 110046364 accepted/14764875 chemical reject/46201 technical UNKNOWN; downstream pool release incomplete |
| 2.4 | Internal min-CID identity dedup, v1 ALL splits/embargo and all named downstream datasets | Complete aliases/candidate materialization and all11 source coverage; Alpha1885120 partial preserved; MoleculeNet closed adoption exists, COCONUT735 unresolved |
| 2.5 | R/N fixed-seed complete ordered10M queues, disjoint first1.25M each, exact novelty and strata | Full filtered pool and frozen reference; no downstream information used for novelty; incomplete |
| 2.6 | 10K actual pilot then full2.5M batch, max3/no fill/no retry, three stored orders and extendability | Actual coordinate/provenance/shortage/failure outputs and reproducibility/extension checks; old UFF runtime source only |
| 2.7 | Graph D20 once, per-actual-conformer D3 and atomSASA, outlier/cross-field masks | Original v1 scientific functions and TRAIN reference, typed family outputs and scan summaries; incomplete |
| 2.8 | Family float64 parquet v2_candidate/stream/CID/sourceversion, manifests/SHA, measured bytes and10M projection | Full batch physical outputs and complete input/geometry/label counts; incomplete |
| 2.9 | Full batch1 report: funnel, decontamination, R/N/v1/PubChem distributions, coverage gain, generation quality, actual corehours/storage | Reproducible tables/figures, all relevant actual terminal accounting, limitations; incomplete |
| GitHub | Code, each task report, manifests and figures pushed, expansion PR opened for user merge | Required repository checker PASS for each commit, remote branch/commit/tree and PR readback; incomplete |

## Execution and provenance

The original `data-v1` worktree contains unrelated uncommitted changes. This independent completion branch starts at f97484723fbb76be867d7864f2badad3a4a956b0 and preserves/copies only the42 existing expansion changes. Frozen sources, successful data, old failures and UNKNOWNs remain unchanged. Agents prepare isolated pool/decontamination/UFF3 changes; Root integrates, budgets, submits and publishes.

Old timeout/STOP2/four-hour and historical cost-ratio automatic stops no longer halt this expansion task. Actual cluster MaxTime, CPU, memory, quota and scientific integrity constraints remain real. Never reinterpret a TIMEOUT, partial output or source test as completed scientific data. Resume only from verified durable results; large data remain outside Git.

Current infrastructure observations: Main native persistent SSH is live; the standard X mapping reconnect fails85. A local-only nativeSSH/SFTP adapter makes the exact same remote tree accessible as Y; all file edits use a local logical X→Y resolution. Alpha direct SSH22 is currently timing out from Main and Windows; prepare independent code and pursue recoverable sources without claiming remote data accessible.
