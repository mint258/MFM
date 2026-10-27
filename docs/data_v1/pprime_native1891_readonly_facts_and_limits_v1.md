# P′1891：已计算事实与解释边界

仅复读已计算的1891报告和冻结诊断源码，未读原始QM正文、未新增科学运算、代码改动、测试、SSH/Slurm或QM。原15FAIL、qa02/qa08原WP5状态UNKNOWN、full/2000 HOLD，以及所有参数、版本、mask和容差保持。1891的C0表示取证报告闭合，不表示科学协变通过。

证据：`artifacts/pprime_causal15_main_v1/native_electronic_readonly_v1/native_electronic_evidence.jsonl`，625595B，SHA256 `c35915888c7f71b5852bbf6290c2bcd3b653258804ea30ced4dd2b039a5b46b7`。实际4521891 C0/33s/16CPU19；独立会计 `control/accounting/pprime15_electronic_4521891_v1.json`。本memo只引用其已存字段/原生token，不另算能量差、梯度、协变或新阈值。

## 三条件的最强控制

| 条件 | B1/B2、P1/P2 | 一般R1 | 能支持的解释 |
|---|---|---|---|
| PM7_B | B重复HOF均为 `+0.436713904198D+01`；P重复均为 `+0.436713904113D+01` kcal/mol。五次显式收敛且正常结束，迭代次数未报告。 | HOF为 `+0.436712780606D+01`；对B原生打印区间不重叠。 | 可重复的方向相关原生数值差异。并非SCF失败证据。B↔P高精度HOF区间也不重叠，但原向量P90仍PASS，不能另造能量质量门槛。 |
| xTB perturbed gradient | B/P均13次显式迭代；原生能量均 `-106.438138253875` Eh。 | 14次；能量 `-106.438138260111` Eh，打印区间与B不重叠。 | 同参数下显式电子迭代路径及原生数值随方向变化；所有调用仍自报收敛并正常结束，不能称未收敛或证明SCF是协变根因。 |
| xTB noisy singlepoint companion | 与同arm gradient相同的13次计数、能量和下述偶极表示模式。 | 与gradient R1同为14次及相同能量。 | 差异并非仅在--grad模式才出现；仍不证明两模式全部内部计算阶段/输出坐标系相同。 |

十个xTB调用报告的实际setup相同：GFN2、restart=false、300K、accuracy=1、max iterations=250、SCF convergence `0.1000000E-05 Eh`、wavefunction convergence `0.1000000E-03 e`、相同integral cutoff/neglect与Broyden damping。未发现改变这些打印设置的证据。显式终止均有正常标记，电子失败标记计数均为0。设置一致/显式收敛不保证相同密度或满足既定属性协变精度。

## PM7、原生gradient与own-output-frame

PM7五个调用的AUX目标 `DIP_VEC:DEBYE`、`GRADIENTS:KCAL/MOL/ANGSTROM`、`ATOM_X_OPT:ANGSTROMS` 等每个key均只出现一次。现有WP5值可用的调用，stored/raw检查为精确0差异；qa02的stored/raw字段是UNAVAILABLE，因为原WP5结果缺失，不能将其读成解析差异或补成功状态。HOF及向量差异已出现在原生输出，单纯重复AUX字段选择在这里没有获得支持。

xTB gradient五次均有唯一且exact3N的engrad梯度块。engrad与gradient文件的binary64值并非逐项完全相同，但已计算的所有对应原生打印区间均重叠。原 `parse_outputs` 对所有15记录的回读又与1802完全一致。此处支持有限打印表示差异，不支持把binary64不等直接称作符号/单位/梯度解析错误。本报告没有完整保留所有力转换检查，不能把上述结果扩大为“所有WP5力字段均已独立闭合”。

五次PM7各自AUX坐标、五次xTB gradient各自gradient坐标均报告MATCHES_INPUT_COORDINATES、atom order=true、supports_input_axes=true。PM7坐标最大差约5e-11Å；xTB约2.4–2.7e-11Å，并选择原WP5 `0.529177210903` 转换。它们不支持可见的大输出轴重定向/原子顺序错误。SP五次则是“当前reader未识别own坐标块”，不是证明raw完全无坐标，更不是借用gradient companion即可证明SP轴正确；SP own frame仍UNKNOWN。

报告还保存原生stdout GRADIENT NORM：B/P为 `1.294293866494`，R为 `1.294292210239` Eh/α，两xTB条件模式相同。这是程序自己打印的标量差异，不能仅用后处理数组轴旋转来解释；没有据此推导SCF失败、真实响应导数或新的质量结论。

## stdout full与JSON：内部闭合不等于独立表示闭合

1845的JSON重复键/作用域/首regex/顶层值/原parser回读全部闭合，仍成立。1891观察的是另一条独立关系：stdout属性full分量与JSON分量。在两xTB条件中，B1/B2与P1/P2各有一个分量的原生打印区间不重叠，R1三分量均重叠。

| 代表调用 | stdout full前三分量（a.u.） | JSON `dipole / a.u.` | 报告已算interval overlap |
|---|---|---|---|
| qa05 B1 | `[-1.161, 0.065, -0.616]` | `[-1.16134370, 0.06434273, -0.61570413]` | `[true,false,true]` |
| qa07 R1 | `[0.331, -1.206, -0.409]` | `[0.33111520,-1.20647531,-0.40855775]` | `[true,true,true]` |
| qa08 P1 | `[-0.065,-1.161,-0.616]` | `[-0.06434273,-1.16134370,-0.61570413]` | `[false,true,true]` |

这些stdout行第四项均为总模长 `3.345` Debye，不能将整行四列都按Debye比较。报告保留了partial charges和atomic dipole moments的原token数组，但未确定其全部单位/语义与阶段并重建full，故atomic contribution闭合仍UNKNOWN；不得charges-only重构完整GFN2偶极。

冻结observer的stdout dipole集合没有采用96条示例cap：它保留全部被该已声明header/branch识别器识别的q-only/full occurrences。现报告每个xTB调用恰有一个q-only和一个full，未发现它从多个已识别full中挑选了旧/初始项。B/P的full在process.out行448，R在447；邻近已保存总能量摘要分别在457/456。可靠SCF终止计数行分别在178/179。**但报告未保留完整相邻header/阶段上下文，也未绑定JSON写出阶段；“唯一识别full”不能严格证明它与最终JSON表示同一个内部量/密度阶段。**

尤其B/P的合并process.out中normal-termination标记在388，反而先于full行448；R标记在471。不能仅凭这些文本行号推断执行时序，合流/缓冲等原因在当前证据中未被核实。因此保留“原生表示差异/阶段或属性定义不同”的候选，尚不将其归为JSON解析bug、程序bug或协变失败根因。

## 必须作废解释的辅助表字段

1891新observer的辅助 `stdout.iteration_tables` 没有在SCF表结束处清除current状态。其 `rows=53/54` 和 `last3_rows` 已混入轨道能级行108、109、187，**不能用作SCF次数或最后迭代的dE/RMSdq证据**。这是诊断辅助提取边界缺陷，不是原QM/SCF失败；不修改已冻结源码或原报告。

可靠的13/14来自未改动的frozen SCF extractor的显式终止证据：B/P行178的13次，R行179的14次。该extractor遇终止marker即关闭自身stage，与上面的辅助table collector不同。MOPAC迭代次数仍NULL，SCF_CALCULATIONS/最大次数不被冒充为测得迭代。

## 实际版本与primary语义边界

实际stdout为 `xtb version 6.7.1 (edcfbbe)`，conda构建，所有xTB arms一致；MOPAC为23.0.3。不能仅凭6.7.1字串把binary当作官方release tag的精确源码。官方v6.7.1 release指向26b2801；本次另查了与打印前缀对应的公开[edcfbbe提交](https://github.com/grimme-lab/xtb/commit/edcfbbe)及其[aespot.f90](https://raw.githubusercontent.com/grimme-lab/xtb/edcfbbe/src/aespot.f90)。该提交的molmom同样将前三分量原样输出，只给总模长乘autod，并将charge-position与atomic-dipole贡献相加。[官方release](https://github.com/grimme-lab/xtb/releases/tag/v6.7.1)

因此所述逐列单位语义有更接近实际打印build前缀的primary支持。但本次没有核验完整conda recipe、所有本地补丁和binary-to-source构建关系，这一完全同一性仍UNKNOWN；没有更改或宣称原程序发生版本漂移。

目前可说的是：方向相关结果与xTB显式迭代路径差异可重复；原生stdout/JSON独立表示尚未完全闭合；PM7与gradient自身输出坐标及已绑定解析不支持明显的后处理轴/顺序/大单位错误。SCF失败、微小几何响应放大、SP自身输出frame以及表示差异是否造成原15FAIL，仍未得到因果证明。
