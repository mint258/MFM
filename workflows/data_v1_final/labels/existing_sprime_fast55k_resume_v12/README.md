# Closed5482 continuation — v1-pilot-provisional

This inactive continuation fixes one resource calculation: allocated bytes of
the current Parquet writer are already in actual quota usage and replace,
once, the corresponding future reservation. The original 200GB floor,
56GiB whole-output cap, live quota source, inode/UID/no-shrink/timestamp guards,
16CPU/24h allocation and software working-memory limits remain in force.

Root first verifies actual5482 terminal accounting and its partial receipt.
The existing SQLite checkpoint, five completed Parquet tables and closed
unaccepted partial input-view file are staged by same-inode rename. The partial
file remains resource-only evidence. Raw WP5 and LMDB inputs stay read-only.

Each completed table is reused only after its entire original row generator,
Arrow schema coercion and full reopened table produce the same raw F64/None/
mask/order digest. A whole-file reference is established on the unchanged
file. The new full input-view table uses the original writer, raw encoder and
all defaults. Final prefix/tail integrity and both original TRAIN statistical
replays remain mandatory; r674 stays LOSS_DISABLED.

Only the inherited six Source checks and existing repository checker run
inside the actual production parent. No standalone test matrix is added.
This source is not a submission, completed D4 receipt, or permission to retry
any older STOP2 issue.
