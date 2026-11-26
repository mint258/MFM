"""Original element-moment population, streamed from the retained atomic H cache."""
import numpy as np


def element_layout(panel):
    z=panel["Z"];offset=panel["molecule_atom_offsets"];owners=panel["owners"]
    conformers=np.bincount(owners,minlength=len(offset)-1)
    elements=[];element_owners=[];counts=[];maps=[]
    for owner,(a,b) in enumerate(zip(offset,offset[1:])):
        values,number=np.unique(z[a:b],return_counts=True)
        mapping={}
        for value,n in zip(values,number):
            mapping[int(value)]=len(elements)
            elements.append(int(value));element_owners.append(owner)
            counts.append(int(n)*int(conformers[owner]))
        maps.append(mapping)
    return dict(elements=np.asarray(elements,np.int64),
        owners=np.asarray(element_owners,np.int64),
        counts=np.asarray(counts,np.float64),maps=maps)


def accumulate_records(atom_sums,atom_squares,features,panel,layout,start,end):
    offsets=panel["record_atom_offsets"];molecule_offsets=panel["molecule_atom_offsets"]
    if not 0<=start<=end<len(offsets):
        raise ValueError("Native conformer prefix out of range")
    for row in range(start,end):
        owner=int(panel["owners"][row])
        z=panel["Z"][molecule_offsets[owner]:molecule_offsets[owner+1]]
        h=np.asarray(features[int(offsets[row]):int(offsets[row+1])],np.float64)
        if h.shape!=(len(z),atom_sums.shape[1]):
            raise ValueError("Native molecule/atom order differs from immutable panel")
        for element,key in layout["maps"][owner].items():
            part=h[z==element]
            atom_sums[key]+=part.sum(0)
            atom_squares[key]+=np.square(part).sum()
    return end


def additional_output_peak(groups,molecules=5000,new_sources=7,dimensions=512):
    # Keep all closed moments/OOFs; one atomic replacement of each may coexist.
    moments=int(groups)*(int(dimensions)*8+8)
    prediction=int(molecules)*int(dimensions)*8
    raw=(int(new_sources)+1)*(moments+prediction)+68*2**20
    return ((raw+2**20-1)//2**20)*2**20
