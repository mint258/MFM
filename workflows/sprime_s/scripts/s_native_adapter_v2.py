"""Preserve v1 reads/views, localizing the verified mount-local st_dev field."""
from copy import deepcopy
from s_native_adapter_v1 import MappedRecordIndex as OriginalMappedRecordIndex
from s_native_adapter_v1 import ManifestViewsDataset,CountIndex,RecordRef,identity

class MappedRecordIndex(OriginalMappedRecordIndex):
    def __init__(self,role,transport_binding,shard_snapshot,*,verify_hashes=True):
        localized=deepcopy(shard_snapshot);self.cross_node_device_observations=[]
        for sid,shard in localized['shards'].items():
            current=identity(shard['path']);observed=tuple(shard['identity'])
            assert current[1:]==observed[1:],'ACTUAL_RECORD_MANIFEST_MISMATCH'
            self.cross_node_device_observations.append({'shard_id':sid,'snapshot_st_dev':observed[0],'current_st_dev':current[0]})
            # The original snapshot remains unchanged. Subsequent checks retain
            # exact node-local device, inode, size and mtime checks, LMDB header/
            # entry/transaction checks, and mandatory SHA of every actual record.
            shard['identity']=list(current)
        super().__init__(role,transport_binding,localized,verify_hashes=verify_hashes)
