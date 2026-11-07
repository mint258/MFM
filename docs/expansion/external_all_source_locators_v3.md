# External all-source identity locators: official metadata review

Prepared 2026-10-26. Status: **METADATA_ONLY_PHYSICAL_ALL_SOURCE_CLOSURE_PENDING**.
This new document supplements the registered locator catalog without editing
its historical bytes. It grants no download, pool release, global
decontamination acceptance, novelty ranking, or formal UFF/QM authority.

Only official HTML, repository text, and GitHub repository metadata were read.
No dataset archive, database body, SQL dump, pickle, labels, or scientific
features were downloaded or decoded. No server reachability test was made.
Official repository commit/blob identifiers below identify metadata source
code; they are **not** SHA256 pins of the external data files.

## Metadata versions actually located

The GitHub connector returned these branch heads on the preparation date.
Immutable file links in this document use the returned commit, while payload
versions remain PENDING.

| Official repository | Observed branch head |
| --- | --- |
| [COCONUT](https://github.com/Steinbeck-Lab/coconut/commit/6f1f6e45fe18d4868ca8653c1e3f111ecc68c202) | `6f1f6e45fe18d4868ca8653c1e3f111ecc68c202` |
| [MARCEL](https://github.com/SXKDZ/MARCEL/commit/dae6b3b824b68d1362ed3b9fa23b34a45fa5366c) | `dae6b3b824b68d1362ed3b9fa23b34a45fa5366c` |
| [DeepChem](https://github.com/deepchem/deepchem/commit/455d07f3e17e880a4d980b5b0365e4a02b417e14) | `455d07f3e17e880a4d980b5b0365e4a02b417e14` |
| [TDC](https://github.com/mims-harvard/TDC/commit/c310c35f27e3f506411018ac43d97b8ba23ca652) | `c310c35f27e3f506411018ac43d97b8ba23ca652` |

## COCONUT: complete active/inactive scope remains unproved

The [official download page](https://coconut.naturalproducts.net/download)
places only the SQL dump under its complete active/inactive heading. It
separately lists CSV lite/full. The [official format documentation](https://steinbeck-lab.github.io/coconut/versions.html)
describes SQL as the complete database and CSV lite/full as different field
sets; that description does not establish equal active/inactive ID coverage.
The [table documentation](https://steinbeck-lab.github.io/coconut/data.html)
includes both molecules and structures in the dump.

The [actual download template](https://github.com/Steinbeck-Lab/coconut/blob/6f1f6e45fe18d4868ca8653c1e3f111ecc68c202/resources/views/livewire/download.blade.php)
uses the current clock to construct the visible month and filenames.
The displayed sizes are literal template text. Therefore its October 2026
label and 31.91 GB / 191 MB / 207.9 MB labels do not prove payload existence,
HTTP Content-Length, release completeness, or an immutable release version.
Template blob: `18bf31272a0d149eea026ead7a28290238565e5c`.

| Template-derived candidate URL, not fetched | Displayed size only | Coverage state |
| --- | --- | --- |
| [coconut-dump-10-2026.sql](https://coconut.s3.uni-jena.de/prod/downloads/2026-10/coconut-dump-10-2026.sql) | 31.91 GB | Officially described active/inactive; actual bytes/IDs PENDING |
| [coconut_csv_lite-10-2026.zip](https://coconut.s3.uni-jena.de/prod/downloads/2026-10/coconut_csv_lite-10-2026.zip) | 191 MB | Inactive-ID coverage PENDING |
| [coconut_csv-10-2026.zip](https://coconut.s3.uni-jena.de/prod/downloads/2026-10/coconut_csv-10-2026.zip) | 207.9 MB | Inactive-ID coverage PENDING |

A smaller CSV can close this project's all-source scope only after a
same-release, independently counted all-ID equality proof against the complete
active/inactive identity universe. Otherwise the complete dump remains the
required locator. A future extractor must project identity columns from every
molecule/structure state, retain missing identities and unresolved composition,
and account for all IDs without status/target/property filtering. Its exact
table columns and any molecule-to-structure multiplicities remain PENDING
until current schema metadata and physical bytes are bound. No database import
or arbitrary SQL execution is proposed here. The future acquisition/storage
budget must use actual server metadata rather than the displayed sizes.

## TDC ADMET: 22 endpoints, train_val plus test

The [official overview](https://tdcommons.ai/benchmark/admet_group/overview/)
defines 22 endpoints and exposes train_val and test. The exact
[metadata source](https://github.com/mims-harvard/TDC/blob/c310c35f27e3f506411018ac43d97b8ba23ca652/tdc/metadata.py)
maps admet_group to ZIP file ID 4426004; metadata blob
`b805138e308e3a95b5bf6b60532c40b082a2f890`.
The [download wrapper](https://github.com/mims-harvard/TDC/blob/c310c35f27e3f506411018ac43d97b8ba23ca652/tdc/utils/load.py)
uses [Dataverse file 4426004](https://dataverse.harvard.edu/api/access/datafile/4426004).
The [group source](https://github.com/mims-harvard/TDC/blob/c310c35f27e3f506411018ac43d97b8ba23ca652/tdc/benchmark_group/base_group.py)
reads each endpoint's train_val.csv and test.csv and derives train/valid from
train_val. Consequently both physical files per endpoint are required.

The exact metadata endpoint set is:

```text
caco2_wang hia_hou pgp_broccatelli bioavailability_ma
lipophilicity_astrazeneca solubility_aqsoldb bbb_martins ppbr_az
vdss_lombardo cyp2d6_veith cyp3a4_veith cyp2c9_veith
cyp2d6_substrate_carbonmangels cyp3a4_substrate_carbonmangels
cyp2c9_substrate_carbonmangels half_life_obach
clearance_microsome_az clearance_hepatocyte_az herg ames dili ld50_zhu
```

This yields 44 required CSV locators, not 44 measured files. Future extraction
must independently count every original row and project source record ID,
Drug/SMILES and split only, with no target/feature decoding or label-based
row filter. Identity-field spelling, missingness, archive members, compressed
and expanded bytes, exact current SHA and all-split conservation remain
PENDING. The web tool could not access the Dataverse metadata endpoint; this
does not establish a server network result. No alternate mirror or access
workaround was used.

## MARCEL: original full archives, not selected conformers

The official [Drugs instructions](https://github.com/SXKDZ/MARCEL/blob/dae6b3b824b68d1362ed3b9fa23b34a45fa5366c/datasets/Drugs/README.md)
give 75099 molecules / 558002 conformers and link
[Drugs.zip](https://drive.google.com/file/d/1PHgbrxdDyyjnxSUA71zXWG8WNwocDLPH/view?usp=sharing).
It contains Drugs.sdf and Drugs.csv. Molecules use name; conformers use ID.
The [loader source](https://github.com/SXKDZ/MARCEL/blob/dae6b3b824b68d1362ed3b9fa23b34a45fa5366c/benchmarks/data/drugs.py)
also exposes the SDF smiles property. README blob:
`b55ed39b852281c3fb7702e9d3acd7cf02f4e2cf`.

The official [Kraken instructions](https://github.com/SXKDZ/MARCEL/blob/dae6b3b824b68d1362ed3b9fa23b34a45fa5366c/datasets/Kraken/README.md)
give 1552 ligands / 21287 conformers and link
[Kraken.zip](https://drive.google.com/file/d/1QrV651Re7s6UF7Lg4KC9PM5QQUMPU7wd/view?usp=sharing).
Kraken.pickle is keyed by ligand ID and contains SMILES plus other data;
the original-author permission statement remains part of those instructions.
README blob: `3b296d59dde00205c2b7450e884a8334e52f1ba4`.

These are upstream descriptive counts, not current extracted counts. Both
archives' byte size, SHA, accessible payload version, identity completeness
and original all-split ID coverage remain PENDING. For Drugs, project only
name/ID/SMILES and the CSV name column; independently count all SDF boundaries
and all CSV rows, then prove complete molecule ID coverage and keep missing
identities. Do not run MARCEL's descriptor/energy sorting, pre_filter or
training loaders. For Kraken, this document does not authorize pickle.load:
a separately reviewed identity-only restricted-format extractor or an
authoritative plain identity export with complete-ID proof is still needed.
No descriptor object should be decoded merely to locate ligand SMILES.
Google Drive login, confirmation, quota or network restrictions must be
reported rather than bypassed.

## MoleculeNet: preserve the proposed 17-dataset union

The 17 rows below preserve this project's conservative proposed union. It
has not been narrowed to the six locally available CSVs. URLs and identity
fields come from the linked official loaders at the observed DeepChem
commit; none of the linked payloads was fetched. The literal official S3
host spelling is preserved. A loader code pin is not a dataset version or
a claim that all original records survive its featurization.

| Dataset | Official loader evidence | Candidate physical locator | Identity projection boundary |
| --- | --- | --- | --- |
| BACE | [bace_datasets.py](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/bace_datasets.py) | [bace.csv](https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/bace.csv) | CSV mol |
| BBBP | [bbbp_datasets.py](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/bbbp_datasets.py) | [BBBP.csv](https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/BBBP.csv) | CSV smiles |
| ClinTox | [clintox_datasets.py](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/clintox_datasets.py) | [clintox.csv.gz](https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/clintox.csv.gz) | CSV smiles |
| ESOL | [delaney_datasets.py](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/delaney_datasets.py) | [delaney-processed.csv](https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/delaney-processed.csv) | CSV smiles |
| FreeSolv | [freesolv_dataset.py](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/freesolv_dataset.py) | [freesolv.csv.gz](https://deepchemdata.s3.us-west-1.amazonaws.com/datasets/freesolv.csv.gz) | CSV smiles; preserve literal official host spelling |
| HIV | [hiv_datasets.py](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/hiv_datasets.py) | [HIV.csv](https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/HIV.csv) | CSV smiles |
| Lipophilicity | [lipo_datasets.py](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/lipo_datasets.py) | [Lipophilicity.csv](https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/Lipophilicity.csv) | CSV smiles |
| MUV | [muv_datasets.py](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/muv_datasets.py) | [muv.csv.gz](https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/muv.csv.gz) | CSV smiles; mol_id locator |
| PCBA | [pcba_datasets.py](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/pcba_datasets.py) | [pcba.csv.gz](https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/pcba.csv.gz) | CSV smiles; filename passed by load_pcba |
| PDBbind | [pdbbind_datasets.py](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/pdbbind_datasets.py) | [pdbbind_v2019_other_PL.tar.gz](https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/pdbbindv2019/pdbbind_v2019_other_PL.tar.gz) | General component only; refined/core locators below |
| QM7 | [qm7_datasets.py](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/qm7_datasets.py) | [qm7.mat](https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/qm7.mat) | Original MAT locator; Z-only conservative identity when graph absent |
| QM7b | [qm7_datasets.py](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/qm7_datasets.py) | [qm7b.mat](https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/qm7b.mat) | Declared official constant; actual variables/graph identity PENDING |
| QM8 | [qm8_datasets.py](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/qm8_datasets.py) | [gdb8.tar.gz](https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/gdb8.tar.gz) | Original SDF archive locator; CSV companion below |
| QM9 | [qm9_datasets.py](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/qm9_datasets.py) | [qm9.tar.gz](https://deepchemdata.s3.us-west-1.amazonaws.com/datasets/qm9.tar.gz) | Current loader SDF archive; do not replace existing raw 133885 source scope |
| SIDER | [sider_datasets.py](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/sider_datasets.py) | [sider.csv.gz](https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/sider.csv.gz) | CSV smiles |
| Tox21 | [tox21_datasets.py](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/tox21_datasets.py) | [tox21.csv.gz](https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/tox21.csv.gz) | CSV smiles |
| ToxCast | [toxcast_datasets.py](https://github.com/deepchem/deepchem/blob/455d07f3e17e880a4d980b5b0365e4a02b417e14/deepchem/molnet/load_function/toxcast_datasets.py) | [toxcast_data.csv.gz](https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/toxcast_data.csv.gz) | CSV smiles |

PDBbind's linked loader builds three explicit archive locators: the general
component above, [v2019 refined](https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/pdbbindv2019/pdbbind_v2019_refined.tar.gz),
and [v2013 core](https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/pdbbind_v2013_core_set.tar.gz).
Do not call a core-only download full PDBbind coverage or infer that the
loader's general component includes refined. The intended version/set union,
all ligand files and any missing/invalid ligands must be closed explicitly
before acceptance; proteins/affinity columns are outside identity projection.

Other constants in the linked QM loaders include
[QM7 original CSV](https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/qm7.csv),
[QM7 SDF v2](https://deepchemdata.s3.us-west-1.amazonaws.com/datasets/gdb7_v2.tar.gz),
[QM8 CSV](https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/qm8.csv),
[QM9 CSV](https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/qm9.csv),
and [older GDB9 SDF archive](https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/gdb9.tar.gz).
They are different physical versions until an ID-level equivalence proof
exists. In particular a converted/sanitized CSV/SDF subset cannot replace
the already located original QM7 Z rows or all 133885 original QM9 members.
The current identity export keeps those original sources regardless of
later benchmark exclusions. QM7b numeric arrays cannot be presumed to carry
graph, isotope or stereo identity before the actual schema is checked.

For every row, the acceptance fields remain:
current raw URL/version and redirects; physical bytes and full SHA256;
independent original record count; identity missingness; all-split membership
or proof that every split is a subset of the complete original-ID universe;
and conserved output IDs plus explicit unresolved/composition exclusions.
Do not filter on missing target values or loader featurization success.
No benchmark target or feature may determine novelty ranking or sampling.

## Explicit unfinished acquisition and acceptance steps

The future Root-owned CPU allocation should first perform bounded official
metadata/HEAD access and freeze actual source versions, sizes and a whole
storage budget. A URL available to the web tool is not proof of server
reachability. Any HTTP/network/access limitation is preserved as a blocker,
without proxy, mirror substitution, VPN, login bypass or repeated rate-limit
evasion. Actual retrieval, current SHA/count extraction and full identity
coverage require new reviewed requests; they have not occurred in this
metadata preparation.

All four external families remain **PENDING**. A successful local 76-input
pin job or local identity export closes only its explicitly bound local
source population. It cannot substitute for TDC's 22 full endpoints, the
proposed 17 MoleculeNet datasets, both MARCEL archives or complete COCONUT
active/inactive coverage. The old test-only embargo remains historical
evidence, not an all-source proof.

