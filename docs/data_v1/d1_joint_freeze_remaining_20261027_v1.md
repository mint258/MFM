# D1 共同冻结剩余项：2026-10-27 增量备忘

SOURCE REVIEW ONLY。只读源码、草案登记和已闭合小manifest/accounting；未执行Python、测试、科学正文读取、SSH、Slurm或Git。只新增本页，不改Root的Source22所pin契约、STATUS、provider或旧证据。D1仍为draft.3；Codex A七条审阅意见已收到，尚非双方v3.0签署。下文D=`runs/data_v1_20261025/repository/`，M=`MFM_model_v3/`，L=`runs/phase1_dataset_rebuild_20261010/scripts/`，均相对原Main项目根。

## 可由现有源码直接核清，毋须再跑fixture

- **r73的通道是双端标签，不是单个AO编号。** 实际链为WP5 engine→冻结NATIVE.invoke→`L/wp4_native_pilot_v4.py:171–196,383–385`的`sparse_sigma_pi`，再由`wp5_parser_v2.py:49`和`wp5_parser.py:60`把hook传入原parser。每端key是`(打印atom号−1, 原S/P/D/F-SIGMA/PI/DEL…字符串)`，保存`atom_i,basis_i,atom_j,basis_j,value`；没有独立AO ordinal。可写成三元键`(src_atom,dst_atom,(src_channel,dst_channel))`，其中channel必须是**有序双端字符串对**，不能压成一个shell、用AO_ATOMINDEX代替、交换两端或推测物理旋转规律。
- 该原parser明确保留`atom_i==atom_j`的onsite项及所选近邻pair；同atom对不同通道应共存，源列表顺序与重复原样保留。它自身按`(atom,basis_label)`登记keys，没有另外保存原打印列/轨道组ordinal；新wire只能注明这一信息缺失，不能补造原AO身份。当前`size_semantics_v1/aggregate.py:22–34`的unordered键仅供既有统计review，不能取代原键，更不能证明原值冲突。
- **r674精确身份**是`registry_id=674 / task=xtb_singlepoint / values.molecular_quadrupole_traceless_au`；成员序`xx,xy,yy,xz,yz,zz`。原registry、`L/wp4_parsers.py:247–250`六值读取及`D/.../wire_v1/mapping.py:6–7,79–115`六分量/对称矩阵编码有对应；人类别名r67_4不进入机器匹配。声明e bohr²和traceless不代替实际程序原点/轴/trace证据，也不许可删zz。
- 各map须分别冻结：①raw registry ID→精确field/component；②physical target→成员、shape、单位、family/condition；③source selector→本字段原键/owner/索引；④D5 native physical key→opaque geometry/来源独立training_rank；⑤model provider target→FieldSpec/shape/pairs/normalizer。当前source_v2的动态n_pairs只解决本字段[p,2]长度，不表达通道；现wire拒重复atom pair，模型collate另拒self，provider显式拒basis、tensor、off-equilibrium。不能把其中任一map的PASS当作另四项已冻结。

## r73最小候选wire字段（仅提案，必须新契约/映射版本与模型线共同确认）

| 候选字段 | 原样来源与约束 |
|---|---|
| record/geometry/source_ref | 原完整owner、原子序/坐标hash与科学source pin；不由atom对猜身份 |
| src_atom / dst_atom | 原atom_i / atom_j，零基，int32范围检查；允许same-atom，不排序/镜像 |
| src_channel / dst_channel | 原basis_i / basis_j，逐条UTF-8字符串；两端分别保存，不推AO或合并shell |
| entry_ordinal | 原已解析sigma_pi_entries列表位置int64；用于保持顺序/重复，明确不是原程序AO ordinal |
| value | 原value及来源精度；永久float64/训练一次float32规则另明确，不求和/平均/去重 |
| valid / reason_refs | 原component/leaf validity；source/new/review、稀疏例外及codebook/hash各自保留，未知原因不补造 |

这是一条有序basis-channel entry域，不是当前unique `[atom_i,atom_j]`普通pair域；即使三元键重复也先以entry_ordinal无损保存并报告，不据此删除或改mask。旧schema/provider仍应拒绝该新域。模型需要通道身份的明确输入/预测语义；本页不决定其head、pooling、等变变换或归一化。

## D1至D5真正剩余门槛

| 项 | 已有证据与下一具体动作 |
|---|---|
| r73 / r674消费 | r73上述域与模型算法未共同确认；r674数据codec已支持，模型FieldSpec/provider尚拒。需明确tensor原点/完整六分量mask、物理loss/尺度与模型实现，不能六不变标量代填。 |
| native geometry/frame/units | 原子序与source hash连接、base F64坐标及perturbed位置/元素/seed/sigma已可保存；真实native轴、原点、打印精度与全部view对应仍未验收。r623/624/625必须连实际child/parent/坐标hash，不能挂base H0或任意S噪声。MolMR、Fukui、Dn/De等单位/convention的pending仍保留。 |
| order / common / D4 / D5 | 模型已同意PM7/UFF独立entry、保留集energy training_rank=0及诊断base/child反连接；候选桥已测，不重做镜像fixture。最终common/opaque geometry/三order/诊断与N=1/N=2/k不足政策未冻结；随后才可共同绑定D5与最终TRAIN-only、逐condition D4，P′不能借PM7统计。 |
| mask /真实provider | granular validity/reasons与provider审计sidecar已有候选实现；契约正文仍须明确field-set+sparse-leaf-v1/65535，不冒称稠密逐叶因果。真实release、VAL与native atom-order authority尚未放行；当前synthetic opt-in/TRAIN/base门不能只改authority字符串绕过。 |
| 联签与D3 | 最终registry/全物理target-map、unit/frame、codebook、D4/D5、schema/shard/hash和双方确认记录尚缺。正式export原闸门仍在；不能用审阅意见、fixture或source投影签v3.0。真实50k+5k/1万源值对照及模型加载验收依旧待办。 |

## 下一次真实CPU只补缺口，不重跑既有1620/2048或投影witness

实际4521789 C0/1334s/16CPU的`artifacts/labels/source_status_v1/bounded_projection32_v1/manifest.json`是有限source/mask投影：10455重叠匹配、16实际parity witness、0diff；其`actual_frame_origin_verified`、`native_program_precision_verified`、`registry_final`、`candidate_masks_frozen`、`final_common_D4`均false。不存在已闭合“20 witness native-frame summary”；20k/每20witness native诊断仍是待办，P′旧15FAIL及独立QA也不替代PM7/base+allviews核验。

最小输入locator：同目录`witness_discovery.json`（23579B，SHA ce85cdd2bbd9c78e8c24ee631ced6db4eb7c639a48a7c868adaa84e39ac42ed0）中record_ordinal=2535608：pm7_B/task2/file29/RG0/physical-row5可同时定位r73/r82；xtb_singlepoint/task11/file33/RG0/row5定位r674；perturbed/task10/file27/RG0/row5定位r625。它们只是原typed表示witness，**不保证raw可得或native-frame代表性**。从manifest的actual_range_plan→原source ref与closed_window/part→原typed provenance/component_map，在CPU按这些既存位置取原输入/输出locator、program ID、input_bundle/file/reproduction SHA，再与base及四个实际perturbed provenance CELL连接；raw缺失明确UNKNOWN，不另跑QM补证。`control/labels_lossless_projection512_stage_v1/config.json`的owner_plan指向既有146009B group_plan（SHA065f6adc6615b8f281bc7373a30fe928d3bb971b5044928ffa01854ce262cc13），不需再扫全源才能确定这类有界读取范围。

既有`labels/payload_audit_v1/run.py:143–167`的`details.raw_precision_candidates`保留task/owner/raw_locator_json/program/input hashes；`pprime/frame_native_precision_diagnosis_v2/{raw_reader,tokens,precision}.py`有有界只读raw、原token/单位和坐标诊断可复用。其`run_v2.py`严格绑定旧retained72，**不是任意PM7/allviews可直接运行入口**；目前未发现已可放行的通用native-frame入口。Root需审阅最小source-specific只读适配和确切raw可得清单，不重启整72、重做旧fixture或以无raw样例声称native PASS。

## 本次关键小文件观测SHA256

| 输入 | bytes / SHA256 |
|---|---|
| D/docs/interfaces/training_format_v3.md | 19059 / 399ee0cebf8497c4e73accc52f84fd7d42b9753f9779433c80d12641df5a5ea2 |
| D/configs/data_v1/label_registry_v3.json | 585411 / b6a230b74b5bebfa0108e67572ed2ccc699718c2958fb69e99c58b8323c6ce45 |
| M/current/phychem_mfm/phase1/v3_wire_provider.py | 22752 / 80c728c157205ca1e9870d511751efc6b87a7c59c795d28a6911c313610c2ea8 |
| L/wp4_native_pilot_v4.py | 56251 / 6943612b2fd6c3c7a492c08183f2328230469dea5113aadc613c32378cc79b59 |
| L/wp4_parsers.py | 20763 / 66938afa8d3d7b7f51e8922c875c0987687a865a97cb1591d6f6c511b38098e0 |
| bounded_projection32_v1/manifest.json | 226933 / 344b7e3dadd09075307b171296e7ae88d008cbe1bd032fd932531230bbf49694 |

这些是小文件实际字节快照及已闭合producer metadata的摘录，不是本child新增科学统计、实际native读取或整树执行commit证明。旧D1、各map、原科学值和全部质量门槛保持。