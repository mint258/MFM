"""Record static review of unexecuted source drafts from small code/metadata only."""
import ast
from pathlib import Path
from workflows.data_v1_final.execution.queue_v1.shared import ROOT,REPO,load,pin,write_new,need,on_login,now

def main():
    on_login();integration_path=ROOT/'control/integrate_sb5_full_sources_v1.json';integration=load(integration_path)
    refs=[];python_files=0
    for row in integration['files']:
        path=REPO/row['relative_path'];actual=pin(path)
        need(actual['bytes']==row['bytes'] and actual['sha256']==row['sha256'],'EXACT_UNREGISTERED_DRAFT_SOURCE_REQUIRED')
        refs.append(actual)
        if path.suffix=='.py':ast.parse(path.read_text(),filename=str(path));python_files+=1
    source=REPO/'workflows/expansion/identity_v2/coverage_v2.py'
    function=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='v1_whole_scope_proof')
    expected=next(ast.literal_eval(n.value) for n in function.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='expected' for t in n.targets))
    raw_ref=pin(ROOT/'artifacts/expansion/raw/pubchem_20261025_v1/attempt_4520348/receipt.json');raw=load(raw_ref['path'])
    evidence={'schema':'UNEXECUTED_FULL_SOURCE_DRAFT_STATIC_REVIEW_V1','observed_at':now(),'source_integration':pin(integration_path),'source_references':refs,'generator':pin(Path(__file__).absolute()),'raw_producer_receipt':raw_ref,'source_files':len(refs),'python_AST_files_passed':python_files,'actual_fixtures_run':False,'science_run':False,'source_draft_execution_approved':False,'whole_original_formal_records':11231854,'all_embargo_records':4900,'original_coverage_code_expected_membership_counts_NOT_measured_by_547':expected,'frozen_molecule_VAL_role_unchanged':{'molecules':7610,'records':72525},'gzip_producer_actual_uncompressed_bytes':raw['gzip']['uncompressed_bytes_read'],'findings':['Old identity projection uses per-record member_routine; it must not be presented as new whole-molecule frozen training VAL. New source-role variant will retain original membership booleans and explicitly not apply effective training roles. All-source identity union remains required.','Inventory v1 retains original TSV bytes once without extra text columns, but per-part/final JSON metadata lacks a separately proven bound. New indexed variant must bound metadata and all temporary/failed output inside10GiB before registration.','SB5 startup requires top-level memory_basis. New queue_v3 proof adds only this redundant tag from actual strict admission before writing ready; inverse bytes/AST equivalence is separately recorded. Frozen queue_v1 and old jobs unchanged.'],'next':'Review corrected new source-role and indexed-inventory drafts and actual tiny fixtures, then profile/raw inventory; no global decontamination or pool/common/UFF/QM/training release.'}
    proof=ROOT/'control/full_sources_static_review_20261026_v1.json';report=REPO/'docs/expansion/full_sources_static_review_20261026_v1.md'
    lines=['# 全源身份与原始文件盘点：初稿静态审查','', '目的：在登记运行前核对新源码、角色口径和输出边界。初稿保留，当前不准其科学执行。','',f"输入：集成清单{integration_path}；全部{len(refs)}个源码/文档的path、bytes、SHA见{proof}。{python_files}个Python源码AST通过；未实际运行fixture或科学数据。",'',f"原coverage代码中的成员计数常量为{expected}，这些值没有由547读取成员布尔值证实，也不代表本轮整分子VAL。已冻结的VAL仍为7610分子、72525记录。",'',f"官方gzip生产回执实测解压正文{raw['gzip']['uncompressed_bytes_read']}字节。初稿按原字节TSV盘点，不添加重复文本列；但元数据总量的独立硬界仍需新版本闭合。",'']
    lines += [f'{i+1}. {v}' for i,v in enumerate(evidence['findings'])]
    lines += ['', '规则与限制：只审查小源码和已有回执；不读原LMDB、标签Parquet或原始gzip正文，不触旧池。后续采用明确SOURCE_*成员角色和有界JSONL分片索引，待Root审查及真实检查后再登记。当前不是全来源去污染完成、筛选放行或任何训练交付。','', '脚本：workflows/expansion/review_full_sources_v1.py。报告证据：'+str(proof)+'。','']
    need(not report.exists() and not proof.exists(),'NEW_REVIEW_OUTPUTS_ONLY')
    with report.open('x',encoding='utf-8') as f:f.write('\n'.join(lines))
    evidence['report']=pin(report);write_new(proof,evidence);print({'report':pin(report),'proof':pin(proof),'source_files':len(refs),'AST_files':python_files,'actual_tests':False})
if __name__=='__main__':main()