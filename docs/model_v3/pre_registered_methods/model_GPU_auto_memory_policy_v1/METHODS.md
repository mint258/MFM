# Shared development-GPU automatic-memory admission v1

This is one source/metadata helper used by the new A routing and Native
operational wrappers. It has no CLI, scheduler, dispatcher, process loop, model,
SDK or data reader. The actual user approval and original plan are protected
rawrefs in source_pins.json. School-server/formal pretraining is outside scope.

New jobs omit fixed Slurm memory directives, argv and inherited SBATCH_*.
They do not request mem=0, exclusive, overcommit or oversubscribe. Scheduler
defaults are actual observations, never a finite physical-memory guarantee.
The unchanged software/RSS pairs are A64/56GiB and Native32/28GiB.

The existing storage registry receives only the optional top-level
GPU_software_memory map. Each entry has a unique registration_id, actual Root
source/package rawrefs, node/UUID and unchanged software/RSS budgets. Existing
reservations, principal, remaining bytes and storage accounting are untouched.
Mutations and snapshots use the exact existing Native/root_phase registry lock,
through the already frozen auto-R2 source_guard delegate. No second registry or
mutex is created. Do not call assess while holding this non-nested mutex.

make_registration / validate_registration / put_registration implement the one
record shape. PRE_SUBMISSION explicitly has job_id=None and
actual_submission=None. It conservatively reserves software budget until Root
reconciles it; it is never a fabricated job. SUBMITTED binds an exact3ref to the
actual Root receipt with status SUBMITTED and its real job field. The accepted
job_id_field is job_id or Native actual_sbatch_job_id. Worker self-admission
requires the actual SUBMITTED record and exact SLURM_JOB_ID. Terminal records
remain SUBMITTED; a fresh node queue lacking their job does not count them as
active. There is no CLOSED state, automatic release, retry or rebinding.

Callers register PRE under the original lock, release it, then call assess.
For the one real submission, hold that same lock across sbatch, actual receipt
write and SUBMITTED registration update; worker assess waits on it. All caller
freshness and one-use rules remain mandatory. Submission outcomes with unknown
job identity retain their PRE intent for Root reconciliation.

assess(node_raw,squeue_raw,meminfo_raw,*,node,software_budget_bytes,
rss_limit_bytes,registry_path,current_job_id=None,current_reservation_id=None)
consumes actual source-bound observations. squeue is the existing target-node
five columns %i|%u|%t|%m|%C. It snapshots registered roles under the original lock.
Unknown active own roles HOLD rather than inventing a software budget or
assuming an unregistered role is CPU-only. A registered automatic role counts
its software budget even if scheduler declaration is zero/default/all-node.
An old registered fixed role counts max(software,finite declaration) once.
Each other-user positive finite declaration counts once; unknown/zero/unparsed
other-user declarations are listed explicitly without finite-guarantee claims.
Observed AllocMem is retained as an observation rather than treating an
automatic all-node/default value as a second software budget.

The strict gate is new software plus registered concurrent own software plus
other PRE intents plus other-user finite declarations <85% of node RealMemory.
MemAvailable separately must cover the new software budget plus15% of node
RealMemory. Integer-byte comparisons preserve these original percentages.
Self is counted once at Root and worker. CPU availability, GPU85%, real UUID /
process / original UUID lock, identity, RSS, dual2GiB, quota/all storage holds,
wall clocks and every scientific gate stay with their original caller/supervisor.

legacy_bindings.json freezes the real original Native slot026/job4524782 on
node21/22e with source-bound fixed32GiB/RSS28GiB provenance. It is a compatibility
registration only, not a claim that the old job ran with automatic memory. It
is counted only when the fresh queue actually contains that job. Live Native
source, request, PID, counters, hold and scientific stream are not changed.

Publish and read back these exact five blobs under
docs/model_v3/pre_registered_methods/model_GPU_auto_memory_policy_v1/ before
any consumer submission. Consumers bind the actual pins SHA and publication.
No future receipt, job, result, default ReqMem/TRES or physical allocation is
invented here. Source tests cover operational arithmetic/schema only; author
has not executed Python, AST, Bash, project tests, SSH or Slurm.
