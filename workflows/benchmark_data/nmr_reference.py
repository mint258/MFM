"""Read the author NMR geometry artifact once; retain original atom indices."""
import argparse
from collections import defaultdict
import io
import json
from pathlib import Path
import pickle
import types
import zipfile
import pyarrow as pa
import pyarrow.parquet as pq
from .admission import protect

SCHEMA=pa.schema([('nucleus',pa.string()),('source_row',pa.int64()),('molecule_id',pa.string()),
    ('source_atom_indices',pa.list_(pa.int32())),('atomic_numbers',pa.list_(pa.int16())),
    ('coordinates_A',pa.list_(pa.list_(pa.float32(),3))),('atom_y',pa.list_(pa.float32())),
    ('source_mask',pa.list_(pa.float32()))])


def restricted_load(payload):
    import torch
    from torch_geometric.data import Data
    from torch_geometric.data.data import DataEdgeAttr,DataTensorAttr
    from torch_geometric.data.storage import GlobalStorage
    from collections import OrderedDict
    allowed={
        ('torch_geometric.data.data','Data'):Data,
        ('torch_geometric.data.data','DataEdgeAttr'):DataEdgeAttr,
        ('torch_geometric.data.data','DataTensorAttr'):DataTensorAttr,
        ('torch_geometric.data.storage','GlobalStorage'):GlobalStorage,
        ('torch._utils','_rebuild_tensor_v2'):torch._utils._rebuild_tensor_v2,
        ('torch','FloatStorage'):torch.FloatStorage,('torch','LongStorage'):torch.LongStorage,
        ('collections','OrderedDict'):OrderedDict,('collections','defaultdict'):defaultdict,
        ('__builtin__','dict'):dict,('builtins','dict'):dict}
    class ContainersOnly(pickle.Unpickler):
        def find_class(self,module,name):
            if (module,name) not in allowed:
                raise pickle.UnpicklingError('Unapproved source pickle global: '+module+'.'+name)
            return allowed[module,name]
    restricted=types.ModuleType('benchmark_author_data_containers_only')
    restricted.Unpickler=ContainersOnly
    # PyTorch weights_only cannot reconstruct the author's defaultdict slice
    # container. The replacement loader allows only the observed tensor/data
    # containers; arbitrary author/custom globals still cannot execute.
    return torch.load(io.BytesIO(payload),map_location='cpu',pickle_module=restricted,weights_only=False)


def rows(data,slices,nucleus):
    for index in range(len(slices['R'])-1):
        def field(name):
            left,right=map(int,slices[name][index:index+2])
            return getattr(data,name)[left:right].tolist()
        coordinates=field('R');z=field('Z');labels=field('atom_y');mask=field('mask')
        if not len(coordinates)==len(z)==len(labels)==len(mask):
            raise ValueError('Author per-atom fields have different lengths')
        yield {'nucleus':nucleus,'source_row':index,'molecule_id':json.dumps(field('molecule_id')),
            'source_atom_indices':list(range(len(z))),'atomic_numbers':z,
            'coordinates_A':coordinates,'atom_y':labels,'source_mask':mask}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--attempt',required=True)
    p.add_argument('--quota-snapshot',type=Path,required=True)
    a=p.parse_args()
    out=a.root/'reference'/'NMRShiftDB2'/a.attempt
    protect(a.root,268435456,a.quota_snapshot)
    out.mkdir(parents=True,exist_ok=False)
    source=a.root/'raw/NMRShiftDB2/NMRShiftDB2_DFT.zip'
    reports=[]
    with zipfile.ZipFile(source) as archive:
        for nucleus,folder in [('13C','carbon'),('1H','hydrogen')]:
            member='NMRShiftDB2_DFT/'+folder+'/processed/processed.pt'
            # Only these known PyG data containers and builtin mappings are
            # allowed; no arbitrary pickle globals or author code is executed.
            data,slices=restricted_load(archive.read(member))
            count=atoms=0;buffer=[]
            target=out/(folder+'.parquet')
            with pq.ParquetWriter(target,SCHEMA,compression='zstd') as writer:
                for row in rows(data,slices,nucleus):
                    buffer.append(row);count+=1;atoms+=len(row['atomic_numbers'])
                    if len(buffer)>=256:
                        protect(a.root,268435456,a.quota_snapshot)
                        writer.write_table(pa.Table.from_pylist(buffer,schema=SCHEMA));buffer.clear()
                if buffer:writer.write_table(pa.Table.from_pylist(buffer,schema=SCHEMA))
            reports.append({'nucleus':nucleus,'source_archive_member':member,'reference':str(target),
                'molecules':count,'atoms':atoms,'source_coordinate_dtype':str(data.R.dtype),
                'source_label_dtype':str(data.atom_y.dtype),
                'source_keys':list(data.keys()),'bytes':target.stat().st_size,
                'original_split_member':'NMRShiftDB2_DFT/'+folder+'/processed/split.pt'})
            print('NMR_REFERENCE_CLOSED',nucleus,count,atoms,flush=True)
            del data,slices
    report={'status':'REFERENCE_GEOMETRIES_READY_DOMAIN_GRAPH_METADATA_PENDING',
        'source':str(source),'records':reports,'reference_geometries_regenerated':False,
        'atom_order':'Original author tensor index, no renumbering',
        'original_f32_precision_preserved':True,'independent_numeric_readback':False,
        'split_decision':'PENDING_USER; original split artifacts preserved, not selected or modified',
        'domain_missing_metadata':['explicit molecular graph','formal charge','multiplicity'],
        'domain_filter_complete':False,
        'dft_auxiliary_shielding_features_used_as_inputs':False}
    protect(a.root,1048576,a.quota_snapshot)
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
