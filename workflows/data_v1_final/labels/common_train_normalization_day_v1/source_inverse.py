"""CPU Source-only full text/AST inverse and direct original mathematical objects."""
import ast,hashlib,json
from pathlib import Path
from . import contract as C,bindings as B

def sha(raw):return hashlib.sha256(raw).hexdigest()

def proof():
    rule_path=C.HERE/'inverse_rules.json';rules=C.meta(C.A.Q.pin(rule_path));out={}
    for row in rules['files']:
        raw=C.A.O.pin_bytes(row['original_reference'],C.A.Q.read_small);text=raw.decode('utf-8-sig')
        for edit in row['replacements']:
            C.need(text.count(edit['old'])==edit['count'],'EXACT_DECLARED_SOURCE_SEAM_COUNT:'+row['file']);text=text.replace(edit['old'],edit['new'])
        current=(C.HERE/row['file']).read_bytes()
        C.need(text.encode()==current,'FULL_ORIGINAL_TO_NEW_BYTE_INVERSE:'+row['file'])
        C.need(ast.dump(ast.parse(text),include_attributes=False)==ast.dump(ast.parse(current),include_attributes=False),'FULL_SOURCE_AST_INVERSE:'+row['file'])
        out[row['file']]={'original_reference':row['original_reference'],'current_sha256':sha(current),'complete_bytes_and_AST_equal_after_declared_seams':True}
    scan=(C.REPO/'workflows/data_v1_final/labels/streaming_v1/scan_v2.py').read_text();audit=(C.HERE/'audit.py').read_text()
    old=[n for n in ast.walk(ast.parse(scan)) if isinstance(n,ast.For) and isinstance(n.target,ast.Name) and n.target.id=='reason'
         and isinstance(n.iter,ast.IfExp) and 'source_reasons' in ast.dump(n.iter)][0]
    new=[n for n in ast.walk(ast.parse(audit)) if isinstance(n,ast.For) and isinstance(n.target,ast.Name) and n.target.id=='reason'][0]
    old.iter=old.iter.body
    class PreviewIO(ast.NodeTransformer):
        def visit_Name(self,n):
            return ast.parse("field['field_id']",mode='eval').body if n.id=='fid' else n
        def visit_Call(self,n):
            n=self.generic_visit(n)
            if isinstance(n.func,ast.Name) and n.func.id=='preview':return ast.parse('B.worst_preview(item,owner,reason,severity,32)',mode='eval').body
            return n
    old=PreviewIO().visit(old)
    C.need(ast.dump(old,include_attributes=False)==ast.dump(new,include_attributes=False),'ORIGINAL_WORST20_SEVERITY_AND_HEAP_AST_AFTER_ONLY_PHASE_AND_PREVIEW_IO_SEAMS')
    return {'status':'CPU_SOURCE_BYTE_AST_SEAMS_AND_DIRECT_OBJECTS_VERIFIED','files':out,
      'worst20_original_arithmetic_AST_verified':True,'original_function_objects':B.verify(),
      'new_fitting_IO_predicate':'FINAL_COMMON_EFFECTIVE_TRAIN_ANTI_D5','science_or_DATA_executed':False}
