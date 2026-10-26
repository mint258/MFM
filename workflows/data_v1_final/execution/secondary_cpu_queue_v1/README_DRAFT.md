# Alpha foreground metadata controller — unregistered source draft

This package is independent of the main cluster's queue/proof namespace. It is
source only: its author ran no Python, fixtures, SSH, Slurm, science or data-body
read. Root reviews/copies these sources before any real controller invocation.
No previous15 checks are changed. test_metadata.py contains2 optional separate
pure checks for the actual colon-field and whole-minute boundaries; they are
not execution or scientific acceptance evidence.

Only alpha UID1264 at218.192.171.238:22, login hostname sonmi, is supported.
The root is /gfshome/alpha/codex_data_v1_20261026. Permitted CPU nodes are
compute-0-1,compute-0-3–6,sonmi1. Every task is one node/one task/16CPU,
whole-minute wall<=48h, partition cpu, no requeue, no requested memory,
exclusivity or GPU. All inherited SBATCH_* variables are removed from the
actual sbatch environment; only their names are retained. Actual scheduler
defaults and SLURM_MEM_* observations are recorded, not relabeled64GiB.

The foreground controller supports:

- acquisition: actual SECONDARY_SOURCE_ACQUISITION_CPU_SPEC_V1 plus
  SECONDARY_EXACT_SOURCE_DEPLOYMENT_V1, exactly matching deployed plan/review.
- portable16: actual PORTABLE_SECONDARY_UFF_CONTROL16_DEPLOYMENT_MAP_V1,
  existing16 software QA only, population added0, two missing forbidden,
  environment READY rather than compatibility PASS.

No producer's scientific body is opened, statted, hashed, unpickled or parsed.
Portable task bytes/SHA remain locators whose runtime verification belongs to
the worker. Every small science/controller source and required metadata target
is actually hashed locally. Main origin_reference and Alpha target_locator
are separate, and equal SHA/bytes do not by themselves claim installation.
Old main absolute paths inside historical provenance are never opened here.

## Source pin record and deployment

After Root static review, the main-side small source helper records exact
current source bytes. This is metadata under the user's existing authorization,
not a new user approval flow:

    $MAIN_PY -B -m workflows.data_v1_final.execution.secondary_cpu_queue_v1.source_manifest \
      --reviewer root --output ABS_NEW_MAIN_CONTROLLER_REVIEW.json

It emits ROOT_SECONDARY_CPU_CONTROLLER_SOURCE_REVIEW_V1 with
status=APPROVED_FOR_METADATA_CONTROL_ONLY, reviewer=root, endpoint/uid/run_root,
login_hostname=sonmi and sources=[{origin_reference,target_locator}]. Copy each
unchanged file to root/code/secondary_cpu_queue_v1/<name>.py using Root's actual
SFTP connection. Copy the review JSON to a new Alpha control metadata path.
The helper's target_current_bytes_verified=false is deliberate. Actual Alpha
source_review checks all deployed target hashes and the exact *.py file set.
Source/helper/test files are all included; no extra *.py file is silently used.
Copying bytes is distinct from a scientific environment or compatibility test.

## Observed gfshome storage scope

Do not apply the observed quota for /dev/sdb to the separate Gluster gfshome
mount. Root confirmed that current tools report no matching independent user
quota for that mount; no claim excludes an unobserved project quota. This is
the current authorized effective-free basis, not an extra blocker or request
for user confirmation. Record the observed mount/fs type and actual evidence.

An optional foreground metadata command obtains raw observations:

    cd /gfshome/alpha/codex_data_v1_20261026/code
    $ALPHA_PY -B -m secondary_cpu_queue_v1.controller storage-evidence \
      --output /gfshome/alpha/codex_data_v1_20261026/control/NEW_storage.json

It records statvfs, findmnt, df and quota commands with their actual stdout,
stderr, returncode and time. Quota failure is retained as a failure, not a fake
unlimited quota. This run explicitly filters findmnt to fuse.glusterfs because
the same /gfshome target also has an autofs systemd-1 entry. Exactly one actual
Gluster row is selected; the raw filtered response and selection basis remain.
Root's small scope record has this shape:

    {
      "schema":"ROOT_SECONDARY_GFSHOME_STORAGE_SCOPE_V1",
      "status":"OBSERVED_CURRENT_MOUNT_AND_QUOTA_SCOPE",
      "reviewer":"root",
      "endpoint":"218.192.171.238:22",
      "uid":1264,
      "run_root":"/gfshome/alpha/codex_data_v1_20261026",
      "mount_target":"ACTUAL_FINDMNT_TARGET",
      "filesystem_type":"ACTUAL_FINDMNT_FSTYPE",
      "no_matching_mount_user_quota_reported":true,
      "statvfs_is_current_effective_free_basis":true,
      "independent_project_quota_absence_claimed":false,
      "out_of_scope_quota_devices":["/dev/sdb"],
      "quota_scope_explanation":"Actual observed device/mount distinction.",
      "evidence_references":[{"path":"ABS_ACTUAL_ALPHA_SMALL_EVIDENCE","bytes":0,"sha256":"ACTUAL_SHA"}],
      "additional_task_output_reservations":[]
    }

Place actual pins in this example; do not use its placeholder values. Controller
admission must match the live mount target/fs type, uses current f_bavail*frsize,
subtracts every registered pending/active/unknown-submit whole output cap plus
the current cap, and retains200000000000 bytes. Terminal parent caps are not
subtracted again from space already consumed. Other task reservations outside
this controller can be explicitly recorded as entries
{metadata_reference,whole_output_cap_bytes}. An unknown submission never
becomes a guessed zero reservation. No memory declaration percentage is used.

## Root held submission and independent proof

On Alpha login, with no SLURM_JOB_ID in the controller's environment:

    cd /gfshome/alpha/codex_data_v1_20261026/code
    $ALPHA_PY -B -m secondary_cpu_queue_v1.controller submit \
      --producer acquisition --reviewer root \
      --input ABS_DEPLOYED_ACQUISITION_SPEC \
      --deployment ABS_DEPLOYED_ACQUISITION_MANIFEST \
      --authority ABS_EXACT_DEPLOYED_PRODUCER_AUTHORITY \
      --controller-review ABS_DEPLOYED_CONTROLLER_SOURCE_REVIEW \
      --storage-review ABS_OBSERVED_GFSHOME_SCOPE \
      --node compute-0-1 --job-name new_safe_name --wall-seconds 3600 \
      --output /gfshome/alpha/codex_data_v1_20261026/control/secondary_cpu_queue/NEW_NAME \
      --max-poll-seconds 90

For portable16, change --producer portable16, use --input ABS_DEPLOYMENT_MAP,
omit --deployment, and add --startup-proof ABS_NEW_ALPHA_PROOF and
--science-output NEW_ALPHA_ROOT/outputs/CHILD. Use the exact deployed portable
authority path from the map. Its finite wall must be a reviewed whole minute
and within the actual authority/map maximum. Root's explicit invocation creates
the exact independent SECONDARY_PORTABLE_UFF_CONTROL16_ROOT_SCOPE_V1, with
script/map/full producer argv/wall bound; it does not grant science acceptance.

The controller writes a new request and generated script, persistent job-name
claim and submission intent, then executes exactly one held sbatch. No retry
follows a rejection, ambiguous response or timeout. A timeout is UNKNOWN and
requires Root to reconcile real scheduler/accounting records. Scripts have
no memory/GPU/exclusive flag. The controller checks the exact owned held
JobId/UID/name/script/CPU/partition/node/wall/NumNodes1 or1-1/no-requeue, checks
fresh>=16 free CPUs and whole-cap storage, rechecks held identity, and releases
only that single job. It never cancels or changes an unrelated job.

A gate runs inside the actual batch allocation for<=120s, printing every10s.
It only waits for this controller's atomic proof+ready marker and then execs
the exact original producer argv. It never creates a proof. This prevents the
portable worker's immediate proof read racing a post-release observer, and
preserves the worker's real __main__, sys.argv and executable checks.

After actual RUNNING, the controller uses the already verified passwordless
Alpha login->compute-node SSH route, BatchMode/StrictHostKeyChecking and ssh-n,
only to run the stdlib metadata probe. It finds the exact own gate argv,
UID/start_ticks/PGID/SID/cgroup+Slurm job environment, boot and actual node,
records memory defaults and fresh compute-side storage observations. The
job membership must be present in the actual cgroup or be independently
confirmed by the exact PID/job row of actual node scontrol listpids. The raw
cgroup is retained in both cases; environment variables alone are insufficient.
The
controller rechecks actual RUNNING after that observation and writes the
producer's independent startup schema atomically/exclusively, then publishes
the ready marker. Actual script and all controller source pins are retained.
The worker is not its own admission signer. No main UID/proof is reused.
Compute observed_unix_seconds is preserved in the proof. Login observation
time is a separate root_login_observed_unix_seconds field. The controller
does not subtract clocks across nodes: its own monotonic interval from probe
query start through proof/ready publication is bounded to90s. Producer-side
compute-clock freshness limits remain portable120s/acquisition300s.

Acquisition receives actual full scontrol text and fresh storage_observation;
portable16 receives the actual parsed job dictionary and its exact root scope
review, account_free_bytes, and raw quota query evidence. Fields containing
colons/slashes are parsed without polluting neighboring fields; duplicates
fail. Main source hashes and target locators never stand in for compute boot,
PID, storage or scheduler observations.

## Finite waiting, recovery of metadata control, and actual costs

Foreground heartbeats are emitted every10s even during a slow metadata query;
normal pending poll output is every5s. Polling is finite (5–1200s, default90).
No background observer or invisible service remains. If CPUs/storage are not
available the job stays held. A soft observation deadline records PENDING and
leaves the existing job unchanged, with no automatic cancel/resubmit. A gate
can fail its own120s timeout if Root does not resume observation in time.
All failures and startup-only parents still belong in actual accounting.

Root can explicitly resume only the same immutable submission:

    $ALPHA_PY -B -m secondary_cpu_queue_v1.controller resume \
      --output ABS_EXISTING_CONTROLLER_CHILD --max-poll-seconds 90

It revalidates source/request/script and the exact same job; no sbatch occurs.
A proof published without its ready marker is not silently repaired or
rewritten; Root reconciles that interrupted publication explicitly. No failed
data/science attempt is retried through resume.

Collect actual parent and steps after completion, including failed parents:

    $ALPHA_PY -B -m secondary_cpu_queue_v1.controller account \
      --output ABS_EXISTING_CONTROLLER_CHILD

This preserves raw endpoint-owned sacct fields, includes startup/wait/failure
allocation, and counts parent ElapsedRaw*AllocCPUS once. Steps are retained,
not summed again. Zero seconds are integer-floor observations. Current running
accounting is explicitly provisional. Acquisition's existing close_actual_v1
can consume the emitted accounting-evidence JSON; Root still accounts unknown
submission outcomes or attempts without producer receipts. Free monetary
compute does not imply zero physical cost. Proof publication is never a
download, software-compatibility or scientific success receipt.
