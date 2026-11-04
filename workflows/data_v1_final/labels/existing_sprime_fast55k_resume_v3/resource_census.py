"""Whole output metadata census via streaming DirEntry stat; never DATA bodies."""
import os,stat
from . import contract as C
ORIGINAL_RESOURCE_CENSUS=None

def unique_bytes(root):
    # Same owner/type, directory bytes, inode dedup and exact internal-hardlink
    # constraints as the original complete census. Nothing is cached or skipped.
    seen=set();links={};counts={};total=0
    first=os.lstat(root)
    C.need(first.st_uid==os.getuid()and stat.S_ISDIR(first.st_mode),'OUTPUT_OWNER_OR_TYPE')
    key=(first.st_dev,first.st_ino);seen.add(key);total+=first.st_size
    pending=[os.fspath(root)]
    while pending:
        directory=pending.pop()
        with os.scandir(directory)as scan:
            for entry in scan:
                value=entry.stat(follow_symlinks=False)
                C.need(value.st_uid==os.getuid()and(stat.S_ISDIR(value.st_mode)or stat.S_ISREG(value.st_mode)),'OUTPUT_OWNER_OR_TYPE')
                key=(value.st_dev,value.st_ino)
                if key not in seen:total+=value.st_size;seen.add(key)
                if stat.S_ISDIR(value.st_mode):pending.append(entry.path)
                else:links[key]=value.st_nlink;counts[key]=counts.get(key,0)+1
    C.need(all(counts[k]==v for k,v in links.items()),'OUTPUT_EXTERNAL_HARDLINK')
    return total

def bind_resource_census(io):
    """Explicit new-Parent resource dependency; no scientific function changes.

    The existing IO context is process-local and already scoped by configure().
    Its save/text/Budget paths all resolve this one resource-only dependency.
    Existing jobs and on-disk original source files are never changed.
    """
    global ORIGINAL_RESOURCE_CENSUS
    C.need(ORIGINAL_RESOURCE_CENSUS is None,'EXACT_ONE_NEW_PARENT_RESOURCE_BINDING')
    ORIGINAL_RESOURCE_CENSUS=io.unique_bytes
    io.unique_bytes=unique_bytes


class current_root_future:
    """Existing Root resource lock; original quota/floor/credits remain in force."""
    def __init__(self,budget):self.budget=budget;self.stream=None
    def __enter__(self):
        import fcntl
        path=C.RUN/'control/root_current_all_future_ledger_v1.json'
        lock=C.RUN/'control/root_current_all_future_ledger_v1.lock'
        self.stream=lock.open('rb');fcntl.flock(self.stream,fcntl.LOCK_SH)
        try:
            pointer=C.meta(C.P.pin(path));review=C.meta(pointer['review_reference'])
            C.need(pointer['schema']=='ROOT_CURRENT_ALL_FUTURE_METADATA_POINTER_V1'
              and type(pointer['total_future_reserved_bytes'])is int and pointer['total_future_reserved_bytes']>=0
              and review['reviewer']=='root'and review['status'].startswith('APPROVED')
              and review['total_future_reserved_bytes']==pointer['total_future_reserved_bytes'],'ACTUAL_CURRENT_SIGNED_ROOT_ALL_WRITER_FUTURE')
            C.need(self.budget.external_initial_credit==0 and not self.budget.external,'NO_EXTERNAL_CREDIT_REINTERPRETATION')
            self.budget.total=pointer['total_future_reserved_bytes']
            return self
        except BaseException:
            self.stream.close();self.stream=None;raise
    def __exit__(self,*args):
        if self.stream is not None:self.stream.close()
