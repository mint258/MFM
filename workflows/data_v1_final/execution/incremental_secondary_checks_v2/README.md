# Fifteen incremental fixtures only

This v2 is an explicit technical retry of failed parent **4521134**. Its first
three child fixtures had passed, but the parent output-accounting walk raced
with acquisition's removal of its own synthetic temporary directories. That
failed parent, partial evidence and logs remain unchanged and are not upgraded
to a completed parent. V2 reruns these same fifteen incremental fixtures, with
no old legacy suites added. The failed-parent log is an exact small source pin.

This new entry uses `cpu_auto_memory_queue_v2.runtime.require_startup` for the
actual Python main, complete argv, exact scope parameters, plan pin and current
source pins. It does not call either old 64 GiB startup guard. The Root-reviewed
stage must be `FIXTURE_ONLY`, analysis, pilot true, 16 allocated CPUs, 600 seconds
(10 whole Slurm minutes), a 1 GiB whole-output ceiling, no requested memory and
no exclusivity. The ceiling is not a runtime or storage forecast.

Only these TestCase classes are loaded:

| suite_id | Original source | Class | Count |
| --- | --- | --- | ---: |
| full_identity_policy | expansion/identity_full_after_profile_v1/test_full_policy.py | FullIdentityPolicyBoundaries | 3 |
| secondary_source_acquisition | expansion/secondary_source_acquisition_v1/test_v1.py | SecondarySourceBoundaries | 4 |
| portable_secondary_uff | data_v1_final/conformers/portable_secondary_uff_v1/test_portable.py | PortableBoundaries | 5 |
| frame_native_precision | data_v1_final/pprime/frame_native_precision_diagnosis_v1/test_v1.py | NativePrecisionFixtures | 3 |

Four fresh Python processes execute sequentially. This avoids the two direct
`test_v1.py` modules and acquisition's `profile.py` sharing a module namespace.
Direct tests use an absolute source loader and their own sibling import path;
the imported project source paths and SHA pins are checked before and after
the suite. No diagnosis `run_v1.py` or scientific producer entry is imported.
The loader must find exactly the stated number of unique TestCase IDs before
execution. Every group must run that exact count, exit 0, and have zero failures,
errors, skips, expected failures and unexpected successes. No prior fixture
legacy suites are rerun. CPU16 is the allocation, not a claim of 16 fixture workers.

These source-bound tests use synthetic objects, temporary files, a pipe, a tiny
ZIP, Decimal arithmetic and small numpy geometry arrays. They authorize zero
retained scientific input records, zero network requests, zero new UFF and zero
new QM. They do not prove production source coverage or release any pool or
training gate. Parent and child receipts state this scope; they do not claim
there is no synthetic mathematical work or temporary-file I/O.

Each suite retains stdout/stderr prefixes of at most 4 MiB each while continuing
to drain pipes. Truncation rejects a pass. Completed suite results, logs and
dispositions are persisted immediately. At 570 elapsed seconds or near the
whole-output cap, no further suite is dispatched; an active child drains
naturally. The code sends no termination signals. A stalled child can reach the
existing Slurm wall, so complete final receipts cannot be promised in that case;
earlier evidence remains. Actual parent allocation cost is bound later from
Slurm accounting, not inferred from subprocess CPU timings.

The three corrective changes are confined to parent technical accounting and
cleanup: `os.walk` plus `lstat` rejects symlinks and tolerates only ENOENT inside
an allowlisted suite's own `synthetic_tmp`; all other filesystem errors fail.
Every parent monitor failure enters `finally`, naturally waits for the active
child, and joins its log-draining threads before returning. A failed capture
file creation produces a failure reference instead of a second stat exception.
Test source files, class allowlist, counts and scientific assertions are unchanged.

Root metadata preparation, after integration:

```sh
/share/home/zixiao/.conda/envs/chemprop/bin/python -B -m workflows.data_v1_final.execution.incremental_secondary_checks_v2.materialize --tag v1 --reviewer root
```

This reads only small source/authority files and writes a source-bound READY
fixture plan and `base_spec_not_request_ready.json` under
`control/incremental_secondary_checks_v2/v1/`. It does not execute tests or
submit. The base spec deliberately has `scope.review=null`; central validation
rejects it until Root creates the actual exact review and a distinct ready
spec. No future review, job, observation or source SHA is invented. The ready
scope's parent evidence list may be empty for this fixture-only stage.

Root then uses central-v2's ordinary metadata materializer with the reviewed
spec, the current user authority, a permitted analysis CPU node, and a fresh job
name. It renders the no-memory/no-exclusive script. The actual primary argv is:

```text
PY -B -m workflows.data_v1_final.execution.incremental_secondary_checks_v2.run --plan ABS_PLAN --startup-proof ABS_FRESH_PROOF
```

Outputs go to a fresh `artifacts/incremental_secondary_checks_v2/TAG/`.
The final `receipt.json` schema is `ACTUAL_INCREMENTAL_SECONDARY_FIXTURES_V1`.
Only success status `FIFTEEN_NEW_INCREMENTAL_FIXTURES_PASSED` is accepted.
`tests_run=15`, `failures=errors=skips=0`, and `suites` has exactly the four
suite_id keys above. Each contains `expected_tests`, `tests_run`, `failures`,
`errors`, `skips`, `expected_failures`, `unexpected_successes`, `exit_code`,
`suite_result_reference`, bounded log references and elapsed time. Child schema
is `ACTUAL_INCREMENTAL_FIXTURE_SUITE_V1`, success `EXACT_SUITE_PASSED`.
Every child acknowledges that fresh admission belongs to the bound parent;
children do not fabricate independent main/argv startup proofs.

Source preparation has not executed Python, tests, scientific inputs, SSH,
Slurm or Git. Root reviews and performs all actual validation and submission.
