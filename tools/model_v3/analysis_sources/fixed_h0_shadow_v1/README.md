# Fresh fixed-H0 capture then CPU terminal shadow v1

SOURCE ONLY, NOT EXECUTED. Candidate16, original48 source, production and1435's
38FAIL remain untouched. This captures a fresh same-forward H0; it never claims
those tensors are the missing1435 H0. No scientific model adoption follows.

GPU: reuse the actual numeric-v2 Root fresh-resource/receipt/fd9/UUID guard,
node21/c35,16CPU32GiB,28GiBRSS,1100s/20min,whole2GiB/private2GiB. The original
48 cases/two fixed seeds/all3 transforms run192 actual encoder forwards. Hooks
retain references only; copying occurs after the original full forward returned.
The original return object and all parameters remain unchanged. Hooks/method
wrappers are removed/restored in finally. No backend flag is changed by the
capture; original registered numerical policy remains the one executing.

Every case archives actual bankH0[44,512], pos[44,3], batch[44], actual kwargs and
all9 PD output tensors for4 states, strict complete bank tensor state plus JSON
extra-state/registry/forms. Its9 PD outputs are checked bitwise against the
untouched13-terminal-per-state original archive from that same forward. The
other original controls are retained. All48 captures are required; physics FAIL
is reported separately from successful analysis capture, never hidden or fixed.

Budget BEFORE EXECUTION (all48 bank copies, no dedup required):

|Policy|Params|F32 buffers|Bytes/case|Cases|
|---|---:|---:|---:|---:|
|H1_fixed|242377|96|969892|12|
|H1_learned|242385|96|969924|12|
|H2_fixed|306249|96|1225380|12|
|H3_fixed|371913|96|1488036|12|

All bank tensors55,838,784B=53.25MiB; allH0 tensors17,301,504B=16.5MiB.
Original52 terminal numeric controls10,902,528B=10.4MiB. Other captured
pos/batch/pairs/PD outputs<0.5MiB. Conservative NPZ/JSON/source overhead24MiB
keeps the complete input below128MiB. Actual state size is checked against this
policy table before its first forward. Writes pre-reserve numeric bytes plus
2048B/member+64KiB overhead; actual written bytes are then counted. All input
NPZ are uncompressed, typedFP32/int64 with exact keys/shapes/raw tensor hashes,
<=8MiB/case and allow_pickle=False. No fallback or sampled input is accepted.

CPU: the existing OLD/run_cpu_supervised_v3.py,16CPU16GiB allocation,
RSS12GiB,childwall120s,whole2GiB/private2GiB. SB reserves3min only for existing
supervisor cleanup; scientific CPU execution remains capped120s. One process
uses exactly4 case workers and <=4 math threads each. It sequentially rebuilds
only the original PD bank and loads captured state strictly (no encoder), then
runs original FP32 and independent functional FP64 readout for all48. Original
compensated modules reject.double(); this source never calls that shortcut.
FP64 covers same topology/weights/pooling/SiLU/centroid/products/norm, and is
explicitly an analysis shadow. CPU-FP32 versus actual GPU readout is reported,
not forced to be bitwise. Small dense/row-R/nonzero/H1/H2/H3/learnedpool parity
selfchecks run inside the same job; no extra CPU QA parent or2639 repetition.

For each transform/field the four crossed inputs are evaluated, F00,Ft0,F0t,Ftt.
L is original row-R for dipole vectors, identity for scalar/magnitude. Signed:
D=Ftt-LF00; H=L(Ft0-F00); G=F0t-LF00; I=Ftt-F0t-L(Ft0-F00).
D=H+G+I and GPU_D=H64+G64+I64+(GPU_D-D64) must close <=1e-10 componentwise.
All terms at each actual GPU argmax are retained; unrelated maxima are not added.
Only p_extensive/p_dipole/p_dipole_magnitude are shadow-evaluated, but no48
configuration/seed is omitted. No dtype promotion is claimed as FP32 acceptance.

Root first audits/source-freezes and preregisters this diagnostic. GPU launcher
'audit' does metadata-only source/public16 dual-Git-identity preflight; submit
uses the existing fresh admission and explicit new receipt. See structured
ROOT_GPU_INVOCATIONS_v1.json. Imports/audit never submit.

After actual capture C0 closure, Root provides the exact CAPTURE_COMPLETE ref,
original GPU supervisor ref, and one actual login-side sacct observation JSON:

```
{"argv":["sacct","-n","-P","-j","<actual-capture-job>","--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS"],"returncode":0,"stdout":"<actual raw single parent row>","stdout_sha256":"<raw UTF8 SHA256>"}
```

This is model-owned QA observation, not a data-line schema or a boolean C0 claim.
CPU verifies terminalCOMPLETED0:0/16CPU, matching job/source/command, supervisor
cleanup/remaining, complete48 typed source and numeric closure. No compute-node
sacct query is attempted. CPU binding template has placeholders until real refs
exist; do not submit them. The byte-identical CPU SB is also prepared in OLD for
the existing sole CPU submission helper. CPU output signed JSON and typedCSV
remain separate from both capture artifacts and1435's original failed outputs.
