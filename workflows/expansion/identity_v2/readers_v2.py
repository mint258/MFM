"""Only allowlisted identity/role columns from actual compute-pinned inputs.

No automatic column inference, target filtering, descriptor, coordinate graph
guess or unsafe pickle load is permitted. These primitives are not a launcher.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import io
from pathlib import Path
import re
import tarfile

from ..common import require


FORMAL_COLUMNS = ("record_id", "molecule_id", "smiles", "canonical_smiles", "isomeric_smiles",
                  "reidentified_smiles", "stored_inchikey", "reidentified_inchikey",
                  "member_train", "member_full", "member_routine")
EMBARGO_COLUMNS = ("record_id", "molecule_id", "smiles", "canonical_smiles", "isomeric_smiles",
                   "reidentified_smiles", "stored_inchikey", "reidentified_inchikey", "legacy_QA_status", "element_counts")
CSV_COLUMNS = {"dataset", "sample_id", "sample_uid", "compound_id", "isoform", "fold", "source_sdf",
               "SMILES", "SMILES_isomeric", "xyz_path", "Compound ID", "Molecule Name"}
MAX_LINE_BYTES = 1 << 20
MAX_QM9_RECORD_BYTES = 2 << 20


def csv_identity_rows(ticket, columns):
    import pyarrow as pa
    import pyarrow.csv as pc
    require(columns and len(set(columns)) == len(columns) and set(columns) <= CSV_COLUMNS,
            "Only explicit ID/role/SMILES CSV projection is allowed")
    path = ticket.current_path()
    with pc.open_csv(str(path), read_options=pc.ReadOptions(use_threads=False, block_size=1 << 20),
                     parse_options=pc.ParseOptions(newlines_in_values=True),
                     convert_options=pc.ConvertOptions(include_columns=list(columns),
                                                       column_types={k: pa.string() for k in columns})) as stream:
        for batch in stream:
            require(batch.schema.names == list(columns), "CSV projection returned unreviewed columns")
            yield from batch.to_pylist()
    ticket.current_path()


def parquet_identity_batches(ticket, *, embargo=False, row_groups=None, batch_size=8192):
    import pyarrow.parquet as pq
    require(ticket.source_id == ("v1_embargo4900" if embargo else "v1_formal"), "Wrong v1 physical identity source")
    columns = EMBARGO_COLUMNS if embargo else FORMAL_COLUMNS
    source = pq.ParquetFile(ticket.current_path())
    require(set(columns) <= set(source.schema_arrow.names), "Missing actual v1 identity/original-role column; no fabricated fallback")
    require(1 <= batch_size <= 32768, "Bounded identity batch required")
    for batch in source.iter_batches(columns=list(columns), row_groups=row_groups, batch_size=batch_size, use_threads=False):
        require(batch.schema.names == list(columns), "Unexpected v1 feature/target column materialized")
        yield batch
    ticket.current_path()


def json_identity_rows(ticket, kind):
    """Explicit Arrow schema skips all unlisted JSON values and nested features."""
    import pyarrow as pa
    import pyarrow.json as pj
    base = [("dataset", pa.string()), ("status", pa.string())]
    if kind in ("cyp_sources", "cyp_folds", "az_sources", "az_folds"):
        fields = base + [("source_file", pa.string()), ("source_record_1based", pa.int64()),
                         ("sample_id", pa.string()), ("sample_uid", pa.string()), ("compound_id", pa.string()),
                         ("fold", pa.int64()), ("inchikey", pa.string()), ("atomic_numbers", pa.list_(pa.int64()))]
        require(ticket.source_id == "ledger_" + kind, "Wrong source-ledger kind")
    elif kind == "qm_sources":
        identity = pa.struct([("smiles", pa.string()), ("inchikey", pa.string()), ("token_sha256", pa.string())])
        fields = base + [("sample_id", pa.string()), ("fold", pa.string()), ("source_path", pa.string()),
                         ("source_sha256", pa.string()), ("source_bytes", pa.int64()),
                         ("original_gdb", identity), ("relaxed", identity)]
        require(ticket.source_id == "ledger_qm_source_records", "Wrong original QM source ledger")
    else:
        raise ValueError("Unreviewed JSON identity schema")
    schema = pa.schema(fields)
    with pj.open_json(str(ticket.current_path()), read_options=pj.ReadOptions(use_threads=False, block_size=1 << 20),
                      parse_options=pj.ParseOptions(explicit_schema=schema, unexpected_field_behavior="ignore")) as stream:
        for batch in stream:
            require(batch.schema == schema, "Unlisted JSON values entered identity projection")
            yield from batch.to_pylist()
    ticket.current_path()


def qm7_native_z(ticket):
    """Only the original Z variable; X/T/R and generated XYZ are never loaded."""
    from scipy.io import loadmat
    require(ticket.source_id == "qm7_raw_mat_Z_only" and ticket.physical_count == 7165, "Actual7165-row original Z pin required")
    data = loadmat(ticket.current_path(), variable_names=("Z",))
    require(set(data) <= {"Z", "__header__", "__version__", "__globals__"} and "Z" in data,
            "MAT loader returned an undeclared numeric variable")
    z = data["Z"]
    require(z.ndim == 2 and z.shape[0] == 7165, "Original native Z row universe changed")
    for i in range(7165):
        yield i + 1, z[i].tolist()
    ticket.current_path()


def qm9_identity_tokens(source):
    """Identity tokens and native symbols only; scalar/coordinate values opaque.

    Exact historical format: two SMILES tokens on1-based N+4, original GDB
    then relaxed. No descriptor line or coordinate is converted to a number.
    """
    require(len(source) <= MAX_QM9_RECORD_BYTES, "QM9 source exceeds reviewed I/O bound; stop, never exclude")
    stream = io.BytesIO(source)

    def line():
        value = stream.readline(MAX_LINE_BYTES + 1)
        require(value and len(value) <= MAX_LINE_BYTES, "Truncated or oversized original QM9 structural framing")
        return value

    count_token = line().strip()
    require(count_token.isdigit() and int(count_token) > 0, "Invalid original QM9 source atom-count framing")
    atom_count = int(count_token)
    line()  # Scalar/property row remains opaque bytes.
    symbols = Counter()
    for _ in range(atom_count):
        token = line().split(maxsplit=1)[0]
        require(re.fullmatch(rb"[A-Z][a-z]?", token) is not None, "Invalid native atom symbol")
        symbols[token.decode("ascii")] += 1
    line()  # Frequency row remains opaque bytes.
    tokens = line().split()
    require(len(tokens) == 2, "Two original/relaxed source SMILES tokens required")
    smiles = [token.decode("ascii") for token in tokens]
    line()  # InChI row remains opaque; no attempt to repair graph from it.
    require(not stream.read().strip(), "Unexpected original QM9 trailing payload")
    return {"original_gdb_smiles": smiles[0], "relaxed_smiles": smiles[1],
            "native_symbol_counts": dict(symbols), "source_sha256": hashlib.sha256(source).hexdigest(),
            "source_bytes": len(source), "identity_line_1based": atom_count + 4}


def qm9_archive_rows(ticket):
    """Current original133885 members; missing archive must remain PENDING."""
    require(ticket.source_id == "qm9_raw_original_archive" and ticket.physical_count == 133885,
            "Actual complete original archive pin required before opening its payload")
    seen = set()
    with tarfile.open(ticket.current_path(), mode="r|*") as archive:
        for member in archive:
            # Stream mode still retains TarInfo in some Python versions. Free
            # metadata already consumed; no source file is deleted or changed.
            archive.members.clear()
            if not member.isfile():
                continue
            match = re.fullmatch(r"dsgdb9nsd_(\d{6})\.xyz", Path(member.name).name)
            require(match is not None and 0 < member.size <= MAX_QM9_RECORD_BYTES, "Unexpected archive member; stop without filtering")
            sample_id = int(match.group(1))
            require(1 <= sample_id <= 133885 and sample_id not in seen, "Original QM9 archive ID duplicated/outside declared universe")
            seen.add(sample_id)
            with archive.extractfile(member) as stream:
                source = stream.read(MAX_QM9_RECORD_BYTES + 1)
            require(len(source) == member.size, "QM9 archive source member changed/truncated")
            yield sample_id, qm9_identity_tokens(source)
    require(seen == set(range(1, 133886)), "Never accept a successful-only QM9 subset")
    ticket.current_path()
