# Authoritative pilot training entry

This is a source-only entry implementation. No actual Data release or three-GPU
pilot smoke has been run or accepted by this change. All stopped FP32 compensation
candidates remain stopped; this entry adds no numeric model implementation.

## Scope and source

The new CLI spelling is:

    python tools/model_v3/run_proxy_experiment.py run --input authoritative_pilot \
      --request /absolute/request.json --request-sha256 <actual-raw-SHA> \
      --output /fresh/job/root --lineage-root /existing/canonical/lineage \
      --lineage <registered-lineage> --segment-id <fresh-segment> \
      --until-samples <registered-sample-endpoint> [--resume-complete <actual-COMPLETE>]

Run it only through the existing Root-owned resource/SDK/Slurm supervision.
The request is still model_v3_proxy_request_v1, with mode=authoritative_pilot,
scope=pilot_smoke and the original exact source/configuration bindings.
Configuration remains model_v3_proxy_configuration_v1; engineering_only=false,
experiment_scope=AUTHORITATIVE_PILOT_SMOKE, six layers of dimension512, original
plain FP32/highest/no-TF32 execution. New training_execution and old
performance_execution_v1 are rejected for this initial entry.

Configuration.pilot_smoke has exactly these keys:

- schema: model_v3_pilot_smoke_contract_v1
- optimizer_update_cap: integer2000
- role_index_sha256: TRAIN, VAL and TRAIN_UNSEEN_CONFORMATION canonical membership SHA
- validation_population_bindings: the actual VAL and TRAIN_UNSEEN_CONFORMATION
  canonical bindings, equal to proxy_contract.validation.population_bindings
- evidence: exact rawrefs for D1, D2, D3, D4, Model_policy_config_ACK,
  Data_release and reader

Evidence uses the existing exact {path,bytes,sha256} metadata convention. It is
not a new Data publication format. The ACK is the actual signed same-version
Model policy/config document, not a draft or a release certificate. Root admission
keeps model_v3_proxy_Root_admission_v1 and has status=ROOT_ADMITTED_PILOT_INPUTS,
scope=pilot_smoke, actual clean code/tree, exact configuration/request identities
and evidence exactly equal to the registered pilot evidence. Required existing
Git preregistration purposes are budget, validation and pilot_smoke; the latter
binds the entire pilot_smoke contract. It does not require D5, selection/platform
or a future three_GPU_SDP_smoke result. Those original requirements remain on
their original proxy/full/grid routes.

Actual bind first reverifies the original actual release and exact request,
then joins each complete rawref: D1=actual joint.contract_reference,
D2=release.evidence.registry, D3=Data_release=release.evidence.release,
D4=release.evidence.d4_statistics, Model_policy_config_ACK=actual
joint.model_ack_reference (also the exact signed ACK), and
reader=release.projection.reader_source. A readable but unrelated document is
rejected. Metadata configuration validation alone does not certify these joins.

Three role_index_sha256 values and both validation_population_bindings are
separately compared to the reverified release/interpreter projection and actual
provider. They are canonical identities, never compared with a raw JSON file
SHA. There are no pilot_TRAIN/VAL/unseen rawref aliases: the current Data
interface exposes no common such per-role rawref contract. This adds no invented
Data population-file format.

Data has now separately published
configs/data_v1/interfaces/D1_v3_0_joint_interface_freeze_20261029_v1.json,
schema ROOT_MODEL_D1_V3_INTERFACE_POLICY_CONFIG_FREEZE_V1, status JOINTLY_FROZEN,
binding the actual signed Model ACK. That document covers policy/config/design;
its five final resolved mapping references remain null and it grants no actual
label/payload/D3-D6 release. It is distinct from the actual final-label joint
and ROOT_FINAL_LABEL_RELEASE_V1 family required by the existing consumer.
JOINTLY_FROZEN alone must not upgrade this D1 interface to a release.

The source-pinned adapter must expose
verify_and_bind_model_v3_pilot_TRAIN_inputs(request)->ProxyInputs. This is a narrow
new dispatch to the already implemented actual Data consumer:
VerifiedDataRelease.reverify() rechecks its original bound interpreter and real
release family. authority_kind must be data_line_pilot, release_accepted must be
true, exact request SHA must agree, the actual scoped projection must be
authoritative_pilot and not final, and all three population identities/two
validation bindings/reader/release/actual joint Model ACK must agree. UNIT
metadata or a caller's self-seal cannot provide this authority. The existing
actual-release family verifies bounded-release status, heldout exclusion,
geometry/codebook/D4/registry/source policies. All source values/masks/scales and
physical target eligibility remain with that consumer.

There is currently no qualifying actual Data release available to this entry.
Missing release, reader, D4, heldout or geometry evidence therefore means HOLD,
not an inferred admission. The true adapter must supply no fake identity frame or
zero labels for a disabled/unknown target.

## Exactly2000 effective updates under the existing sample plan

The cap is part of sealed configuration and therefore the original experiment
and checkpoint/resume identity. The original sample budget, scheduler, sampling,
batching, milestones, checkpoint counts/reserves, RSS/wall/storage guards and
optimizer/trainer algorithm are unchanged.

The original STEP preflight reads the committed optimizer_updates cursor. At
2000 it raises the original cooperative SegmentPause before any next update.
A sample count is never substituted for an update count. All-disabled batches
still follow the original trainer clock; they cannot manufacture a committed
optimizer update.

The CHECKPOINT preflight, while inside the original training lease, makes sure
both complete actual validation populations are evaluated at that exact update
cursor before the original safe checkpoint is saved/published. Existing
validation records at the same cursor are reused. This ordering avoids creating
a second different event at an already published sample cursor. Pending-log
failure keeps the original recovery path. No second checkpoint implementation,
lease type or validation algorithm is introduced.

After run_segment returns, UPDATE_LIMIT_RESULT.json verifies the original
EXPERIMENT_COMPLETE/STATE/trainer marker and actual samples/updates/log cursor,
pending_log=false and both validation records. At2000 it records
PILOT_2000_UPDATES_COMPLETE_PENDING_ROOT_CLOSURE. A bounded segment paused below
2000 records UPDATE_LIMIT_SEGMENT_PAUSED_NOT_COMPLETE and may resume explicitly
from the same original checkpoint/lineage. Exhausting the full registered sample
budget below2000 is HOLD with the original checkpoint and failed SDK finish
preserved. Checkpoint/wall/storage reserve exhaustion remains a failure or
bounded pause under the unchanged original guard.

Pilot requires no formal downstream panel binding (omit it or use null).
Original checkpoint/outbox schema and CP/H0 interfaces remain unchanged; without
panel binding its outbox cannot become a READY formal panel ACK. Smoke evidence
grants no platform/architecture/recipe choice, S/D/B* selection, real-release
acceptance or Stage5/D5/full240000 qualification.

## Planned engineering tests, not Data or GPU acceptance

Only the new test_model_v3_pilot_entry.py is authored. Original112/133 test files
are untouched. The tests cover exact2000 and typed cursors, scoped metadata/ACK
and missing references, no pilot↔proxy/full/grid fallback, the original UNIT
release's inability to acquire actual family authority, and unchanged default
engineering configuration.

A synthetic-only engineering_update_cap keyword/prepare-engineering flag (1..2000)
exercises the same original preflight/CP mechanism. A small original provider
case uses two fresh CLI processes: update, two validation populations, immutable
CP, explicit resume, stop at the sealed update cap, native offline SDK finish and
changed-cap resume rejection. Another original-provider case exhausts its
sample budget too early and must HOLD after safe CP/SDK cleanup. These are
engineering fixtures, not an actual authoritative_pilot positive or a synthetic
Data publication. No production test exemption or mocked release authority is
added.

All test/CPU/GPU results for this source change are pending Root execution.
Root must run its normal checker before commit, relevant/new and original
regression tests inside an owned CPU allocation, publish exact sources/method,
then bind actual Data and preregistration/admission/resources for any real
pilot. A successful UNIT CLI test never completes D3/D4/D5/D6 or the real
three-GPU smoke.

## Source revision v2

V1 source/freeze/handoff are retained. V2 only joins the metadata aliases to
existing actual release fields, removes three unsupported population rawref
aliases and adds both canonical validation population bindings to the sealed
pilot contract. Two CLI/proxy execution files remain V1 bytes; no cap, trainer,
checkpoint, resource, precision, final/proxy/full/grid or Data authority gate is
relaxed. Pure metadata join tests do not mock actual release qualification.
