"""Allocation-only inverse Source proofs; no author-time AST/test claim."""
from __future__ import annotations
import ast,hashlib,inspect,textwrap
from . import contract as C,project as P,store as STORE,transport as T,verify as V


def tree(text):return ast.dump(ast.parse(textwrap.dedent(text)),include_attributes=False)


def transform_resolve(source):
    source=source.replace('def resolve(', 'def resolve_base(',1)
    old='    found = db.execute(query, (mid, src, physical, view)).fetchall()'
    new="    args = [mid, src, physical, view]\n    if keys.get(\"geometry_id\"):\n        query += \" AND geometry_id=?\"; args.append(row[keys[\"geometry_id\"]])\n    found = db.execute(query, args).fetchall()"
    C.need(source.count(old)==1,'ONE_EXACT_OLD_PHYSICAL_LOOKUP_CALLSITE');return source.replace(old,new)


def proof():
    L=C.legacy();entries=[]
    pairs=[('resolve_exact_identity',P.resolve_base,transform_resolve(inspect.getsource(L['pipeline_v1.export'].resolve))),
        ('original_atomic_write_transaction',STORE.Writer.write_batch,inspect.getsource(L['pipeline_v1.granular_store'].GranularFamilyWriter.write_batch).replace('validate(meta, encoded, self.schema)','validate_record(meta, encoded, self.schema)')),
        ('original_reader_mask_transaction',STORE.Reader.get,inspect.getsource(L['pipeline_v1.granular_store'].GranularFamilyReader.get).replace('validate(meta, arrays, self.schema)','validate_record(meta, arrays, self.schema)'))]
    for name,function,expected in pairs:
        actual=inspect.getsource(function);C.need(actual==expected and tree(actual)==tree(expected),'EXACT_DOCUMENTED_SOURCE_INVERSE:'+name)
        entries.append({'function':name,'expected_sha256':hashlib.sha256(expected.encode()).hexdigest(),'actual_sha256':hashlib.sha256(actual.encode()).hexdigest(),
            'entire_function_bytes_equal_after_declared_IO_edit':True,'AST_equal_after_declared_IO_edit':True})
    direct=[('geometry_arrays',P.S.geometry_arrays,L['pipeline_v1.source'].geometry_arrays),('f64_pack',P.S.pack,L['pipeline_v1.source'].pack),
        ('f64_unpack',P.S.unpack,L['pipeline_v1.source'].unpack),('source_extract',T.S.extract,L['pipeline_v1.source'].extract),
        ('ordinary_sparse_and_scalar_targets',T.PAIR.target_arrays,L['pipeline_v1.source_v2'].target_arrays),
        ('compact_restore',T.MASK.restore,L['pipeline_v1.masks'].restore),('tensor_vector_assembly',T.WIRE.assemble_target,L['wire_v1.mapping'].assemble_target),
        ('canonical_MFM3_encoder',STORE.encode_record,L['wire_v1.codec'].encode_record),('canonical_MFM3_decoder',STORE.decode_record,L['wire_v1.codec'].decode_record),
        ('original_f64_single_f32_compare',V.compare,L['pipeline_v1.verify'].compare)]
    for name,a,b in direct:
        C.need(a is b,'DIRECT_ORIGINAL_OBJECT:'+name);text=inspect.getsource(a);entries.append({'function':name,'direct_original_object':True,'source_sha256':hashlib.sha256(text.encode()).hexdigest()})
    return {'schema':'FAMILY_EXPORT_DECLARED_IO_SOURCE_INVERSE_V1','status':'EXACT_THREE_FUNCTION_BYTES_AST_AND_TEN_ORIGINAL_OBJECTS',
        'revision2_IO_source_proof':revision2_proof(),'entries':entries,'new_IO_not_claimed_old_function_bytes':['per-field actual geometry claims','ordered r73 transport','raw native S bonds',
            'candidate-inline authority','exact disjoint target/geometry shards','persistent bounded worker orchestration','source QA metadata','external seal'],
        'old_global_modules_mutated_or_monkeypatched':False,'new_scientific_normalization_or_geometry_math':False,
        'author_executed_this_proof':False}

def function_text(source,name):
    source=source.replace('\r\n','\n');parsed=ast.parse(source)
    nodes=[n for n in parsed.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name]
    C.need(len(nodes)==1,'ONE_BASELINE_MODULE_FUNCTION:'+name);node=nodes[0]
    lines=source.splitlines(keepends=True)
    # Match linecache's one-LF view of an unterminated physical EOF only.
    # The whole original module bytes/SHA remain checked before extraction.
    if lines and node.end_lineno==len(lines) and not lines[-1].endswith('\n'):
        lines[-1]+='\n'
    return ''.join(lines[node.lineno-1:node.end_lineno])


def revision2_proof():
    from . import writer as W,metadata as M
    frozen=C.Q.load(C.HERE/'frozen_sources.json');w=frozen['family_r1_witness'];delta=frozen['revision2_declared_IO_deltas']
    C.need(w['source_zip_bytes']==67577 and w['source_zip_sha256']=='a48453a51935f0c610f4baca764a1dd3a6f597aa480a7e5e2d5f1625f2b96ffd','EXACT_RETAINED_R1_SOURCE_BUNDLE_WITNESS')
    baseline={row['root_relative_path'].rsplit('/',1)[-1]:row for row in w['mechanical_function_sources']};comparisons=[]
    for row in baseline.values():C.need(hashlib.sha256(row['source_text'].encode()).hexdigest()==row['sha256'] and len(row['source_text'].encode())==row['bytes'],'ORIGINAL_WHOLE_SOURCE_BYTES_WITNESS')
    targets=[('writer.py','export_shard',W.export_shard,delta['writer_old_select'],delta['writer_new_select']),
        ('store.py','open_accepted',STORE.open_accepted,delta['store_old_call'],delta['store_new_call']),
        ('metadata.py','seal',M.seal,delta['metadata_old_call'],delta['metadata_new_call']),
        ('project.py','selection_database',P.selection_database,delta['selection_callsite'],delta['diag_insert_source']+delta['selection_callsite'])]
    for file,name,function,old,new in targets:
        expected=function_text(baseline[file]['source_text'],name);C.need(expected.count(old)==1,'ONE_R1_IO_CALLSITE:'+name)
        expected=expected.replace(old,new);actual=inspect.getsource(function)
        C.need(actual==expected and tree(actual)==tree(expected),'ENTIRE_FUNCTION_ONLY_DECLARED_R2_IO_DELTA:'+name)
        comparisons.append({'function':name,'actual_source_sha256':hashlib.sha256(actual.encode()).hexdigest(),'full_function_bytes_and_AST_equal_after_exact_declared_IO_edit':True})
    unchanged=[]
    for row in w['files']:
        name=row['root_relative_path'].rsplit('/',1)[-1]
        if name in ('__init__.py','claims.py','io.py','run.py','transfer.py','transport.py','verify.py'):
            C.need(C.Q.pin(C.HERE/name)=={'path':str(C.HERE/name),'bytes':row['bytes'],'sha256':row['sha256']},'ENTIRE_R1_WORKER_MATH_RESOURCE_CODEC_ROUTE_UNCHANGED:'+name);unchanged.append(name)
    return {'status':'EXACT_R1_WITNESS_FOUR_NARROW_IO_FUNCTION_INVERSES_AND_SEVEN_WHOLE_UNCHANGED_LEAVES',
        'r1_source_zip_sha256':w['source_zip_sha256'],'inverse_functions':comparisons,'unchanged_whole_Source_files':unchanged,
        'new_pure_IO_authority_helpers':['assert_diagnostic_lineage','assert_publication_links','validate_published_release'],
        'mathematics_sampling_values_storage_codec_changed':False,'author_executed_this_proof':False}