# Strict numerical settings: independent15-call QA, execution unapproved

This is new diagnostic code, not a production recipe change or a fix claim.
User approval has not been supplied. No native computation or submission was
performed in developing this package; the three pure methods also await actual
Root CPU execution. The four-file proposal and proposed protocol stay frozen.

The only numerical differences are PM7 B `SCFCRT=1.D-9` and xTB SP/perturbed
gradient trailing `--acc 0.01`. `contract.protocol` re-derives those three task
fields with the frozen proposal and inversely restores the entire old protocol.
All other nine task entries, methods, program/version/environment/binary pins,
original record IDs, seed20261010, sigma0.1, atom order, actual input geometry,
original900-second timeout, parser and covariance tolerances stay fixed. The new
calls use the exact15 B1/B2/R1/P1/P2 arms of original six cases054/055/058/059/060/061.

## Before any execution

`run` requires `user_decision_reference` before parent traversal, output creation,
scientific body reads or native initialization. The actual pinned JSON must have:

```
schema: USER_AUTHORIZED_PPRIME_STRICT_NUMERICS15_QA_V1
status: USER_AUTHORIZED
authorization_basis: EXPLICIT_USER_MESSAGE_IN_THIS_SESSION
actual_user_statement: the actual nonempty user statement
candidate_protocol_reference: exact proposed protocol triple
original_protocol_reference: exact original protocol triple
maximum_new_QM_calls: 15
cpus: 16
maximum_wall_seconds: 7200
per_call_timeout_seconds: 900
whole_output_cap_bytes: 2147483648
original_quality_thresholds_unchanged: true
production_recipe_unchanged: true
automatic_retry: false
full_or2000_release: HOLD
```

There is no such decision file in this source package. Cost report-and-continue
authority cannot substitute for it. A real fresh central v2 `kind=qm`, `pilot=false`
proof, exact full argv/current sources and independent Root exact-stage review are
also mandatory. Root chooses the current authority's actual free QM CPU node;
the job uses16CPU, no requested Slurm memory/exclusive/GPU,7200 seconds,2GiB output.

## Minimal metadata CLI (Root only; no scientific bodies)

Install this nine-file package, the frozen four-file proposal and candidate JSON
in their exact Root paths. A Root request JSON requires schema
`ROOT_REQUESTED_PPRIME_STRICT_NUMERICS15_QA_V1`, status `REQUESTED_FOR_REVIEW`,
requested_by `root`, and these actual refs/fields:

- `native_control_receipt_reference`: actual1891 electronic receipt, whose own
  plan/proof close1845/1802/1766/1765 and the original six-case authority.
- `native_control_accounting_reference`: actual1891 C0/raw accounting.
- `original_protocol_reference`: frozen phase1 protocol, original SHA enforced.
- `candidate_protocol_reference`: repository/configs/data_v1/pprime/
  strict_numerics15_qa_v1_protocol_proposed.json, frozen derivation enforced.
- Current `resource_authority_reference` and `cost_decision_reference`.
- Fresh `output_directory` under artifacts/pprime_strict_numerics15_qa_v1/.
- `user_decision_reference`: null before approval; actual triple afterward.

```
python -B -m workflows.data_v1_final.pprime.strict_numerics15_qa_v1.metadata draft --request ACTUAL_REQUEST_JSON --output FRESH_CONTROL_DIRECTORY
```

With null decision this emits an unapproved plan and concrete review-only stage
fields, never a review template or runnable spec. After actual user approval,
Root creates a new request with its genuine decision triple and a fresh control
directory. The same command then emits the independent Root review template.
Root copies that template to a separate file, independently inspects all fields,
and changes only status to `APPROVED_FOR_EXACT_STAGE` and reviewer to `root`.

```
python -B -m workflows.data_v1_final.pprime.strict_numerics15_qa_v1.metadata finalize --draft ACTUAL_DRAFT_RECEIPT --root-review INDEPENDENT_ROOT_REVIEW
```

The resulting ordinary central stage_spec is for Root's existing queue helper.
No helper queries or submits Slurm. The exact runtime argv is
`PY -B -m workflows.data_v1_final.pprime.strict_numerics15_qa_v1.run --plan PLAN --startup-proof PROOF`.

## Synthetic CPU checks before user approval

Root may execute the exact three unittest methods in `test_v1.Boundaries` in a
separate central fixture-only CPU allocation. They exercise the protocol inverse,
new once/O_EXCL, absent or wrong decision rejection, and original pure rendering
of synthetic three-atom inputs. They import the frozen engine as a renderer only,
assert `NATIVE is None`, never initialize/invoke, and never read scientific DATA.
This is not authorization of any native call. During the real authorized job the
same three methods must all pass before the original15 input/result bodies open.

## One allocation, bounded output and once domain

After fresh admission and pure tests, the parent reuses the original actual-byte
renderer bridge to derive new targets in the allocation. It verifies bit-identical
coordinates and atom order: MOPAC changes only its first keyword line, xTB input
files stay byte-identical. It never calls the source LMDB reader.

The fixed new ledger is artifacts/pprime_strict_numerics15_qa_v1/qa_once_ledger.
An O_EXCL claim includes candidate protocol triple, original prepared triple,
old qa-ID, actual job, fresh proof and actual user decision. Claims are made before
dispatch and are never deleted, reused or automatically retried. Any lost result
is consumed/UNKNOWN. A new output directory or new approval cannot reuse a key.
The fixed candidate locator and inverse check prevent an arbitrary alias or
changed scientific protocol from evading this same-protocol once domain.

Each of at most15 processes calls the frozen `initialize_worker` with the explicit
candidate protocol and directly calls the original `NATIVE.invoke` exactly once.
Its original900-second timeout remains enforced, and dispatch requires enough
allocation wall time for that full timeout. No new monkeypatch is installed.
The existing engine's established capture/deferred-cleanup lifecycle is reused.
Live worker continuation requires the same admitted parent PID/startticks, boot,
UID, job, node and unchanged source/plan/protocol/user pins; it is not a stale
proof or another-parent freshness exception.

Output partitions are15*112MiB plus parent256MiB =1936MiB, below whole2GiB.
Each worker prepays32MiB for its original16MiB SQLite/raw journal overlap.
The frozen RawSink enforces its original cap, full sync commit and actual content
readback. Other new files are charged cumulatively by exact bytes plus file
overhead before stable atomic publication. No budget recursively stats an output
tree, so another worker deleting a SQLite-journal cannot trigger the old race.
Only this job's process subtree is observed. Actual RSS64GiB is an algorithm soft
limit, not a Slurm memory request; MemAvailable must remain at least4GiB and15%.
Physical free minus full2GiB must retain200GB, separately from fresh central
account-quota and Root's registered-cap admission. Pressure stops new dispatch;
inflight calls drain naturally, with no new cancellation or signal mechanism.

## Interpretation limits

All original15 FAIL and original qa02/qa08 WP5 unknown states remain unchanged.
New call results retain actual return/termination, parser, source bytes, raw
container, original cleanup boundary and independent readback. Missing fields
or technical failures are UNKNOWN/HOLD and never replaced.

New repeats/R1/P90 use original outer-arm rotation matrices and original frozen
measurement/covariance functions, not nested historical case.arm. PM7/gradient
own frame/order and xTB same-input gradient/SP companion controls retain the
original gates. Historical source and1802 same-arm values are compared as
observations; changed-settings agreement does not become an invented gate.
`limited_new15_predeclared_QA_checks_all_pass` records this bounded experiment
only. Receipt C0 means technical closure, not scientific release. No outcome
changes masks/tolerances/production or authorizes20-molecule all12-task QA,
2000 pilot, pool or full generation. Terminal allocation accounting is appended
by Root afterward, including failures/startup; no pending cost is called final.
