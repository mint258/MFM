# MolNet case18 source-correspondence evidence proposal

Status: **PROPOSED ONLY.** No new source adoption, rule change, index amendment,
filter release or user scope exception has been performed.

The evidence supports a narrow native investigation of whether the original
PDBbind1PTS seven-residue ligand can be covered by the already accepted exact
composition of original PDBbind1SLG. Original1PTS still has only three observed
C-alpha sites and graph UNKNOWN. Nothing here changes those observations.

## Direct source evidence

The original case18 binding and original opaque PDBbind index locate1PTS with
the annotation7-mer. The current official1PTS PDB and polymer-entity API are
byte-identical to the old source responses: PDB199179B SHA d0a26c6e...be2fa and
API1098B SHA b180040d...927e2. The API and mmCIF declare entity2, chainC/authP,
FSHPQNT, seven standard L-peptide monomers, with no nonstandard monomer or
inter-monomer linkage. Its atom table contains only HIS/PRO/GLN CA. [Official1PTS](https://www.rcsb.org/structure/1PTS).

The original PDBbind1slg SDF whole record is7972B at offset80352136 in the
closed Alpha native-record blob. Its exact source SHA is4d5c4bb6...86b4c0.
The MOLECULAR_FORMULA field is the whole literal C36H51N11O12; its header begins
at record offset7844, line228. Independently closed SDF and MOL2 native atom
tables both report C36N11O12; graph parsing remained UNKNOWN. Their two original
strict5 rows already cover this exact composition in the accepted187 index.
The machine bundle retains complete references, record offsets and SHA values.

The official1SLG description says FCHPQNT, and that literal is retained.
Its actual polymer sequence and per-position monomers instead say FSHPQNT:
PHE,SER,HIS,PRO,GLN,ASN,THR. The observed residue is SER, not CYS. Full entity metadata, including the different source-method annotations, is retained in the bundle.
Entity2 chainD/authP has two PHE alternatives. Each complete alternative includes
the common shared sites once and gives59 non-H sites, C36N11O12. ChainB/authM
lacks PHE and remains separately recorded as incomplete. ChainD includes an
explicit terminal THR OXT and N-terminal PHE N/H1/H2/H3. No coordinates,
charges or bonds were inferred. [Official1SLG](https://www.rcsb.org/structure/1SLG).

The1995 primary paper explicitly compares its redetermined linear-peptide
complex to the earlier Weber1992 complex. The compliant excerpts are
“same complex published” and “only the HPQ segment”; the exact locator is the
official entry page's PubMed-abstract section, with PMID7492542 and
DOI10.1021/bi00047a005. The full entry HTML is cached outside Git; the paper's
full text has not been acquired. [Primary research](https://pubmed.ncbi.nlm.nih.gov/7492542/).

Independent1VWA provides corroborating official observations of the same declared
standard FSHPQNT sequence and complete chainD alternatives, with the same non-H
counts. It is not substituted for original1PTS. [Official1VWA](https://www.rcsb.org/structure/1VWA).

## Evidence boundary

Matching declared sequence, standard monomers/linkage, the primary comparison,
the original complete1slg formula/atom tables and independently observed atoms
form a source-correspondence candidate. They do not make1PTS's missing atoms
experimentally observed. Original1PTS terminal atom chemistry is not directly
observed in its three-site model. Root's new source policy must explicitly judge
whether the depositor's standard-polymer entity definition and primary linkage
sufficiently identify the same chemical entity; unresolved modification or
terminal correspondence keeps the old rule active.

The original Root policy specifically restricts the peptide case to native
observations of1PTS entity2 chainC/authP. Adding sequence-derived atoms or atoms
from another entry under that old policy would violate its stated source scope.
An explicit independently validated source-correspondence version is required.
The proposed version retains the finite molecular record in decontamination and
introduces no record quarantine. The existingCOCONUT732 approval is unchanged.
Dictionary flags describe standard monomers and monomer-to-monomer links; they
are not proof that every atom was observed. [Linkage definition](https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/_entity_poly.nstd_linkage.html),
[monomer definition](https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/_entity_poly.nstd_monomer.html).

## Minimal closure route if native evidence and Root review pass

A new admitted evidence producer should verify the exact original source
segments, whole formula and observed atom metadata, and call the unchanged
original identity_keys on the two existing composition-only strict5 rows. It
must report all source alternatives and the description disagreement. It
creates no graph, CCD key, QM/UFF output or replacement original geometry.

A separate current-parent amendment can read-lock and privately back up the
accepted187 index. Prove excluded-table bidirectional equality, PK counts and a
logical digest; prove all remaining constraints and atom rows identical; remove
only the exact case18/C3 constraint after accepting its source-bound composition
coverage. The exact composition is already present under moleculenet, so no new
excluded identity row or fabricated1PTS strict5 row is necessary.

Create an explicit new source-manifest amendment and actual producer receipt,
with fresh source-index SHA/accounting and the new coverage evidence. Preserve
the old manifest, rule,21-case audit and index. Reuse the genuine187
577-input full EOF/SHA and full source-count evidence as inherited authority;
do not claim the amendment parent reread all sources or that SQLite bytes remain
identical. Keep original source counts/roles/splits and all other sources intact.
Run the unchanged full corrected-population filter against the newly accepted
index before claiming any final eligibility.

The frozen292 headers.molnet currently fixes the old acceptance/receipt schema,
two-part identities,21-disposition counter with two lower-bound cases, and
expected_rules=2 (headers.py lines36–76). Its build.constraints also fixes two
rules/subdatasets ClinTox and PDBbind (build.py lines57–76). These old contracts
should stay unchanged. A bounded index-amendment producer can validate the old
index's accepted authority and explicit new case18 coverage without relaxing
those old builders or rescanning all11 sources.

validate.py is the existing four synthetic-source fixture entry; it is not a
new-source adoption authority. C.index_header, original identity_keys, exact
composition equality, positive-bound operators and filter functions can stay
unchanged. After adoption the actual rule counts would be MolNet1/COCONUT0;
the allowed constraint-source namespace remains the original two datasets.
This count change must be explicit in the new receipt, not hidden by retaining
the old value2.

## ClinTox case00

The pinned DeepChem455d07 version has1491 records; the current official S3 file
has1484. They are distinct source versions and have not been substituted.
Both retain the exact wildcard SMILES in the first record. The files contain
SMILES and two target columns, without a concrete drug name or stable compound
ID mapping. Those target values were not used or reported in this audit.
[Official loader](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/clintox_datasets.py).

The official SWEETLEAD download page identifies the upstream database files, but
the download request requires login. No access workaround was attempted.
No concrete-drug/full-graph recovery is established for case00. Its old rule
remains unchanged. If a later explicit scope exception becomes necessary, the
smallest identifiable proposal is this single source-bound case00 row; no
approval for it or any broader MolNet exception is assumed.

## Machine bundle and actual-read boundaries

The companion JSON stores the old case18 binding, original source receipts,
old union row ordinal0=1947/ordinal1=1948, exact SDF/MOL2/native-result/source-row
segments, original formula property and two strict5 row offsets/SHA, official
payload cache pins, per-chain/per-alternative atom metadata, bibliography and
unadopted policy requirements. Complete dataset records and official payload
bodies remain outside Git.

Original Alpha native jobs1884856/1884866 and Main projection UID1278 are
separate provenance axes. The187 consumption evidence provides actual full-body
verification for the Main-exported union and strict5 projections in Alpha
UID1264 replicas. This audit freshly verifies only the stated bounded segments
and small metadata; it does not rehash the entire229MB native blob or claim a
new science-parent C0. A future native parent must bind the original actual C0
authorities and current inputs honestly, and can freshly hash that229MB blob
without replaying chemistry or the full source corpus.

