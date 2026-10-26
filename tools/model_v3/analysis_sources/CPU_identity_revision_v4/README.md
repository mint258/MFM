# CPU supervisor revision v4: prepared, not executed

This independent package preserves OLD/run_cpu_test_supervised_v2.py,
OLD/run_cpu_supervised_v3.py and regression_control_v4 byte for byte. It has no
Slurm submission or test result yet. Job 4521159 remains FAILED without a test
summary. The exact identity field that changed was not recorded; fork-to-exec
argv transition is a hypothesis, not an established cause.

The fixed original nine identity keys remain mandatory. The wall-clock created
value is diagnostic only. A changed identity is written with before/after full
frames and changed_keys, fsynced before raising. Exception cleanup never rewrites
observed identities. The original stop_recorded rechecks the complete identity
before individual signals. There is no killpg and no unregistered PID signal.

Strict mode adds this evidence/cleanup behavior without exec exemptions.
Opt-in pytest4 mode admits exactly four direct, source-declared pytest roles:
the worker publishes an immutable, atomic/fsynced manifest before spawning, then
uses Popen + wait with the original shard grouping, argv, cwd and streams.
After Popen returns, it captures the exact child's actual kernel identity and
publishes a no-replace/fsynced exec receipt. The supervisor independently derives
the same four commands from the frozen assignment. It binds job, UID, parent
PID/identity, child PID/start_ticks, boot ID, PGID/SID, cgroup, full argv and all
source/plan/manifest raw references before enrollment.

A declared child is pending accounting evidence until receipt plus a fresh
complete identity match. Pending processes are included by the unchanged owned
process-tree RSS monitor and all output/private/wall budgets. Their control
files are inside the measured output; identity events are outside it and added
to total accounting. No pending process has signal authority. Only a declared
parent-argv clone to the exact declared target is an enrollment transition;
PGID/SID/allocation/parent/birth differences or undeclared argv fail. The
30-second pending deadline is fixed. Repeated stable frames do not prove that
exec has completed and never enroll a fork-only worker. Genuine fork-only
workers are outside this four-exec protocol: no automatic fork_only role is
accepted. Other descendants retain the old strict first-capture behavior;
a later unknown exec still fails. This scope does not purport to solve every
possible nested fork/exec workload.

At failure, newly found descendants are quarantined without granting authority.
Only complete MATCH identities are signalled. Changed/pending/unreadable live
identities remain FAILED and in remaining; empty authorized cleanup is not proof
of total cleanup. GONE/EXITING is recognized independently. The private storage
module stops sampling without deleting its roots. Root or the existing Slurm
allocation timeout may close unresolved processes; such outer closure needs
its own actual receipt. The package does not call scancel.

The new preparer retains the original assignment, source scope, admission,
capacity and submission algorithms. Its narrow differences bind the new worker
and all package/source inventory files as controls. It does not alter old plans.
The new template keeps the real scan_v2/deps PYTHONPATH and original 16 CPU,
32GiB request, 28GiB RSS bound, 1100s wall, 2GiB output and reserves. No new model
or scientific parameters are present.

Root execution interfaces (commands have NOT been run here):

    python -B -m pytest /share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/cpu_supervisor_revision_v4_source/test_cpu_identity_revision_v4.py -q -p no:cacheprovider --junitxml=NEW.xml --basetemp=NEW_tmp

The planned count is 45 cases: metadata/tamper/strict-key oracles, actual atomic
publication and fsync, unchanged fixture census, a real owned fork -> exec
transition with real /proc and RSS measurements, and a real Popen receipt plus
strict cleanup. The three Linux process/diagnostic cases must run in Root's owned CPU Slurm
allocation. They submit no jobs and never touch other processes. This is a
planned count, not a collected/passed claim.

For a new eight-part run, Root invokes the new preparer with the same existing
baseline/external-python/workflow-config arguments and a fresh label:

    python -B N/cpu_supervisor_revision_v4_source/prepare_regression_identity_v4.py --source-pins N/cpu_supervisor_revision_v4_source/source_pins_v1.json --source-pins-sha256 ACTUAL_MACHINE_PIN_SHA --action freeze --label native_s_precision_postmerge_identity_v4 --tree PROJECT/MFM_model_v3 --scheduler-script N/cpu_supervisor_revision_v4_source/run_regression_identity_v4.sbatch [the existing exact baseline/external-python/workflow-config arguments]

All eight parts must be newly executed; old passed slices do not establish this
new runtime's completion. Original regression_control_v4 validation accepts the
new runner through its explicit contract runner ref; no historical schemas or
old sources are rewritten. The new supervisor report schema is
model_v3_CPU_supervisor_revision_v4; normal status/exit_code/job_id/command/
first_failure/remaining fields remain explicit. Identity event schema is
model_v3_CPU_identity_event_v4. Manifest/receipt schemas are independently
versioned v4, not data-line contracts.

N means /share/home/zixiao/descriptor_analysis/runs/model_v3_20261026.
OLD means the sibling model_v3_20261025; PROJECT is the server project root.
source_pins_v1.json excludes itself to avoid a recursive hash; its exact raw SHA
must be bound by the CPU request, supervisor CLI and fresh control plan.
