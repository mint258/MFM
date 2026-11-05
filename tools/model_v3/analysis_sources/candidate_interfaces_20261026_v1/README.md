# A → B actual candidate interface interop

Prepared test source only; no test, training or submission has been run by this agent. The separately tested A/B sources are unchanged. Root must first merge both into one current/phychem_mfm package and finish the pending source/full-suite checks. This external package adds one test module with **4 expected pytest cases**, a source inventory and this README.

Positive scope is **PM7-only, synthetic engineering**. The actual pinned DataB `project_training_sources` source (SHA50aceee73de4718b7f35dbd2a37a207a7739d57f8ed53f39a36da16bfbc0e2dd) is executed as its original bytes. Actual B fixture geometry/native bindings, n_atoms and exposure metadata provide A's original kwargs; the real A CandidateProjectionInput/build_candidate_sampling_index rechecks the projection and produces its original sampler/index. index.version is exactly the B manifest value. The test never copies a projector, A/B adapter, sampler or trainer implementation.

The existing projector requires both source entries per molecule. To satisfy that reviewed candidate contract, a separate synthetic UFF **index-metadata-only** row is declared for each molecule. It has no wire record, coordinates, labels or claimed cross-source conformer correspondence. Only real B fixture PM7 records are exported/decoded. Source-specific original rank1/training_rank0 and explicit disjoint diagnostic IDs are declared fixture metadata; they are not an authoritative D5 readback. Sprime_UFF and mixed requests must reject their unexported locator. No UFF label or mixed-condition normalization is fabricated, admitted or tested positively.

The positive path is:

1. Root's actual private TMPDIR → unchanged B fixture helper → actual DataB MFM3 FamilyWriter/GranularFamilyWriter → small new local LMDBs.
2. Read the actual geometry/physics metadata and original native five fields through the real readonly readers; compute the source projection with the fixed actual DataB function.
3. Real A typed index → original sampler → ManifestSampleDataset with real B factory → 2 spawned readonly workers → original collate and CPU audit. All native fields/hash, source, component validity, missing y leaf reason9 and review11 remain queryable.
4. Original WirePreparedProvider produces PreparedV3Batch from the same choices; compare its P/D values (including invalid NaN), masks and field-specific pairs exactly with the worker-collated batch.
5. Original6×512/8heads/ff_mult2 encoder, V3HeadBank/V3MultiViewModel and original V3StepTrainer perform **one** CPU optimizer update. Require positive loss/valid counts for all S element/noise/bond fields and observed P/D fields, finite gradients, one acknowledged unit-tracker row, and sampler/clock/scheduler consumed2.
6. A real second batch was already prefetched while all consumed cursors were0. Persist only the small committed sampler/clock/scheduler cursor JSON, restore the original state APIs, and require that the next two choices equal that uncommitted batch. Close the old readonly provider, reopen a fresh real provider, and verify identical source input/targets/audit without consuming the restored draws.

Recovery scope is the committed cursor, source identity and deterministic provider inputs. This test does **not** claim a model/optimizer/RNG checkpoint roundtrip, persistent W&B durability, native data authority, D3 acceptance or a scientific training result. The existing tested original trainer checkpoint suite remains separate. Native5 mismatch is a separate negative test; the other two negatives reject absent UFF locators for Sprime_UFF/mixed rather than borrowing PM7 labels.

Every runtime source before/after hash is retained, including actual imported module locations after the merge. A/B production module bytes and the original B fixture helper are hard-pinned; missing modules/source pins cause FAIL, never skip. Six real DataB reader/codec package sources plus the actual projector are also verified. The rev2 change moving a **different B negative symlink test** outside private storage does not change the imported B production modules/fixture helper. This interop source creates no symlink anywhere.

Each test creates only its own new normal-directory fixture below the Root-bound physical /tmp TMPDIR. Actual B local filesystem/readonly handle checks stay active. Small closure JSON and committed cursor are retained under the shared pytest basetemp; LMDBs are not copied there or into Git. Every original fixture data.mdb SHA remains unchanged. Actual open/close events must balance per PID, including main-process reader instances and worker finalization. Only the verified private child directory is cleaned after handles close. All original sources/data/evidence remain in place.

## Root execution request — not executed

Use the merged A/B tree's current and current/tests on PYTHONPATH, the existing Torch/PyG/numpy/lmdb overlay and the already tested CPU environment. Root selects an actually available CPU node in partition cpu with at least16CPUs, suggested16GiB and15minutes, GPU hidden. Root's PrivateStorage must provide the real /tmp private TMPDIR. Set PYTHONDONTWRITEBYTECODE=1 and bind **MODEL_V3_INTEROP_CODE_SHA** to the actual merged code commit read by Root before submission. This required SHA is not guessed from the old base commit. Shared pytest output must be admitted by the normal unit output census.

```bash
MODEL_V3_INTEROP_CODE_SHA=ACTUAL_MERGED_CODE_SHA \
PYTHONPATH=current:current/tests:EXISTING_OVERLAY \
python -m pytest -q -p no:cacheprovider \
  /share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/interface_interop_v1/test_A_B_interop.py \
  --basetemp SHARED_UNIT_PYTEST_ROOT
```

The inventory pins original A/B worktree source bytes and the external test; runtime receipts additionally bind the actual merged imported locations. Root should snapshot/check sources before and after, run the external4-case suite, retain all real terminal/closure results, then perform the usual repository checks. Four passes and S+D+P interoperability are expectations until those actual tests finish; no throughput, accuracy or adoption result is asserted here.
