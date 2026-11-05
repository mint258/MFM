# Model D1 v3.0 同版本 policy/config ACK

**文件状态：FINAL_SIGNED_POLICY_CONFIG_ACK**  
**决定：无条件接受以下精确同版本 policy/config；接受范围仅限该政策与配置语义。**

Root 已明确接受本文件所列五项 A 和已验证 physical exposure consumer 的同版本 policy/config。
本决定无条件接受上述精确政策与配置，实际科学数据交付按独立接口验收。
Root 已签发本文件；公开后的精确最终 JSON 可供 Data joint 的 model_ack_reference 引用。

## 1. 接受对象与精确版本

contract_version：v3.0；policy_version：D1_USER_SELECTED_20261029_V1。
接受对象是以下用户决定、三份 all-A 设计及实际 physical 决议的组合，不修改其原字节：

| 资料 | 字节 | SHA256 |
|---|---:|---|
| 用户决定 | 5336 | e4a5e9fe42038394c43aa67bf03dbf416ae39b29be16b88d4cf17b205fabae96 |
| 冻结设计 policy | 20923 | b933a32199a059c3793fce719ac605776ee9ba1d59d1b3c74409b54f9b058acf |
| 五层 mapping selections | 12073 | c2fa1e4b98efeee04d943cbf3fda3fd18bb6e694ed4eb56cdec8f6e34c95afd8 |
| 正式设计 Markdown | 14843 | 226bff0271adce232802393b12e32f2f5f188cacf5b7933c5ac6e3536f217645 |
| native-frame30 后 physical exposure 决议 | 17221 | f0738ab48a3f8517aec955e64001e96710ee9921f6b666122a8595f28cddc43c |

各完整三字段 rawref 见同目录 MODEL_ACK.json。
旧设计中的 conditional/pending 历史状态保持；f073 决议按其实际 post-test 作用域叠加。
本 ACK 不把 native 测试改为全部物理 PASS，也不重新讨论用户已固定的算法。

## 2. 五项 A 的固定配置

1. **r73：F64 权威 sidecar，训练恰一次 F32。** 保留两个原子端点及两个源 UTF-8 channel
   （或可逆且绑定版本/SHA 的 codebook）、onsite、方向、重复项、entry 顺序、有效性和原因。
   entry_ordinal 仅恢复原 retained-list 次序，不作 learned ID；不排序、合并、求和、镜像或别名折叠。
2. **r674：full6、同一实际 geometry、完整资格。** 顺序 xx,xy,yy,xz,yz,zz；
   每实际 task/condition/source 是一个 physical tensor target。原 partial 值、component masks、
   geometry 与原因保留；六项全有效、同一实际 geometry 且 exposure 允许才有 loss。
   不删 zz、不乘1.5、不作 trace projection，不因 loss 关闭制造 numeric mask。
3. **TRAIN Frobenius winsorized std 单尺度、中心零。** 绑定实际 Common/effective TRAIN、
   D5 全部 heldout base/children 反连接、独立 task/condition、人口/版本/SHA；保原 type7
   q0.001/q0.999，仅统计副本缩尾，std_ddof0 给一个实际有限正标量 s；训练 Q/s、c=0。
   缺/空/退化/不可用尺度独立记 LOSS_DISABLED_SCALE_UNBOUND_OR_DEGENERATE；
   不造 s=1、epsilon、RMS、各向异性尺度或新中心。原始 mean(F)/s 与 winsor mean 分列；
   缺原始统计如实待补，不借此改算法。
4. **d9 radial Huber，delta=1，单 target weight=1。**
   E=(Qhat-Q)/s，r=sqrt((Exx²+Eyy²+Ezz²+2Exy²+2Exz²+2Eyz²)/9)，
   Huber_1(r)=0.5r²（r<=1），否则 r-0.5。先平均完整 eligible geometry，
   再进原 target/group 分母；不逐 component 先作 Huber，不把 full6 改六个 target。
5. **5A source provenance 和实际物理范围。** 接受可信普通文件系统、同目录连续性和精确
   native task/geometry source chain 的显式假设；当前文件不存在不是历史绝对证据。
   一次 native-frame30 后按精确 physical 决议处置，不外推未审条件。
   原192条缺独立 native 输出坐标仍 UNKNOWN，不由 Source 假设或新测试补成 PASS。

原单位、符号、源 frame、row-coordinate X'=XR+t、对应原点 Q'=RᵀQR、完整资格与排除率/
化学分布披露及原1%质量门保持。实际 child 必须绑定真实 geometry、原子序、配方、seed、
输入 hash 和相应 view/H0；不以 clean H0 替代实际 child。
带电平移依真实 QM 总电荷、native 定义和偶极交叉项，不用 SMILES 形式电荷代替。

## 3. 物理政策、尺度与其他目标

1. r674 的全部 symmetric6 conditions 按精确 f073 决议独立关闭：
   LOSS_DISABLED_PHYSICAL_POLICY_UNBOUND，保留原 reason。合法 scale 已存在也不恢复该物理 loss；
   physical-disabled 和 LOSS_DISABLED_SCALE_UNBOUND_OR_DEGENERATE 两轴独立记录，
   不互相冒充，不伪称 NO_VALID_LABELS。
2. ORIGIN_SENSITIVE_ACTUAL_QM_CHARGE_NONZERO_TARGETS 必须有实际逐 target/condition/source
   与 QM charge 绑定。上述精确版本未提供该分类；未绑定的启用原点敏感目标 HOLD，
   不从名字、representation 或 SMILES 猜测，不按局部诊断通过样本筛训练人口。
3. 其他经真实来源及既有 scale/frame/资格门确认 ready 的目标继续实际更新；
   未解析目标不能改称 ordinary 来绕 HOLD。关闭目标保留 Source 数值、masks、reasons、
   原 frame 和合法 scale，只跳过无用 head，不造 numeric origin/basis、0/I 或 prediction。
   未执行 head 的 MAE/RMSE 为 None，不能写0。
4. ready r73/typed target 仍需实际 numeric frame/origin、codebook、原子序与真实 geometry/view。
   source-only 传输不授 disabled/ready 权威；loss 独立复核资格。
   provider、配置、CP、source/loss counts 和日志绑定同一实际政策及来源。
5. UNIT/synthetic 工程正例不授实际 Data release、reader、真实标签或全域物理资格。
   原192 UNKNOWN 不变；未审 task/condition 的物理状态不自动提升。

## 4. 已公开 canonical 代码及真实 QA

canonical local commit：**2370d98725732c8b699172b59d93a15c55b5eaa6**  
canonical public commit：**8adb58698ba3187726d37b92080fd10676cef10f**  
canonical Git tree：**3575ec091abf33081fdd979b6ac98eb08efc7982**  
repository / branch：mint258/MFM / model-v3。

真实源码公开证明：/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/canonical_model_v3_delivery_publication_20261029_v1/PUBLICATION.json  
49561B / SHA256 86d0b9da0e7a1b15cce88eab204066353f0b4f6add89677fa67846837d3b22aa。

该实际证明列出106个精确公开 blob 映射，并记录 branch/tree 两项 readback；
完整 recursive tree 的 blob 计数是3405，不能把“106个列出映射”改称整个树只有106文件。
main/tag 未因此变更，scientific_adoption=false。

后验完整 CPU：**4524922，133模块，3125 collected，3122 PASS，0 fail/error，3原 CUDA skip**；
compute-0-19，16CPU，C0。实际执行 commit：
**d900f8cdf5b340006aca84de299687101ae10d9d**。后来的 canonical local2370/public8adb 是文档后继；
PUBLICATION 原件明确记录 runtime code 和133测试逐字节等于实际验收 d900。
不能将2370冒称实际 pytest 执行 commit，也不能把 closure 的 tree 工作树路径冒 Git tree SHA。

真实后验 CPU 证书：/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/delivery_v2_full_auto_post_v1_CPU_4524922_Root_closure_actual_v1.json  
970926B / SHA256 5078dfc904a19a60c94175615315e9cd183fde62ec7b1b2b240ae968ff5054eb。

正常 checker：4524935，PASS，3405文件，errors=[]；原 supervisor 为 C0、无 first_failure、
remaining=[]；原 SUBMITTED 绑定该 job 和 CPU19/16CPU 自动内存入口。
直接引用这三个原文件，未另造 checker_closure：

- /share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/canonical_model_v3_delivery_publication_20261029_v1/check_4524935/repository_check.json
- /share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/canonical_model_v3_delivery_publication_20261029_v1/supervisor_4524935.json
- /share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/canonical_model_v3_delivery_publication_20261029_v1/SUBMITTED.json

133回归和 checker 证明实现、工程契约与源码身份；三项原 CUDA skip 不授 CUDA 或真实 D3。
本 ACK 不将 FP64 数学成功、任何旧失败或已停止 FP32 补偿候选改判为正式 FP32物理通过。
全部补偿候选保持停止、不采用。

## 5. 接受范围与 Data joint 的既有引用

**policy/config 接受为 true 且无条件；以下事项均不在接受对象内：**
D3、D4、D5、D6的实际完成，真实标签/科学 payload、全 release、192坐标 PASS、
global physical PASS、实际 Model 科学采用或最终训练资格。
独立验收门是接受对象之外的职责边界，不是今后可改变本次固定 policy/config 的条件。

现 Data final_release_v1/contract.py 使用既有
ROOT_MODEL_JOINT_FINAL_LABEL_POLICY_V1 / JOINTLY_FROZEN，
要求实际 actual_final_Model_ack_not_conditional、root/model signoff 和其他原 gates。
本 Model ACK 使用自己的 schema，不创建、不签署 Data joint，不代填任何 Data 字段。

Root 签署并公开最终文件后，既有 Data joint 可将最终 MODEL_ACK.json 的真实
{path,bytes,sha256} 填入 **model_ack_reference**。原 **root_review_reference** 和
**contract_reference** 仍分别引用真实 Root 审阅和 Data 合同；不能将本 ACK 冒作这两者。
Data 原 actual_final_Model_ack_not_conditional、model_signoff/root_signoff 等字段须由其真实
joint 制作流程据最终已签引用处理，不能凭本候选状态预置。

实际 registry/mapping source、逐 field unit/sign/basis/frame、完整人口与 D5反连接、
真实 D4技术闭合及Root接受、provider/值/mask/view/恢复验收、FULL实际Model runtime接受
仍按原接口独立满足。UNKNOWN 不得改成 VERIFIED，未解析 symbol/reference 仍拒绝。
本次配置核对的五层 final_resolved_reference 仍为 null；不是实际五层数据交付证明。

## 6. Root 签发栏

签署者：Codex A / Model Root (/root)  
签署UTC时间：2026-10-29T03:46:44.397944+00:00  
发布日期：2026-10-29  
最终本 ACK 公开证明：发布后另存独立 Root receipt，不嵌回本文件  

Root 已核对具体内容及全部原引用，并填写真实署名和时间。JSON 的 document_reference 绑定签后本文的实际 bytes/SHA。
公开后的精确最终 JSON rawref 可进入 Data model_ack_reference；本文件不嵌自身发布回执。
原 DRAFT 和 FINAL_CANDIDATE 均保留；本次签署未修改 Data 或模型源码。
