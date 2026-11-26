"""One CPU producer for registered cap/subset views; original inputs read only."""
import json
import os
from pathlib import Path
import socket
import sys

ROOT = Path('/share/home/zixiao/descriptor_analysis')
REPO = ROOT/'MFM_s_recipe'
CONTROL = ROOT/'runs/s_recipe_20261120'
if socket.gethostname().split('.')[0] not in {'compute-0-'+str(i) for i in range(8,20)} or os.environ.get('CUDA_VISIBLE_DEVICES'):
    raise ValueError('CPU-only actual allocation required')
sys.path.insert(0, str(REPO/'tools/s_recipe'))
from storage_20261122 import write, shared_guard
from extension_population_20261124 import conformer_rows, intersect_saved_mids
shared_guard.check_with_timeout('s-recipe', 'node_ram', 4*1024**3)
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
pa.set_cpu_count(1)
pa.set_io_thread_count(1)
sys.path.insert(0, str(ROOT/'MFM_p_recipe/current'))
from phychem_mfm.phase1.p_recipe_data import train_indices

read = lambda p: json.loads(Path(p).read_text())
base = read(REPO/'configs/s_recipe/population.json')
output = CONTROL/'extension_populations_20261124'
if (output/'COMPLETE.json').exists():
    raise ValueError('Population producer already closed; never resample or replay')
output.mkdir(exist_ok=False)
manifest = read(Path(base['source_root'])/'manifest.json')
id_map = Path(manifest['split_roots']['TRAIN'])/'id_map.parquet'
id_table = pq.read_table(id_map, columns=['molecule_id','molecule_index'],
                         filters=[('record_kind','=','M')])
index_to_mid = dict(zip(id_table['molecule_index'].to_pylist(), id_table['molecule_id'].to_pylist()))
del id_table
subsets = {}
origins = {}
for arm, nominal in (('T5',250000),('T6',500000)):
    ref = ROOT/'MFM_p_recipe/configs/p_recipe/fixed_20261115/confirmation'/(arm+'.json')
    c = read(ref)
    if (c['root'] != base['source_root'] or c['subset_molecules'] != nominal or c['subset_seed'] != 20261112
            or c['samples'] != 9000000 or c['seed'] != 0):
        raise ValueError('Original P subset configuration differs from directive')
    indices = train_indices(c)
    mids = [index_to_mid[int(i)] for i in indices]
    if len(mids) != nominal or len(set(mids)) != nominal:
        raise ValueError('Actual original P selected identity definition is unavailable')
    subsets[arm] = set(mids)
    origins[arm] = dict(P_configuration=str(ref), original_P_corpus=c['corpus'],
        original_P_selected_molecules=len(mids), subset_seed=20261112,
        P_selected_MIDs=str(output/(arm+'_original_P_selected_MIDs.parquet')),
        selection_provider='original P p_recipe_data.train_indices(saved original configuration)',
        S_resampling=False)
    pq.write_table(pa.table({'molecule_id': mids}), origins[arm]['P_selected_MIDs'])
del index_to_mid
names = ('k1','k2','k5','T5','T6')
counts = {name:dict(molecules=0, PM7=0, UFF=0) for name in names}
source = pq.ParquetFile(base['train'])
writers = {name:pq.ParquetWriter(output/(name+'_TRAIN.parquet'), source.schema_arrow)
           for name in names}
try:
    for batch in source.iter_batches(batch_size=32768):
        rows = batch.to_pylist()
        for name in names:
            selected = (conformer_rows(rows, int(name[1:])) if name.startswith('k') else
                        intersect_saved_mids(rows, subsets[name]))
            if selected:
                writers[name].write_table(pa.Table.from_pylist(selected, schema=source.schema_arrow))
            counts[name]['molecules'] += len(selected)
            counts[name]['PM7'] += sum(len(row['PM7']) for row in selected)
            counts[name]['UFF'] += sum(len(row['UFF']) for row in selected)
finally:
    for writer in writers.values():
        writer.close()
plans = {}
for name in names:
    n = counts[name]['molecules']
    if n == 0 or (name.startswith('k') and n != 1192951):
        raise ValueError('Population transformation lost common TRAIN membership')
    p = dict(base, train=str(output/(name+'_TRAIN.parquet')), TRAIN_molecules=n,
        original_population=str(REPO/'configs/s_recipe/population.json'),
        mean_allowed_PM7=counts[name]['PM7']/n, mean_allowed_UFF=counts[name]['UFF']/n,
        normalization_refitted=False, VAL_unchanged=True,validation_k=10)
    if name.startswith('k'):
        p.update(k=int(name[1:]), conformer_cap=int(name[1:]),
                 selection='original_allowed_PM7_fixed_random_prefix_after_D5')
        c = read(REPO/'configs/s_recipe/screening/S-R1.json')
        c.update(run='S_E1_'+name+'_s0_3M', extension_kind='E1', conformer_cap=int(name[1:]),
                 extension_authority='docs/s_recipe/USER_DIRECTIVE_20261123.md')
    else:
        p.update(origins[name], P_source_arm=name,
                 selection='original_P_selected_MIDs_intersect_S_TRAIN')
        c = read(REPO/'configs/s_recipe/confirmation/S-final.json')
        c.update(run='S_subset_'+name+'_s0_9M', extension_kind='molecule_subset',
                 extension_authority='docs/s_recipe/USER_DIRECTIVE_20261123C.md')
    population_path = REPO/'configs/s_recipe/extensions_20261124'/(name+'_population.json')
    population_path.parent.mkdir(exist_ok=True)
    write(population_path, p)
    for key in ('node','gpu_uuid','resume','resume_samples','baseline_acceptance','execution_attempt'):
        c.pop(key, None)
    c.update(population=str(population_path), output=str(CONTROL/'training'/c['run']),
             evaluation_samples=[3000000] if name.startswith('k') else [3000000,6000000,9000000])
    config_path = population_path.with_name(name+'_training.json')
    write(config_path, c)
    plans[name] = dict(configuration=str(config_path), population=str(population_path),
        TRAIN_molecules=n, mean_allowed_PM7=p['mean_allowed_PM7'],
        mean_allowed_UFF=p['mean_allowed_UFF'], original_P=origins.get(name))
from cpu_execution_20261126 import execution_fields
write(output/'COMPLETE.json', dict(status='COMPLETE', **execution_fields(),
    source=str(REPO/'configs/s_recipe/population.json'), plans=plans,
    same_fixed_VAL=True, old_labels_or_predictions_loaded=False))
print(json.dumps(plans), flush=True)
