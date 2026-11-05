Prepared only; child has not signalled, run this fixture, or executed the guard.

Use actualnode0 /usr/bin/python3 (pidfd supported), not Chemprop Python.
Only the new test_guard_pp6126_boundary.py method is pending; it now includes
safe exit, unsafe and unknown capacity with zero CONT, atomic recovery state,
and later capacity-confirmed resume. Do not repeat already passed49/50/51.

The guard's final exit rechecks actual statvfs before each CONT. If available
bytes are below53GiB or available inodes are not above the reserved count, or
capacity cannot be read, confirmed-boundary workers stay parked. It atomically
saves exactPID/start/UID/job/argv/cgroup and parent/target to:
  CONTROL/pp6126_ram_guard_parked_state.json
This is process-control recovery state, not a delivery or acceptance receipt.
stdout prints the reason and this Root recovery command:
  /usr/bin/python3 -B CONTROL/guard_pp6126_ram.py --resume-state CONTROL/pp6126_ram_guard_parked_state.json --execute

Recovery again verifies the actual owned RAM filesystem, capacity and exact
process identities. It never sends CONT to a different/reused PID. Unsafe or
unknown capacity leaves workers parked and retains the state. Normal/INT/TERM
exit does not override the filesystem reserve. ForcedSIGKILL/host failure cannot
run Pythonfinally; Root owns monitoring and recovery. No activeNative or timer
phase is ever parked. Current free160GB means the guard should park nothing.
