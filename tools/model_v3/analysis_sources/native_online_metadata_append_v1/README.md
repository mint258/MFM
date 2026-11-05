# Local online-index append after actual Root closure

This publisher only consumes the explicitly supplied successful Root closure
and runID list. It rechecks small local source/proof refs, creates a separate
immutable online JSON/page and appends one uniquely marked link to the
unified HTML. It does not open/retransmit SDKs or call a cloud API. Original
scientific states, especially failed, are retained and no B acceptance is
claimed. Source/stage SDK hashes remain actual-worker evidence; Root's
current SDK independent rehash is explicitly false.

The existing archive lock prevents concurrent archive updates. Complete
pre-append unified HTML bytes are backed up in the fresh publication root;
the pinned original775-byte prefix and all current old bytes are preserved.
New artifacts are create-or-equal only. The root entry is appended atomically
once, and a repeated identical call verifies existing content without adding
another entry. The old online50 page and offline index remain untouched and
their raw SHA is checked. No old bytes, runs or evidence are deleted.
