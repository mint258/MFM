# Retained six-CSV byte census: physical lines are not chemical samples

SOURCE ONLY / NOT EXECUTED. This is an independent bounded diagnosis. It edits
neither the registered FORMAT source/reports, the frozen six-CSV11 implementation,
nor queue v12/v11/PubChem sources. Queue v12 deliberately rejects this new key;
Root needs a separate exact adapter/review before any actual CPU submission.

The static audit found no rule that doubles normal CRLF. The frozen
CSVProjection.feed increments decoded_bytes, then, when pending_cr is set, skips
an immediately following LF. pending_cr survives feed chunk boundaries. Its
quoted branch treats CR/LF as field bytes. Therefore one unquoted CRLF closes one
record. The original test_CSV_RFC4180_projection_never_decodes_assay already feeds
three-byte chunks with quoted CRLF and asserts two data records. The frozen new
callback tests also compare one/two/seven-byte chunks against original summaries.
Those fixtures are source/grammar evidence; they do not establish actual payload
newline bytes. Actual792's HIV82255/MUV186175/PCBA875859 and short41128/93088/437930
are unusual observed populations, not evidence sufficient to declare CRCRLF or a
parser fault. The actual cause remains UNKNOWN until retained bytes are read on CPU.

Six-source actual792 metadata totals1162144 logical physical data records:
589998 have the complete header width and572146 are short. Full width, nonblank
SMILES, original logical records and literal physical lines are different counts.
None is an effective molecule count or a valid/full-key identity count. Blank,
missing, invalid, duplicate/zero IDs and no-key rows remain preserved by the
frozen six-CSV stage; this diagnosis does not remove, normalize or rewrite them.

The new pure ByteCensus never text-decodes a source value. It counts raw CR, LF,
CRLF and CRCRLF through the complete decoded stream, including cross-chunk
patterns. CRCRLF contains a CRLF suffix, so these pattern counts are explicitly
not disjoint. Bare CR/LF are derived from raw counts minus CRLF. Only the first
four pattern offsets are saved, without raw context, identity strings or assay
values. It independently counts quote-agnostic physical lines with CRLF as one
terminator, literal empty body lines and nonempty ASCII-space/tab-only body lines.
Those lines include the header and any embedded newlines inside quoted fields.
EOF adds no imaginary trailing empty line. Empty-line evidence contains only
ordinal/offset/span/terminator labels, at most four examples; no body values.

In parallel for each same decoded chunk, the unchanged original CSVProjection
computes its original structural summary. Its own selected identity UTF8 counters
still run as originally defined, but no identity or assay values are persisted.
All header/count/selected-field statistics, decoded bytes and decoded SHA must
match792. The report presents both counts and their difference rather than
subtracting physical blank lines from a claimed chemical population. A byte pattern
can support a later reviewed explanation; the program does not automatically
assert source cause or infer a number of effective molecules. Quoted-newline
physical lines remain visibly separate from logical CSV record boundaries.

The CPU job verifies each current complete compressed/plain payload SHA and
fstat against the actual792 retained frame, then reads every decoded byte through
EOF and gzip CRC (plain HIV says CRC not applicable). The source output metadata
is the already frozen code/secondary_moleculenet_csv6_identity_v1/
format792_authority.json. Six original payload references stay scientific data;
no login body hash/parse is authorized by this source-only handoff. There are no
new GET, key, X-rule, descriptor, UFF, QM, native graph, pool or training operations.
QM7b/SDF/MOL2 identity remains outside this diagnosis. All source files and older
results remain unchanged.

Protocol:
- key moleculenet_csv6_newline_diagnosis_alpha_v1;
- MODULE secondary_csv6_newline_diagnosis_v1.run;
- plan SECONDARY_CSV6_NEWLINE_DIAGNOSIS_PLAN_V1;
- proof SECONDARY_CSV6_NEWLINE_DIAGNOSIS_STARTUP_V1;
- stage SIX_CSV_RETAINED_NEWLINE_BYTE_CENSUS;
- mode newline_diagnosis, scope_mode BOUNDED_SIX_CSV_ORIGINAL_BYTES_DIAGNOSIS;
- analysis, pilot=false, performance_profile=false; CPU16/no requested memory or
  exclusive; whole-minute wall<=1800s, whole output64MiB;
- fixed current storage_scope_v7_pubchem_uniform_index_copy_v1.json and normal
  PYTHONPATH=Alpha/code. Exact parameters are contracts.parameters(mode).

Entry uses the usual complete eight argv:
python -B -m secondary_csv6_newline_diagnosis_v1.run --plan PLAN --startup-proof PROOF
The guard binds fresh Alpha UID1264/node/boot/PID/argv/script/Slurm state and
recomputes the signed raw storage/scope/all-caps/200GB summary. Root review and all
new/imported code pins are mandatory. It reuses the same actual792 historical
receipt/plan/proof/fixtures/account+raw parents and six report source refs as the
frozen six-CSV interface. The original test_profile.py source is also required
through792 fixtures.source_reference. The shared pure integrity writer comes
from the frozen six-CSV journal/runtime; its exact sources must be approved.
All11 source authority helper pins are preserved even though no B key function
is called. The new9 files and every frozen six-CSV file must be source pins.

The unchanged original8 pure input-format fixture methods plus3 new byte-census
fixtures must actually pass11/zero failures/errors/skips/expected failures/
unexpected successes before any payload read. New fixtures establish normal
CRLF chunk invariance, a synthetic CRCRLF empty-line case, quoted-newline physical
versus logical record counts and EOF behavior. A synthetic CRCRLF example is
never claimed as an observation of actual source bytes. No tests ran during this
source-only implementation; Root performs the actual CPU gate.

Six source threads run at most, despite16 allocated CPUs;16 busy workers are not
claimed. The job observes actual RSS/MemAvailable/free storage and owned bytes.
Its64MiB cap includes an8MiB drain/failure reserve. It stops new chunks/work on
software pressure and lets threads return without signals. Every successful
source report is independently persisted; partial/unknown source failures are
retained. A completed byte census still requires interpretation and grants no
identity, decontamination, global pool, UFF/QM/training/export release. Actual
parent cost remains pending Root accounting, including failed/startup attempts;
multiplier1.5 overrun REPORT_AND_CONTINUE leaves quality thresholds unchanged.
