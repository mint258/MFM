# Native source evidence for MolNet case18

This producer records independent source observations. Its only terminal evidence status is `EVIDENCE_ONLY_PENDING_C0_AND_ROOT_SOURCE_REVIEW`. It neither adopts source/terminal correspondence nor edits an exclusion rule, index, graph, coordinate, pool, or scientific scope. The original 1PTS three observed C-alpha atoms, UNKNOWN graph, case18 C3 rule, and all old records remain intact.

Run module `workflows.expansion.molnet_case18_native_evidence_v1.run --plan PLAN --startup-proof PROOF` through the existing Alpha clean isolated entry and same-node launcher. Root alone reviews, deploys and submits. Allocate16 CPU withoutGPU, use `#SBATCH --time=0`, and unset `SBATCH_MEM_PER_NODE SBATCH_MEM_PER_CPU SBATCH_MEM_PER_GPU`. An8GiB software RSS budget and24GiB node available-memory reserve suffice for this bounded evidence stage. The bulk aggregate cap/other/floor must exactly match the actual Root `reviewed_storage_budget_reference`; no historical other-future amount is hardcoded. New production/native execution remains pending.

`inputs` is a metadata-only input-field helper:

```
ENTRY workflows.expansion.molnet_case18_native_evidence_v1.inputs \
 --bundle ACTUAL_ALPHA_PROPOSED_BUNDLE \
 --index-root-acceptance B/all11_index_1885187_root_actual_v1.json \
 --original-index A/artifacts/pdbbind_general27_original_index_v1/v1/original27_index_lines.DATA.raw \
 --future-budget-review ACTUAL_ROOT_BUDGET \
 --official-transport EXPLICIT_TRANSPORT_JSON --output NEW_INPUT_FIELDS_JSON
```

Each `official-transport` object is keyed by the cache basename, with exact `source_reference` (Windows capture), `replica_reference` (actual Alpha body) and `url` from the33f2176 PROPOSED bundle. Required basenames are official_1PTS.pdb, official_1PTS.cif, official_1PTS_entity2.json, official_1SLG.cif, official_1SLG_entity2.json, official_1SLG_summary.html, official_nstd_linkage_definition.html and official_nstd_monomer_definition.html. Optional official_1VWA.cif and official_1VWA_entity2.json must be supplied together. Raw bodies remain outsideGit. No network calls occur in this producer.

Root merges these input fields into schema `ALPHA_MOLNET_CASE18_NATIVE_EVIDENCE_PLAN_V1`, scope_key `molnet_case18_native_evidence_v1`, with actual profile, quota, output paths, execution_argv and code_references. Every source binding is explicit. Main UID1278 origins, Alpha UID1264 replicas and Windows captures remain distinct. The helper hashes only bounded metadata/index files. Native processing performs fresh complete same-FD SHA reads of original229MB blob,185MB strict5,60MB union, source locator/native-result bodies and342MB closed187 database; the latter is opened read-only with a read transaction before hashing and narrow queries. Old577 full-source EOF proofs are explicitly inherited, not claimed as fresh reads by this parent.

Borrowed original function objects, whose exact physical source references must be in both plan.code_references and startup proof.request.source_references: original Alpha `secondary_moleculenet_native4_identity_v1.native.elements`, its F.sdf_metadata/F.mol2_metadata, frozen `identity_v2.projection_v2.native_composition`, original `coconut735_recovery_v1.consumer.identity_keys` and `index_header`. The existing Alpha/code path must expose the unchanged original native/formats packages and their import dependencies. No load_kernel, graph parser or key generator is invoked. The original identity_keys function is called on the two existing1slg composition-only rows.

The4 stdlib fixtures cover shared alternate sites/models, incomplete ligands and CIF row width, whole formula fields, and incorrect bound bytes/SHA. Local metadata parsing verified captured CIF/API and bibliography locators only; actual borrowed native functions and resource admission await Alpha's independently admitted run. Outputs are receipt.json, source_tests.json, actual_source_reads.json and case18_source_observations.DATA.json; full paper/raw records are not copied into public source. Actual C0 and Root's later scientific source review are separate and both pending.
