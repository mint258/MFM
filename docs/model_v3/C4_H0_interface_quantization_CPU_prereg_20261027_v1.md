# 历史H64接口量化：纯CPU执行前协议

2026-10-27。本诊断只测已保存historical1561 H64的一次接口量化，不运行或选择encoder，不把历史参考称为当前1838全六层centered隐藏H0。当前C4仍21PASS/27FAIL、HOLD；候选、GPU/encoder实现、生产精度及512维FP32 H0 API不变，无adoption、门槛放宽、层或seed选择。

[冻结协议](../../tools/model_v3/analysis_sources/H0_interface_quantization_CPU_v1/protocol_v1.json)与[源README](../../tools/model_v3/analysis_sources/H0_interface_quantization_CPU_v1/README.md)保持原始DRAFT字节，记录编写时状态。其后Root已完成3个Python AST、1个bash语法检查与SA4只读审阅，并执行纯metadata装配；这不表示新CPU计算或科学验收已经发生。源快照实际执行仍使用N原路径；本协议及exact source公开读回后，才由Root唯一提交。

## 固定对照与可比性

保留原48case、两seed、全部head policy、two/three views、四role、三transform及三个P字段。每arm48×4=192次CPU head调用、432个field/transform观察；A/B/C共576次head调用，0 encoder前向、0 GPU工作。共享原FP32 bank state与实际FP32 geometry/index，不改冻结1503公式、池化或dipole数学；原tiny controls在同一CPU作业内执行。

| arm | 固定路线 | 解释边界 |
| --- | --- | --- |
| A | 已存1561 H64 → 冻结1503 functional64 | 历史数值参考，非当前centered encoder |
| B | 同H64仅一次转FP32，再无损提升FP64 → 同functional64 | A→B仅隔离这组固定参考值的最终接口量化 |
| C | 与B相同的一次量化FP32 H0 → 原FP32 V3HeadBank CPU实现 | B→C同时包含dtype、实现与CPU backend差异 |

全部48例必须匹配case/seed/view/fixture/transform与role、完整named-parameter SHA、bank state keys/extras/identity/tensor headers、constructor/registry/forms及实际pos/batch/pair typed-header/provenance。实际CPU严格解码1838已存bank输入并独立hash实际pos/batch字节对1492 headers，H64各role固定44×512/FP64，校验原SHA/shape/dtype；不打开未使用1492 NPZ。历史1561不同encoder算法不是当前1838的隐藏H0。

A逐项核对全部432×3个已存1561标量控制：最大绝对D、原参考argmax处有符号D、固定旧GPU argmax处有符号D，诊断绝对界1e-10。历史头在CUDA而本次在CPU，原完整functional输出未保存；这不是全终端bitwise重放或backend等价承诺。数值控制失败仍保存全部48例观察，结束时nonzero/HOLD并禁止归因；损坏输入/state、来源或资源失败另作执行失败。

保留每arm完整有符号D、B−A/C−B与各arm自身argmax的同分量tuple。物理报告仍absolute1e-5、rtol0。B失败不证明普遍FP32下界或必须改H0 API；B/C不声称CUDA路径对照、纯精度因果或生产采用。与当前1838/1842结果的范围差异必须随报告保留。

## 已绑定metadata与有限输入

冻结源与三份Root metadata证明均在[本源快照](../../tools/model_v3/analysis_sources/H0_interface_quantization_CPU_v1/)。以下摘要来自本次机器原件，原始SDK/NPZ/权重均不入本次Git快照。

| 原件 | 字节 | raw SHA256 |
| --- | ---: | --- |
| [inputs_v1.json](../../tools/model_v3/analysis_sources/H0_interface_quantization_CPU_v1/inputs_v1.json) | 116864 | 3f44c53a1b0de92af699360a48cabd8b6593c837913a5d48a1bafd5f3c25141c |
| [source_pins_v1.json](../../tools/model_v3/analysis_sources/H0_interface_quantization_CPU_v1/source_pins_v1.json) | 39843 | 6c62f4adcc92b86ca9c56568f63e485f8f7c03086f5c367d56c559d80616e352 |
| [H0_interface_quantization_metadata_assembly_actual_v1.json](../../tools/model_v3/analysis_sources/H0_interface_quantization_CPU_v1/H0_interface_quantization_metadata_assembly_actual_v1.json) | 1395 | b34d892e4593fb38abfd5b30914978fda72fe1345e9f2e70446c33889a4ab629 |
| [Root_H0_interface_quantization_DRAFT_static_actual_v1.json](../../tools/model_v3/analysis_sources/H0_interface_quantization_CPU_v1/Root_H0_interface_quantization_DRAFT_static_actual_v1.json) | 2947 | 9ce30f2fc3d4341dfb0a4a99a06a39efa24e356df1abb9225264f932bced7a28 |
| [Root_H64_counterfactual_selected_input_stat_actual_v1.json](../../tools/model_v3/analysis_sources/H0_interface_quantization_CPU_v1/Root_H64_counterfactual_selected_input_stat_actual_v1.json) | 98506 | 617fc8afbb221b24e1fed6f11e1068b415d7e8f0b223f5e0716fbc5e900d7b65 |

Root装配按唯一物理输入stat计得125739933B，固定总上限134217728B（128MiB），余量8477795B。该装配未读或hash NPZ payload、未模型计算或提交。实际CPU须重新核所有真正读取的payload/metadata/source/input/pins原始SHA和物理身份并计量；超限即拒绝，余量不构成扩大scope或豁免。旧selected-stat证明的122658306B只是payload与144case JSON小计，最终装配总数另记；排除unused1492/1838终端NPZ、SDK和encoder权重。

## 原资源与执行闭合

仅CPU分区16CPU/16GiB，子监督120秒、RSS12GiB、Slurm3分钟，whole/private各2GiB；沿用原fresh节点、全用户内存85%、MemAvailable/quota与身份守卫，不增预算、不借旧资源快照、不增加独立QA父或调度器。记录实际CPU环境、运行argv、源前后、原始结果/COMPLETE或FAILED、supervisor和Slurm终态；当前均尚未发生。完整CPU测量与Root实际C0/闭合后才可解释结果，不把本次metadata成功称为新科学PASS。
