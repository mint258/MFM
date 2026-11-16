"""Keep the registered run path; back new side-line outputs on available NFS."""
from resources import R,REPO,CONTROL,TRAIN,SIDE,MEAN,load,save,guard,GIB

def main():
    capacity=guard(force=True,lustre=True)
    target=CONTROL/'training';target.mkdir(exist_ok=True)
    if TRAIN.is_symlink():
        if TRAIN.resolve()!=target.resolve():raise ValueError('Existing side-line link has another owner target')
    elif TRAIN.exists():raise ValueError('Existing side-line output must be retained; no relocation performed')
    else:TRAIN.symlink_to(target,target_is_directory=True)
    save(CONTROL/'storage_layout.json',dict(logical_training_root=str(TRAIN),physical_training_root=str(target),molecular_mean_root=str(MEAN),F64_sidecar_root=str(SIDE),NFS_peak_bytes=10*GIB,side_training_and_evaluation_cap=4*GIB,sidecar_peak_bytes=int(1.1*GIB),sidecar_cap=2*GIB,mean_table_cap=GIB,source_or_LMDB_moved=False,mainline_61GB_reserve_modified=False,capacity=capacity,sidecar_layout_forecast='22027705 conformer rows*(4+2+7+4*8)=991246725 bytes plus dense molecule offsets and small headers,within1.1GiB'))
    print('STORAGE_LAYOUT_READY',TRAIN,'->',target,flush=True)
if __name__=='__main__':main()