Optional exact P-prime radix part execution
==========================================

Plan flag: `shard_radix_typed_parts: true`; default OFF. Root may opt in only
for a future pass/resume after the active pass closes. This change neither edits
the actual plan nor restarts an active process. PM7 is untouched.

Only normalization_quantiles and diagnostic_median_MAD use flat whole-existing-
part pool tasks. Each task calls the same P-prime source reader and unchanged
Original._group_pass bytecode with original group_index/source_job_id. All part
entries and per-row F64 operations stay identical. TSQR element_reference and
floating normalization_moments always retain the original unsplit dispatch.

A stage's radix_parts_checkpoint.json binds the active stage reference, original
logical group identities and complete ordered typed-part references. Completed
shards persist their actual submitted part binding. On restart, closed logical
groups dispatch nothing; closed shards are reused without rereading typed data.
Unclosed interrupted shards are not claimed complete. Completion order may vary;
merging always uses the original part order, each index exactly once. A changed
stage or reordered part plan is rejected. No new hashes, receipts or QA pass.

A single-part group validates and returns its original bound report reference
without creating radix_merged or opening/rewriting a histogram.

Group merge rejects any nonempty TSQR/moment/joint scientific state or noninteger
side output. Only histogram n, field/role/task/series counts are added as Python
integers. The unchanged finish_stage therefore receives exactly the same integer
masses and keys; original Fraction rank selection and F64 results are unchanged.
The normal original logical-group report order and format remain; reports add
part/stage references for producer recovery. pid is coordinator metadata and
elapsed_seconds is max shard elapsed, excluding merge/queue time.

The existing Runtime guards new shard roots/checkpoints and integer merge reads/
writes under the already budgeted shared output. Extra shard histogram prefix
rows plus the merged histogram consume additional producer-output space; they
are not a new raw/typed-data copy. There is no row-group split, second source
scan, benchmark, new dependency or node-root temporary storage.

Only the new synthetic fixture, Root runs once in its actual safe-temp parent:
python -B -m unittest workflows.data_v1_final.labels.window2_pprime_statistics_v1.test_radix_parts.RadixParts.test_original_golden_exact_refinement_and_interrupted_reordered_resume

The one method compares every quantile/median/MAD refinement and final original
finish_stage result against the actual unsplit Original kernel on synthetic
packed typed Parquet. It also checks interrupted/reordered completion, duplicate
and conflicting bindings, changed-input refusal, float-state refusal, closed-
group/shard reuse, and the TSQR/moments unsplit selector. Prior tests stay passed.