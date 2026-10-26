# Independent Alpha readback of the existing16 UFF QA controls

Source-only handoff. The author ran no Python, tests, science, SSH, Slurm or
Git. Root reviews, pins, deploys and runs this entry on an actual Alpha CPU
allocation through secondary_cpu_readonly_queue_v2. It does not replace the
previous Main readback entry or claim that a Main CPU executed this check.

The only data read are the16 original Alpha1884766 reproduction JSON gzip
packets and byte-identical copies of their16 existing Main baseline gzip
packets. There are no UFF, QM, pickle deserialization, LMDB, original run_one,
scientific initialization or production once-ledger calls. Population added
is0; the two missing molecules remain forbidden. The existing Alpha QA map,
receipt and formal=false fields are unchanged.

## Exact plan and CLI

Deploy this readback.py at
/gfshome/alpha/codex_data_v1_20261026/code/secondary_uff_readback_alpha_v1/readback.py.
The new directory is a Python namespace package; no new __init__.py is needed.
Reuse the already deployed portable_secondary_uff_v1 and
secondary_cpu_queue_v1 packages as pinned dependencies.

Plan schema is SECONDARY_UFF_CONTROL16_READONLY_PLAN_V1. producer_key and
scope_key are uff_control16_independent_readback_alpha_v1. Stage is
UFF_CONTROL16_INDEPENDENT_READBACK. scope_parameters must exactly equal
PARAMETERS in readback.py; in particular the historical jobs are Main4521182
and Alpha1884766, and readback endpoint/UID are Alpha218.192.171.238:22/1264.
Use analysis, pilot=false,16CPU, SLURM_DEFAULT_UNSPECIFIED, wall_seconds600,
output_cap_bytes67108864 and a new artifacts child as output_directory.
No memory, exclusive, GPU or requeue directive is permitted.

The exact8-argument execution_argv is:

    [AlphaPython, "-B", "-m", "secondary_uff_readback_alpha_v1.readback",
     "--plan", AbsolutePlanPath, "--startup-proof", AbsoluteStartupProofPath]

Use the actual Alpha Python path, not a Main path. The producer validates
__main__.__file__, sys.argv, interpreter path, the exact plan/review and actual
fresh Alpha1264 CPU/node/boot/gate process/Slurm script. Startup proof schema
is SECONDARY_UFF_CONTROL16_READONLY_STARTUP_V1. It is made by the independent
Alpha login controller, not by this worker. Root review uses the existing
EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1 protocol and exact source set.
The storage check reserves every declared whole-output cap and200GB on the
observed Alpha mount; it does not invent a Main or hidden-quota allowance.

## Inputs and origin-to-copy locators

plan.inputs_reference points to a small pinned JSON with:

    {
      "schema": "SECONDARY_UFF_CONTROL16_ALPHA_READBACK_INPUTS_V1",
      "status": "ROOT_STAGED_EXACT_COPIES_FOR_ALPHA_CPU_READBACK",
      "reviewer": "root",
      "metadata_copies": [
        {"origin_reference": MainTriple, "target_locator": AlphaCopyTriple}
      ],
      "main_preparation_origin_reference": MainPreparationTriple,
      "main_accounting_origin_reference": MainOwnedAccountingTriple,
      "fee_override_origin_reference": UnchangedMainOverrideTriple,
      "alpha_receipt_reference": AlphaReceiptTriple,
      "alpha_deployment_map_reference": AlphaMapTriple,
      "alpha_startup_proof_reference": AlphaOriginalStartupTriple,
      "alpha_accounting_reference": AlphaAccountingTriple,
      "alpha_raw_sacct_reference": AlphaRawSacctTriple,
      "alpha_deployed_recipe_reference": AlphaRecipeTriple,
      "baseline_copies": [
        {"molecule_id": ExistingControlId,
         "origin_reference": MainBaselineGzipTriple,
         "target_locator": AlphaCopiedBaselineGzipTriple}
      ]
    }

Every triple is {path,bytes,sha256}; no future hash or fictitious origin path
is accepted. metadata_copies maps each consumed original Main small file to
its unchanged Alpha copy. Original and target bytes/SHA must match. Keep paths
inside copied JSON unchanged; the resolver follows the explicit map. Existing
Alpha copies can be reused as targets. Main original paths are never opened
on Alpha and cannot masquerade as current Alpha file views.

The small map must cover Main preparation, its334 complete_packages metadata,
its root_preflight, Main owned-accounting/master evidence, raw sacct and the
Main4521182 submission receipt, unchanged fee override, the original recipe
and all7 original science sources. It may contain other explicitly reviewed
small unchanged copies. Reuse deployment.main_preparation_target_locator,
the existing original-recipe copy and deployment.science_sources target
locators where applicable. The actual deployed recipe is the separate
Alpha recipe_target_locator, not a rewritten original recipe.

All consumed small targets, the inputs JSON, authority, dependency source
files and this readback source must be in plan.source_references, or small
parent_evidence_references as appropriate. Imported code must specifically
be in Root's approved source_references: portable __init__.py, bridge.py,
contract.py, prepare_existing_controls.py, plus secondary_cpu_queue_v1
__init__.py/common.py and this primary. Pin the new readonly controller and
adapters and the existing8 base-controller files under the actual queue
protocol. Inputs and data references are disjoint; no packet body is a small
source reference. Root review must list exactly the approved sources.

plan.data_references contains exactly32 unique triples: the16 original
Alpha execution.packet_reference values plus the16 baseline_copies target
locators. Copied Main baselines must be under Alpha ROOT/inputs; originals
stay under ROOT/outputs/software_control16_v1/reproduction. The readonly
controller checks only these locators on login. The CPU entry separately
requires their exact16+16 grouping, molecule identities and Main golden pins.

## Readback and limited result

The entry rederives the fixed <=32heavy, <=30N, <=60oldseconds and hash-order
selection of exactly16 from the original334 SUCCESS metadata, including
new_real_accepted_count>0. It requires the original336 protected set and
16-control allowlist, original TIMEOUT provenance, Main4521182 actual C0/raw
parent and submission, Alpha1884766 actual C0/raw parent and16 distinct worker
identities. Parent cost is reported once; raw steps are retained separately.

On actual Alpha CPU it fully hashes both compressed packet groups, checks
current owner1264/fstat before and after, and reads each gzip to EOF/CRC with
a finite1GiB inflated cap. It requires exact four-way equality of the actual
Alpha packet, actual Alpha copy of Main baseline, Alpha execution SHA and
Main golden SHA through portable.bridge.scientific_sha. Only
summary.elapsed_seconds is excluded. No tolerance or coordinate rewrite is
introduced. Seed, geometry IDs/hashes, source anchor and native atom order
are also compared explicitly. Historical Main fstat values remain evidence
from Main4521182; they are not claimed to be observed from Alpha.

Recipe comparison reuses recipe_equivalence, allowing only source-path and
output-root substitutions. All7 original scientific source bytes and the
exact original recipe SHA are checked against their actual Alpha copies.
Alpha1884766's recorded Python3.11.14/NumPy2.2.6/RDKit2025.09.5/
Torch2.5.1+cpu/PyG2.7.0 identity is checked without pretending it matches the
different Main Torch build. The pure metadata helpers normalized,
actual_parent and packet_facts retain the exact text of the pinned Main
readback source identified by MAIN_HELPERS_SOURCE.

Success writes only a new readback.json with status
ALPHA_INDEPENDENT_CONTROL16_EXACT_READBACK_COMPLETE_REQUIRES_ROOT_UNIFIED_SOFTWARE_SCOPE_REVIEW.
The result names the actual new Alpha job/UID/node. Root's unified software
scope review and this job's terminal actual sacct cost remain pending; neither
is self-certified by the worker. This result supports only the bounded16
controls/current7-source recipe/version. It grants no formal generation or
all-molecule equivalence, adds no population and does not rewrite old reports.
The unchanged fee override is attached by origin and actual-copy pins; no
quality gate is waived or actual cost treated as zero. The600s allocation
stops starting another packet pair at540s and drains the current read; it
does not signal or modify another job. Existing failures remain actual costs.
