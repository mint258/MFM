from tools.extend_quality_filtered_pool import segment_identity, validation_records


def test_fixed_validation_records_and_segment_identity():
    manifest = {
        "records": [{
            "shard": "principal.lmdb",
            "real_index": 7,
            "domain": "principal",
            "parent_molecule_id": "smiles:C",
            "structure_id": "sample-7",
            "atom_count": 5,
        }]
    }
    records = validation_records(manifest)
    assert records[0].parent_molecule_id == "smiles:C"
    assert segment_identity([{"shard": "x", "start": 1, "end": 3, "count": 3}]) == [
        ("x", 1, 3, 3)
    ]
