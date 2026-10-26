# Alpha CPU validation of the unchanged Main PubChem gzip copy

Source-only entry. The author ran no Python, tests, SSH, Slurm, Git, data SHA
or data-body parsing. Root deploys this file as
Alpha ROOT/code/secondary_pubchem_raw_validation_v1.py, pins it and executes
it only in an actual Alpha CPU allocation. No new queue, fixture suite or
chemistry dependency is introduced. The pinned secondary_cpu_queue_v1
common.py/__init__.py are reused for small metadata and startup checks.

## Exact plan

Use schema SECONDARY_PUBLIC_RAW_PIN_VALIDATION_PLAN_V1, producer_key and
scope_key pubchem_original_raw_copy_validation_alpha_v1, stage
PUBLIC_RAW_COPY_SHA_GZIP_EOF and the exact PARAMETERS in the entry. The fresh
proof schema is SECONDARY_PUBLIC_RAW_PIN_VALIDATION_STARTUP_V1. Root's new
secondary_cpu_readonly_queue_v3 supplies the actual independent login proof;
the worker does not self-sign or reuse a Main UID1278 proof for admission.

The existing EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1 must bind the
precise plan scope, source set and parent evidence. Use endpoint
218.192.171.238:22, uid1264, actual permitted Alpha CPU node,16CPU,
SLURM_DEFAULT_UNSPECIFIED, pilot=false, wall_seconds3600 and
output_cap_bytes67108864. Current startup independently checks actual primary,
full argv, interpreter, fresh compute time/boot/process identity, Slurm cpu
partition/16CPU/requeue0/script/1h wall and the observed200GB storage reserve
after all declared caps. There are no memory/GPU/exclusive directives.

The exact8-element execution_argv is:

    [AlphaPython, "-B", "-m", "secondary_pubchem_raw_validation_v1",
     "--plan", AbsolutePlanPath, "--startup-proof", AbsoluteProofPath]

inputs_reference, resource_authority_reference, root_review_reference,
startup_proof_path and a fresh artifacts child output_directory use the
existing readonly protocol. source_references must approve this exact file,
actual base common.py/__init__.py, readonly-v3 controller/adapters and all
base-controller dependencies, plus consumed small copies/inputs/authority.
Parent small copies can be in parent_evidence_references. Review the whole
actual dependency list; packet-sized data must remain separate.

## Minimal inputs and explicit copy map

plan.inputs_reference points to this small JSON structure:

    {
      "schema": "SECONDARY_PUBLIC_RAW_COPY_VALIDATION_INPUTS_V1",
      "status": "ROOT_STAGED_EXACT_MAIN_PUBLIC_RAW_COPY",
      "reviewer": "root",
      "raw_copy": {
        "origin_reference": OriginalMainRawTriple,
        "target_locator": ActualAlphaCopiedRawTriple
      },
      "metadata_copies": [
        {"origin_reference": OriginalMainSmallTriple,
         "target_locator": ActualAlphaUnchangedSmallCopyTriple}
      ],
      "main_source348_receipt_origin_reference": Main348ReceiptTriple,
      "main_inventory1093_receipt_origin_reference": Main1093ReceiptTriple,
      "main_accounting_origin_reference": ActualMainOwnedMasterTriple,
      "fee_override_origin_reference": UnchangedMainCostOverrideTriple
    }

All references are exact {path,bytes,sha256}. The origin Main bytes/SHA must
equal their actual Alpha target copy. Do not rewrite embedded paths in copied
JSON; the resolver follows only the explicit origin-to-copy map. The raw
target is the one completed SFTP copy, including a .part suffix if Root keeps
that name. There is no rename or download performed by this entry. Generate
the actual target triple only after transfer completion, not for an active
partial file. plan.data_references is exactly [ActualAlphaCopiedRawTriple].
The login controller checks its locator; only this CPU entry hashes its body.

Required mapped Main small inputs are:

-348 receipt: artifacts/expansion/raw/pubchem_20261025_v1/attempt_4520348/receipt.json.
-1093 receipt: artifacts/expansion/raw/sb5_pubchem_raw_inventory_v2_cpu_default_memory_v1/receipt.json.
-348 receipt.pin (the original official source pin) and root_submission (the
 original pre-submit intent, whose actual schema has no job_id).
-1093 receipt.startup_proof (historical Main admission, not current Alpha).
-Actual owned master, its raw_sacct_reference and the two selected
 actual_parent.receipt_reference final submission receipts. checkpoint21 is
 sufficient for these two actual completed jobs; it need not invent future
 Alpha cost. The348 final receipt differs from348.root_submission intent.
-Unchanged configs/data_v1/user_allocation_overrun_report_continue_20261026_v1.json.

The map can reuse earlier actual Alpha small copies with unchanged bytes.
Main348 is historically compute-0-20/Partition=all/16CPU/C0 and Main1093 is
compute-0-13/Partition=cpu/16CPU/C0. Those observed historical partitions are
kept exact; they grant no current Alpha partition exception. Main current
inode/device data are not read from Alpha. Alpha's copied gzip must currently
be a regular owned1264 file with exact size and unchanged fstat throughout.

## Exact byte checks and bounded conclusion

The entry requires original compressed1488715010B/SHA
2504bc00da1b0587ae208d8a5fb2a4fe6043c215436150f2023d59c57c5cd2b7,
Main348 gzip.uncompressed_bytes_read8880849781 and Main1093
counts.records124857440/counts.uncompressed_bytes8880849781. Both actual
receipts are checked for their real schemas/statuses and full EOF/CRC claims.
Actual sacct raw rows, final submission receipts and owner1278 evidence bind
the two real C0 parent costs. Batch/extern steps are retained without double
adding parent allocation cost. The override changes only overrun handling,
never integrity or quality, and does not turn costs into zero.

The real Alpha CPU hashes every compressed byte, then streams gzip through
EOF/CRC while counting decoded bytes and physical lines in4MiB chunks.
Neither historical receipt has an explicit trailing-newline field. This
entry records whether the last decoded byte is LF and counts physical rows
as LF count plus one nonempty unterminated final line. It does not invent a
historical last-newline claim or parse CID/SMILES. With the fixed full SHA,
the count must equal the actual original inventory. No decoded file is saved.

There is one reader process, not16 workers.16CPU is the actual requested
allocation and its full parent cost must be reported. Every bounded batch
checks current process RSS <=2GiB and actual node MemAvailable >=15% of
MemTotal; these are software guards, not requested/assumed Slurm memory.
At3540s or memory pressure it stops new reads, drains the current chunk and
writes an incomplete receipt/nonzero exit without signals or automatic retry.
This conservative wall guard includes actual startup Slurm RunTime plus
entry monotonic elapsed, preserving the gate/startup allocation overhead.
Normal progress emits at20s intervals between chunks. Output stays below
64MiB; actual receipt uses the base2MiB atomic small-output limit.

Success status is EXACT_MAIN_PUBLIC_RAW_COPY_SHA_GZIP_EOF_VALIDATED.
It means this exact public raw copy passed integrity checks on the actual
new Alpha job/UID/node. Root still records the job's true terminal sacct cost.
It is not chemistry screening, decontamination, features profiling, a new
molecule count, candidate-pool release, guide1M evidence or formal generation.
Any later real feature-profile scope remains independently authorized.
