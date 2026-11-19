"""Read official tabular sources in place, preserving source rows and splits."""
import csv
import io
import json
from pathlib import Path
import zipfile


def tdc_rows(path):
    with zipfile.ZipFile(path) as archive:
        names=sorted(n for n in archive.namelist() if n.endswith('.csv'))
        for name in names:
            components=Path(name).parts
            if len(components)!=3 or components[0]!='admet_group' or components[2] not in ('train_val.csv','test.csv'):
                raise ValueError('Unexpected official TDC member: '+name)
            with archive.open(name) as binary,io.TextIOWrapper(binary,encoding='utf-8-sig',newline='') as stream:
                reader=csv.DictReader(stream)
                if not {'Drug_ID','Drug','Y'}<=set(reader.fieldnames):
                    raise ValueError('Missing official TDC fields')
                for index,row in enumerate(reader):
                    yield name,index,row,components[2][:-4]


def parquet_rows(path):
    import pyarrow.parquet as pq
    index=0
    for batch in pq.ParquetFile(path).iter_batches(batch_size=4096):
        for row in batch.to_pylist():
            yield Path(path).name,index,row,None
            index+=1


def curated_pka_rows(rows,filename='combined_unified_dataset.tsv'):
    for index,row in enumerate(rows):
        if (row.get('exclude_flag') or '').strip().lower()!='exclude':
            yield filename,index,row,None


def decode_column(payload,metadata):
    import numpy as np
    from numcodecs import get_codec
    # The published ASAP artifact has one full 1D chunk per column. Do not
    # silently synthesize Zarr fill values or infer absent chunks.
    if len(metadata['shape'])!=1 or metadata['chunks']!=metadata['shape'] or metadata['order']!='C':
        raise ValueError('Unsupported source Zarr layout')
    compressor=metadata.get('compressor')
    value=get_codec(compressor).decode(payload) if compressor else payload
    filters=metadata.get('filters') or []
    for filter_spec in reversed(filters):
        if filter_spec['id']=='categorize':
            value=np.frombuffer(value,dtype=filter_spec['astype'])
        value=get_codec(filter_spec).decode(value)
    if not filters:
        value=np.frombuffer(value,dtype=np.dtype(metadata['dtype']))
    value=np.asarray(value)
    if value.shape!=tuple(metadata['shape']):
        raise ValueError('Source Zarr column length differs')
    return value.tolist()


def asap_rows(root,source):
    metadata=json.loads((root/'zmetadata.json').read_text())['metadata']
    columns={}
    for asset in source['files']:
        key=asset.get('zarr_key')
        if key:
            column=key[:-2]
            if not key.endswith('/0') or column not in {k[:-8] for k in metadata if k.endswith('/.zarray')}:
                raise ValueError('Source chunk has no column metadata')
            columns[column]=decode_column((root/asset['name']).read_bytes(),metadata[column+'/.zarray'])
    required={'CXSMILES','Molecule Name','Set','HLM','MLM','KSOL','LogD','MDR1-MDCKII'}
    if set(columns)!=required or len({len(v) for v in columns.values()})!=1:
        raise ValueError('Incomplete official ASAP table')
    for index in range(len(columns['CXSMILES'])):
        row={name:values[index] for name,values in columns.items()}
        yield 'official_data.zarr',index,row,row['Set']


def source_rows(plan,dataset):
    source=plan['assets'][dataset]
    root=Path(plan['data_root'])/'raw'/dataset
    if dataset=='TDC_ADMET':
        yield from tdc_rows(source['existing_source'])
    elif dataset=='Biogen_ADME':
        yield from parquet_rows(root/'table.parquet')
    elif dataset=='ASAP_Polaris2025':
        yield from asap_rows(root,source)
    elif dataset=='pKahub':
        with (root/'combined_unified_dataset.tsv').open(newline='') as stream:
            yield from curated_pka_rows(csv.DictReader(stream,delimiter='\t'))
    else:
        raise ValueError('No tabular source adapter: '+dataset)
