# Encoder 精度参考结果与下一局部诊断

2026-10-27。1561实际C0/131秒，384前向及268个实际unique来源独立闭合；下一AV诊断尚未执行。

## 问题、结果与决定

同一1492实际输入、原参数和完整88/132 packed views下，先192次FP32 bank H0逐位重放，再192次有限F64 encoder参考及192次三PD functional bank调用。小控制12次tiny encoder和4CPU+4CUDA head另计。源码与独立控制、全部48成员及state-copy证据见ROOT_METADATA_CLOSURE.json和[完整分析](ANALYSIS.md)。

三终端F64最大误差分别extensive8.449005797e-7、dipole1.223000957e-6、magnitude7.935851844e-7，全部432观测/48组合无>1e-5。最终clean H0漂移max由原FP32的1.907348633e-6对应到F64参考1.918896353e-7。每层、同分量、完整分组与48原始ref摘要见ALL48_SUMMARY.json。

这支持继续研究FP32求值。它是同实数公式的有限legacy/direct参考，改变了补偿规约的数值次序；不能说逐指令仅换dtype、严格分出坐标舍入或证明FP32下界。末out_norm总体max下降，不能将其唯一归因LayerNorm。原FP32仍10PASS/38FAIL，无架构、dtype或配方采用。

下一可否证假设是attention共同V分量的数值消减；AV中心化表达式只作局部固定输入控制，区分Rraw和Rnorm，并承认新layout/kernel影响。规则与全部边界见../../C4_attention_AV_centering_prereg_20261027_v1.md，先公开再执行。

## 执行与剩余

S已安全5000更新/2034688base，1548实际C0/2462秒，1616续5000→6000。4k与5k两段SDK核验1635已正常Slurm排队，实际分配前不称完成；在线已闭合56个run，原7不完整保留。

CPU队列改为先核硬件容量/全用户mem85%/真实MemAvailable/quota后由Slurm公平等待16CPU，仍16GiB且无oversubscribe；不把观察到的10空闲伪称已获16核。旧helper和历史快照保持。七项集中CSV/曲线归档的旧120秒额度不随队列携带，分配后新鲜元数据接线在准备中，尚无归档C0。正常排队不修改/取消其他或数据线作业。

D3–D6最终未交，D1draft3未共同冻结；真实SDP三卡、代理P/SDP决策、面板种子SD、全量B*与最终用户确认均未完成。A01/4090的1338仍排队。无main合并、最终tag、recipe冻结或学校付费预训练。