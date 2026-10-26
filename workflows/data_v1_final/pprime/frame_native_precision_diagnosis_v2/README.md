# Retained frame72 precision diagnosis v2 (draft)

This namespace is a reviewable replacement entry for the retained72 diagnostic.
It makes no new QM/UFF calls, releases no production population, revises no
original result or tolerance, and preserves the original15 VECTOR_NOT_COVARIANT
failures and original72 evaluation. The frozen v1 namespace is unchanged.
This draft has not been executed, tested, registered, submitted or accepted.
Root alone integrates, pins, reviews the exact stage, submits and closes costs.

The two static blockers in v1 were an uncapped `raw_bytes` metadata check followed
by the frozen reader's unbounded `gzip.decompress`, and a 100-digit Decimal
context used to claim exact propagation despite longer permitted native tokens.
Those are source findings; no real raw body has been read to implement this v2.
The existing small evaluation metadata still has72 cases and15 failures; its
postcall input metadata matches prepared inputs. No actual input mismatch or
SCF cause has been established by this review.
The retained small evaluation metadata has32 MATCHES_INPUT_COORDINATES source
output-coordinate records and40 singlepoint records with unavailable own-source
output coordinates. Actual input binding does not certify those unavailable
native output frames, and no full-population frame PASS is inferred.

## Exact scientific dependencies

`tokens.py` and `frozen_sources.json` are byte-for-byte copies of v1. The latter
still pins the original common, raw archive, vector evaluator, output reader,
vector math and audit preparation sources. Original configuration, pilot
configuration, contract, protocol, source pins and native parser hooks remain
authoritative. The driver imports the frozen engine only to render the original
inputs and obtain its original output archive. It imports the frozen parser and
AST-extracts its original two native AUX/sparse parser hooks. It does not call
engine initialization, a QM executable, old main/runner/queue logic, LMDB,
population load_config, or a scientific calculation.

Raw token locations and branches remain the original AUX first-declared-count,
unique top-level xTB dipole JSON numeric array and frozen len3-numeric gradient
row predicates. Duplicate/missing/ambiguous selections remain UNKNOWN. Native
token conversion uses the frozen parser `f` and factor, with binary64 comparisons
against the freshly parsed value, independent audit and original retained label
or the frozen intentional task projection. Signed zero is checked bitwise at
this stage. Rational residuals have mathematical zero, without changing those
earlier signed-zero checks. Dtype/float repr is never used to infer print digits.

`geometry_orbit` is unchanged from v1: actual native program coordinates, declared
R/t and only an explicit supplied permutation; no fit or inferred remapping.
Noise tests continue to compare actual noisy-minus-clean coordinates in the
rotated and laboratory hypotheses. The driver separately reports whether a
translation matches the frozen configuration. Any failed actual-input render,
prepared-SHA or target-coordinate binding makes the affected failure diagnosis
UNKNOWN, while preserving its numeric/source evidence. This is a conservative
new safeguard; it does not assert a mismatch in the retained72.

## Bounded retained data read

Only after the four actual synthetic methods pass, the driver reads all72
bounded result metadata records and validates each `raw_bytes` against the
original `max_raw_bytes_per_case` (16777216), original result cap (8388608),
original total input cap (65536), atom cap, unique result paths/case IDs/raw keys/
group-arms, and exact equality with the72 original evaluation case IDs. Any
preflight error blocks every raw-container read and is recorded with traceback.
Pinned result/input bodies use bounded reads and recheck exact size and SHA.

The new dedicated raw reader opens SQLite `mode=ro` and starts a read snapshot.
It checks original row SHA/size and SQLite frame/metadata byte lengths before
fetching their bodies. Its finite compressed-frame bound is original raw cap
plus1MiB (gzip storage overhead allowance, not a scientific raw-size increase);
raw metadata is bounded by the original8MiB result cap. It calls
`GzipFile.read(max_raw+1)`, rejects output above the original raw cap, and requires
EOF/CRC validation for an allowed stream, including concatenated gzip members.
It then checks original body size/SHA and invokes the exact frozen
`archive.unbundle`, retaining original offsets, sizes, member SHA, manifest and
forbidden-input-name checks. It does not first perform an unbounded decompress.

There are at most16 active read/parser tasks and16 node-local output-only temp
directories. Their simultaneous output body bytes are bounded by16 times the
original raw cap (256MiB). That is not a bound on total Python/native RSS:
compressed bodies, metadata, decoded/parser objects and report state coexist.
Actual parent plus live workers RSS and node MemAvailable are sampled;8GiB RSS
and4GiB available are algorithm soft STOP thresholds, not Slurm memory requests.
STOP ceases new dispatch and drains existing tasks naturally. No forced signal
is sent. The dispatch deadline is `max(0,min(3000,request.wall_seconds-600))`
seconds after producer startup; a shorter wall does not gain a false completion.
No deadline guarantees that all tasks finish before Slurm's actual wall limit.

## Exact arithmetic and its limited meaning

The native decimal center and its exponent-derived last-place step/2 are
constructed exactly without ambient Decimal arithmetic. Every center, halfwidth,
R coefficient, frozen conversion factor and parsed float is converted to exact
`Fraction`: Decimal token values are exact decimals, and binary64 values use
`Fraction.from_float`. The complete propagation, residuals and comparisons use
integer rational arithmetic. Exact terminating decimal report strings are
constructed by factoring denominators into powers of2/5 and integer scaling;
no 100-digit context or rounded Decimal division participates.

The half last printed decimal place is explicitly a **round-to-nearest-decimal
hypothesis for diagnosis**. This does not establish the output binary's printing
error policy, explain SCF failures, identify a cause, certify all program frames,
add a new numerical allowance, turn any of the15 failures into PASS, or authorize
another QM run. The frozen evaluator is called with its original tolerances and
the original per-token audit values; its exact retained check must reproduce.
Differing actual geometry, input binding, unit/parser uncertainty or unreproduced
old checks remain DIFFERENT_GEOMETRIES/UNKNOWN with the original failure retained.

## Four actual tests before retained raw

`run_v2.py` runs `test_v2.NativePrecisionFixtures` directly inside its admitted
allocation, without a subprocess, before opening a raw container or reading
retained program input bodies. The original three methods are retained:
E/D exponent halfsteps and duplicate JSON rejection; propagation from a large
component into a small rotated component; and noisy lab geometry with explicit
permutation only. The fourth method checks a >100-significant-digit cancellation
at exponent250 using exact Fraction expectations, and a small rotated component
just inside/outside an exact0.0505 hypothesis bound.

Exactly four methods must run and succeed; skips, expected failures, unexpected
successes, load failures and subtest failures prohibit raw dispatch. The report
embeds the actual tests-run count, all successful IDs, complete errors/failures/
tracebacks, stdout/stderr and observed test wall time. This source's four tests
are not claimed as executed or as comprehensive archive/CLI integration tests.
Only a real fresh admitted execution can supply their receipt.

## Primary entry and Root binding

Use central `workflows.data_v1_final.execution.cpu_auto_memory_queue_v2` with a
new exact Root review/spec/request/proof, `kind=analysis`, `pilot=false`, scope key
`pprime_frame_native_precision72_v2`, and exact `SCOPE` from `run_v2.py`. This is
retained72 read-only diagnosis with four prerequisite tests, not a new pilot.
No sbatch memory/exclusive directives and no64GiB/85% admission are used. Actual
resource admission, CPU16, CPU-only, all allowed main analysis nodes, fresh UID/
boot/job/node identity and quota200GB reserve come from the central v2 policy.
Any Slurm memory environment value is only an observation.

The canonical `execution_argv` is the list below, where every path is literal and
absolute and `PY` is the exact central contract interpreter. The producer requires
`-B`, primary file and all six option/value pairs in this order; the central
runtime also checks actual `__main__`, actual primary argv and the complete
bound request/review/spec chain. Do not use a wrapper's `--producer` argument,
an unrelated `-m` position, an old v1 primary, or another CLI option order as proof.

```text
[PY, "-B", REPO+"/workflows/data_v1_final/pprime/frame_native_precision_diagnosis_v2/run_v2.py",
 "--evaluation", ORIGINAL_FRAME_EVALUATION,
 "--run-closed", ORIGINAL_RUN_CLOSED,
 "--config", ORIGINAL_ROOT_AUDIT_CONFIG,
 "--pilot-config", ORIGINAL_PILOT_CONFIG,
 "--root-preflight", NEW_ACTUAL_STARTUP_PROOF,
 "--output", NEW_REPORT_ABSOLUTE_PATH]
```

`require_startup` requires all seven local files, the unchanged six frozen source
pins, and four input references (evaluation, closed run, config, pilot config) to
be explicitly present in authorized source/data refs. Small source pins are
hashed. The driver verifies actual local helper locations as well as primary.
Root must also pin the complete central v2 sources and the scientific dependency
closure used by the original contracts, and retain the exact original immutable
parent evidence. No future output reference or terminal state is invented here.

There is a single new exclusive-created JSON report, capped at2MiB before file
creation, with no truncation or fake PASS on overflow. The4-method receipt,
metadata preflight and all72/15 diagnostics share that cap; a large report can
safe-fail. Node-local output copies are temporary and removed normally. Root's
whole-stage output estimate must also cover its own wrapper/Slurm logs and any
separately recorded metadata. Actual terminal `sacct` cost is deliberately null
in the running producer and must be closed by Root with all related failed or
cleanup costs; requested wall is neither an observed cost nor a prediction.
