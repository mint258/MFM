"""Structural paths first; bounded literal evidence without ID/SMILES acceptance."""
import collections,hashlib
from .primitive import AssignmentMap,F64Bits


def kind(value):
    return 'assignment_map' if type(value) is AssignmentMap else 'tuple' if type(value) is tuple else 'unicode' if type(value) is str else 'float64_original_bits' if type(value) is F64Bits else 'UNKNOWN'


def string(value,literal=False):
    raw=value.encode('utf-8',errors='surrogatepass');v={'UTF8_surrogatepass_bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    try:value.encode('utf-8');strict=True
    except UnicodeError:strict=False
    v['strict_UTF8_text_valid']=strict
    if literal:
        v['literal_if_at_most_512_bytes']=value if len(raw)<=512 and strict else None
        v['literal_omitted_due_to_bound_or_nonUTF8']=len(raw)>512 or not strict
    else:v.update(line_breaks=value.count('\n'),M_END_literal_marker_present='M  END' in value,body_literal_persisted=False)
    return v


def key(value):return {'type':kind(value),**(string(value,True) if type(value) is str else {'literal_not_interpreted':True})}


def graph(root):
    counts=collections.Counter();seen=set();active=set();reused=cycles=deep=0;stack=[(root,0,False)];max_depth=0
    while stack:
        value,depth,leave=stack.pop();k=kind(value);container=type(value) in (AssignmentMap,tuple)
        if leave:active.discard(id(value));continue
        counts[k]+=1;max_depth=max(max_depth,depth)
        if not container:continue
        if id(value) in active:cycles+=1;continue
        if id(value) in seen:reused+=1;continue
        seen.add(id(value));active.add(id(value));stack.append((value,depth,True))
        if depth>=64:deep+=1;continue
        children=[x for pair in value.entries for x in pair] if type(value) is AssignmentMap else list(value)
        stack.extend((v,depth+1,False) for v in reversed(children))
    return {'visited_value_kind_counts':dict(counts),'unique_container_objects':len(seen),'reused_container_edges':reused,
        'cycle_edges':cycles,'depth_bound_hits':deep,'maximum_observed_depth':max_depth}


def mapping(value):
    if type(value) is not AssignmentMap:return {'type':kind(value),'source_assignments':None}
    keys=collections.Counter(kind(k) for k,_ in value.entries);strings=[k for k,_ in value.entries if type(k) is str]
    duplicates=sum(v-1 for v in collections.Counter(strings).values());fields=sorted(set(strings))
    return {'type':'assignment_map','source_assignments':len(value.entries),'key_kind_counts':dict(keys),
        'duplicate_unicode_key_assignments':duplicates,'non_unicode_keys':len(value.entries)-len(strings),
        'field_name_evidence':[key(k) for k in fields[:64]],'field_name_evidence_truncated':len(fields)>64,
        'value_kind_counts':dict(collections.Counter(kind(v) for _,v in value.entries))}


def inspect(root):
    g=graph(root);report={'root_type':kind(root),'primitive_graph':g,'normalized_key_calls':0,
        'ligand_conformer_ID_or_field_semantics_accepted':False,'pool_or_decontamination_release':False,
        'tuple_positions_are_source_positions_not_new_schema':True,'literal_top_entry_examples':[],
        'identity_strings_not_normalized_or_trimmed':True,'assay_float_values_persisted':False}
    if type(root) is not AssignmentMap:
        report.update(status='ROOT_STRUCTURE_UNKNOWN_HOLD',root_mapping=mapping(root));return report
    root_names=[k for k,_ in root.entries if type(k) is str]
    report['root_mapping']={k:v for k,v in mapping(root).items() if k!='field_name_evidence'}
    shapes=collections.Counter();nested=collections.Counter();issues=collections.Counter();props0=collections.Counter();props2=collections.Counter()
    tuple_entries=secondary_entries=matching_secondary=0;native_secondary_duplicates=0;secondary_nonunicode_keys=0
    for ordinal,(native,value) in enumerate(root.entries):
        shapes[kind(value)+(':'+str(len(value)) if type(value) is tuple else '')]+=1
        if type(value) is not tuple or len(value)!=3:issues['top_value_not_tuple3']+=1;continue
        tuple_entries+=1;a,b,c=value
        if not(type(a) is str and type(b) is AssignmentMap and type(c) is AssignmentMap):issues['top_tuple_position_types_unknown']+=1
        if type(b) is AssignmentMap:
            for k,v in b.entries:props0[(k if type(k) is str and len(k)<=256 else '<NONSHORT_UNICODE_KEY>',kind(v))]+=1
        example={'source_top_assignment_ordinal':ordinal,'native_root_key':key(native),'tuple_position_types':[kind(x) for x in value]}
        if type(a) is str:example['tuple_position_0_literal_evidence']=string(a,True)
        if type(b) is AssignmentMap:example['tuple_position_1_mapping']=mapping(b)
        if type(c) is AssignmentMap:
            ss=[k for k,_ in c.entries if type(k) is str];native_secondary_duplicates+=sum(v-1 for v in collections.Counter(ss).values())
            secondary_nonunicode_keys+=len(c.entries)-len(ss);examples=[]
            for subordinal,(subkey,subvalue) in enumerate(c.entries):
                secondary_entries+=1;nested[kind(subvalue)+(':'+str(len(subvalue)) if type(subvalue) is tuple else '')]+=1
                if type(subvalue) is not tuple or len(subvalue)!=3:issues['secondary_value_not_tuple3']+=1;continue
                x,y,z=subvalue
                if type(x) is str and type(y) is F64Bits and type(z) is AssignmentMap:matching_secondary+=1
                else:issues['secondary_tuple_position_types_unknown']+=1
                if type(z) is AssignmentMap:
                    for pk,pv in z.entries:props2[(pk if type(pk) is str and len(pk)<=256 else '<NONSHORT_UNICODE_KEY>',kind(pv))]+=1
                if ordinal<8 and len(examples)<3:
                    e={'source_secondary_assignment_ordinal':subordinal,'native_secondary_key':key(subkey),'tuple_position_types':[kind(t) for t in subvalue]}
                    if type(x) is str:e['tuple_position_0_opaque_string_metadata']=string(x,False)
                    if type(y) is F64Bits:e['tuple_position_1_float64_original_bits_retained_not_persisted']=True
                    if type(z) is AssignmentMap:e['tuple_position_2_mapping']=mapping(z)
                    examples.append(e)
            if ordinal<8:example['tuple_position_2_first3_assignment_examples']=examples
        if ordinal<8:report['literal_top_entry_examples'].append(example)
    duplicate_top=sum(v-1 for v in collections.Counter(root_names).values());non_unicode_top=len(root.entries)-len(root_names)
    if duplicate_top:issues['duplicate_root_unicode_key_assignments']+=duplicate_top
    if non_unicode_top:issues['non_unicode_root_keys']+=non_unicode_top
    if native_secondary_duplicates:issues['duplicate_secondary_unicode_key_assignments']+=native_secondary_duplicates
    if secondary_nonunicode_keys:issues['non_unicode_secondary_keys']+=secondary_nonunicode_keys
    if g['cycle_edges'] or g['depth_bound_hits']:issues['cycle_or_depth_bound_structure_unknown']+=1
    def fields(counter):
        items=sorted(counter.items());return {'observations':[{'field_name_evidence':key(k),'value_kind':v,'source_occurrences':n} for (k,v),n in items[:256]],
            'unique_field_and_kind_pairs':len(items),'truncated':len(items)>256}
    shape_ok=bool(root.entries) and secondary_entries>0 and not issues and tuple_entries==len(root.entries) and secondary_entries==matching_secondary
    report.update(status='ALL_SOURCE_ASSIGNMENTS_STRUCTURALLY_OBSERVED_SEMANTICS_PENDING' if shape_ok else 'SOURCE_STRUCTURE_UNKNOWN_HOLD',
        top_source_assignments=len(root.entries),top_value_shape_counts=dict(shapes),top_tuple3_values=tuple_entries,
        secondary_source_assignments=secondary_entries,secondary_value_shape_counts=dict(nested),secondary_tuple3_expected_type_matches=matching_secondary,
        tuple_position_1_field_name_and_type_inventory=fields(props0),secondary_tuple_position_2_field_name_and_type_inventory=fields(props2),
        shape_issue_counts=dict(issues),matches_author_loader_expected_tuple_positions=shape_ok,
        author_reported_counts_used_as_cutoff_or_acceptance=False,all_native_keys_and_strings_retained_in_bounded_decoder_memory=True,
        original_float64_tokens_retained_in_memory_without_numeric_transform=True,
        literal_evidence_limits={'top_assignments':8,'secondary_assignments_per_top':3,'literal_string_maximum_bytes':512})
    return report
