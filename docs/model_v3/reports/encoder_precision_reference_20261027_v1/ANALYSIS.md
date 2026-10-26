# 全encoder FP64分析参考：4521561（只读，非模型采用）

同一实际1492输入和权重来源下，独立全encoder FP64参考的三类终端全部432观测、48组合均未超过1e-5；最大值分别为extensive 8.4490057972175237e-7、dipole 1.2230009573399592e-6、magnitude 7.9358518442762538e-7。它支持继续研究FP32编码器的求值稳定性，但不把原FP32的10通过/38失败改为通过，也不证明FP32误差下界或严格二分坐标舍入。

Root实际回报GPU4521561在公开1715cac7da6743c56a7e84894bf13e3072f2ec07之后运行，COMPLETED/0:0、131秒、node21/c35。已闭合JSON确认192次原FP32+192次F64 encoder，192次scientific functional64 bank调用/576字段输出，failure=null/source_equal。原FP32全部48×4 bank H0先与1492逐位一致，才开始F64。小控制另计12次dim4单层前向及4CPU+4CUDA functional64 bank调用，不能混入384次6×512病例前向。

本报告仅读取闭合JSON；48份case原bytes/SHA逐一核对，保留完整3C1×2views×4head/pooling×2seed，未读NPZ/SDK/坐标或权重张量，未跑模型/新作业、未改源码。完整48成员、分C1/views/seed/head分组、18个stage/scope汇总均在配套紧凑JSON。

| 字段 | 原GPU FP32 D（F64 L）max / 超限观测 | 全encoder+头F64 D max / 超限观测 | F32−F64 D max / 超限观测 |
|---|---:|---:|---:|
| p_extensive | 1.549721E-05 / 14/144 | 8.449006E-07 / 0/144 | 1.550662E-05 / 14/144 |
| p_dipole | 2.193984E-05 / 35/144 | 1.223001E-06 / 0/144 | 2.207680E-05 / 35/144 |
| p_dipole_magnitude | 5.651265E-05 / 32/144 | 7.935852E-07 / 0/144 | 5.699330E-05 / 31/144 |

每个字段144观测=48组合×3变换，超限指保存maxabs>1e-5，非分量个数。原GPU D使用F64的L作用于保存FP32输出，不能替换原C4的FP32期望公式；其81条超限/38组合与原物理门槛的边界保持。F64仅覆盖canonical H0与三PD，不是其他头/整模型F64验收。

逐层clean44节点的最大漂移如下（每格分别对144观测取最大，来自不同分量也可能不同case，严禁相加）：

| stage | FP32 drift max | FP64 drift max | F32−F64 drift max | 同FP32 argmax处残差较大/144 |
|---|---:|---:|---:|---:|
| embedding | 0.000000E+00 | 0.000000E+00 | 0.000000E+00 | 0 |
| layer0 | 1.430511E-06 | 2.590041E-07 | 1.430919E-06 | 144 |
| layer1 | 2.026558E-06 | 2.873313E-07 | 2.033988E-06 | 144 |
| layer2 | 2.861023E-06 | 3.294545E-07 | 2.889095E-06 | 144 |
| layer3 | 3.099442E-06 | 3.607198E-07 | 3.120308E-06 | 144 |
| layer4 | 3.814697E-06 | 4.242007E-07 | 3.836112E-06 | 144 |
| layer5 | 3.814697E-06 | 4.171025E-07 | 3.855762E-06 | 144 |
| out_norm | 1.907349E-06 | 1.918896E-07 | 1.927746E-06 | 144 |
| packed_H0 | 1.907349E-06 | 1.918896E-07 | 1.927746E-06 | 144 |

embedding在两条路径下漂移均0。第一层后FP32最大1.4305e-6，至第六层后达到3.8147e-6；末out_norm后降至1.9073e-6，packed H0与其相同。非embedding的每个stage在其全部144个FP32最大分量处，|F32−F64 drift|都大于|F64 drift|。这比只看跨case最大值更直接支持整体求值差异占主导，但不是解释方差或单kernel因果分摊。全88/132 packed物理view另表保存在JSON，未以clean44替代encoder输入。

每个stage的最坏FP32观测同分量：D32=D64+residual；以下每行三个带符号数严格来自同一case/transform/row/channel，而不是独立max相加。

| stage | FP32 | FP64同分量 | residual同分量 |
|---|---:|---:|---:|
| embedding | 0 | 0 | 0 |
| layer0 | +1.430511474609E-06 | -4.071718517906E-10 | +1.430918646461E-06 |
| layer1 | +2.026557922363E-06 | -7.429705295436E-09 | +2.033987627659E-06 |
| layer2 | -2.861022949219E-06 | +2.807229226853E-08 | -2.889095241487E-06 |
| layer3 | -3.099441528320E-06 | +2.086679407043E-08 | -3.120308322391E-06 |
| layer4 | -3.814697265625E-06 | +2.141480814899E-08 | -3.836112073774E-06 |
| layer5 | +3.814697265625E-06 | +3.983903873461E-09 | +3.810713361752E-06 |
| out_norm | +1.907348632813E-06 | -3.929279124293E-10 | +1.907741560725E-06 |
| packed_H0 | +1.907348632813E-06 | -3.929279124293E-10 | +1.907741560725E-06 |

最终clean H0分C1的FP32/F64最大漂移：

- C1-0（完整16组合）：1.9073486328125E-06 / 7.0700424292802211E-08。
- C1-a（完整16组合）：1.6689300537109375E-06 / 1.5896582317154184E-07。
- C1-b（完整16组合）：1.7583370208740234E-06 / 1.9188963529259695E-07。

这不是C1排序依据：三C1/两views/两seed全部保留，参考差异不能代替真实标签面板或训练效果。

最坏原GPU终端处的同分量对照（原GPU D=F64 D+residual）：

| 字段 | 原GPU D | F64同分量 | residual同分量 |
|---|---:|---:|---:|
| p_extensive | -1.549720764160E-05 | +9.410150880740E-09 | -1.550661779248E-05 |
| p_dipole | +2.193984128284E-05 | -1.369607901050E-07 | +2.207680207294E-05 |
| p_dipole_magnitude | +5.651265382767E-05 | -4.806474395019E-07 | +5.699330126717E-05 |

每字段最坏F64观测另行保存其自己的位置/带符号值，不把它与上述原GPU argmax错配。报告的同分量对照只使用原保存的“同原GPU argmax”tuple，不用两端各自max拼装贡献，也未读取数组重构F64 argmax处的另一端值。

实际geometry/mask：48原模型及48影子均6层use_radius_mask=false、effective radius=null；C1-a/b cutoff=null，Gaussian中心范围8不是cutoff。192个参考mask均bool，two为6×32、three为9×32；完整输入/packed88或132，之后同clean行取44。原R最大正交残差2.2204460492503131e-16，未改R、无ideal/polar/重生成高精度坐标。S的5Å几何头与8Åpair envelope没有获得F64验证。

小检查：三C1的tiny legacy FP32原/适配forward逐位相同，tiny FP64 dtype/同输入重放通过；四head/pooling的原functional64 CPU/CUDA最大差为1.1102230246251565e-16，低于预声明1e-10。旧functional64算术原字复用，PD bank原权重仍FP32，在函数内提升，未将拒Double的补偿头直接.double()。

状态证据：本只读解析核15488个tensor-state映射头，其中15488个F32→F64的dtype/shape/字节翻倍规则成立，0个非浮点头保持相同。32个C1 extra_state只去除numeric_mode=compensated_fp32_v1以声明分析legacy映射；其他字段不变。已知geometry_head.rbf_centers的持久buffer映射记录共48份。实际cast-back字节相等由公开源码在运行中逐tensor断言并随C0闭合；当前JSON映射主要保存原/提升后SHA，本只读报告未重读张量来独立复算cast-back。尤其1492没有单独保存整个encoder buffer rawSHA，不能把本轮当前原→影子复制闭合冒充旧buffer的独立历史核验。

下一步判断：继续研究FP32规约、LayerNorm、GEMM/QK/AV、softmax与残差求值仍有明确依据。候选已经补偿部分几何平方和/图级求和，但第一层内部还有多个标准FP32算子；现有post-layer采样不能区分它们。末out_norm总体最大误差下降，不能凭此指控末LayerNorm是唯一放大源，更不能据此指定必须替换某个kernel。应只提出有明确数学语义、事前冻结的单项FP32数值候选并保留原全48门槛，而非再挑seed/构型或把F64本身作为生产采用。

同样，F64残余仍可能混合实际FP32坐标离散化、原R非完美正交、有限F64求值及legacy/direct距离实现的舍入；这是同实数公式的有限参考，不是逐指令仅换dtype或无误差实数oracle。结果不支持本输入已强迫三终端超限的断言，但不提供严格独立坐标项/算术项二分，不能证明任意FP32实现可通过或不可能通过。原10PASS/38FAIL、质量阈值/真实面板/配方与采用状态均不变。

来源与复核：按所有48个result raw refs核bytes/SHA，完整展平432 terminal与2592 stage观测，按字段/stage/scope及全部因素分组取保存maxabs、严格>1e-5计数、case去重；同分量仅用原保存tuple。没有重算模型、数组或权重。

- result：`/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/full_encoder_FP64_GPU_v1_4521561/ANALYSIS_RESULT.json`；16314B；`d70ae21a68b3a21185b9da7d1b0264b3ce52aa7c65887f6cebc0927299361a26`。
- complete：`/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/full_encoder_FP64_GPU_v1_4521561/COMPLETE.json`；571B；`233eac98943416f314f21df186fd96b395157d8faed02593dbc3bbf3ea65cd9b`。
- FP32_replay_gate：`/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/full_encoder_FP64_GPU_v1_4521561/FP32_REPLAY_GATE.json`；423B；`4e877b18f74b2703cea6653ac65a93b112891b34988bbacddf12faa6545e82f1`。
- inline_controls：`/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/full_encoder_FP64_GPU_v1_4521561/INLINE_DEVICE_SELFCHECK.json`；992B；`44402af50de58f5398669046363e6827939b1a6dec9aa7e87941141ab1b4758b`。
- supervisor：`/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/full_encoder_FP64_GPU_v1_supervisor_4521561.json`；3062B；`4549ff8b8b30108bdfffd4b67c850d00841134dee4d4b991dcf353c4036a5d9b`。
- sources_before：`/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/full_encoder_FP64_GPU_v1_4521561/sources_before.json`；92676B；`d22a2e1a5f29811c285e664235f14ed0fe3318333f56dc6578de0f3db063744f`。
- sources_after：`/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/full_encoder_FP64_GPU_v1_4521561/sources_after.json`；92676B；`d22a2e1a5f29811c285e664235f14ed0fe3318333f56dc6578de0f3db063744f`。
- 紧凑JSON：`/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/full_encoder_FP64_1561_readonly_analysis_v1.json`；744465B；`d9b203f4e5a159c0c62cdac906add05a21a29c2936eb412f041ea11a2470cb78`。
