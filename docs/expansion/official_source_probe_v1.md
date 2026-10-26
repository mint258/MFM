# Official external-source HEAD probe: draft for Root review

Status: **SOURCE_PREPARATION_ONLY_NOT_EXECUTED_NOT_FROZEN**. This draft adds no
download, all-source acceptance, pool release, novelty ordering or formal
UFF/QM authority. All previously registered sources and outputs stay frozen.

The companion [official locator review](external_all_source_locators_v3.md)
records the official text actually read, immutable source-code commits and
the distinction between source-code versions and data versions. This draft's
catalog contains only its 30 explicitly supported candidate data URLs.
No guessed HTTP URLs are created for individual TDC CSV archive members.

## Exact scope proposed to Root

The new scope is `sb5_official_source_headers_v1`, kind `analysis`, honest
`pilot=false`, proposed queue_v3 mode `BOUNDED_METADATA_PREPARATION`.
Resources remain strict16CPU/64GiB/exclusive=user, CPU partition nodes2/8–19,
all-user declared-memory85% admission, actual current memory sampling, fresh
startup proof and quota with200GB reserve. A900-second allocation and64MiB
whole output cap are ceilings, **not runtime/storage forecasts**. No previous
3CID/10k/identity scope is reused. Root alone generates the new exact scope
review, queue request, current preflight and submission.

The main calls the unmodified queue_v1 request/fresh-startup validators once,
plus queue_v3's exact bound-spec/review validator. Before any HEAD it checks
own actual Slurm job/node/CPU64GiB/CUDA-empty/thread environment, exact plan
and self/runtime/helper/catalog/document pins in request sources, and an
empty data_references list. The plan parameters must equal the catalog-bound
scope parameters. Root's normal queue_v3 creator adds its existing central
runtime/proof sources. Nothing reads or hashes an external dataset body.

The unmodified expansion `full_queue_v1.RuntimeBudget` samples current own
process-tree RSS and node MemAvailable, prevents new dispatch on memory/wall
STOP, and lets in-flight HEADs close. Startup freshness is not rechecked after
metadata work or in workers. The existing120-second wall drain margin stays.

## Network protocol and evidence limits

Sixteen actual nonempty thread workers own fixed catalog slices. A barrier
and distinct native-thread IDs prove their creation; receipts retain each
worker's assigned source IDs. Network work uses global concurrency4 and
per-actual-host concurrency1. Each individual HEAD releases both leases before
the next redirect obtains new leases. No host lease survives A-to-B redirects.
The20-second logical URL timeout budget includes lease waits and all redirects;
budget exhaustion is recorded even when no HEAD could be dispatched. Curl's
own max-time is a requested timeout, not an absolute child-process wall
guarantee. Any overrun and its real drain/wall cost remain visible.

Each subprocess uses curl HEAD only, TLS verification, connection timeout at
most8seconds, remaining total time at most20seconds, retry0 and no automatic
redirects. Only actual server Location values may receive another HEAD, up to
five redirects, always HTTPS with no URL userinfo or alternate port. HTTP303
still receives HEAD; no method fallback to GET is allowed. There is no GET,
HTML scrape, release API fetch, alternate URL/domain search or mirror choice.

The normal network environment, including existing proxy routing, is inherited
without modification, including already configured environment credentials.
There is no --proxy, --noproxy, environment clearing,
insecure TLS, alternate port, User-Agent spoof, cookie or auth option. Curl's
--disable prevents personal curlrc parameters from introducing implicit auth;
that choice does not prove that a path dependent on curlrc configuration is
reachable. Existing authenticated proxy variables are inherited by curl and
are never rejected, rewritten, printed or copied to artifacts. Only the
candidate/redirect URL itself must have no userinfo. There is no author contact.

HTTP403/404, TLS/DNS/connect failures and other curl return codes remain
observations, with coverage still PENDING. HTTP429 blocks every later HEAD to
that actual host, including redirect targets, with explicit unrequested
dispositions. No retry or rate-limit workaround occurs. Missing curl or
unsupported protocol responses are recorded as command/protocol failures.

Only HTTP status, Content-Length, ETag, Last-Modified, Content-Type,
Content-Disposition and Location are retained. Proxy CONNECT/informational
blocks are distinguished from the last response block. Set-Cookie,
Authorization and Proxy-Authenticate are never persisted. Every URL has its
full-original SHA256; query values are redacted except the registered harmless
usp=sharing value. No raw headers, stderr text or token-bearing exception text
is written. Curl return code, parsed curl error number, byte counts and header/
stderr-prefix digests preserve bounded error evidence. These header-buffer
digests are explicitly **not data-file SHA256**.

Per curl, in-memory stdout/stderr prefixes are bounded256KiB/32KiB and are
continuously drained without persistence. If curl remains live beyond its
max-time plus2seconds observation grace, an immediate bounded overrun notice
is written and new dispatch stops. The process is still drained to natural
exit. No child or other process receives kill/terminate/send_signal from this
entry. There is no finite natural-drain guarantee; Slurm's predeclared wall
and actual parent accounting remain authoritative. If the wall ends first,
completed per-URL records and the overrun notice survive as partial evidence.

## Source mapping and permanent PENDING fields

The catalog preserves TDC's22 endpoints and44 train_val/test logical CSVs;
each expected loader path is marked NOT_INSPECTED. A ZIP HEAD never proves
that a CSV member exists, its schema, identity count, split union or SHA.
All17 proposed MoleculeNet datasets remain mapped, including PDBbind general/
refined/core and the explicit QM versions listed in the official review.
Version/set equality is not inferred from similar filenames. Both MARCEL
Google Drive URLs are official landing-page locators; an HTML HEAD does not
establish archive metadata or bypass Drive access restrictions.

COCONUT's three October2026 URLs remain clock-template candidates. The
template's displayed sizes are not Content-Length; its visible month is not
a release pin. Only the complete SQL candidate is described by the official
page as active/inactive. CSV inactive-ID coverage remains PENDING regardless
of HEAD success. No SQL, pickle, benchmark labels/features or molecule body
is decoded. None of these benchmark observations is used for novelty ranking.

Every source keeps data physical_sha256=null, record_count=null, and coverage
PENDING. A completed probe receipt means that all30 candidate locators have
an observation or an explicit unrequested disposition. It does not mean all
HEADs succeeded or any data was acquired. A separate future Root request must
bind actual versions, downloads, storage and all-identity/split proof.

## Output and meaningful source-only fixtures

Each completed URL immediately receives its one fresh JSON observation through
a budget-checked callback, limited128KiB before writing. Final aggregation
collects the existing pins without rewriting observations. Thus one stalled
child cannot erase observations already completed by other workers.
The logical manifest is limited128KiB and final receipt512KiB. Thirty URL
files plus these summaries total at most4.375MiB logical metadata before
bounded overrun notices (at most16KiB per source) and the small failure record;
allocation is also sampled using st_blocks and the parent directory. An8MiB
stop reserve remains inside64MiB. Raw headers are
never spilled, and no partial, failed or prior file is deleted. Overflow
causes a preserved failure, not silent field loss or a larger cap.

Five new fixtures check complete30/44/17 mapping and narrowing refusal;
header allowlisting/query redaction/ambiguous length; HEAD-only redirects with
an inherited authenticated proxy, secret-free results and a production-AST
no-signal/env-override assertion;16 real threads with4/1 leases released per
hop and exactly-once result callbacks; and429 host suppression/callback
conservation plus refusal of a missing Root scope review.
They use synthetic captures only and are also run after startup before real
HEAD work. No prior scientific test suite is repeated.

## Root-only metadata CLI and handoff

After review/integration, Root can produce actual source-bound metadata:

```bash
PY -B -m workflows.expansion.official_source_probe_v1.materialize \
  --tag v1 --goal-authority ABS_CURRENT_ROOT_GOAL_AUTHORITY --reviewer root
```

This creates only a new READY source-bound plan and an explicitly
NOT_REQUEST_READY base spec under control/queue_specs. It creates no scope
review, queue request, script, quota observation, network process or Slurm job.
There are no fabricated future reference triples. Root must independently
create an exact queue_v3 scope review and reviewed spec; the central contract
rejects the base spec as it stands. Root's subsequent queue_v3 materializer
and observer use the existing strict pipeline with pilot=false.

The final execution argv is exactly:

```bash
PY -B -m workflows.expansion.official_source_probe_v1.run \
  --plan ABS_SOURCE_BOUND_PLAN --root-preflight __ROOT_STARTUP_PROOF__
```

Standalone fixture entry for Root's allocation:

```bash
PY -B -m unittest workflows.expansion.official_source_probe_v1.test_probe -v
```

New draft files comprise the namespace __init__/catalog/transport/run/
materialize/test_probe, the JSON catalog, and this document. All remain drafts
until Root static review; no sourcechecker, fixture, probe or scientific task
has been run by this child agent.
