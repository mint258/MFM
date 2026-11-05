# Global seed SD and decision evidence

Implementation only; no actual global SD anchor, scientific comparison, recipe or
B* is selected by this work. D-1 through D-6 remain unobserved. This work does not
claim that a model-side metadata schema is the data line's authoritative format.
The existing SoM binary tasks satisfy classification coverage by the user's
2026-10-25 decision; no new ExpansionRx labels are introduced.

The source is isolated in `model-v3-decision-evidence`, initially based on
`dd6cbafb5f6bc86fb064fedfab313c7983003bee`. Existing modules, APIs, training
defaults, frozen configurations and scientific results are unchanged.

## Audited gaps and boundary

| Required work | Audited source / finding | This change |
|---|---|---|
| One global pretraining-seed SD | `phase1/v3_dev_evaluation.py:seed_standard_deviation` only accepted two scores and equal caller-supplied config hashes; `tools/model_v3/summarize_experiments.py` used the full request SHA, including the seed/output/checkpoint, as its row config SHA | Add an independently fixed Git registration plus actual request/result/checkpoint/contract/membership source chains |
| C1/C3/H/pooling rules | `docs/model_v3/DECISION_RULES.md` specified the rules; no executable selector | Add pure, explicitly non-frozen proposals with missing/undefined inputs rejected |
| Recipe intersection / WSD / B* | Existing sample-based scheduler and strict resume do not implement these choices | Add pure LR/batch/schedule/doubling/B* proposal functions |
| Proxy experiment plan and cost tracking | No stage-5/6 controller in this base tree | Root is implementing a separate `v3_proxy_plan.py` worktree; this change does not duplicate or claim acceptance of it |
| Training endpoint and curve collection | `V3StepTrainer.run` saves reached milestones, so a 6M run with the default 1/2/4/8M milestones has no automatic 6M endpoint | Reported to Root; trainer left unchanged. SA-1's independent budget/precision work is handling endpoint/curve lineage |
| Adaptive top-two repeats | A first-seed ranking must lead to two genuine second-seed runs under an unchanged scientific configuration | These functions verify supplied repeats have distinct seeds and equal registered identities, but do not implement an adaptive repeat controller or certify its ranking lineage |
| Gradient p99 / loss spikes | Trainer logs preclip norms, but this base has no source-bound p99 extractor or quantitative spike policy | Not invented here. LR selection requires a predeclared spike-policy binding and externally classified, bound stability evidence |
| D-5/D-6 and full-data measurements | Physical data-line delivery and actual panel/curve results are absent | Required real-data gates remain pending; no synthetic substitute is accepted as a real experiment |

## Global SD input and verification

`phase1/v3_decision_evidence.py` supplies `scientific_identity`, `inspect_run`,
`build_global_seed_sd` and `verify_global_seed_sd`. `scientific_identity` is also
usable before training with the exact planned runtime contracts, so a human can
choose and register one anchor without looking at its results. The implementation
does not choose that anchor or its actual two seeds.

An input manifest has schema `model_v3_global_seed_sd_inputs_v1` and three fields:

- `registration`: `repository`, full 40-character `commit`, repository-relative
  `path`, and raw-file `sha256` for a committed registration JSON blob. The caller
  must separately supply the expected SHA from the preregistration review.
- `panel`: a raw-file `{path, sha256}` reference to the existing frozen nine-task
  panel.
- `runs`: exactly two run entries, each with raw-file references `request`,
  `result`, `sampler_contract`, `execution`, plus `memberships` mapping every panel
  dataset to its actual exported membership JSON and `source_snapshot_root`
  pointing to the immutable executed-source snapshot preserving all relative
  paths in the original evaluation request.

The registration blob has schema
`model_v3_global_seed_sd_registration_v1`, a nonempty `anchor_id`, precisely two
different `pretraining_seeds`, `scientific_identity_sha256`,
`panel_identity_sha256` and metric
`equal_mean_18_task_readout_normalized_error_improvements_v1`. The Git blob is
read at the fixed commit, so editing a working-tree file cannot replace it.
There is no shipped actual anchor registration in this change.
The frozen executed-code commit and the later preregistration commit are separate:
freeze the code first, then register the anchor/policy against that code identity.
They are not required to be the same commit. This avoids a registration blob
depending on the hash of the commit containing itself.

Each actual run must use a recognized v3 sample checkpoint and its byte-bound
`COMPLETE.json`, with the actual sampler contract projected from that training
run. The sampler contract's canonical hash must equal the saved sampler state;
it is not inferred from a run name. The safe CPU checkpoint reader checks the
original configuration SHA, trainer contract SHA, source/data/registry/stats
bindings, actual optimizer parameter-group recipe, sample/update cursors,
scheduler contract/budget and actual pretraining seed. No encoder is constructed,
optimizer is run, target payload is opened or GPU is used by this reader.

The existing evaluation result must be `COMPLETED` and primary, with matching
request/encoder/checkpoint/configuration/architecture/random-reference/readout
provenance. It must retain exactly all 18 task-by-readout cells, each with a
positive reference error and observed population, and both separate nine-cell
readout reports. All cell normalizations and all three means are recomputed.
Historical B3 sanity results and incomplete/N/A panel results cannot define SD.

Membership file references use their raw byte SHA. The evaluation's membership
hash is instead the existing ASCII-canonical JSON hash from
`GroupedTrainingView`; these two kinds of hash are deliberately verified
separately. Only `train` and `train_inner_validation` roles are accepted.
The actual training-store metadata sidecar and every listed executed source in
`source_snapshot_root` are rehashed. This opens metadata/source bytes only,
never the store's native target payload; inherited source references therefore
cannot silently drift after the evaluation. The snapshot location is operational,
while its complete relative-path/content inventory remains scientific.

The execution receipt has schema `model_v3_run_execution_evidence_v1`,
`authority=root_verified_slurm_accounting`, `status=COMPLETED`, checkpoint and
configuration SHA values, actual `pretraining_seed`, `training_run_id`,
`training_job_id`, explicit UTC `training_start_utc`, and nonempty byte-bound
`source_files` containing the original accounting/source evidence. This receipt
is a model-owned projection reviewed by Root, not a claim that Slurm emits this
schema. Existing optional run/job/start bindings in the checkpoint and original
configuration are cross-checked. The preregistration commit timestamp must
precede both starts. Git timestamps do **not** by themselves prove public
availability, and byte hashing does **not** independently authenticate an
accounting receipt: Root must verify those external facts. File mtimes and
run-name guesses are never used.

The seed-excluded identity retains the full scientific configuration, trainer,
sampler, scheduler, actual execution/runtime settings, consumed checkpoint
budget, architecture, data/subset/geometry, registry/stats/source bindings,
complete panel/membership, readout/reference policies and H0 packing.
It excludes only the original configuration's top-level `seed`, `output_root`,
`cache_root`, `run_id`; the verified sampler's member seed; and the verified
trainer's exact `view_configuration.seed` when it equals that same member seed.
If the original configuration includes `view_configuration` or `view_config`,
the entire object must first equal the actual saved structural-view object;
only that object's member seed is normalized. Independent noise-policy,
initialization and readout seeds remain scientific. No recursive removal of
arbitrary `seed` keys occurs. Output checkpoint identities do not enter the
scientific hash; a checkpoint appearing *inside the original configuration*
might control initialization and is therefore retained. Raw config/trainer hashes
are replaced by their normalized full content rather than compared across seeds.

The artifact computes the sample SD with `ddof=1` from exactly two actual complete
panel scores, `abs(score0-score1)/sqrt(2)`. Bootstrap CIs never substitute for
pretraining-seed SD. `verify_global_seed_sd` recomputes the artifact from all bound
originals before a saved artifact is used. Any source drift rejects it. All
decisions use this one verified artifact even when comparing other scientific
configurations; SD is not recomputed to favor a candidate.

Root can run the following CPU-only metadata analysis after the actual inputs
and fixed registration exist, substituting independently measured real SHA
values. It does not submit jobs or overwrite an existing output:

```text
python -B tools/model_v3/build_seed_sd.py --manifest /external/seed_sd_inputs.json --manifest-sha256 <actual-file-SHA256> --registration-sha256 <fixed-preregistered-blob-SHA256> --output /external/global_seed_sd.json
```

Actual artifacts stay outside the Git source tree. No example value in tests is
a proposed real seed, budget, model, spike threshold or SD anchor.

## Pure rule API and unresolved choices

`phase1/v3_decision_rules.py` consumes inspected `RunEvidence`, one **verified**
global SD artifact, and `RulePolicy` loaded by `registered_policy` from an
independently pinned Git blob. Policy schema is
`model_v3_decision_policy_v1` with a `rules` mapping. For each rule, its
`scientific_identities[condition][candidate]` pins the exact intended scientific
configuration before the corresponding runs. The policy commit must precede each
supplied actual training start. One or two supplied repeats must have distinct
actual seeds, the same registered scientific identity and the global anchor's
panel/membership identity. Each rule also requires explicit
`pretraining_seed_roles={initial: ..., repeat: ...}` and
`seed_aggregation=equal_seed_mean`; there is no actual seed or aggregation choice
shipped as a default. A one-seed result must be the registered initial seed; a
two-seed result must contain exactly the registered initial and repeat seeds.
A run/checkpoint cannot be reused as another candidate. The registered mean of
supplied complete seed scores is used; a repeat controller must still
prove the guide's initial-ranking/top-two-repeat lineage before stage acceptance.

`AuxiliaryMetric`, `Timing` and `Stability` are explicit pure-rule inputs with
source SHA and actual run/population bindings. Their caller must load and verify
their original metric/timing/classification files; these small value objects do
not authenticate arbitrary dictionaries or open training logs. This module does
not claim to supply the missing production metric/stability/curve collector.
Invalid bindings raise; missing/undefined evidence yields an explicit missing
proposal. `frozen` is always false.

| Function | Implemented rule / required policy |
|---|---|
| `choose_c1` | Complete C1-0/a/b on S/P. Explicit `cross_condition_ranking` (`equal_mean_S_P` or `worst_condition`) and timing aggregation must be preregistered; no default is selected. Preserve separate S/P baseline safeguards and choose the fastest eligible candidate on the same actual GPU UUID. Exact timing ties remain missing policy. |
| `choose_c3` | Two views only within global 1 SD of three on both S and SDP and with no registered auxiliary regression. Require masked-only element accuracy plus at least one clean-bond metric, explicit direction/population and numeric regression tolerances. An unexplained N/A remains missing evidence. |
| `choose_heads` | Simplest common H1/H2/H3 within 1 SD on P/D/SDP. Without a common form, report for field-consistent review rather than assign conflicting heads. Registry-bound field groups, R2 scope and the condition supplying each group's R2 must be preregistered. Strict H1 R2<0.5 and H3 R2>0.9 yields H2 for that group in every label combination. |
| `choose_pooling` | Registry default unless learned pooling improves P by strictly more than global 1 SD. |
| `choose_learning_rate` | Full fixed LR grid on S/P; require predeclared quantitative spike policy and bound external stability classifications. Exclude a rate if either condition diverges/spikes; choose the smallest rate within 1 SD of both own optima; empty intersection reports. No spike threshold is invented. |
| `choose_batch` | Prefer 2B0 when neither S nor P regresses. Any measured regression retains B0 as the guide directs. |
| `choose_schedule` | Exact WSD decay fraction in [0.1,0.2] must already be registered and bound through the candidate identity. Prefer WSD if it is within 1 SD on both tasks; conflicting S/P preferences with no common form report. |
| `doubling_plateau` | One actual continuing run/seed and recipe/data/architecture identity, correct actual checkpoint sample cursors, exact doublings, earliest strict improvement<global SD. Require a registered full-data curve identity, cap and explicit lower-vs-confirming endpoint interpretation. A missing earlier confirming doubling cannot certify 'earliest'; a 64M cap without a plateau is right-censored. |
| `propose_b_star` | Both converged S/P proposals must share the same policy, global SD and endpoint interpretation. Propose max(S,P); a ratio strictly>2 requires reporting. Every valid B* still requires user confirmation. |

Every comparison proposal records the decision-source SHA, fixed policy SHA/commit,
global SD artifact hash and each actual run/seed/checkpoint/scientific identity.
These are rule proposals, not a completed scientific selection, a substitute for
real data acceptance, an adaptive experiment controller or permission to freeze.

## Validation request

No tests or scientific fits were run in this worktree by SA-4. Root owns CPU
Slurm submission, checker, exact source snapshots and Git publication. Following
the user's current rule, pure CPU validation belongs on available CPU nodes;
GPU nodes are reserved for model training/fine-tuning and other GPU work.

Proposed targeted command from the independent worktree:

```text
PYTHONPATH=current python -B -m pytest -q -p no:cacheprovider current/tests/test_model_v3_decision_evidence.py current/tests/test_model_v3_decision_rules.py
```

Expected collection from the source: 39 cases (23 bound-evidence/CLI cases and
16 pure-rule cases); this is a count request, not a PASS claim. Tests use temporary
synthetic weights/metadata, the real `StructuralViewConfig` shape, actual local
Git blobs/commits and deliberate source rebinding. They cover valid distinct-seed
equivalence, retained independent seed/noise/precision/recipe/budget/initialization
differences, actual optimizer contract mismatch, complete panel arithmetic,
source/role/time tampering, duplicate seeds, CI-vs-SD separation, CLI refusal to
overwrite, strict/inclusive rule boundaries, missing/N/A metrics, conflicting
conditions, exact doubling, censored curves and the >2x/user-confirmation gate.
Synthetic accounting receipts and Git dates are explicitly fixtures and are not
evidence of any real Slurm run or real preregistration.
