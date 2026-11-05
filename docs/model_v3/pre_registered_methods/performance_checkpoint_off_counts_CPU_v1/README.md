# Native TRAIN counts and checkpoint-off planning audit

This source-only helper binds the original 4,238-byte manifest, its original shard snapshot, the exact 44,419,088-byte train.atoms.u32 declaration (11,104,772 little-endian uint32 rows), and the relevant frozen9e16 sources. The author has not opened that array or executed this package. There is no new model, data provider, sampling rule, Slurm job, capacity authority or scientific acceptance here.

Root will run one fresh CPU subprocess sequentially with the repository checker in the already planned necessary geometry precommit allocation, under the existing CPU supervisor and shared whole/private2GiB limits. The original full-regression runner and its3300-second contract remain unchanged. No separate counts-QA parent or targeted test pass is requested.

## Exact scope

The actual CPU child hashes the complete44,419,088-byte counts input before and after, verifies stable device/inode/size/mtime, and mmaps it read-only. It hashes the small original manifest, snapshot, protocol, B1 configuration and explicit source refs before and after. It does not inspect, stat, hash or open the LMDB shard paths inside the snapshot, or the Arrow record metadata. It does not construct MappedRecordIndex, ManifestViewsDataset, a model, optimizer, views, labels, geometry, SDK or checkpoint.

The counts-only facade supplies the original index identity formula to the **actual s_native_adapter_v2.CountIndex** (the unchanged v1 alias). Sampling uses the **actual BlockAtomBatchSampler** from this one9e16 worktree. The view multiplier is derived by parsing the frozen FullCorpusViewsDataset constructor's clean/geom/topo recipe and zero topology-deletion policy, then cross-checked against the actual B1 sampler multiplier. Parsing source does not generate views.

All original sampler settings stay: seed0, epoch0, block4096, max512 base molecules, native atom target65536 and atom bucket width16. Only max_padded_cost changes from8000000 to500000. That change participates in the original contract SHA and block permutation: this is a **new common reference/candidate stream**, not an8M prefix, and it cannot borrow the8M total201216 or numerical gate.

The global count scan reports min/maxN, the full count histogram,3*N² singleton costs, counts above500k and the native-atom target. The exact original sampler then yields and commits its first500 metadata batches. CSV includes each base/physical batch, summed atoms, actual padded dense shape, valid pairs, padded cost and oversized singleton. Prefix ordinals are checked for range/uniqueness and hashed in order; no IDs or ordinal lists are exported. The first20 subset has its own digest/cursor, corresponding to the paired harness's fixed20 phase followed by reset to the same trajectory origin. No loader, noise or training is run by this helper.

The global scan covers all11,104,772 count entries; the sampler audit covers only its first500 updates. It does not claim a full epoch enumeration, inclusion of the global maximum in that prefix, or payload/target integrity. Both whether the maximum occurs in that prefix and all oversized singleton updates are reported. The original singleton_no_discard policy retains an oversized record;500k is a target, not a hard cap:3*408²=499392,3*409²=501843. No cropping, exclusion, forced global-max insertion or changed batching rule is allowed.

## One Root invocation

Use the same9e16 GPU5090 Python environment on the actual allocated CPU node. In a **fresh process**, hide CUDA and bind the exact package source path; do not inherit the geometry candidate's package ahead of this worktree:

    W=/share/home/zixiao/descriptor_analysis/MFM_model_v3_performance_integration_v1
    N=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026
    PKG=$N/performance_checkpoint_off_counts_CPU_v1_source
    DEPS=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
    CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="$W/current:$W/workflows/sprime_s/scripts:$W/tools/model_v3:$DEPS" \
    "$PY5090" -u -B "$PKG/audit_counts.py" \
      --inputs "$PKG/inputs.json" --inputs-sha256 ACTUAL_INPUTS_RAW_SHA \
      --source-pins-sha256 ACTUAL_SOURCE_PINS_RAW_SHA \
      --expected-node ACTUAL_ALLOCATED_CPU_NODE \
      --output-root ACTUAL_EXISTING_PARENT/counts_500k_audit

The two raw SHAs are in the source-only handoff; Root verifies them before invocation. The output leaf must be fresh and its parent must already exist below the model-v3 runs roots. The script requires UID1278, an actual Slurm CPU node2 or8–19, the exact expected node, >=16 allocated/affinity CPUs and hidden/uninitialized CUDA. It records actual Python/numpy/Torch versions/threads and checks import origins. Torch uses1 intra/inter-op thread; original sampling is serial Python metadata work.

Default cooperative wall budget600s includes setup/imports, source and counts hashing, the full scan and500 batches; the existing parent supervisor remains the hard deadline/RSS/output authority. No parent resources are enlarged. Expected host footprint is roughly1–2GiB including imports and <=85MiB count mappings, plus small chunks/sets; this is an unmeasured estimate, not a qualification. Output is bounded to8MiB (individual JSON2MiB); expected CSV+metadata is under1MiB. Input accounting is conservative, below128MiB, including duplicate small refs. A failed child preserves its fresh output and exits nonzero.

Outputs are RESULT.json, global_native_atom_count_histogram.csv and sampler_seed0_epoch0_first500_updates_500k.csv. A successful child writes COUNTS_AUDIT_COMPLETE_PENDING_ACTUAL_CPU_OUTER_C0. Actual outer C0 and source closure still belong to Root; this child never grants GPU capacity, automatic checkpointing or A acceptance.

## Two candidate plans after the observed counts

Both plans use the unchanged paired_a_acceptance.py in code9e16d4c5a15c558051499d3dc0c55c9bd3787734, published8147f44baa1ea1ecc3822af7affd0a95401ed248. The exact original options/manual/reference/source refs are in inputs.json. Each future run needs its own full20-batch forward/gradient and500-step numerical gate, original thresholds, same paired two-model residency, actual fresh GPU85% guard, root quota/independent hold and separate output. Neither inherits a capacity result from old8ece, another UUID, all-onR2, R1ABBA or this CPU audit.

First tier: **a03_head_off at8M**. Checkpoint tuple(distance,backbone,head)=(true,true,false). Native S/seed0/workers8/original sampler/views remain8M. Head-only savings/overheads are observed by the real run; the historical old8ece A03 result on22e is context, not acceptance for new9e/C35.

Second tier: **a04_all_off at500k**, only if the counts/prefix evidence and honest memory ledger make an actual guarded attempt reasonable. Tuple=(false,false,false). Reference and candidate both use the new500k stream. Oversized singletons are retained and their true costs reported. A500k budget does not itself prove that the global maximum or the first500 batches fit.

Common exact child argv, with options and maxcost selected as above:

    "$PY5090" -u -B tools/model_v3/paired_a_acceptance.py \
      --candidate-options current/configs/model_v3/performance/a03_head_off.json \
      --performance-execution current/configs/model_v3/performance/a1_manual_capacity_observation_v1.json \
      --performance-execution-sha256 7cabbd4a0300d551154ffb9bcbed5466fc9886d0eb886a1ae37ee3e7f70db46e \
      --reference-config "$W/workflows/sprime_s/formal_s/B1_seed0_v2.json" \
      --input native_s --seed 0 --workers 8 --max-padded-cost 8000000 \
      --expected-gpu 5090 --code-sha 9e16d4c5a15c558051499d3dc0c55c9bd3787734 \
      --prereg-sha 8147f44baa1ea1ecc3822af7affd0a95401ed248 \
      --shard-snapshot-sha256 d2e1ace1636485cd3dd0106b1177518dd37eb9741919195a9efcd846c1c2242f \
      --deterministic-controls --output FRESH_CHILD

For tier2 replace **only candidate-options with a04_all_off.json and common max-padded-cost with500000**, then bind those actual bytes/options/workload in the fresh wrapper. No smoke, checkpoint export, regrouping or resume is added. The smallest future SB derivative is the already used N/performance_manual_R2_GPU_v1_source/run_manual_R2.sbatch with those option tuple/path/budget checks and a new independent family/pins; source text must not run a hardcoded A00 preflight unchanged. Preserve its16CPU64GiB/2h/6900s/RSS56GiB/whole+private2GiB and sole paired inner UUID lock. Root chooses, publishes as required and submits; this package submits nothing and does not touch4567/1338/4558 or other jobs.

## Memory interpretation

For all-off, dense tiled distance processing is not made autograd-free merely by pair_rows65536. With backbone checkpointing off, each of6 layers retains distance-MLP backward state. The actual eager SiLU input and second Linear input yield **2*6*P*512*4 bytes** of512-wide F32 saved-tensor components at padded pair costP. The audit exports that arithmetic for each true singleton/prefix cost. At an ordinary P=500000 it is12,288,000,000 bytes (~11.44GiB), before other live tensors. This is **not a final peak upper bound or admission**.

Other distance inputs/output lists, QKV/attention, FFN/LayerNorm, native supervision/heads, gradients/Adam, the resident reference, temporary workspace/context and allocator remain additional. Their missing upper bounds are not zero. Oversized singleton costs may make even these components exceed available memory. At the already observed8M padded cost7998894, even only one such saved buffer per layer is98,290,409,472 bytes (~91.54GiB), so that all-off combination was rejected before launch. This argument does not transfer all six uncheckpointed layers to a partially checkpointed configuration.

No result here resolves A5 packing, three-card speed acceptance, auto selection, a scientific data release or final B precision acceptance.
