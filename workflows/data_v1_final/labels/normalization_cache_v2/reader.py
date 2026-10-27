"""Narrow base metadata projection; all task/calibration readers stay frozen."""
import json
from ..normalization_cache_v1.reader import (CompatibilityGap,TASK_KEYS,PARITY_KEYS,need,equal_bits,
 projected_decode,cell_view,logical_source,entries,finite_train)


def member(node,key):
    need(isinstance(node,list) and node and node[0]=='d','BASE_METADATA_OBJECT_REQUIRED')
    names=[k for k,v in node[1]];need(len(names)==len(set(names)),'BASE_METADATA_DUPLICATE_KEY')
    selected=[v for k,v in node[1] if k==key];need(len(selected)==1,'BASE_METADATA_REQUIRED_KEY:'+key)
    return selected[0]


def base_metadata(template):
    """Decode exactly owner.ordinal and four geometry fields, with NO F64 pool.

    The genuine producer source_reference.seconds is an unrelated float. Its
    original tagged node and every XYZ node are simply unselected, never read,
    replaced, reindexed or declared corrupt. Required-field F64 dependencies
    still fail the unchanged frozen projected_decode bounds/uniqueness check.
    """
    top=json.loads(template);provenance=member(top,'provenance');owner=member(provenance,'owner')
    ordinal=member(owner,'record_ordinal');geometry=member(top,'original_geometry')
    keys=('atomic_numbers','native_atom_order_sha256','source_payload_sha256','geometry_status')
    for key in keys:member(geometry,key)
    selected=['d',[
      ['provenance',['d',[['owner',['d',[['record_ordinal',ordinal]]]]]]],
      ['original_geometry',['d',[[k,v] for k,v in geometry[1] if k in keys]]]]]
    value=projected_decode(json.dumps(selected,separators=(',',':')),[],{'provenance','original_geometry'})
    need(type(value['provenance']['owner']['record_ordinal']) is int,'BASE_RECORD_ORDINAL_MUST_BE_INTEGER')
    return value
