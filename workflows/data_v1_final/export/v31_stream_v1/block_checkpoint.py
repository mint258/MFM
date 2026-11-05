"""Owned raw-writer block recovery; no scientific values are inspected."""
import collections,os,pathlib
from ..pilot_v31_compact_v1.codec import encode_key
from ..pilot_v31_compact_v1.run import Writer,IDMap
P=pathlib.Path


class BlockWriter(Writer):
    def __init__(self,path,estimate,closed=None,committed_molecules=0):
        if closed is None:return super().__init__(path,estimate)
        import lmdb
        self.path=P(path)
        if not (self.path/'data.mdb').is_file():raise ValueError('CHECKPOINTED_RAW_LMDB_MISSING')
        self.env=lmdb.open(str(self.path),map_size=max(closed['map_size'],(self.path/'data.mdb').stat().st_size*2),subdir=True,max_dbs=0,create=False)
        self.count=collections.Counter(closed['count']);self.bytes=collections.Counter(closed['bytes'])
        # These are only this producer's unclosed tail keys. Values are neither
        # decoded nor revalidated; all committed prefix keys remain untouched.
        with self.env.begin(write=True) as transaction:
            cursor=transaction.cursor()
            try:
                for kind in ('M','P','U'):
                    threshold=encode_key(kind,committed_molecules) if kind=='M' else encode_key(kind,committed_molecules,0)
                    while cursor.set_range(threshold) and cursor.key()[:1]==kind.encode():cursor.delete()
            finally:cursor.close()
        self.env.sync()

    def snapshot(self):
        self.env.sync()
        return {'map_size':self.env.info()['map_size'],'count':dict(self.count),'bytes':dict(self.bytes)}


class IDFragments:
    def __init__(self,root,closed=()):
        self.root=P(root);self.root.mkdir(parents=True,exist_ok=True)
        self.closed=list(closed);self.current=None;self.path=None
        self.rows=sum(ref['records'] for ref in self.closed)
        for ref in self.closed:
            if not P(ref['path']).is_file() or P(ref['path']).stat().st_size!=ref['bytes']:raise ValueError('CLOSED_ID_FRAGMENT_MISSING_OR_SIZE_DIFFERS')

    def append(self,rows):
        if self.current is None:
            path=self.root/('fragment_%07d.parquet'%len(self.closed));attempt=0;original=path
            while path.exists():attempt+=1;path=original.with_name(original.stem+'_attempt_%03d.parquet'%attempt)
            self.path=path;self.current=IDMap(path)
        self.current.append(rows);self.rows+=len(rows)

    def close_block(self,ordinal):
        if self.current is None:raise ValueError('EMPTY_SOURCE_BLOCK_CANNOT_BE_ACKNOWLEDGED')
        records=self.current.rows;self.current.close();self.current=None
        with self.path.open('rb') as stream:os.fsync(stream.fileno())
        self.closed.append({'path':str(self.path),'bytes':self.path.stat().st_size,'records':records,'source_block':ordinal})

    def close(self):
        if self.current is not None:self.current.close();self.current=None

    def finish(self,path):
        """Merge only external identity metadata in unchanged block/row order."""
        import pyarrow as pa,pyarrow.parquet as pq
        if self.current is not None:raise ValueError('UNCLOSED_ID_FRAGMENT')
        path=P(path);attempt=0;original=path
        while path.exists():attempt+=1;path=original.with_name(original.stem+'_attempt_%03d.parquet'%attempt)
        writer=IDMap(path)
        try:
            for ref in self.closed:
                table=pq.ParquetFile(ref['path'],pre_buffer=False)
                try:
                    for batch in table.iter_batches(batch_size=8192,use_threads=False):
                        writer.writer.write_table(pa.Table.from_batches([batch]));writer.rows+=batch.num_rows
                finally:table.close()
            if writer.rows!=self.rows:raise ValueError('ID_FRAGMENT_ROW_COUNTS_DIFFER')
        finally:writer.close()
        return path


def consume_id_fragments(active):
    """The merged IDmap is closed/checkpointed; only its owned inputs expire."""
    path=P(active['idpath'])
    if not path.is_file() or path.stat().st_size!=active['idmap_file_bytes']:raise ValueError('CLOSED_MERGED_IDMAP_REQUIRED_FOR_FRAGMENT_LIFECYCLE')
    root=P(active['fragment_root']).resolve()
    for ref in active['id_fragments']:
        fragment=P(ref['path'])
        if fragment.parent.resolve()!=root or fragment.is_symlink():raise ValueError('ONLY_OWNED_ID_FRAGMENT_INPUTS_MAY_EXPIRE')
        if fragment.exists():
            if fragment.stat().st_size!=ref['bytes']:raise ValueError('ID_FRAGMENT_CHANGED_BEFORE_LIFECYCLE_END')
            fragment.unlink()
