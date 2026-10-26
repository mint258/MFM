# Secondary COCONUT acquisition v1

Source-only draft for independent Root review and actual execution. The child has not executed Python, networking, SSH, Slurm, a fixture, or a scientific-data read. This namespace imports no main-cluster guard and uses no main-cluster startup evidence.

The endpoint is `alpha@218.192.171.238:22`, UID 1264. Its hostname/ClusterName may also be sonmi; that name is not an endpoint identity. All deployed work stays under `/gfshome/alpha/codex_data_v1_20261026`. The allowed CPU nodes are compute-0-1, compute-0-3 through compute-0-6, and sonmi1. Root must choose currently available CPUs, allocate one task with 16 CPUs in partition cpu, use no memory or exclusive request (including inherited SBATCH variables), and set CUDA_VISIBLE_DEVICES empty. No paid pretraining endpoint or container is used.

## Stages

1. `CSV_ZIP_PROFILE`: one complete official fullCSV ZIP GET, currently HEAD length 247959854 bytes. Retain the raw ZIP, compute physical SHA256, stream every ZIP member to EOF with the ZIP library CRC check, and count bounded CSV structure/rows. No CSV file is extracted. The maximum scheduled wall is 3600 seconds; total output is capped at 1 GiB; effective free space must exceed the whole output cap by 200000000000 bytes. The inflated stream has a separate 32 GiB finite read limit. This is not disk output.
2. `PLAIN_SQL_FULL_DOWNLOAD`: current HEAD length 37876914074 bytes, application/sql, plain `.sql`. This stage has no automatic submission or promotion. A new materialization requires the actual successful Alpha profile receipt, its successful actual terminal parent accounting, a separately chosen whole-minute wall within 48 hours, and a new exact Root review. The measured profile transfer time is only a linear throughput projection with a stated assumption and margin. Downloading SQL does not establish logical database coverage.

The source URLs, ETag, Last-Modified, and lengths are inherited from actual main job 4521094 HEAD observations; UID 1278 and that job are provenance, never Alpha admission evidence. Month templates and multipart ETags are not release identities or physical SHA256. FullCSV containing any inactive literals does not prove the inactive/deleted universe. Both stages leave normalized identity, chemical processing, candidate release, and active/inactive completeness false.

## Source package and review

Files are `contracts.py`, `transport.py`, `profile.py`, `run_v1.py`, `materialize_v1.py`, `close_actual_v1.py`, `test_v1.py`, and this README. Only standard Python 3.12.7 modules and the existing curl executable are needed.

Root first integrates the exact source bytes into the main run repository, reviews them, and performs the four synthetic fixtures on an authorized CPU job. No fixture contacts a network or uses scientific input. Execute the script directly so its flat local imports resolve:

```sh
"$PY" -B "$REPO/workflows/expansion/secondary_source_acquisition_v1/test_v1.py" -v
```

Then Root can materialize the exact profile plan using its verified absolute Alpha Python path. This helper reads only small source/metadata and does not submit, transfer, hash a scientific body, or contact Alpha:

```sh
"$PY" -B "$REPO/workflows/expansion/secondary_source_acquisition_v1/materialize_v1.py" \
  --repository "$REPO" \
  --head-dir /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/expansion/official_sources/sb5_official_source_headers_v1_cpu_default_memory_v1 \
  --catalog "$REPO/configs/data_v1/expansion/official_source_head_catalog_v1.json" \
  --authority "$REPO/configs/data_v1/secondary_cluster_user_authorization_20261026_v1.json" \
  --output-dir "$NEW_METADATA_DIRECTORY" --secondary-python "$VERIFIED_ALPHA_PYTHON" \
  --node compute-0-1 --name secondary_coconut_profile_v1 --reviewer root --stage profile
```

`--reviewer root` is Root's exact-scope approval action; the materializer has no external submission capability. It outputs new `review.json`, `plan.json`, `spec.json`, `deployment_manifest.json`, and a deferred `sql_proposal.json`. Root must review the concrete files before submission. The deployment manifest maps each actual main-source reference to its independent Alpha path, preserving bytes and SHA. Copy only to those new authorized paths, verify every target SHA/length on Alpha, and do not treat X edits as Alpha deployment. A failed attempt gets a new name, plan, review, output directory, and accounting entry; no overwrite/resume.

The materializer must run against the original main HEAD paths because it compares their complete reference triples against the actual HEAD receipt. It must not be run using remapped Alpha paths as if they were the original observation. A later SQL call adds `--stage sql --profile-receipt <small actual receipt copy> --profile-cost <small actual cost copy> --sql-wall-seconds <new reviewed integer>` and a new name. Local evidence copies retain their exact SHA/length; deployment remaps paths explicitly.

## Independent actual startup proof

Root is the sole submitter and controller. Before any payload GET, it must write a fresh `SECONDARY_SOURCE_ACQUISITION_STARTUP_V1` JSON to the exact new plan startup path. The worker waits up to 120 seconds without network work. The proof fields are:

- `endpoint`: 218.192.171.238:22; `uid`: 1264; exact actual `node`, `hostname`, `boot_id`, and decimal string `job_id`.
- Exact `plan_reference` and `root_review_reference` triples for the deployed files.
- `observed_unix_seconds`, at most 300 seconds old, not in the future.
- `memory_policy`: SLURM_DEFAULT_UNSPECIFIED; `memory_limits_requested`: false; `exclusive_requested`: false. Root establishes these from its actual submission and scheduler evidence, not from an assumed physical memory allocation.
- `job_metadata`: actual full RUNNING scontrol job text with JobId, UserId=alpha(1264), JobState=RUNNING, Partition=cpu, NumCPUs=16, exact NodeList, TimeLimit exactly equal to the whole-minute plan wall, and actual RunTime=HH:MM:SS or days-HH:MM:SS. Both TimeLimit and RunTime support days-HH:MM:SS. Runtime accounting includes the startup wait; the worker derives its remaining scheduled wall from this evidence.
- `storage_observation`: fresh `observed_unix_seconds`, integer `effective_free_bytes`, nonempty `effective_free_basis`, and small `evidence_references` to actual storage/quota observations. Effective free must exceed the whole plan output cap by 200 GB. Raw filesystem df is not silently equated to effective user quota. Root must preserve the independent effective-free basis and evidence.

The proof is independent from every main-cluster schema. The worker checks actual os.getuid, job environment, boot, exact Python 3.12.7 path, working/source paths, actual __main__.__file__ and sys.argv[0] equal to the real run_v1.py path, exact argv, all deployed source references, actual copied HEAD metadata, exact Root review, and node equality with the plan. It does not reuse a main UID, main CPU whitelist, old job, or fake 64 GiB memory proof.

## HTTP, output, and stopping

The downloader sends one ordinary curl GET with If-Match. It preserves the process environment and proxy/CA configuration; hashes only the presence/value of relevant environment variables without persisting secret plaintext. `curl -q` disables implicit curlrc extra transfers, matching the preceding HEAD approach. No proxy bypass, CA override, TLS downgrade, alternate endpoint, redirect follow, range, continuation, or retry is requested. HTTP 403/429 ends the attempt without retry or alternate route. HTTP 200, GET length, physical length, HEAD length, ETag, Last-Modified, content type, and effective URL must agree; any Content-Range is rejected. A future range implementation needs independent review with exact Content-Range/validator/length checks.

The stage has one network worker and serial CSV parsing. Sixteen allocated CPUs are accounted honestly and are not described as 16 parallel curl workers. Two flock slots enforce at most two concurrent host transfers within this Alpha run root. Root must also coordinate the total across clusters and other acquisition code so the global per-host bound remains two; the local lock is not cross-cluster enforcement.

Pipe readers continuously drain curl body/headers/stdout/stderr while retaining only bounded bytes; body never exceeds the expected raw length. Selected response headers and hashes of discarded streams are recorded, not raw unredacted headers/stderr. Every received partial remains at its new `.part` path, including on failure. Completion is a receipt field, not an extension change.

Actual self RSS and MemAvailable are observed each second. The algorithm software limits are distinct from Slurm requests: self RSS 512 MiB, MemAvailable minimum 512 MiB. Memory pressure latches a stop for new work and lets the existing curl drain naturally. Bounded retained samples plus callback extrema are recorded. No child kill, terminate, cancellation, or forced signal is used. Curl's own maximum time is not claimed to be an absolute OS wall guarantee: overrun is recorded and the same live child is observed. Finite profile reads stop before new parsing work when the remaining wall or software soft limits are reached. The scheduler may still enforce its submitted wall.

## Actual closure and cost

Root records actual job/UID/endpoint, parent plus all steps, terminal state, ExitCode, elapsed seconds, AllocCPUS, CPU usage, and MaxRSS from Alpha sacct, including failed attempts and startup/proof failures. No monetary charge does not mean zero core time. The runtime receipt leaves allocated core seconds null until terminal accounting.

`close_actual_v1.py --receipt <actual receipt> --accounting-evidence <small Alpha evidence> --output <new cost.json>` closes a receipt with actual terminal parent elapsed times AllocCPUS, retaining steps without double counting. Accounting evidence schema is documented in that source: endpoint, uid, query_returncode, command_argv, and raw_sacct_reference. Root's complete submission registry must also account for attempts that fail before a receipt exists; this helper is not that registry. Only a successful actual CSV profile plus actual C0 completed parent can feed a separately reviewed SQL plan. No acceptance or fixture PASS is asserted by this source-only delivery.