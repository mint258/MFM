# Explicit online metadata append v2

Publisher v1 body unchanged except two explicitly named compatible Root closure schemas:
native_wpgg_sync_Root_closure_v1 and native_S_explicit_sync_Root_closure_v1.
All accepted_count/runIDs/metadata-only/success/source/hash/backup/idempotent guards remain.
Only caller-named runIDs and slug are published; no discovery, SDK access, API or upload.
The v1 rejection of the wpgg schema happened before any publication mutation and is retained.
Prior publishers, proofs, fixed50 page and offline index remain unchanged.