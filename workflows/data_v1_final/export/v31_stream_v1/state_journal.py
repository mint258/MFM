"""Owned append-only checkpoint deltas; no source reads, casts or scientific QA."""
import os,pathlib,pickle,struct
P=pathlib.Path
HEADER=struct.Struct('<Q')
VERSION=1


class Ledger:
    def __init__(self,root,name,reference=None,guard=None):
        self.guard=guard;root=P(root).resolve();self.pending=[]
        if reference is None:
            self.path=root/(name+'_journal.bin');attempt=0;original=self.path
            while self.path.exists():attempt+=1;self.path=original.with_name(original.stem+'_attempt_%03d.bin'%attempt)
            self.closed_bytes=0;self.records=0
        else:
            self.path=P(reference['path'])
            if self.path.parent.resolve()!=root or self.path.is_symlink():raise ValueError('ONLY_OWNED_CHECKPOINT_JOURNAL_ALLOWED')
            self.closed_bytes=reference['closed_bytes'];self.records=reference['records']
            if any(type(v)is not int or v<0 for v in (self.closed_bytes,self.records)):raise ValueError('INVALID_CLOSED_JOURNAL_OFFSET_OR_COUNT')
            if not self.path.is_file():raise ValueError('CLOSED_JOURNAL_MISSING')
            size=self.path.stat().st_size
            if size<self.closed_bytes:raise ValueError('JOURNAL_SHORTER_THAN_CLOSED_PREFIX')
            if size>self.closed_bytes:
                # Only this ledger's uncheckpointed tail, never a closed record.
                with self.path.open('r+b') as stream:stream.truncate(self.closed_bytes);stream.flush();os.fsync(stream.fileno())

    def replay(self):
        remaining=self.closed_bytes;count=0
        with self.path.open('rb') as stream:
            while remaining:
                if remaining<HEADER.size:raise ValueError('CLOSED_JOURNAL_FRAME_HEADER_TRUNCATED')
                header=stream.read(HEADER.size)
                if len(header)!=HEADER.size:raise ValueError('CLOSED_JOURNAL_FRAME_HEADER_TRUNCATED')
                size=HEADER.unpack(header)[0];remaining-=HEADER.size
                if size>remaining:raise ValueError('CLOSED_JOURNAL_FRAME_PAYLOAD_TRUNCATED')
                payload=stream.read(size)
                if len(payload)!=size:raise ValueError('CLOSED_JOURNAL_FRAME_PAYLOAD_TRUNCATED')
                yield pickle.loads(payload);remaining-=size;count+=1
        if count!=self.records:raise ValueError('CLOSED_JOURNAL_RECORD_COUNT_DIFFERS')

    def flush(self):
        if not self.pending and self.path.is_file():return self.reference()
        if self.guard:self.guard.wait(self.path,inodes_needed=2)
        mode='r+b' if self.path.exists() else 'xb'
        with self.path.open(mode) as stream:
            if stream.seek(0,os.SEEK_END)!=self.closed_bytes:raise ValueError('JOURNAL_HAS_UNEXPECTED_LIVE_TAIL')
            for value in self.pending:
                payload=pickle.dumps(value,protocol=5)
                if self.guard:self.guard.wait(self.path,len(payload)+HEADER.size,1)
                stream.write(HEADER.pack(len(payload)));stream.write(payload)
            stream.flush();os.fsync(stream.fileno());offset=stream.tell()
        self.closed_bytes=offset;self.records+=len(self.pending);self.pending.clear()
        return self.reference()

    def reference(self):return {'path':str(self.path),'closed_bytes':self.closed_bytes,'records':self.records}


class Journals:
    def __init__(self,root,guard=None,reference=None):
        if reference is not None and reference.get('version')!=VERSION:raise ValueError('UNSUPPORTED_CHECKPOINT_JOURNAL_VERSION')
        self.seen=Ledger(root,'producer_seen',None if reference is None else reference['seen'],guard)
        self.samples=Ledger(root,'producer_samples',None if reference is None else reference['samples'],guard)
        self.sample_count=0 if reference is None else reference['sample_count']
        self.seen_count=0 if reference is None else reference['seen_count']

    def mark_seen(self,mid):self.seen.pending.append(mid)
    def sample(self,index,entry):self.samples.pending.append((index,entry))

    def flush(self,seen_count,sample_count):
        count=self.sample_count
        for index,_ in self.samples.pending:
            if type(index)is not int or not 0<=index<=count:raise ValueError('JOURNAL_SAMPLE_SLOT_OUT_OF_ORDER')
            if index==count:count+=1
        if count!=sample_count or self.seen.records+len(self.seen.pending)!=seen_count:raise ValueError('DIRTY_JOURNAL_STATE_COUNT_DIFFERS')
        seen=self.seen.flush();samples=self.samples.flush();self.sample_count=count;self.seen_count=seen_count
        return {'version':VERSION,'seen':seen,'samples':samples,'seen_count':seen_count,'sample_count':sample_count}

    @classmethod
    def restore(cls,root,reference,guard=None):
        journals=cls(root,guard,reference);seen=set();samples=[]
        for mid in journals.seen.replay():
            if mid in seen:raise ValueError('DUPLICATE_MID_IN_CLOSED_JOURNAL')
            seen.add(mid)
        for index,entry in journals.samples.replay():
            if type(index)is not int or not 0<=index<=len(samples):raise ValueError('CLOSED_SAMPLE_SLOT_OUT_OF_ORDER')
            if index==len(samples):samples.append(entry)
            else:samples[index]=entry
        if len(seen)!=reference['seen_count'] or len(samples)!=reference['sample_count']:raise ValueError('CLOSED_JOURNAL_STATE_COUNT_DIFFERS')
        return journals,seen,samples

    @classmethod
    def migrate(cls,root,seen,samples,guard=None):
        # Legacy checkpoint data is already loaded. Do not reopen any source,
        # recast a target or alter the in-memory set/list or its sample order.
        journals=cls(root,guard)
        journals.seen.pending.extend(seen)
        journals.samples.pending.extend(enumerate(samples))
        return journals
