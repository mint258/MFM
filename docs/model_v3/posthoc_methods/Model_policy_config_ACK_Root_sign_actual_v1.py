import json, hashlib, pathlib, datetime, subprocess
B=pathlib.Path('/share/home/zixiao/descriptor_analysis')
N=B/'runs/model_v3_20261026'
C=N/'Model_same_version_policy_config_ACK_20261029_FINAL_CANDIDATE_v1'
P=N/'Model_same_version_policy_config_ACK_20261029_FINAL_v1'
assert not P.exists(), 'Refuse to replace final signature'
j=json.loads((C/'MODEL_ACK.json').read_text())
assert j['status']=='FINAL_CANDIDATE_PENDING_ROOT_SIGNATURE'
assert j['decision']['policy_config_accepted'] is True
assert j['decision']['policy_config_acceptance_is_unconditional'] is True
assert all(v is False for v in j['additional_authorities_granted'].values())
assert all(v is None for v in j['signature'].values())
def ref(p):
 p=pathlib.Path(p); b=p.read_bytes()
 return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def verify(r):
 assert ref(r['path'])=={k:r[k] for k in ('path','bytes','sha256')}, r['path']
for r in [j['document_reference'],j['canonical_model']['actual_publication_reference'],j['actual_postintegration_CPU']['Root_closure'],j['actual_postintegration_CPU']['summary'],j['physical_source_freeze'],j['existing_Data_joint']['source_reference']]+j['exact_Data_inputs']+[j['actual_normal_checker'][k] for k in ('repository_check','supervisor','submission')]+list(j['previous_DRAFT_preserved'].values()):
 verify(r)
W=B/'MFM_model_v3_delivery_integration_v2'
G=B/'runs/model_v3_20261025/cpu_git_tools_v1/bin/git'
assert subprocess.check_output([str(G),'-C',str(W),'rev-parse','HEAD'],text=True).strip()==j['canonical_model']['local_code_sha']
assert not subprocess.check_output([str(G),'-C',str(W),'status','--porcelain'],text=True).strip()
assert subprocess.check_output([str(G),'-C',str(W),'rev-parse','HEAD^{tree}'],text=True).strip()==j['canonical_model']['Git_tree_sha']
t=datetime.datetime.now(datetime.timezone.utc).isoformat()
signer='Codex A / Model Root (/root)'
md=(C/'MODEL_ACK.md').read_text()
md=md.replace('FINAL_CANDIDATE_PENDING_ROOT_SIGNATURE','FINAL_SIGNED_POLICY_CONFIG_ACK')
md=md.replace('在 Root 完成署名并公开最终字节前，本候选不能冒充已签发的 Data joint 引用。','Root 已签发本文件；公开后的精确最终 JSON 可供 Data joint 的 model_ack_reference 引用。')
md=md.replace('本决定不是新的条件性设计意见；尚空的署名和发布日期是这份文件的签发手续。','本决定无条件接受上述精确政策与配置，实际科学数据交付按独立接口验收。')
md=md.replace('签署者：未填写','签署者：'+signer).replace('签署UTC时间：未填写','签署UTC时间：'+t).replace('发布日期：未填写','发布日期：'+t[:10])
md=md.replace('Root 最后核对具体内容，填写真实署名/时间/日期并发布最终版本。\n同时将 JSON 的 document_reference 更新为签署后本文真实 bytes/SHA；\nJSON 本身不嵌自己的 SHA 或包含自身字节的发布回执，避免自引用。Data 只引用签署后最终字节，不引用当前候选 rawref。\n原 DRAFT 保留，新 FINAL_CANDIDATE 不覆盖它；未改 Data、源码或 reporting。','Root 已核对具体内容及全部原引用，并填写真实署名和时间。JSON 的 document_reference 绑定签后本文的实际 bytes/SHA。\n公开后的精确最终 JSON rawref 可进入 Data model_ack_reference；本文件不嵌自身发布回执。\n原 DRAFT 和 FINAL_CANDIDATE 均保留；本次签署未修改 Data 或模型源码。')
assert '未填写' not in md
P.mkdir()
(P/'MODEL_ACK.md').write_text(md)
j['status']='FINAL_SIGNED_POLICY_CONFIG_ACK'
j['signature']=dict(signer=signer,signed_utc=t,publication_date=t[:10])
j['decision']['signature_status']='ACTUALLY_ROOT_SIGNED'
j['decision']['effective_as_signed_Data_joint_reference']=True
j['decision']['publication_readback_is_external_receipt']=True
j['document_reference']=ref(P/'MODEL_ACK.md')
j['existing_Data_joint']['future_reference_value']='Exact {path,bytes,sha256} of this actual signed final MODEL_ACK.json, with actual publication readback recorded externally'
j['signing_instructions']=['Root actually signed these final bytes after concrete content and raw-reference checks','Actual public readback receipt must be external and must not rewrite these signed bytes']
j['author_operations']='Model Root final review, all bound raw-reference revalidation, actual signature; no Data or model source changes'
(P/'MODEL_ACK.json').write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
record=dict(schema='MODEL_POLICY_CONFIG_ACK_ROOT_SIGNATURE_ACTUAL_V1',status='ACTUALLY_SIGNED_PUBLICATION_PENDING',signed_utc=t,signer=signer,final_files=[ref(P/'MODEL_ACK.md'),ref(P/'MODEL_ACK.json')],candidate_files=[ref(C/'MODEL_ACK.md'),ref(C/'MODEL_ACK.json')],data_modified=False,scientific_adoption=False)
(N/'Model_policy_config_ACK_Root_signature_actual_v1.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(record))
