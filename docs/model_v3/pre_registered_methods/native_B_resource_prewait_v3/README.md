# Original Native B resource prewait, operational v3

The v1 coordinator closed slot027/job4524904 at bf16 seed0 update6000, then the
original v8 submit-next wrote only a PRE_SUBMISSION software registration and
refused slot028 before intent/sbatch because fewer than16 actual CPUs were free.
Root reconciled the absent028 intent/submission/layout/sbatch copy, all27 exact
closed attempts, absent old controller and actual queue. Only that unsubmitted
software registration was removed. Storage holds, Native principal/counters and
all old artifacts remain intact.

This new finite coordinator adds only a read-only resource delay before invoking
the same immutable v8 submit-next command once for a fresh slot. It waits for
16 actual free CPUs and the original32GiB+15% node MemAvailable reserve; the full
original v8/software/foreign-declaration/UUID/GPU/lock/quota guard still revalidates
and remains the sole authority. A race or any original child failure still stops
for Root reconciliation and is never automatically retried. No submitted/live/
ambiguous/failed segment is replayed. The original seven-day absolute deadline,
81 finite loop bound, science/source/CP/sampler/optimizer/seeds/member plan,
20k endpoint,2h/GPU85%/32GiB software/RSS28GiB/dual2GiB and all SDK/science gates
are unchanged. Read-only wait interval is at most60 seconds, no new compute work
is run on login. Root must verify source pins, actual public bytes and external
reconciliation receipt before launching a separate control namespace.

V3 rechecks the original absolute deadline after the bounded node/SSH observations and immediately before Popen. This prevents a ready observation that finishes after the horizon from starting a new original submit-next. V2 remains unlaunched and preserved.
