"""Exact observed opcode allowlist, no pickle/import/global/object execution."""
import collections
ALLOW={'PROTO','FRAME','EMPTY_DICT','MEMOIZE','MARK','SHORT_BINUNICODE','BINUNICODE','BINFLOAT','SETITEMS','BINGET','TUPLE3','SETITEM','STOP'}
CODE={0x80:'PROTO',0x95:'FRAME',0x7d:'EMPTY_DICT',0x94:'MEMOIZE',0x28:'MARK',0x8c:'SHORT_BINUNICODE',
      0x58:'BINUNICODE',0x47:'BINFLOAT',0x75:'SETITEMS',0x68:'BINGET',0x87:'TUPLE3',0x73:'SETITEM',0x2e:'STOP'}
MARK=object()


class UnknownPrimitive(ValueError):pass


def need(ok,message):
    if not ok:raise UnknownPrimitive(message)


class F64Bits:
    """Original big-endian BINFLOAT payload; never rounded or numerically edited."""
    __slots__=('raw',)
    def __init__(self,raw):need(type(raw) is bytes and len(raw)==8,'EXACT_FLOAT64_TOKEN');self.raw=raw


class AssignmentMap:
    """Retain every source SETITEM assignment/order, without calling payload hash."""
    __slots__=('entries',)
    def __init__(self):self.entries=[]


class Reader:
    def __init__(self,stream,check,decoded_bytes):
        self.stream,self.check,self.size=stream,check,decoded_bytes;self.pos=0;self.frame_end=None;self.stack=[];self.memo=[]
        self.counts=collections.Counter();self.nodes=0;self.edges=0;self.string_bytes=0;self.max_stack=0;self.frames=0
    def read(self,n):
        need(type(n) is int and 0<=n<=16<<20 and self.pos+n<=self.size,'BOUNDED_DECLARED_OPCODE_ARGUMENT')
        need(self.frame_end is None or self.pos+n<=self.frame_end,'OPCODE_ARGUMENT_CROSSES_FRAME_BOUNDARY')
        value=self.stream.read(n);need(type(value) is bytes and len(value)==n,'TRUNCATED_OPCODE_ARGUMENT');self.pos+=n;return value
    def add(self,value):
        self.nodes+=1;need(self.nodes<=1000000,'PRIMITIVE_NODE_BOUND_UNKNOWN');self.stack.append(value)
    def assign(self,target,key,value):
        need(type(target) is AssignmentMap,'SETITEM_TARGET_MUST_BE_PRIMITIVE_DICT')
        self.edges+=1;need(self.edges<=2000000 and len(target.entries)<1000000,'PRIMITIVE_ASSIGNMENT_BOUND_UNKNOWN')
        # Preserve duplicate/unhashable keys as evidence; no opaque equality or
        # hash is invoked, and no source assignment disappears by overwriting.
        target.entries.append((key,value))
    def decode(self):
        stop=False
        while self.pos<self.size:
            self.check()
            if self.frame_end is not None and self.pos==self.frame_end:self.frame_end=None
            offset=self.pos;byte=self.read(1)[0];need(byte in CODE,'UNOBSERVED_OR_EXECUTING_OPCODE_REJECTED_AT_'+str(offset));name=CODE[byte];self.counts[name]+=1
            if name=='PROTO':need(offset==0 and self.counts[name]==1 and self.read(1)==b'\x04','ONLY_INITIAL_PROTOCOL4')
            else:need(self.counts['PROTO']==1,'PROTOCOL4_REQUIRED_BEFORE_PRIMITIVES')
            if name=='FRAME':
                need(self.frame_end is None,'NESTED_OR_PREMATURE_FRAME_UNKNOWN');length=int.from_bytes(self.read(8),'little')
                need(length<=self.size and self.pos+length<=self.size,'BOUNDED_DECLARED_FRAME');self.frame_end=self.pos+length;self.frames+=1
            elif name=='EMPTY_DICT':self.add(AssignmentMap())
            elif name=='MEMOIZE':
                need(self.stack and self.stack[-1] is not MARK and len(self.memo)<1000000,'BOUNDED_MEMO_VALUE');self.memo.append(self.stack[-1])
            elif name=='BINGET':
                i=self.read(1)[0];need(i<len(self.memo),'BINGET_MUST_REFERENCE_EXISTING_MEMO');self.stack.append(self.memo[i])
            elif name=='MARK':self.stack.append(MARK)
            elif name in ('SHORT_BINUNICODE','BINUNICODE'):
                length=int.from_bytes(self.read(1 if name=='SHORT_BINUNICODE' else 4),'little');raw=self.read(length)
                self.string_bytes+=length;need(self.string_bytes<=128<<20,'TOTAL_LITERAL_STRING_BYTE_BOUND_UNKNOWN')
                try:value=raw.decode('utf-8',errors='surrogatepass')
                except UnicodeError as exc:raise UnknownPrimitive('INVALID_PICKLE_UNICODE_TOKEN') from exc
                need(value.encode('utf-8',errors='surrogatepass')==raw,'EXACT_UNICODE_TOKEN_BYTE_ROUNDTRIP');self.add(value)
            elif name=='BINFLOAT':self.add(F64Bits(self.read(8)))
            elif name=='TUPLE3':
                need(len(self.stack)>=3 and all(x is not MARK for x in self.stack[-3:]),'EXACT_THREE_PRIMITIVE_TUPLE_ITEMS')
                values=tuple(self.stack[-3:]);del self.stack[-3:];self.add(values)
            elif name=='SETITEM':
                need(len(self.stack)>=3 and all(x is not MARK for x in self.stack[-3:]),'EXACT_DICT_KEY_VALUE_STACK')
                value=self.stack.pop();key=self.stack.pop();self.assign(self.stack[-1],key,value)
            elif name=='SETITEMS':
                marks=[i for i,x in enumerate(self.stack) if x is MARK];need(marks,'SETITEMS_MARK_REQUIRED');j=marks[-1]
                need(j>=1 and (len(self.stack)-j-1)%2==0,'EVEN_SOURCE_ASSIGNMENT_PAIRS');target=self.stack[j-1]
                for i in range(j+1,len(self.stack),2):self.assign(target,self.stack[i],self.stack[i+1])
                del self.stack[j:]
            elif name=='STOP':
                need(len(self.stack)==1 and self.stack[0] is not MARK,'ONE_FINAL_PRIMITIVE_ROOT_REQUIRED')
                need(self.frame_end is None or self.pos==self.frame_end,'STOP_MUST_CLOSE_CURRENT_FRAME')
                need(self.pos==self.size and self.stream.read(1)==b'','STOP_AT_EXACT_ORIGINAL_MEMBER_EOF');stop=True;break
            self.max_stack=max(self.max_stack,len(self.stack));need(len(self.stack)<=1000000,'PRIMITIVE_STACK_BOUND_UNKNOWN')
        need(stop,'COMPLETE_STOP_REQUIRED')
        return self.stack[0],{'opcode_counts':dict(self.counts),'PROTO':4,'STOP_at_EOF':True,'decoded_bytes':self.pos,
            'memo_entries':len(self.memo),'allocated_primitive_nodes':self.nodes,'source_assignments':self.edges,
            'literal_UTF8_token_bytes':self.string_bytes,'maximum_stack':self.max_stack,'frames':self.frames,
            'payload_globals_imported_or_executed':False,'pickle_load_Unpickler_or_constructor_dispatch_used':False,
            'BINFLOAT_original_eight_bytes_retained':True,'all_dict_assignments_order_and_duplicates_retained':True}
