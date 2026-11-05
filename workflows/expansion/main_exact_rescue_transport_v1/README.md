# Complete exact-rescue transport catalogs

The running Main producer writes bounded4096-row result Parquets. Its27.7M
distinct FP scope may produce about6800 parts; an inline origin/replica mapping
can therefore exceed the original2MiB metadata bound.

This adapter retains EXACT_RESCUE_TRANSPORT_V1 and the original inline files
form, and additionally accepts one files_catalog_reference plus exact file_count.
The external catalog is newline JSONL, whole-byte/SHA verified, at most64MiB,
at most100000 entries, with1MiB maximum per row, exact EOF/count and unique origin
triples. The descriptor remains at most2MiB. Every replica still receives actual
destination owner/frame/SHA checks on first use; final frames include descriptor
and external catalog. No score, query membership, reference, precision or math changes.

Main4525875 and its immutable source files are not modified. A fresh Alpha
namespace may alias its common.Transport to this adapter and pin both source
sets. The actual import plan and source descriptor must name that new namespace.
No scientific result is accepted solely because transport or fixtures succeeded.

Run the3 standard-library tests through the appropriate isolated native entry.
They exercise an actual catalog exceeding2MiB, all row-count/newline/duplicate/
hash failures, post-admission mutation, and the previous inline160-input format.
