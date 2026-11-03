# UFF3 source, runtime and final mask review

Current software status: source implementation only. The pure tests, real native
fixture, actual 10k pilot and whole 2.5M execution must each have independent
actual evidence; source syntax or a manifest name proves none of those outcomes.

`plan_template.json` and `source_manifest_template.json` deliberately contain
null actual references and are NONEXECUTABLE. Root fills these from the real
released R/N ranking, actual immutable source bytes, current scheduler resources
and fresh quota publisher. No new approval from the user is needed for routine
execution already authorized by the current goal.

## Execution

After source checking in the actual Linux environment:

```text
PY -B -m unittest workflows.expansion.uff3_candidate_v1.test_v1 -v
PY -B -m workflows.expansion.uff3_candidate_v1.native_smoke --output FRESH_FIXTURE_DIRECTORY
PY -B -m workflows.expansion.uff3_candidate_v1.run --plan ACTUAL_PILOT_PLAN
PY -B -m workflows.expansion.uff3_candidate_v1.run --plan ACTUAL_FULL_PLAN
PY -B -m workflows.expansion.uff3_candidate_v1.quality --plan ACTUAL_FULL_QUALITY_PLAN
```

The native fixture runs two synthetic source graphs, never actual PubChem data.
It checks real D3 and corrected D20 binary64/masks against the original wire,
real 3-to-4 cache-only extension with native calls forbidden, dedup against all
saved coordinates, and original float64 family Parquet counts. Four exported
fixture rows explicitly test the future API; production retains at most three.
The fixture needs the exact Linux RDKit2025.09.5 plus original dependencies and
PyArrow; it is restricted to compute20 or an actual Slurm allocation.

The production source manifest contains all 2.5M graph rows in closed JSONL
parts. Every part is whole-SHA/stable-FD checked during ingestion. Full-key,
CID, MID and stream/rank uniqueness are proved on disk. R=N1.25M and exact
rank1..1.25M are checked, then a bidirectional exact anti-join against actual
ranking.batch1 proves the source is the requested batch. Actual original
screen/regression/all-source/exact-novelty release gates are called. No 10k
prefix or a convenient source subset substitutes for the full batch.

Pilot membership is one Python Random(20261025), successive sample5000 of
R ranks then5000 of N ranks. It uses the same molecular cache as full execution;
valid closed pilot results are adopted without repeated UFF. Root must inspect
the real 10k terminal/accounting/cost/storage/scientific results before launching
full production. A completed source-only or native-two-molecule fixture is not
that 10k evidence.

Full execution has no 1024-molecule parent cap and no application wall-clock,
repair-time or failure-count stop. One allocation can process its entire
assigned scope, or Root can choose disjoint ordinal-modulo CPU shards. Initial
cache creation is at most one native call per candidate. A whole output root
has an exclusive parent lock; each source has a deterministic exclusive output
directory. On continuation, closed per-MID caches/packets and whole family batch
manifests are verified/adopted. Interrupted scientific directories retain their
original raw events and explicit UNKNOWN/null labels; they are never erased or
scientifically retried. Source integrities and physical resource limits remain
hard protections. No active optimizer is killed by this program.

## Data and quality

Each source packet has graph D20 once, D3/atom SASA on only actual selected
coordinates, fixed-random/energy/diversity permutations, canonical generation
order, source key/CID/version/stream/rank, physical SHA, original kernel/recipe
provenance, explicit shortage/failure and source masks. Internal30-candidate
caches are separately inventoried for future extension; they are not thirty
delivered geometries. Original WP5 float64 schemas/writer are called directly
for D20 and D3. New geometry/status fields have explicit Arrow types.

The source native/family writer never fits R/N as TRAIN or creates PM7/xTB/Pprime
labels. A real original field map, mask configuration and matching closed TRAIN
calibration/domain review is required for the final robust review. The unchanged
original source-value/cross-field/reference-review functions produce per-leaf
masks and original reason codes. Unknown original labels remain null/masked.
Within-molecule jumps and robust-z findings remain review reasons under the
original policy; they do not silently become new chemical exclusions.

The quality pass reads actual generation receipts and closed batch indices,
proves a unique complete R=N1.25M source census, verifies actual family hashes,
then reports source states, per-field/per-stream component and masked counts,
all-stream masked fractions, reason-set frequencies, and twenty cases per field.
Fields above1% masking are explicit. Output remains pending Root's actual
scientific review; it does not claim final training release or full task
completion. All failure/UNKNOWN sources and missing-value domains are retained.

## Resources and accounting

Both production and quality require an actual Main UID1278 CPU allocation with
at least16 workers/allocated CPUs and Root-listed CPU nodes. Shared
`completion_runtime_v1.quota.budget_check` validates fresh actual account quota,
publisher/source identity, raw text/SHA and all future reservations, separately
from current filesystem free space. No old24h provider lease or hardcoded node13
is introduced. Registered closed output files avoid repeated growing-tree
metadata scans in the adapter; the shared quota implementation handles safe
pre-snapshot credit. Actual RSS/MemAvailable are checked between native calls;
resource partials finish normally, retain real results and stop new dispatch.

Worker/native elapsed and CPU seconds are observations, not Slurm allocated
core-hours. Root appends real terminal accounting, including failures, source
checks and startup costs, and reports actual total bytes plus linear2.5M/10M
storage extrapolation from the measured pilot/full data. No future C0, SHA,
throughput, success rate or scientific acceptance is prefilled.
