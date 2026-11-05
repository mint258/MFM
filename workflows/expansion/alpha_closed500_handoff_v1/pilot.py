"""Count real accepted heavy0/empty composition only inside an allocated pilot."""
from pathlib import Path
from ..alpha_runtime_v1.common import frame, need


def domain_observation(receipt, guard):
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    ref = receipt['accepted_parquet']; path = Path(ref['path']); before = frame(path)
    total = heavy0 = empty = both = inconsistent = 0; examples = []
    columns = ['cid', 'full_key', 'source_smiles', 'heavy_atoms', 'non_h_composition', 'elements']
    with pq.ParquetFile(path) as parquet:
        for batch in parquet.iter_batches(batch_size=8192, columns=columns, use_threads=False):
            guard.check()
            import pyarrow as pa
            table = pa.Table.from_batches([batch]); zero = pc.equal(table['heavy_atoms'], 0); blank = pc.equal(table['non_h_composition'], '[]')
            equal = pc.and_(zero, blank); legal_empty = pc.and_(equal, pc.equal(pc.list_value_length(table['elements']), 0))
            total += len(table); heavy0 += pc.sum(pc.cast(zero, pa.int64())).as_py() or 0; empty += pc.sum(pc.cast(blank, pa.int64())).as_py() or 0
            both += pc.sum(pc.cast(equal, pa.int64())).as_py() or 0
            inconsistent += pc.sum(pc.cast(pc.and_(pc.or_(zero, blank), pc.invert(legal_empty)), pa.int64())).as_py() or 0
            if len(examples) < 20:examples.extend(table.filter(pc.or_(zero, blank)).slice(0, 20-len(examples)).to_pylist())
    need(frame(path) == before and total == receipt['accepted_rows'], 'Actual accepted pilot source changed or was not counted completely')
    return {'schema': 'ALPHA_ACTUAL_TYPED_H_ONLY_DOMAIN_OBSERVATION_V1', 'source_fragment_id': receipt['source_fragment']['fragment_id'], 'accepted_parquet': ref, 'accepted_rows_counted': total, 'actual_heavy_atoms_zero': heavy0, 'actual_empty_non_H_composition': empty, 'actual_both_zero_and_empty': both, 'actual_inconsistent_zero_empty_fields': inconsistent, 'actual_examples_first20': examples, 'new_chemical_calls': 0, 'source_screen_decisions_modified': False}
