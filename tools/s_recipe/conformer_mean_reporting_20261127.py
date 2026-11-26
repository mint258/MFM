"""Report the previously unreported full-cohort mean once; reuse cap deliveries."""
import json
from pathlib import Path

from cpu_execution_20261126 import execution_fields, native_record
from storage_20261122 import REPO as R, write


def means():
    native_record()
    read = lambda path: json.loads(Path(path).read_text())
    target = R/'results/s_recipe/E1_actual_mean_conformers_20261127.json'
    if target.exists():
        return read(target)['mean_allowed_PM7']
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    population = read(R/'configs/s_recipe/population.json')
    count, total = 0, 0
    # This aggregate was absent from the original delivery. No identity, geometry,
    # label or prediction is loaded, and the population is never rebuilt.
    for batch in pq.ParquetFile(population['train']).iter_batches(
            columns=['PM7'], batch_size=65536):
        lengths = pc.list_value_length(batch.column(0))
        if lengths.null_count or pc.min(lengths).as_py() < 1 or pc.max(lengths).as_py() > 10:
            raise ValueError('Original allowed PM7 lists must contain 1..10 entries')
        count += len(batch)
        total += pc.sum(lengths).as_py()
    if count != population['TRAIN_molecules'] or count != 1192951:
        raise ValueError('Full-cohort cardinality must match the frozen population')
    result = {str(k): read(R/'configs/s_recipe/extensions_20261124'/
              ('k'+str(k)+'_population.json'))['mean_allowed_PM7'] for k in (1, 2, 5)}
    result['10'] = total/count
    write(target, dict(status='COMPLETE', mean_allowed_PM7=result,
        TRAIN_molecules=count, original_k10_allowed_PM7_count=total,
        k10_source=population['train'], original_column='PM7',
        cap_means_reused=True, population_rebuilt=False,
        role='First missing descriptive aggregate only; no training or evaluation',
        **execution_fields()))
    return result
