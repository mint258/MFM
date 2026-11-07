# Pprime formal sharded day v3: private formal resource observer

This isolates the observed RSS16GiB stop inherited from the small Marcel tool.
Root selected a finite64GiB software working budget and RSS56GiB stop for formal
16-worker Pprime under the user's authorization to fix resource issues. These are
new operational limits, not a claim that the data guide specified56GiB or that
Slurm allocated/guaranteed64GiB. No sbatch memory request is introduced.

resource.Budget.check is copied from marcel_drugs_keys_main_v1/runtime.py with
only rss>=16<<30 changed to rss>=self.RSS_LIMIT_BYTES. The parent identity checks,
1s cadence, original parent-plus-direct-children RSS observation, MemAvailable
>=max(4GiB,15%node), finite wall/drain and current200GB free-space checks remain.
io.Budget inserts this private subclass immediately before the common observer
base in the instance MRO. Original Preparation.Budget.check calls its super()
through the private observer, then performs the original quota/lease/identity/all
future200GB checks. Original v2 io.Budget.check still runs local NodeBook/space and
the same2x cost gate. Only its constructor is copied to bind the new scope key;
its original roles, local bookkeeping and shared output caps are inherited.

run.py differs from v2 only in module imports. prepare, hash_one, worker and
publication are the actual unchanged v2 objects. No UPDATE rewrite, new QM,
retry mechanism, scientific filter or numerical keyword is introduced. The
original3 Source test methods remain; only imports/origin location and4 necessary
resource/MRO assertions are adapted. Root runs these in the actual next Parent.

Frozen-v2 globals compatibility reviewed from Source:
- prepare.hash_block calls the old source_session/continuation, which bind only
  actual UID/PID/ticks/job/boot/node/16CPU/source pins and carry the exact new
  plan/review references; neither checks a v2 module/scope literal.
- hash_initialize/hash_one bind the original protocol and use NoInvoke; their
  budget callback is the actual passed v3 Budget instance.
- the reused worker initialize/one calls v2 precision, which checks unchanged
  release/precision/mode fields, not a v2 resource key or module. Physical once
  key, ledger and prepared-header identity stay original.
- publication.Pool intentionally remains the v2 object using the same existing
  PREP32GiB and EXEC32GiB pool roots and CAS authority. The new Parent metadata
  output root is artifacts/pprime_formal_packed_sharded_day_v3; no new pools.

Metadata keeps V2 wire schemas, partition/header acceptance and stage shape.
New resource scopes are pprime_formal_shared_pairs_prepare_v3,
pprime_formal_assigned_pairs_execute_v3 and pprime_formal_readonly_publish_recovery_v3.
Use new exact root carveouts/reviews for those keys, the same existing provider
identities, release/partition/pool authorities, and unchanged future reservations.
Existing v2 actual-C0 prepared headers are accepted by the inherited bootstrap.

Root-only pure metadata helper root_metadata.py is an isolated copy of
control/pprime_dual_parallel_20261030/construct_sharded_batch.py. New draft paths
and imports target v3; closed_preparation accepts only actual registered v2/v3
producer+scope pairs and checks each version's exact original scope_parameters.
It preserves all original C0/sacct/UID/argv/source3/hash-worker closures and
registration links. It does not autosign generic stage reviews, read science
DATA, submit Slurm, create a producer, or retry physical records.

After Root installs this new package, existing batch config schema/CLI can be
used with fresh batch_id/output/slot metadata and new scope carveouts:

    python -B -m workflows.data_v1_final.pprime.formal_packed_sharded_day_v3.root_metadata prepare-batch --inputs CONFIG --output FRESH_CONTROL
    python -B -m workflows.data_v1_final.pprime.formal_packed_sharded_day_v3.root_metadata execute-batch --inputs CONFIG --output FRESH_CONTROL --approve-actual-c0
    python -B -m workflows.data_v1_final.pprime.formal_packed_sharded_day_v3.metadata finalize --draft DRAFT --root-review ROOT_REVIEW

Root supplies actual closed preparation seven-reference registrations (v2 and/or
v3) for execute-batch, only pending assigned headers for fresh preparation,
actual available CPU nodes, exact new Root reviews/carveouts, finite providers
and all prior failed/UNKNOWN/live future budgets. Original scopes/source/results
and all running tasks stay unchanged. No helper or Slurm job was run by this
Source-edit agent; no import/compile/test/science DATA read or data SHA was done.
