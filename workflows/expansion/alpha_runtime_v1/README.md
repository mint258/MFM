# Independent Alpha runtime and directory quota

This package is Alpha-only: endpoint218.192.171.238:22, usernamealpha, UID1264.
It does not import or modify Main's quota backend or imply a Main1278 allocation.
The actual initial compute profile is sonmi1/cpu,16CPUs. Root supplies its own
reviewed software RSS/node-memory/output/all-future budgets; no Slurm memory
reservation is inferred from these software allowances.

Native read-only observation established volume gv1 (source sonmi1:/gv1),
VolumeID34f41e7e-c1c0-49b2-b194-7ce34fa3dc78, with features.quota,
features.inode-quota and features.quota-deem-statfs all ON. Native statvfs at the
volume root showed71,996,545,171,456B, while its direct child/gfshome/alpha and the
old run root showed2,199,023,255,552B. This is directory-quota-deemed capacity,
not a whole-volume df or /dev/sdb user quota. Direct quota-list/xattrs were not
readable; no successful direct limit-xattr query is claimed.

Gluster documents this behavior in its directory quota guide:
https://docs.gluster.org/en/v3/Administrator%20Guide/Directory%20Quota/
The installed client reports9.5. Its published source shows quota_statfs_continue
validating the applicable directory's quota and quota_statfs_cbk replacing total
blocks with hard_lim, and available blocks with hard_lim-usage:
https://github.com/gluster/glusterfs/blob/v9.5/xlators/features/quota/src/quota.c

All Alpha commands use an exact clean code cwd and Python-I, avoiding the existing
home/string.py without deleting or editing it. For unpacked source, use:

```
cd CLEAN_CODE_ROOT
PY -I -B ABSOLUTE_ALPHA_RUNTIME_ENTRY workflows.expansion.YOUR_MODULE --plan PLAN
```

entry.py is a standalone absolute script that initializes standard libraries
under-I, adds only its clean code root and invokes the explicit expansion module.
Spawn workers inherit that clean module path. profile.admit(plan,minimum_workers=16)
checks the actual Slurm node/partition/CPUs/UID, noGPU, code hashes and clean cwd.
It creates only output_scope_root when absent; it preserves a fresh stage's absence.

Root freezes runtime_profile_reference to schema ALPHA_FREE_CPU_RUNTIME_PROFILE_V1:
endpoint,uid1264,usernamealpha,allowed_nodes['sonmi1'],allowed_partitions['cpu'],
minimum_workers16,no_gpu=true,no_paid_server=true,clean_code_root. Plans also supply
workers,software_rss_budget_bytes,minimum_node_available_bytes,output_scope_root,
output_directory inside that scope,output_cap_bytes,other_future_reserved_bytes,
minimum_free_bytes,quota_snapshot and quota_authority.

quota_authority binds kind=gluster_directory_quota_deem_statfs,endpoint,uid1264,
quota_root=/gfshome/alpha,volume_root=/gfshome,volume_source=sonmi1:/gv1,volume_id,
the ACTUALLY observed hard_limit_bytes,maximum_age_seconds and the exact publisher
identity from Root's newly launched publisher. No future PID is invented. Root runs
the metadata-only publisher from clean code using the same isolated entry:

```
PY -I -B ENTRY workflows.expansion.alpha_runtime_v1.quota \
  --authority OBSERVED_AUTHORITY_JSON --output LIVE_SNAPSHOT --publish
```

The publisher retains native volume-info and mount argv/output/returncodes/SHA,
directory/parent statfs and the real process identity. Atomic snapshots expire when
the publisher stops. budget_check(plan,own_output_bytes,output_root,
prequery_credit_provider=None) accepts that one aggregate output scope; verifies
the live native quota basis; subtracts remaining own outputs, all other future
reservations and the free-space floor; then checks local compute-node directory
statfs too. Only actual unchanged own inode blocks older than the quota query earn
credit. Caller-supplied prequery providers may conservatively return zero. No
original scientific input outside the output scope earns credit.

Guard(plan,stop_event=None,usage_provider=None,prequery_credit_provider=None)
samples immediately and starts a5s quota/RSS/MemAvailable monitor automatically.
check() is cheap and preserves a stop even if a later measurement recovers;
close() joins the monitor; receipt() reports actual measurements. An optional
producer's measured usage provider avoids scanning millions of output files;
invented/fixed usage is not an acceptable provider. No arbitrary wall/retry limit,
process signal or scheduler submission is implemented. Resource stops never become
chemical rejections or completed-data claims.

Root runs pure metadata tests with unittest alpha_runtime_v1.test_runtime, and
the actual Alpha native profile/quota smoke after deployment. Source preparation
and passing synthetic tests do not claim an actual Alpha producer is admitted.
