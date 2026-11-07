# N1 prepare32 v4: fresh same-storage account quota, unchanged science

Registered v3 job4521407 actually FAILED3:0 after39 seconds on16 CPUs
(624 allocated core-seconds), before any physical validation dispatch/UFF/QM.
Its two mother audits conserved all5105 rows. Runtime quota returned1 with no
retained stdout; a separate new node13 follow-up also actually returned1 with
empty stdout/stderr. These are missing resource observations, not science failure.
Keep both original runs/results/source and all costs unchanged. The measured
v3 reasons were FULL/missing65, UFF_UNSUPPORTED176, baseline-count-not1 233,
validation-unstarted-after-observed-STOP4631. Neither this new version nor that
role count retrospectively proves the old5040 hardcode's provenance.

Only the resource observation path changes. New outputs are under
`artifacts/conformers/n1_pprime2_pilot_v4`; the logical once ledger stays exactly
`artifacts/conformers/n1_pprime2_pilot_v2/once_ledger`. Existing/unknown attempt
keys block new dispatch and are never removed. `core.py`, `test_core.py` and
`__init__.py` remain complete byte copies of v3/v2. Original PM7 pointer1,
accepted real Sprime baseline1, UFF desired2, actual candidate10/cap300,
seed/task ID, ETKDGv3, graph/atom/stereo/fixed-index Kabsch/0.5A selection,
MinimizeTrajectory(2000,E1e-6,F1e-4), optimizer events/failure prefixes,
geometry SHA/readback and ten original tests remain unchanged. Scientific task,
baseline, checkpoint, event and packet schemas remain V2. No geometry or PM7
pointer is cloned. No retry/seed extension is introduced.

The exact actual Root count review stays2857B/SHA256
`df97851fdb4a03bcdc11d43b2e27abfc54dca964ceb326e15c1a34e598f70dbc`.
Count5105 still derives from actual4521326 and its same perMol source pins,
not from a newly guessed population. The original source/effective-role and
Sprime-status/usable-count eligibility chain and full5105 before/after conserved
audits remain. PM7 `S_usable_conformers` and original Sprime `Sprime_conformers`
stay separately labeled; catalog retains original producer/closed-definition
pins. All mothers/tasks remain common=false, pilot_membership=false,
production_membership=false and final_common_reference=null. Original Pprime
15FAIL and2000/full HOLD stay. Count correction and quota review do not release
production or authorize any extra scientific call.

## Independent finite metadata publisher

`quota_provider.py` is a new Root-started metadata process on Main login sonmi,
UID1278, endpoint202.38.247.57:22. It never SSHes, submits jobs, starts science,
starts itself, or revives the old completed S-repair publisher. Root starts it
explicitly after source freeze and an actual same-storage probe/review. Lifetime
is at most24h, refresh30s, whole output at most64MiB. The directory must be new
and exactly the reviewed location under this run's control directory.

Each observation preserves actual quota argv/returncode/stdout/stderr, times,
endpoint/UID/host, live findmnt result and fresh shared-marker verification.
Current source is narrowed to actual Main login `/share /dev/sda1 xfs /` and
compute-0-13 `/share/home nfs:/share/home nfs4 /`. The complete two-line compute
findmnt also contains `/share/home systemd-1 autofs /`. `parse_mount` keeps every
raw row and accepts exactly one non-autofs active row; only matching-target
systemd-1/autofs rows are overlay metadata. A new same-path `df -Pk` raw query
must have exactly one row whose source/target match the active mount. Two/zero
active rows, malformed/failing/incomplete commands or df mismatch reject. Fresh
df total must remain31251898368KiB, the actual common physical total; df available
bytes are never used as account quota. Marker inode12957712902/UID1278/213B/
mtime1793029110467007740 stay fixed; login device2049 and NFS device53 are local
identities and are not required equal.
Parser requires return0, no stderr, exact user zixiao/UID1278 header and exactly
one finite quota row for the reviewed login filesystem. Numeric blocks are KiB;
free bytes are(minimum positive soft/hard quota-used)*1024. Empty/return1,
wrong device/user, duplicate row or no finite limit fail. No local df/statvfs
fallback is provided. Large data bodies are never read by the publisher.
An unexpectedly oversized command result is explicitly marked incomplete,
retaining actual byte counts/SHA and bounded prefixes; it cannot become a valid
quota/mount observation. Ordinary bounded observations retain the complete raw.

Immutable identity binds actual pid/start_ticks/login boot_id, exact full CLI,
source pins, endpoint/UID/host, start/expiry and Root review. Each snapshot is
O_EXCL-written, flushed and fsynced. An O_EXCL temporary latest pointer containing
only actual immutable references is atomically replaced and its directory
fsynced. A256KiB terminal reserve is kept inside64MiB. On quota/mount/marker error,
requested stop or normal expiry, a new ERROR/STOPPED/EXPIRED terminal snapshot
replaces latest. Actual failed-query stdout remains in its immutable observation.
No number is reconstructed for job4521407.

Root CLI, with literal actual paths and no invented authority SHA:

```
MainPY -B REPO/workflows/data_v1_final/conformers/n1_pprime2_pilot_v4/quota_provider.py
  --review ACTUAL_ROOT_SAME_STORAGE_REVIEW
  --output EXACT_NEW_REVIEWED_PROVIDER_DIRECTORY
  --max-seconds FINITE_INTEGER_LE86400
```

Root review schema is `ROOT_MAIN_N1_SAME_STORAGE_QUOTA_PROVIDER_REVIEW_V1`,
status `APPROVED_FOR_EXACT_SAME_STORAGE_PROVIDER`, reviewer root. Required fields:

- endpoint202.38.247.57:22, uid1278, run_root, login_node sonmi;
- actual mapping probe_reference included in actual small evidence_references:
  `control/n1_same_storage_mapping_probe_v1.json`,8195B/SHA256
  `d7046a46882617aef2ffa3708ff4249a57828fea7aee3c62b24a2c1b324d714d`;
  also include Root's actual `control/n1_nfs_hostname_resolution_v1.json`
  reference, automatically pinned by Root. It records nfs and sonmi resolving
  to the same10.1.1.1. No future DNS hash is inserted;
- login_quota_device and exact login_mount{target,source,fstype,fsroot};
- compute_mount_by_node mapping exactly the actually probed compute-0-13 to
  `{target:'/share/home',source:'nfs:/share/home',fstype:'nfs4',fsroot:'/'}`, and
  same_shared_account_quota_applies_to_all_listed_compute_mounts=true;
- actual shared marker_reference<=4096B and original count-correction reference;
- provider_source_references with exact current contract.py/quota_provider.py
  triples; publisher_output_dir is a new literal control subdirectory;
- policy MAIN_LOGIN_SAME_STORAGE_REVIEWED_REFRESH30_FRESH120_POLL60,
  refresh_seconds30, maximum_age_seconds120, cpu_poll_seconds60,
  maximum_runtime_seconds integer1..86400, whole_provider_output_cap_bytes67108864,
  quota_reserve_bytes200000000000, quota_units KiB,
  local_df_is_not_account_quota=true.

There is no authority template populated with future probe/source/output hashes.
Root creates the real review from actual source pins and observed mapping. The
review's marker bytes and probe are metadata; no scientific body is included.
Source source/contract pins exist before the review is written, avoiding a hash
cycle. The mutable latest pointer is not misrepresented as an immutable request
data pin: only its reviewed namespace/source/immutable observation chain is used.

## CPU consumption and exact stage interfaces

Each new request pins the actual review and its source/probe/marker references.
Admission still uses unchanged Main cpu_auto_memory_queue_v2 actual primary,
complete argv, source, UID/node/boot/16CPU/no_mem fresh proof. No fake login proof
is passed as a CPU identity. Parent-only resource observation reads the provider
every60s, freshly checks its own reviewed output mount/marker, validates immutable
identity/snapshot SHA, exact review/source/user/mount bindings and raw quota, and
requires snapshot age0..120s and unexpired finite identity. Identity replacement
or sequence rollback rejects. No direct compute quota query is retried.

An observed terminal/error/missing/stale provider stops new dispatch and naturally
waits for running work. A crash that cannot publish terminal is detected by the
120s freshness limit at the next60s poll; instantaneous remote-process liveness
is not claimed. Source keeps all actual memory/RSS/wall/storage checks. Account
free space conservatively reserves the full8GiB task cap, provider64MiB,
pending/inflight output and admin reserve, and still must leave200000000000B.
No memory size/exclusive/85% admission is added. Every failed/cleanup core-second
remains in accounting; cost1.5 is report-and-continue.

Preparation argv options are exact and ordered:

```
MainPY -B REPO/workflows/data_v1_final/conformers/n1_pprime2_pilot_v4/prepare_cpu.py
  --formal-config REPO/configs/data_v1/conformers/formal_v1.json
  --root-preflight ACTUAL_NEW_CPU_PROOF
  --quota-provider-review ACTUAL_ROOT_SAME_STORAGE_REVIEW
  --output RUN/artifacts/conformers/n1_pprime2_pilot_v4/prepared_v1
```

Scope key n1_pprime2_prepare32_v4, literal contract.PREP_SCOPE, analysis,
pilot=false, BOUNDED_METADATA_PREPARATION, CPU16/no_mem, finite wall<=48h,
whole output8GiB. Same23 full bodies plus original small metadata are freshly
verified on actual CPU. No LMDB/body reading occurs on login. All5105 mothers
and pending/exclusion reasons survive, then fixed-hash32 is selected only after
original physical PM7/real baseline validation. New outer metadata schemas areV4;
the task/science schemas remainV2. `io.prepare_input_references(formal_path,
quota_provider_review_path)` is metadata-only and enumerates source/input
locators, including inherited v1/v2/v3 pins, count evidence, two usability
definition pins and actual provider review/probe/source/marker pins. Root adds
current central/policy/scope references. The namespace now has11 source files.

After real prepare C0 and actual standard parent accounting, runner options:

```
MainPY -B REPO/workflows/data_v1_final/conformers/n1_pprime2_pilot_v4/run32.py
  --prepared ACTUAL_V4_PREPARED_JSON
  --prepare-accounting ACTUAL_STANDARD_PARENT_ACCOUNTING_CLOSURE_JSON
  --root-preflight ACTUAL_NEW_CPU_PROOF
  --quota-provider-review ACTUAL_CURRENT_ROOT_SAME_STORAGE_REVIEW
  --ledger-root RUN/artifacts/conformers/n1_pprime2_pilot_v2/once_ledger
  --output RUN/artifacts/conformers/n1_pprime2_pilot_v4/pilot32_v1
```

Scope key n1_pprime2_pilot32_v4, literal contract.SCOPE, conformer,pilot=true,
BOUNDED_PERFORMANCE_BATCH, CPU16/no_mem/8GiB, finite wall<=48h. Bind actual task/
baseline/population/aggregates/prepare-accounting/raw-sacct references. Provider
may have a new finite lease for the later runner, independently Root-reviewed;
it does not change task identities. No future ready references are manufactured.

Original ten tests retain truthful absolute v2 imports and are inherited science/
identity tests; new metadata is not claimed covered by those ten. Six separate
synthetic resource tests in test_quota_provider.py cover exact KiB/finite limits,
failed/empty query, user/device/duplicate/unbounded row, freshness/expiry/terminal,
and mount/marker/source/process/raw recomputation boundaries. The sixth uses
the real autofs+NFS two-line form and actual df shape/counts, requiring successful
unique-active selection and rejecting two/zero active rows, source/target
mismatch and failing/incomplete df. They call no
subprocess or science. Root must execute actual checks on an authorized CPU;
no test or execution result is claimed by this source-only delivery.

This source does not certify scientific PASS or release full5105 generation.
