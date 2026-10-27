"""CPU-only source inverse proof; no scientific DATA and no copied code execution."""
import ast,hashlib,json
from . import contract as C


def region(raw,start=None,end=None):
    if start is None:return raw
    C.need(raw.count(start)==1 and raw.count(end)==1,'UNIQUE_SOURCE_REGION_ANCHORS')
    a=raw.index(start);b=raw.index(end,a);return raw[a:b]


def verify():
    m=json.loads((C.HERE/'adaptation_manifest.json').read_text())
    C.need(m['schema']=='SPRIME_CPU17_LIMITED_SOURCE_INVERSE_MANIFEST_V1'
      and m['scientific_sources_copied_or_changed'] is False,'EXACT_SOURCE_ONLY_EDIT_MANIFEST')
    rows=[]
    for row in m['files']:
        original=C.pinned(row['origin'],2<<20).read_bytes()
        original_region=region(original.decode(),row.get('origin_start'),row.get('origin_end'))
        new=region((C.HERE/row['target']).read_bytes().decode(),row.get('target_start'),row.get('target_end'))
        expected=original_region
        for op in row['edits']:
            C.need(expected.count(op['old'])==op['count'],'EXACT_FORWARD_LITERAL_COUNT:'+row['target'])
            expected=expected.replace(op['old'],op['new'])
        expected+=row.get('append','')
        C.need(new.encode()==expected.encode(),'ONLY_DECLARED_LITERAL_IMPORT_RESOURCE_CHANGES:'+row['target'])
        inverse=new
        if row.get('append'):
            C.need(inverse.endswith(row['append']),'EXACT_RESOURCE_SUFFIX');inverse=inverse[:-len(row['append'])]
        for op in reversed(row['edits']):
            C.need(inverse.count(op['new'])==op['count'],'EXACT_REVERSE_LITERAL_COUNT:'+row['target'])
            inverse=inverse.replace(op['new'],op['old'])
        C.need(inverse.encode()==original_region.encode(),'INVERSE_SOURCE_REGION_BYTES_MUST_RESTORE_ORIGINAL')
        restored=original.decode().replace(original_region,inverse,1)
        C.need(restored.encode()==original and ast.dump(ast.parse(restored),include_attributes=False)
          ==ast.dump(ast.parse(original.decode()),include_attributes=False),'INVERSE_WHOLE_SOURCE_BYTES_AND_AST_EQUAL')
        rows.append({'target':row['target'],'origin':row['origin'],'origin_start':row.get('origin_start'),
          'inverse_original_sha256':hashlib.sha256(restored.encode()).hexdigest()})
    C.need(C.sources()['science']==m['original_science_reference'],'ORIGINAL_SCIENCE_PATH_AND_SHA')
    return {'schema':'ACTUAL_MAIN17_SOURCE_INVERSE_PROOF_V1','inverse_bytes_and_AST_equal':True,
      'scientific_kernel_modified':False,'rows':rows,'original_science_reference':m['original_science_reference']}