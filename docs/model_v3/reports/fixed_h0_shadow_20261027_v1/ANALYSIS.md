# Fixed-H0 影子分析：4521503（只读，未采用）

同一次新鲜 GPU 捕获的 H0/坐标/权重经闭合 CPU 影子分析后，FP64 终端仍有 **31/48 组合、65/432 观测**超过 1e-5。偶极相关失败以继承的 H0 变化为主；头算术也是可见因素，单独重写电荷中心化没有足够依据作为完整 C4 修复。

Root 实际回报 CPU4521503 在 compute-0-13、16CPU、13秒、COMPLETED/0:0；本报告独立读取到 supervisor COMPLETED/exit0/first_failure=null/remaining=[]。48组合、两seed、3字段×3变换共432观测完整，COMPLETE 绑定结果原字节，sources_before/after 原始 SHA 相同。未查询集群会计；未读 NPZ、SDK、坐标、权重或重跑模型。

来源是 GPU4521492 的新鲜同次前向捕获，不能冒充1435的 H0。GPU捕获48组合/192前向、原物理10通过/38失败保持权威。GPU_FP32_D 使用 FP64 L 对已保存FP32终端作差（向量为行向量@R），不是原C4的FP32期望公式；它的计数不能替代原物理判定。FP64只是独立functional头影子，并未把整个模型改为FP64。

每字段144观测=48组合×3变换。超限计数采用每个观测保存的 maxabs >1e-5；不把分量数、组合数与观测数混用。下面最大值分别取该字段/指标的144条原始观测，不相加。完整精度保留于配套JSON。

| 字段 | 指标 | 最大绝对值 | 超限观测/144 | 涉及组合/48 |
|---|---|---:|---:|---:|
| p_extensive | GPU_FP32_D | 1.549721E-05 | 14 | 12 |
| p_extensive | CPU_FP32_D | 1.811981E-05 | 16 | 11 |
| p_extensive | D | 1.133058E-05 | 1 | 1 |
| p_extensive | H | 1.133058E-05 | 1 | 1 |
| p_extensive | G | 0.000000E+00 | 0 | 0 |
| p_extensive | I | 0.000000E+00 | 0 | 0 |
| p_extensive | head_arithmetic_delta | 1.046411E-05 | 2 | 2 |
| p_dipole | GPU_FP32_D | 2.193984E-05 | 35 | 23 |
| p_dipole | CPU_FP32_D | 2.852082E-05 | 58 | 40 |
| p_dipole | D | 2.391421E-05 | 39 | 26 |
| p_dipole | H | 2.391374E-05 | 37 | 26 |
| p_dipole | G | 2.376578E-07 | 0 | 0 |
| p_dipole | I | 5.443600E-13 | 0 | 0 |
| p_dipole | head_arithmetic_delta | 1.348466E-05 | 2 | 2 |
| p_dipole_magnitude | GPU_FP32_D | 5.651265E-05 | 32 | 19 |
| p_dipole_magnitude | CPU_FP32_D | 4.001707E-05 | 38 | 23 |
| p_dipole_magnitude | D | 3.890569E-05 | 25 | 17 |
| p_dipole_magnitude | H | 3.898112E-05 | 25 | 17 |
| p_dipole_magnitude | G | 2.551003E-07 | 0 | 0 |
| p_dipole_magnitude | I | 4.283339E-11 | 0 | 0 |
| p_dipole_magnitude | head_arithmetic_delta | 1.760696E-05 | 8 | 4 |

跨三字段去重：GPU_FP32_D为81观测/38组合，CPU_FP32_D为112/45，FP64 D为65/31，H为63/31，head_arithmetic_delta为12/8。CPU FP32与GPU已保存终端的 moved 输出最大差3.0636787414550781e-5，说明CPU FP32不能充作GPU实际误差的替代。FP32与FP64四项闭合最大残差分别为1.0587911840678754e-22、1.3234889800848443e-23。

定义：F00=F(h0,p0)，Ft0=F(ht,p0)，F0t=F(h0,pt)，Ftt=F(ht,pt)；向量L(v)=v@R，标量/模长L为恒等。FP64 D=Ftt-L(F00)，H=L(Ft0-F00)，G=F0t-L(F00)，I=Ftt-F0t-L(Ft0-F00)。head_arithmetic_delta=GPU_FP32_D-D。只有在同一个输出分量，才使用 GPU_FP32_D=H+G+I+head_arithmetic_delta。

每字段最坏GPU观测的同分量带符号值如下；全部是 graph row2=32原子、component0。不同字段各用自己的最坏观测和权重，不能将不同行的最大值相加。

| 字段 | GPU_FP32_D | CPU_FP32_D | FP64 D | H | G | I | head_arithmetic_delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| p_extensive | -1.549720764160160E-05 | -7.152557373046880E-06 | -6.323082230252910E-06 | -6.323082230252910E-06 | 0 | 0 | -9.174125411348650E-06 |
| p_dipole | +2.193984128283890E-05 | +2.060735137883120E-05 | +1.718687756340280E-05 | +1.719393339976830E-05 | -7.056001515709510E-09 | +1.651501607994810E-13 | +4.752963719436080E-06 |
| p_dipole_magnitude | +5.651265382766720E-05 | +4.001706838607790E-05 | +3.890569487283170E-05 | +3.898112151624890E-05 | -7.542357315787340E-08 | -3.070259324555740E-12 | +1.760695895483550E-05 |

- p_extensive：C1-a__three__H1_fixed__seed20261026；general_rotation。
- p_dipole：C1-0__two__H3_fixed__seed20261026；general_rotation。
- p_dipole_magnitude：C1-0__three__H1_fixed__seed20261027；other_rotation_and_translation。

在81个GPU超限观测各自已保存的GPU argmax处，逐项比较 |H|、|G|、|I|、|head_arithmetic_delta|，H最大61次，head算术差最大20次，无并列；这不是解释方差或全模型普遍因果占比。分字段为extensive的6/14与8/14、dipole的30/35与5/35、magnitude的25/32与7/32（前者H、后者head差）。81个argmax全部在32原子图。

就这次捕获而言，偶极与模长的FP64残余几乎由H给出：G最大分别2.3765780809981152e-7、2.5510031725906046e-7，I最大分别5.4435999944626914e-13、4.2833389612972894e-11。extensive与坐标无关，G和I严格为0；FP64头下仍1条超限，且等于H。因而不能把本轮全部失败归因于最终质心/求和，也不能由头部FP64化宣称已解决。此影子分析不能进一步区分encoder中距离/RBF/注意力/层累积的来源。

电荷中心重写 Σ(q−qmean)(r−anchor) 与原 Σq(r−rmean) 在实数算术下等价，但会改变FP32舍入。当前head差最大约1.7607e-5，支持它作为次级算术假设讨论；该差同时包含读出MLP、池化、乘积、质心、矩及模长、CPU/GPU路径差异，尚未单独证明共同电荷项消减是主因。FP64头仍31组合超限，因此不支持把该重写作为唯一修复，或预告它能使全48通过。若后续测试，应先公开单变更协议，复用此次实际bank输入做全48固定H0比较并保留原标准；本报告未实现新候选。改善继承的H0变化仍是主要待解决项。

以上为本固定夹具/两seed/同权重输入域的实测归因；不证明所有FP32重排不可能、不可避免量化下界或必须全模型FP64，也不选择C1/头策略、不改变1e-5、不冻结配方、不采用候选。

复核算法：按原cases顺序展平全部432观测；逐字段/指标取保存maxabs的最大值并计严格>1e-5及去重case数；逐字段取第一个严格最大GPU观测并原样保留GPU_argmax.same_component_terms；贡献比较仅用各自同分量；CSV按原顺序逐ID/字段/变换和7个值与JSON精确核对，实际3024数值单元一致。所有模型数值来自闭合文件，没有读取数组重新计算终端。

关键原件（bytes / SHA256）：

- result：`/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/fixed_h0_shadow_cpu_v3_4521503/SHADOW_RESULT.json`；714257B；`112bef0fd9523d6435be35d9bb49a42a6dfe4ac2e508f4cc9c89bbb37146500b`。
- complete：`/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/fixed_h0_shadow_cpu_v3_4521503/COMPLETE.json`；317B；`24ef7302dd59025c9486b6b1f57018b814b07f823f12ee841a392dc0205f7b1a`。
- CSV：`/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/fixed_h0_shadow_cpu_v3_4521503/shadow_summary.csv`；92906B；`bc6ac7da7c157c737ec216645e66d5ecad527cf4382fcd317456b417ff0620a7`。
- CPU_supervisor：`/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/fixed_h0_shadow_cpu_v3_supervisor_4521503.json`；4574B；`12819f2eb6ed87808ba092a809ca58e9af784562ab91439b98414d2a11ec4f52`。
- CPU_metadata_preflight：`/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/fixed_h0_shadow_cpu_v3_4521503/CPU_METADATA_PREFLIGHT.json`；1296B；`096486893b1a93ffa46c8e81b434a2f9edf4a8e339c24623954d4bd8b0d513f6`。
- sources_before：`/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/fixed_h0_shadow_cpu_v3_4521503/sources_before.json`；73012B；`0d32318cd3a5275f3f7bf6c39fc574254223a7e1df63ad570fb62bf5e93bf982`。
- sources_after：`/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/fixed_h0_shadow_cpu_v3_4521503/sources_after.json`；73012B；`0d32318cd3a5275f3f7bf6c39fc574254223a7e1df63ad570fb62bf5e93bf982`。
- 配套紧凑JSON：`/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/fixed_h0_shadow_1503_readonly_analysis_v1.json`；28366B；`8f9f8b80d12da1636264e80c574b67378c645fa7eac2cd44e6a004c6199173cd`。

捕获producer source为v2 manifest230a1ed…；CPU分析source为v3 manifest2fc31c5…，完整路径/原SHA与capture COMPLETE/supervisor/raw accounting均在配套JSON。Root声明CPU v3于公开commit9179d4818798144d0c6a56dea8f2135b0d56f18f后运行；本报告不改任何源码、已冻结报告或原结果。
