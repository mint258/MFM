"""MFM4 assembly from already projected original arrays, without F64 sidecars."""
import numpy as np
from ..pilot_v31_compact_v1.assemble import assemble_molecule


class ProjectedStore:
    def __init__(self,kind,records):
        self.schema={'kind':kind};self.path='original-projection';self.records=records
    def records_for_molecule(self,mid):
        return [gid for gid,(metadata,_) in self.records.items() if metadata['molecule_id']==mid]
    def get(self,gid):
        metadata,arrays=self.records[gid]
        # This is the sole F64 -> F32 conversion for the training representation.
        values={name:(np.asarray(array,dtype='<f4') if np.asarray(array).dtype.kind=='f' else np.asarray(array)) for name,array in arrays.items()}
        return metadata,values


def assemble_entries(mid,entries,schema):
    """Entries retain descriptor/gid/metadata/arrays from the source projection.

    No physical quantity, validity mask, source order or coordinate frame is
    defined here. PM7 and UFF labels use the same assembler and MFM4 schema.
    Full source adapters call the original scientific projection functions.
    """
    readers=[]
    for entry in entries:
        descriptor=dict(entry['descriptor']);gid=entry['gid'];metadata=entry['metadata']
        store=ProjectedStore(descriptor['kind'],{gid:(metadata,entry['arrays'])})
        readers.append((descriptor,store))
    return assemble_molecule(mid,readers,schema,include_uff_labels=True)


def apply_pprime_eligibility(item,eligible_by_gid):
    """Copy producer fit flags; do not define a new training predicate."""
    item['m_arrays'][18]=np.asarray([int(bool(eligible_by_gid.get(record['identity']['base_geometry_id'],False))) for record in item['u_records']],dtype='u1')
    return item