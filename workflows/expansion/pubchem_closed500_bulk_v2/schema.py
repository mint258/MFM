"""Original stored Arrow layout; no molecular calculation is imported."""
FLOAT_FEATURES = ('molecular_weight_Da', 'tpsa_A2', 'logp')
INT_FEATURES = ('heavy_atoms', 'isotopic_atoms', 'rings', 'aromatic_rings', 'rotatable_bonds', 'hbd', 'hba', 'stereocenters')
TEXT_FEATURES = ('isomeric_smiles', 'full_key', 'wp5_key', 'non_h_composition', 'element_combination', 'generic_murcko', 'ecfp4_2048_hex')


def original_schema():
    import pyarrow as pa
    import pyarrow.parquet as pq
    fields = [(name, pa.string()) for name in ('sample_group', 'cid_source_ascii', 'source_smiles', 'source_smiles_sha256', 'source_part_reference_json', 'category', 'audit_flags_json', 'full_dispatcher_result_json', 'error_evidence_json')]
    fields += [('ordinal', pa.int64()), ('worker_pid', pa.int64()), ('audit_parse_succeeded', pa.bool_()), ('technical_codes', pa.list_(pa.string())), ('legacy_reasons', pa.list_(pa.string()))]
    fields += [('audit_' + name, pa.bool_()) for name in ('X01', 'X02', 'X03', 'X04', 'X05')]
    fields += [(name, pa.float64()) for name in (*FLOAT_FEATURES, 'audit_wall_seconds', 'audit_CPU_seconds', 'dispatcher_wall_seconds_includes_legacy_X_parse', 'dispatcher_CPU_seconds_includes_legacy_X_parse')]
    fields += [(name, pa.int64()) for name in INT_FEATURES] + [(name, pa.string()) for name in TEXT_FEATURES]
    fields += [('elements', pa.list_(pa.int32())), ('generic_ring_systems', pa.list_(pa.string()))]
    # Match the original compliant Parquet Writer list-child representation.
    sink = pa.BufferOutputStream()
    schema = pa.schema(fields)
    with pq.ParquetWriter(sink, schema, compression='zstd') as writer:
        writer.write_table(pa.Table.from_batches([], schema=schema))
    return pq.read_schema(pa.BufferReader(sink.getvalue()))
