"""Nonexecuting pickletools token inventory. No payload object is deserialized."""
import collections,pickletools,re
UNKNOWN=object();MARK=object()
IDENT=re.compile(r'^[A-Za-z_][A-Za-z0-9_.]*$')
CALLS={'GLOBAL','STACK_GLOBAL','REDUCE','BUILD','INST','OBJ','NEWOBJ','NEWOBJ_EX','EXT1','EXT2','EXT4','PERSID','BINPERSID'}


def inventory(stream,check):
    counts=collections.Counter();symbols=collections.Counter();memo={};stack=[];unknown=collections.Counter();events=[]
    stop=False;protocols=[];max_stack=0;parsed_end=0;error=None
    def symbol(v):return v if isinstance(v,str) and len(v)<=256 and IDENT.fullmatch(v) else UNKNOWN
    def event(name,pos,details=None):
        if len(events)<4096:events.append({'opcode':name,'byte_position':pos,'details':details})
        else:unknown['event_examples_truncated']+=1
    try:
        for op,arg,pos in pickletools.genops(stream):
            check();n=op.name;counts[n]+=1
            if n=='PROTO':protocols.append(arg)
            if n in CALLS:event(n,pos)
            if n=='MARK':stack.append(MARK)
            elif n in ('UNICODE','BINUNICODE','SHORT_BINUNICODE','BINUNICODE8','STRING'):stack.append(symbol(arg))
            elif n in ('PUT','BINPUT','LONG_BINPUT','MEMOIZE'):
                if len(memo)>=1000000:raise ValueError('MEMO_SOFTWARE_BOUND_UNKNOWN')
                memo[len(memo) if n=='MEMOIZE' else int(arg)]=stack[-1] if stack else UNKNOWN
            elif n in ('GET','BINGET','LONG_BINGET'):stack.append(memo.get(int(arg),UNKNOWN))
            elif n=='DUP':stack.append(stack[-1] if stack else UNKNOWN)
            elif n=='GLOBAL':
                parts=arg.split(' ');key=tuple(parts) if len(parts)==2 and all(symbol(v) is not UNKNOWN for v in parts) else None
                if key is not None:symbols[key]+=1
                else:unknown['unresolved_GLOBAL']+=1
                stack.append(UNKNOWN)
            elif n=='STACK_GLOBAL':
                name=stack.pop() if stack else UNKNOWN;module=stack.pop() if stack else UNKNOWN
                if isinstance(name,str) and isinstance(module,str):symbols[(module,name)]+=1
                else:unknown['unresolved_STACK_GLOBAL']+=1
                stack.append(UNKNOWN)
            elif n in ('PROTO','FRAME'):pass
            elif n=='STOP':stop=True;parsed_end=stream.tell();break
            else:
                # Symbolic stack effects only. Constructors/callables never run.
                before=[v.name for v in op.stack_before];after=[v.name for v in op.stack_after]
                if 'stackslice' in before:
                    if MARK not in stack:unknown['symbolic_stack_unknown']+=1;stack=[]
                    else:
                        j=len(stack)-1-stack[::-1].index(MARK);prefix=before.index('mark') if 'mark' in before else 0
                        stack=stack[:max(0,j-prefix)]
                else:
                    take=len(before)
                    if take>len(stack):unknown['symbolic_stack_unknown']+=1;stack=[]
                    elif take:del stack[-take:]
                stack.extend(MARK if v=='mark' else UNKNOWN for v in after)
            max_stack=max(max_stack,len(stack))
            if len(stack)>1000000 or len(symbols)>4096:raise ValueError('BOUNDED_SYMBOL_INVENTORY_UNKNOWN')
    except (ValueError,UnicodeError,EOFError,IndexError) as exc:error=type(exc).__name__+': '+str(exc)
    trailing=0
    while True:
        check();data=stream.read(1<<20)
        if not data:break
        trailing+=len(data)
    return {'status':'NONEXECUTING_OPCODE_STREAM_COMPLETE_IDENTITY_PENDING' if stop and not trailing and not error else 'OPCODE_STRUCTURE_UNKNOWN_HOLD',
        'opcode_counts':dict(counts),'protocol_declarations':protocols,'STOP_observed':stop,'parsed_bytes_through_STOP':parsed_end,
        'bytes_after_STOP_or_parser_error':trailing,'parser_error':error,'global_symbols':[{'module':m,'name':n,'occurrences':v} for (m,n),v in sorted(symbols.items())],
        'symbol_resolution_unknown_counts':dict(unknown),'bounded_call_opcode_examples':events,'memo_entries':len(memo),'maximum_symbolic_stack':max_stack,
        'pickle_load_or_Unpickler_called':False,'payload_named_globals_imported':False,'REDUCE_BUILD_or_constructor_executed':False,
        'native_ligand_or_conformer_IDs_observed':False,'molecule_counts_and_graph_identity':'UNKNOWN_PENDING_SEPARATE_REVIEWED_PRIMITIVE_READER'}
